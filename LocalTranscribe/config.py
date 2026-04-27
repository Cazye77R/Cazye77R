"""
Configuration and constants for LocalTranscribe.
"""

# Whisper model settings
WHISPER_MODEL = "large-v3"
WHISPER_DEVICE = "cuda"
WHISPER_COMPUTE_TYPE = "float16"

# Ollama settings
OLLAMA_BASE_URL = "http://localhost:11434"

# Supported audio/video formats
SUPPORTED_FORMATS = [".mp3", ".wav", ".m4a", ".ogg", ".flac", ".wma"]

# Output directory for transcription results
OUTPUT_DIR = "outputs"
