"""
Cost calculation utilities for AI API usage
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class CostCalculator:
    """Calculate and track costs for AI API usage"""
    
    # Pricing as of March 2026 (per 1M tokens)
    PRICING = {
        'anthropic': {
            'claude-3-5-sonnet-20241022': {
                'input': 3.00,
                'output': 15.00
            },
            'claude-3-haiku-20240307': {
                'input': 0.25,
                'output': 1.25
            },
            'claude-3-opus-20240229': {
                'input': 15.00,
                'output': 75.00
            }
        },
        'openai': {
            'gpt-4-turbo': {
                'input': 10.00,
                'output': 30.00
            },
            'gpt-3.5-turbo': {
                'input': 0.50,
                'output': 1.50
            }
        }
    }
    
    @classmethod
    def calculate_cost(
        cls,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """
        Calculate cost for API call
        
        Args:
            provider: 'anthropic' or 'openai'
            model: Model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        
        Returns:
            Total cost in USD
        """
        try:
            pricing = cls.PRICING[provider][model]
            input_cost = (input_tokens / 1_000_000) * pricing['input']
            output_cost = (output_tokens / 1_000_000) * pricing['output']
            return input_cost + output_cost
        except KeyError:
            logger.warning(
                f"Unknown pricing for provider={provider}, model={model}. "
                "Using default estimate."
            )
            # Fallback estimate (Claude 3.5 Sonnet)
            return ((input_tokens / 1_000_000) * 3.00 + 
                    (output_tokens / 1_000_000) * 15.00)
    
    @classmethod
    def estimate_cost_for_audio(
        cls,
        provider: str,
        model: str,
        audio_duration_seconds: float,
        task: str = 'duplicate_detection'
    ) -> Dict[str, Any]:
        """
        Estimate cost for processing audio
        
        Args:
            provider: 'anthropic' or 'openai'
            model: Model identifier
            audio_duration_seconds: Length of audio in seconds
            task: 'duplicate_detection' or 'pdf_comparison'
        
        Returns:
            Dict with estimated tokens and cost
        """
        # Rough estimates based on average transcription
        # ~150 words per minute, ~1.3 tokens per word
        minutes = audio_duration_seconds / 60
        words = minutes * 150
        tokens = int(words * 1.3)
        
        if task == 'duplicate_detection':
            # Input: Full transcript + segments structure
            # Output: Duplicate groups + markers
            input_tokens = int(tokens * 1.5)  # +50% for JSON structure
            output_tokens = int(tokens * 0.2)  # ~20% of input
        elif task == 'pdf_comparison':
            # Input: Transcript + PDF text
            # Output: Alignment + discrepancies
            input_tokens = int(tokens * 2.0)  # Transcript + PDF
            output_tokens = int(tokens * 0.3)  # More detailed output
        else:
            input_tokens = tokens
            output_tokens = int(tokens * 0.2)
        
        cost = cls.calculate_cost(provider, model, input_tokens, output_tokens)
        
        return {
            'audio_duration_seconds': audio_duration_seconds,
            'estimated_input_tokens': input_tokens,
            'estimated_output_tokens': output_tokens,
            'estimated_total_tokens': input_tokens + output_tokens,
            'estimated_cost_usd': round(cost, 4),
            'provider': provider,
            'model': model,
            'task': task
        }
    
    @classmethod
    def format_cost_summary(cls, cost_usd: float, tokens: int) -> str:
        """
        Format cost for display
        
        Args:
            cost_usd: Cost in USD
            tokens: Total tokens used
        
        Returns:
            Formatted string
        """
        if cost_usd < 0.01:
            return f"${cost_usd:.4f} ({tokens:,} tokens)"
        elif cost_usd < 1.00:
            return f"${cost_usd:.3f} ({tokens:,} tokens)"
        else:
            return f"${cost_usd:.2f} ({tokens:,} tokens)"
