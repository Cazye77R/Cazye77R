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

# Fallback compute type used when the primary type causes a CUDA OOM.
WHISPER_COMPUTE_TYPE_FALLBACK = "int8"

# ---------------------------------------------------------------------------
# Language settings
# ---------------------------------------------------------------------------

# Supported transcription languages shown in the UI.
LANGUAGES = {"Deutsch": "de", "English": "en"}

# Display-key (must match a key in LANGUAGES) used when no language is selected.
DEFAULT_LANGUAGE = "Deutsch"
assert DEFAULT_LANGUAGE in LANGUAGES, (
    f"DEFAULT_LANGUAGE '{DEFAULT_LANGUAGE}' not found in LANGUAGES keys"
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

# Output directory for transcription results
OUTPUT_DIR = "outputs"
