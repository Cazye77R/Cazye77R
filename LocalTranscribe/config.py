"""
Configuration and constants for LocalTranscribe.

VRAM budget note (RTX 3060, 6 GB):
  Whisper large-v3 + float16  ≈ 5.0 GB  → leaves almost nothing for diarization
  Whisper large-v3 + int8     ≈ 2.5 GB  → comfortable headroom
  pyannote diarization-3.1    ≈ 2.0 GB  → loaded only while Whisper is unloaded

  Recommended flow: load Whisper (int8) → transcribe → unload →
                    load diarizer → diarize → unload → query Ollama (CPU)
"""

# ---------------------------------------------------------------------------
# Whisper model settings
# ---------------------------------------------------------------------------

WHISPER_MODEL = "large-v3"

# Prefer CUDA; fall back to CPU automatically when the GPU is absent or torch
# is not yet installed (e.g. during a bare import of this module in tests).
try:
    import torch as _torch
    WHISPER_DEVICE = "cuda" if _torch.cuda.is_available() else "cpu"
    del _torch
except ImportError:
    WHISPER_DEVICE = "cpu"

# int8 saves ~50 % VRAM compared to float16 with negligible quality loss
# on large-v3.  On CPU, int8 is also the fastest compute type.
WHISPER_COMPUTE_TYPE = "int8"

# Compute type used when falling back to the CPU.  int8 is already the most
# memory-frugal option on the GPU, so there is no lighter GPU precision to
# retry with – a CUDA OOM is escaped by moving to the CPU instead.
WHISPER_COMPUTE_TYPE_FALLBACK = "int8"

# ---------------------------------------------------------------------------
# Language settings
# ---------------------------------------------------------------------------

# Supported transcription languages shown in the UI.
LANGUAGES = {"Deutsch": "de", "English": "en"}

# Display-key (must match a key in LANGUAGES) used when no language is selected.
DEFAULT_LANGUAGE = "Deutsch"

# A plain raise, not an assert: assert statements are stripped when Python runs
# with -O, which would silently remove this guard.
if DEFAULT_LANGUAGE not in LANGUAGES:
    raise ValueError(
        f"DEFAULT_LANGUAGE '{DEFAULT_LANGUAGE}' is not a key of LANGUAGES "
        f"({sorted(LANGUAGES)})"
    )

# ---------------------------------------------------------------------------
# Ollama timeouts
# ---------------------------------------------------------------------------

OLLAMA_GET_TIMEOUT = 10       # seconds – used for GET /api/tags
OLLAMA_GENERATE_TIMEOUT = 120 # seconds – used for POST /api/generate

# ---------------------------------------------------------------------------
# Ollama settings
# ---------------------------------------------------------------------------

OLLAMA_BASE_URL = "http://localhost:11434"

# ---------------------------------------------------------------------------
# File handling
# ---------------------------------------------------------------------------

# Supported audio/video formats
SUPPORTED_FORMATS = [".mp3", ".wav", ".m4a", ".ogg", ".flac", ".wma"]
