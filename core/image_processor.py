import base64
import io
import os
import logging
from typing import Tuple, Optional
from PIL import Image, ImageEnhance, ImageFilter

logger = logging.getLogger(__name__)

class ImageProcessor:
    """
    Handles image loading, contrast enhancement, base64 encoding,
    and diagram normalization for the Vision Agent.
    """

    @staticmethod
    def allowed_file(filename: str, allowed_extensions: set) -> bool:
        """Check if filename has an approved extension."""
        return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions

    @staticmethod
    def encode_image_to_base64(image_path: str, max_dimension: int = 1600) -> str:
        """
        Loads an image, optimizes resolution for vision LLMs, and encodes to base64.
        """
        with Image.open(image_path) as img:
            # Convert RGBA / P to RGB
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # Scale down if too large to conserve local GPU memory
            width, height = img.size
            if max(width, height) > max_dimension:
                scale_ratio = max_dimension / max(width, height)
                new_size = (int(width * scale_ratio), int(height * scale_ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            # Contrast enhancement to highlight ER diagram text and connector lines
            enhancer = ImageEnhance.Contrast(img)
            enhanced_img = enhancer.enhance(1.2)

            buffer = io.BytesIO()
            enhanced_img.save(buffer, format="JPEG", quality=85)
            buffer.seek(0)
            return base64.b64encode(buffer.read()).decode("utf-8")

    @staticmethod
    def get_image_metadata(image_path: str) -> dict:
        """Retrieve dimensions, format, and file size."""
        file_size_kb = os.path.getsize(image_path) / 1024.0
        with Image.open(image_path) as img:
            return {
                "format": img.format,
                "dimensions": f"{img.width}x{img.height}",
                "mode": img.mode,
                "file_size_kb": round(file_size_kb, 2)
            }
