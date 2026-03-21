"""
AI Services for Duplicate Detection and PDF Comparison

This package contains AI-powered features including:
- Sentence-level duplicate detection
- Paragraph-level expansion
- PDF comparison and verification
"""

from .anthropic_client import AnthropicClient
from .cost_calculator import CostCalculator
from .duplicate_detector import DuplicateDetector

__all__ = [
    'AnthropicClient',
    'CostCalculator',
    'DuplicateDetector',
]
