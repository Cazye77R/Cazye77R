"""
Workflow smoke-test for LocalTranscribe.

Tests every module without requiring ML models to be downloaded.
Missing ML packages (torch, faster-whisper, pyannote) are handled gracefully
so the test can run in a plain Python environment.

Run:
    cd LocalTranscribe
    python test_workflow.py
"""

from __future__ import annotations

import math
import struct
import sys
import tempfile
import wave
from pathlib import Path

# ---------------------------------------------------------------------------
# Minimal test harness
# ---------------------------------------------------------------------------

_results: list[tuple[str, bool, str]] = []
PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
SKIP = "\033[33mSKIP\033[0m"


def check(name: str, ok: bool, detail: str = "") -> None:
    _results.append((name, ok, detail))
    tag = PASS if ok else FAIL
    suffix = f"  ({detail})" if detail else ""
    print(f"  [{tag}]  {name}{suffix}")


def skip(name: str, reason: str) -> None:
    _results.append((name, True, f"SKIP: {reason}"))
    print(f"  [{SKIP}]  {name}  ({reason})")


def section(title: str) -> None:
    print(f"\n{'─' * 60}\n  {title}\n{'─' * 60}")


def make_wav(path: Path, duration_s: float = 2.0, freq_hz: float = 440.0) -> None:
    """Write a minimal mono 16-bit 16 kHz sine-wave WAV file."""
    sample_rate = 16_000
    n_samples = int(sample_rate * duration_s)
    amplitude = 16_000
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(n_samples):
            value = int(amplitude * math.sin(2 * math.pi * freq_hz * i / sample_rate))
            wf.writeframes(struct.pack("<h", value))


# ---------------------------------------------------------------------------
# Section 1 – config.py
# ---------------------------------------------------------------------------

section("1. config.py")

import config

check("WHISPER_MODEL == 'large-v3'",         config.WHISPER_MODEL == "large-v3",  config.WHISPER_MODEL)
check("WHISPER_COMPUTE_TYPE == 'int8'",      config.WHISPER_COMPUTE_TYPE == "int8", config.WHISPER_COMPUTE_TYPE)
check("WHISPER_COMPUTE_TYPE_FALLBACK == 'int8'", config.WHISPER_COMPUTE_TYPE_FALLBACK == "int8")
check("WHISPER_DEVICE in {cuda, cpu}",       config.WHISPER_DEVICE in ("cuda", "cpu"), config.WHISPER_DEVICE)
check("OLLAMA_BASE_URL starts with http",    config.OLLAMA_BASE_URL.startswith("http"))
check("SUPPORTED_FORMATS not empty",         len(config.SUPPORTED_FORMATS) >= 5)
check("OUTPUT_DIR defined",                  bool(config.OUTPUT_DIR))
check(".wav in SUPPORTED_FORMATS",           ".wav" in config.SUPPORTED_FORMATS)

# CUDA presence check (optional – gracefully skipped if torch absent)
try:
    import torch
    _has_torch = True
    _cuda = torch.cuda.is_available()
    if _cuda:
        props = torch.cuda.get_device_properties(0)
        total_gb = props.total_memory / 1024**3
        check(f"CUDA device: {props.name}", total_gb > 0, f"{total_gb:.1f} GB VRAM")
        check("WHISPER_DEVICE == 'cuda' on CUDA machine", config.WHISPER_DEVICE == "cuda")
    else:
        check("No CUDA → WHISPER_DEVICE == 'cpu'", config.WHISPER_DEVICE == "cpu")
except ImportError:
    _has_torch = False
    _cuda = False
    skip("CUDA detection", "torch not installed")

# ---------------------------------------------------------------------------
# Section 2 – transcriber.py (static methods, no model download)
# ---------------------------------------------------------------------------

section("2. transcriber.py – static methods & safety guards")

try:
    from transcriber import TranscriptionEngine, TranscriptionError

    # format_timestamp
    ts_cases = [
        (0.0,    "00:00:00"),
        (59.0,   "00:00:59"),
        (60.0,   "00:01:00"),
        (3661.0, "01:01:01"),
        (-5.0,   "00:00:00"),   # negative → clamp to 0
    ]
    for secs, expected in ts_cases:
        got = TranscriptionEngine.format_timestamp(secs)
        check(f"format_timestamp({secs!r}) == '{expected}'", got == expected, got)

    # unload() must be idempotent when model is None
    class _FakeEngine(TranscriptionEngine):
        def __init__(self) -> None:
            self.model = None
            self.device = "cpu"
            self.model_size = "tiny"
            self.compute_type = "int8"

    fe = _FakeEngine()
    try:
        fe.unload()
        fe.unload()
        check("unload() idempotent when model=None", True)
    except Exception as exc:
        check("unload() idempotent when model=None", False, str(exc))

    # _segment_to_dict
    fake_seg = type("S", (), {"start": 1.0, "end": 2.5, "text": "  Hallo Welt  ", "words": None})()
    sd = TranscriptionEngine._segment_to_dict(fake_seg)
    check("_segment_to_dict strips whitespace",  sd["text"] == "Hallo Welt")
    check("_segment_to_dict words=None → []",    sd["words"] == [])
    check("_segment_to_dict has start & end",    "start" in sd and "end" in sd)

    fake_word = type("W", (), {"start": 1.0, "end": 1.3, "word": "Hallo", "probability": 0.99})()
    fake_seg2 = type("S", (), {
        "start": 1.0, "end": 2.5, "text": "Hallo", "words": [fake_word]
    })()
    sd2 = TranscriptionEngine._segment_to_dict(fake_seg2)
    check("_segment_to_dict word list length",   len(sd2["words"]) == 1)
    check("_segment_to_dict word keys present",  "word" in sd2["words"][0])

except ImportError as exc:
    skip("transcriber.py tests", f"missing dependency: {exc}")

# ---------------------------------------------------------------------------
# Section 3 – diarizer.py (lazy loading & assign_speakers)
# ---------------------------------------------------------------------------

section("3. diarizer.py – lazy load guard & assign_speakers")

try:
    from diarizer import DiarizationError, SpeakerDiarizer

    # Empty token must raise *before* any network call
    try:
        SpeakerDiarizer(hf_token="")
        check("Empty HF token raises DiarizationError", False)
    except DiarizationError:
        check("Empty HF token raises DiarizationError", True)

    # Fake token: __init__ must succeed cheaply without loading the pipeline
    try:
        d = SpeakerDiarizer(hf_token="hf_FAKE_FOR_TEST")
        check("__init__ with fake token is cheap (lazy)",  True)
        check("_pipeline is None after __init__",          d._pipeline is None)
        d.unload()   # pipeline is None → must not crash
        d.unload()   # double unload safe
        check("unload() idempotent when pipeline=None",    True)
    except DiarizationError as exc:
        check("__init__ with fake token is cheap (lazy)", False, str(exc))

    # assign_speakers correctness
    transcript = [
        {"start": 0.0,  "end": 4.0,  "text": "Guten Morgen.", "words": []},  # mid=2.0  → SPEAKER_00
        {"start": 4.5,  "end": 9.0,  "text": "Wie geht es?",  "words": []},  # mid=6.75 → SPEAKER_01
        {"start": 9.5,  "end": 14.0, "text": "Gut, danke.",   "words": []},  # mid=11.75→ SPEAKER_01
        {"start": 20.0, "end": 24.0, "text": "In einer Lücke.", "words": []}, # mid=22   → gap
    ]
    turns = [
        {"start": 0.0,  "end": 5.0,  "speaker": "SPEAKER_00"},
        {"start": 5.0,  "end": 15.0, "speaker": "SPEAKER_01"},
    ]
    enriched = SpeakerDiarizer.assign_speakers(transcript, turns)
    check("assign_speakers returns same length",           len(enriched) == len(transcript))
    check("seg[0] mid=2.0 → Sprecher 1",                  enriched[0]["speaker"] == "Sprecher 1")
    check("seg[1] mid=6.75 → Sprecher 2",                 enriched[1]["speaker"] == "Sprecher 2")
    check("seg[2] mid=11.75 → Sprecher 2",                enriched[2]["speaker"] == "Sprecher 2")
    check("seg[3] in gap → Unbekannt",                    enriched[3]["speaker"] == "Unbekannt")
    check("original dicts not mutated (copy returned)",    "speaker" not in transcript[0])

    # Test stable ordering: SPEAKER_01 first in time → must still get Sprecher 1
    turns_rev = [{"start": 0.0, "end": 5.0, "speaker": "SPEAKER_01"}]
    segs_rev  = [{"start": 1.0, "end": 4.0, "text": "Hi", "words": []}]
    r = SpeakerDiarizer.assign_speakers(segs_rev, turns_rev)
    check("First encountered speaker → Sprecher 1 regardless of raw ID", r[0]["speaker"] == "Sprecher 1")

except ImportError as exc:
    skip("diarizer.py tests", f"missing dependency: {exc}")

# ---------------------------------------------------------------------------
# Section 4 – llm_processor.py (formatting & prompt building)
# ---------------------------------------------------------------------------

section("4. llm_processor.py – formatting & prompt building")

try:
    from llm_processor import LLMError, LLMProcessor

    # format_transcript_for_llm – with speakers
    segs_sp = [
        {"start": 0.0,  "end": 5.0,  "text": "Hallo.",     "words": [], "speaker": "Sprecher 1"},
        {"start": 5.5,  "end": 10.0, "text": "Wie läuft's?", "words": [], "speaker": "Sprecher 2"},
        {"start": 10.5, "end": 14.0, "text": "",            "words": [], "speaker": "Sprecher 1"},  # empty
    ]
    txt = LLMProcessor.format_transcript_for_llm(segs_sp)
    check("format with speaker: badge format",         "Sprecher 1 [00:00:00]:" in txt)
    check("format with speaker: second speaker",       "Sprecher 2 [00:00:05]:" in txt)
    check("format with speaker: empty text skipped",   txt.count("Sprecher 1") == 1)

    # format_transcript_for_llm – without speakers
    segs_ns = [
        {"start": 0.0,  "end": 5.0,  "text": "Hallo.", "words": []},
        {"start": 5.5,  "end": 10.0, "text": "Tschüss.", "words": []},
    ]
    txt2 = LLMProcessor.format_transcript_for_llm(segs_ns)
    check("format without speaker: starts with [HH:MM:SS]", txt2.startswith("[00:00:00]"))
    check("format without speaker: no badge",               "Sprecher" not in txt2)

    # _build_prompts – built-in tasks
    proc = LLMProcessor.__new__(LLMProcessor)
    proc.base_url = "http://localhost:11434"
    for task in ("zusammenfassung", "themen", "protokoll"):
        sp, up = proc._build_prompts("TRANSCRIPT", task, None)  # type: ignore[arg-type]
        check(f"task '{task}': non-empty system prompt",    bool(sp))
        check(f"task '{task}': transcript in user prompt",  "TRANSCRIPT" in up)

    # custom task with {text} placeholder
    _, up_ph = proc._build_prompts("MY_TEXT", "custom", "Analysiere: {text}")
    check("custom with {text}: replaced correctly", "MY_TEXT" in up_ph and "{text}" not in up_ph)

    # custom task without placeholder → appended
    _, up_ap = proc._build_prompts("MY_TEXT", "custom", "Kein Platzhalter")
    check("custom without {text}: transcript appended", "MY_TEXT" in up_ap)

    # error cases
    try:
        proc._build_prompts("T", "custom", None)
        check("custom + no prompt raises ValueError", False)
    except ValueError:
        check("custom + no prompt raises ValueError", True)

    try:
        proc._build_prompts("T", "ungültig", None)  # type: ignore[arg-type]
        check("unknown task raises ValueError", False)
    except ValueError:
        check("unknown task raises ValueError", True)

except ImportError as exc:
    skip("llm_processor.py tests", f"missing dependency: {exc}")

# ---------------------------------------------------------------------------
# Section 5 – synthetic WAV
# ---------------------------------------------------------------------------

section("5. Synthetic WAV creation & read-back")

with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as _tmp:
    wav_path = Path(_tmp.name)

make_wav(wav_path, duration_s=2.0, freq_hz=440.0)
check("WAV file created",           wav_path.exists())
check("WAV file > 0 bytes",         wav_path.stat().st_size > 0)

with wave.open(str(wav_path)) as wf:
    check("WAV channels = 1",       wf.getnchannels() == 1)
    check("WAV rate = 16 000 Hz",   wf.getframerate() == 16_000)
    check("WAV depth = 16-bit",     wf.getsampwidth() == 2)
    dur = wf.getnframes() / wf.getframerate()
    check(f"WAV duration ≈ 2.0 s",  abs(dur - 2.0) < 0.05, f"{dur:.3f} s")

wav_path.unlink()
check("Temp WAV cleaned up",        not wav_path.exists())

# ---------------------------------------------------------------------------
# Section 6 – VRAM accounting
# ---------------------------------------------------------------------------

section("6. VRAM accounting")

if _has_torch and _cuda:
    before = torch.cuda.memory_reserved(0)
    buf = torch.zeros(1024 * 1024, dtype=torch.float32, device="cuda")  # 4 MB
    after = torch.cuda.memory_reserved(0)
    check("Allocation increases reserved VRAM", after >= before)
    del buf
    torch.cuda.empty_cache()
    freed = torch.cuda.memory_reserved(0)
    check("empty_cache() reduces reserved VRAM", freed <= after)
elif _has_torch:
    skip("VRAM accounting", "no CUDA GPU on this machine")
else:
    skip("VRAM accounting", "torch not installed")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

section("Summary")

total  = len(_results)
passed = sum(1 for _, ok, _ in _results if ok)
failed = total - passed

print(f"\n  {passed}/{total} checks passed", end="")
if failed:
    print(f"  –  {failed} FAILED:")
    for name, ok, detail in _results:
        if not ok:
            print(f"    • {name}" + (f"  ({detail})" if detail else ""))
else:
    print("  – all good ✓")

print()
sys.exit(0 if failed == 0 else 1)
