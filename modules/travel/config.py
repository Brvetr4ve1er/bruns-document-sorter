import os

OLLAMA_MODEL = "llama3"
OLLAMA_TIMEOUT = 180

# Settings for output structures
TRAVEL_EXPORT_DIR = os.environ.get("BRUNS_DATA_DIR", "data")
