import os
from pathlib import Path

# Resolve base project directory dynamically (supports Windows, Linux, and Docker/Render containers)
BASE_DIR = Path(os.environ.get("BASE_DIR", Path(__file__).resolve().parent.parent.parent))
APP_DIR = BASE_DIR / "backend" / "app"
INPUT_DIR = Path(os.environ.get("INPUT_DIR", BASE_DIR / "input"))
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", BASE_DIR / "output"))
LOGS_DIR = Path(os.environ.get("LOGS_DIR", BASE_DIR / "logs"))
DEBUG_DIR = Path(os.environ.get("DEBUG_DIR", BASE_DIR / "debug"))
REFERENCES_DIR = Path(os.environ.get("REFERENCES_DIR", BASE_DIR / "references"))

# Dynamic sample PDFs directory fallback
default_sample_dir = (
    Path(r"D:\zz\Extraction_PDFs_UBP")
    if os.name == "nt" and Path(r"D:\zz\Extraction_PDFs_UBP").exists()
    else BASE_DIR / "input"
)
SAMPLE_PDFS_DIR = Path(os.environ.get("SAMPLE_PDFS_DIR", default_sample_dir))

# Ensure required runtime directories exist
for d in [INPUT_DIR, OUTPUT_DIR, LOGS_DIR, DEBUG_DIR, REFERENCES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Host & Port configuration: reads Render's dynamic $PORT environment variable
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
FRONTEND_PORT = int(os.environ.get("FRONTEND_PORT", "5173"))

