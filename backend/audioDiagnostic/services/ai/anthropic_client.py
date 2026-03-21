"""
Anthropic Claude API Client for AI-powered duplicate detection
"""

import logging
import time
import json
from typing import Dict, Any, Optional
from anthropic import Anthropic, AnthropicError, APIError, RateLimitError
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class AnthropicClient:
    """
    Wrapper for Anthropic Claude API with:
    - Automatic retry with exponential backoff
    - Rate limiting handling
    - Token counting and cost tracking
    - Error handling and logging
    """
    
    def __init__(self):
        """Initialize Anthropic client with API key from settings"""
        api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not found in settings. "
                "Please add it to your .env file."
            )
        
        self.client = Anthropic(api_key=api_key)
        self.model = getattr(settings, 'AI_MODEL', 'claude-3-5-sonnet-20241022')
        self.max_tokens = getattr(settings, 'AI_MAX_TOKENS', 4096)
        self.max_retries = 3
        self.base_delay = 1  # seconds
        
        logger.info(f"Initialized AnthropicClient with model: {self.model}")
    
    def call_api(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0
    ) -> Dict[str, Any]:
        """
        Call Anthropic API with retry logic
        
        Args:
            prompt: The user prompt/question
            system_prompt: Optional system instructions
            max_tokens: Maximum tokens in response (default: self.max_tokens)
            temperature: Sampling temperature 0-1 (default: 0 for deterministic)
        
        Returns:
            Dict with 'content', 'usage', and 'cost' keys
        
        Raises:
            AnthropicError: If API call fails after all retries
        """
        max_tokens = max_tokens or self.max_tokens
        
        for attempt in range(self.max_retries):
            try:
                # Build messages
                messages = [{"role": "user", "content": prompt}]
                
                # Make API call
                kwargs = {
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "messages": messages,
                    "temperature": temperature,
                }
                
                if system_prompt:
                    kwargs["system"] = system_prompt
                
                logger.debug(f"Calling Anthropic API (attempt {attempt + 1}/{self.max_retries})")
                
                response = self.client.messages.create(**kwargs)
                
                # Extract response
                content = response.content[0].text
                usage = {
                    'input_tokens': response.usage.input_tokens,
                    'output_tokens': response.usage.output_tokens,
                    'total_tokens': response.usage.input_tokens + response.usage.output_tokens
                }
                
                # Calculate cost
                cost = self._calculate_cost(usage['input_tokens'], usage['output_tokens'])
                
                logger.info(
                    f"API call successful. "
                    f"Tokens: {usage['total_tokens']} "
                    f"(in: {usage['input_tokens']}, out: {usage['output_tokens']}), "
                    f"Cost: ${cost:.4f}"
                )
                
                return {
                    'content': content,
                    'usage': usage,
                    'cost': cost,
                    'model': self.model
                }
                
            except RateLimitError as e:
                logger.warning(f"Rate limit hit (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)  # Exponential backoff
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    logger.error("Max retries reached for rate limit")
                    raise
                    
            except APIError as e:
                logger.error(f"Anthropic API error (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    logger.error("Max retries reached for API error")
                    raise
                    
            except AnthropicError as e:
                logger.error(f"Anthropic client error: {e}")
                raise
                
            except Exception as e:
                logger.error(f"Unexpected error calling Anthropic API: {e}")
                raise
        
        raise AnthropicError("Max retries exceeded")
    
    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost for Claude 3.5 Sonnet
        
        Pricing (as of March 2026):
        - Input: $3.00 per 1M tokens
        - Output: $15.00 per 1M tokens
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        
        Returns:
            Total cost in USD
        """
        input_cost = (input_tokens / 1_000_000) * 3.00
        output_cost = (output_tokens / 1_000_000) * 15.00
        return input_cost + output_cost
    
    def parse_json_response(self, response_content: str) -> Dict[str, Any]:
        """
        Parse JSON from AI response, handling markdown code blocks
        
        Args:
            response_content: Raw text response from AI
        
        Returns:
            Parsed JSON as dictionary
        
        Raises:
            ValueError: If JSON cannot be parsed
        """
        try:
            # Try direct JSON parse first
            return json.loads(response_content)
        except json.JSONDecodeError:
            # Try extracting from markdown code block
            if "```json" in response_content:
                # Extract content between ```json and ```
                start = response_content.find("```json") + 7
                end = response_content.find("```", start)
                json_str = response_content[start:end].strip()
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON from markdown block: {e}")
                    raise ValueError(f"Invalid JSON in response: {e}")
            elif "```" in response_content:
                # Try generic code block
                start = response_content.find("```") + 3
                end = response_content.find("```", start)
                json_str = response_content[start:end].strip()
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON from code block: {e}")
                    raise ValueError(f"Invalid JSON in response: {e}")
            else:
                raise ValueError("No JSON found in response")
    
    def check_user_cost_limit(self, user_id: int) -> bool:
        """
        Check if user has exceeded monthly cost limit
        
        Args:
            user_id: Django user ID
        
        Returns:
            True if under limit, False if exceeded
        """
        from datetime import datetime
        
        # Get current month key
        month_key = f"ai_cost_{user_id}_{datetime.now().strftime('%Y_%m')}"
        
        # Get current usage from cache
        current_usage = cache.get(month_key, 0.0)
        
        # Get limit from settings
        limit = getattr(settings, 'AI_COST_LIMIT_PER_USER_PER_MONTH', 50.0)
        
        if current_usage >= limit:
            logger.warning(
                f"User {user_id} has exceeded monthly AI cost limit "
                f"(${current_usage:.2f} / ${limit:.2f})"
            )
            return False
        
        return True
    
    def track_user_cost(self, user_id: int, cost: float):
        """
        Track AI API cost for user
        
        Args:
            user_id: Django user ID
            cost: Cost in USD to add
        """
        from datetime import datetime
        
        # Get current month key
        month_key = f"ai_cost_{user_id}_{datetime.now().strftime('%Y_%m')}"
        
        # Get current usage
        current_usage = cache.get(month_key, 0.0)
        
        # Add new cost
        new_usage = current_usage + cost
        
        # Store in cache (expires at end of month)
        # Calculate seconds until end of month
        now = datetime.now()
        if now.month == 12:
            next_month = datetime(now.year + 1, 1, 1)
        else:
            next_month = datetime(now.year, now.month + 1, 1)
        
        seconds_until_next_month = int((next_month - now).total_seconds())
        
        cache.set(month_key, new_usage, seconds_until_next_month)
        
        logger.info(f"User {user_id} AI cost: ${new_usage:.4f} this month")
