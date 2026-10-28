"""Audio Book Using Python - automated audiobook generator."""
from .converter import AudiobookConverter, ConversionError

__all__ = ["AudiobookConverter", "ConversionError"]
__version__ = "1.0.0"
