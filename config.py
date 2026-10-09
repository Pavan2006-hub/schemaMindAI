
import os
from pathlib import Path
from dotenv import load_dotenv

# Project root
BASE_DIR = Path(__file__).resolve().parent

# Load .env from project root
load_dotenv(BASE_DIR / ".env")


class Config:
    """Application configuration for SchemaMind AI."""

    # --------------------------------------------------
    # Flask settings
    # --------------------------------------------------

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-this-key")

    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() in {
        "true", "1", "yes"
    }

    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "5000"))

    # --------------------------------------------------
    # File storage
    # --------------------------------------------------

    UPLOAD_FOLDER = os.getenv(
        "UPLOAD_FOLDER", str(BASE_DIR / "uploads")
    )

    OUTPUT_FOLDER = os.getenv(
        "OUTPUT_FOLDER", str(BASE_DIR / "outputs")
    )

    # PDFs are allowed for ERD uploads.
    # SVG is excluded until you implement SVG sanitization.
    ALLOWED_EXTENSIONS = {
        "png", "jpg", "jpeg", "webp", "bmp", "pdf"
    }

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

    # --------------------------------------------------
    # LLM provider
    # --------------------------------------------------

    # Supported by the current GemmaClient:
    # ollama, openai_compatible, mock
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()

    # --------------------------------------------------
    # Ollama
    # --------------------------------------------------

    OLLAMA_BASE_URL = os.getenv(
        "OLLAMA_BASE_URL", "http://localhost:11434"
    ).rstrip("/")

    # Must match the exact installed Ollama model tag.
    # Change this if your installed model has a different name.
    GEMMA_MODEL = os.getenv("GEMMA_MODEL", "gemma4:e2b")

    # Use one vision-capable model for image analysis and text
    # generation unless you implement separate model routing.
    VISION_MODEL = os.getenv("VISION_MODEL", GEMMA_MODEL)

    # --------------------------------------------------
    # OpenAI-compatible local server
    # --------------------------------------------------

    OPENAI_COMPATIBLE_BASE_URL = os.getenv(
        "OPENAI_COMPATIBLE_BASE_URL",
        "http://localhost:8000/v1"
    ).rstrip("/")

    OPENAI_COMPATIBLE_API_KEY = os.getenv(
        "OPENAI_COMPATIBLE_API_KEY", "local"
    )

    # --------------------------------------------------
    # Multi-agent workflow
    # --------------------------------------------------

    MAX_VALIDATION_RETRIES = int(
        os.getenv("MAX_VALIDATION_RETRIES", "3")
    )

    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))

    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "300"))

    # --------------------------------------------------
    # Runtime directories
    # --------------------------------------------------

    @classmethod
    def ensure_directories(cls):
        """Create required directories when the application starts."""

        Path(cls.UPLOAD_FOLDER).mkdir(
            parents=True, exist_ok=True
        )

        Path(cls.OUTPUT_FOLDER).mkdir(
            parents=True, exist_ok=True
        )

    # --------------------------------------------------
    # Upload validation
    # --------------------------------------------------

    @classmethod
    def allowed_file(cls, filename):
        """Check the file extension against the allowlist."""

        if not filename or "." not in filename:
            return False

        extension = filename.rsplit(".", 1)[1].lower()
        return extension in cls.ALLOWED_EXTENSIONS