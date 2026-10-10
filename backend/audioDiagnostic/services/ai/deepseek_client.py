"""
DeepSeek API Client for AI-powered duplicate detection

DeepSeek exposes an OpenAI-compatible Chat Completions API, so this wraps the
official `openai` SDK pointed at DeepSeek's base URL. The public interface
mirrors `AnthropicClient` so it can be used as a drop-in replacement by
`DuplicateDetector`.
"""

import logging
import time
import json
from typing import Dict, Any, Optional
from openai import OpenAI, APIError, APIConnectionError, RateLimitError
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class DeepSeekClient:
    """
    Wrapper for the DeepSeek Chat Completions API with:
    - Automatic retry with exponential backoff
    - Rate limiting handling
    - Token counting and cost tracking
    - Error handling and logging
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize DeepSeek client.

        Args:
            api_key: Optional per-user decrypted API key. Falls back to the
                server-wide DEEPSEEK_API_KEY setting when not supplied.
            model: Optional model override.
        """
        resolved_key = api_key or getattr(settings, 'DEEPSEEK_API_KEY', None)
        if not resolved_key:
            raise ValueError(
                "No DeepSeek API key available. Add one on the AI Settings page "
                "or set DEEPSEEK_API_KEY in your .env file."
            )

        base_url = getattr(settings, 'DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
        self.client = OpenAI(api_key=resolved_key, base_url=base_url)
        self.model = model or getattr(settings, 'DEEPSEEK_MODEL', 'deepseek-chat')
        self.max_tokens = getattr(settings, 'AI_MAX_TOKENS', 4096)
        self.max_retries = 3
        self.base_delay = 1  # seconds
        self.provider = 'deepseek'
        # True when using a key the user supplied themselves (rather than our
        # server-wide key), so our internal cost limits shouldn't apply to them.
        self.using_own_key = bool(api_key)

        logger.info(f"[DeepSeekClient] Initialized with model='{self.model}', api_key_prefix='{resolved_key[:8]}...'")

    def call_api(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0
    ) -> Dict[str, Any]:
        """
        Call DeepSeek API with retry logic

        Args:
            prompt: The user prompt/question
            system_prompt: Optional system instructions
            max_tokens: Maximum tokens in response (default: self.max_tokens)
            temperature: Sampling temperature 0-1 (default: 0 for deterministic)

        Returns:
            Dict with 'content', 'usage', and 'cost' keys

        Raises:
            Exception: If API call fails after all retries
        """
        max_tokens = max_tokens or self.max_tokens

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Calling DeepSeek API (attempt {attempt + 1}/{self.max_retries})")
                logger.info(f"[DeepSeekClient] Sending request: model='{self.model}', max_tokens={max_tokens}")

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

                content = response.choices[0].message.content
                usage = {
                    'input_tokens': response.usage.prompt_tokens,
                    'output_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens,
                }

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
                    delay = self.base_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    logger.error("Max retries reached for rate limit")
                    raise

            except (APIError, APIConnectionError) as e:
                logger.error(f"[DeepSeekClient] API error (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    logger.error("Max retries reached for API error")
                    raise

            except Exception as e:
                logger.error(f"Unexpected error calling DeepSeek API: {e}")
                raise

        raise RuntimeError("Max retries exceeded calling DeepSeek API")

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost using centrally-maintained DeepSeek pricing."""
        from .cost_calculator import CostCalculator
        return CostCalculator.calculate_cost('deepseek', self.model, input_tokens, output_tokens)

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
            return json.loads(response_content)
        except json.JSONDecodeError:
            if "```json" in response_content:
                start = response_content.find("```json") + 7
                end = response_content.find("```", start)
                json_str = response_content[start:end].strip()
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON from markdown block: {e}")
                    raise ValueError(f"Invalid JSON in response: {e}")
            elif "```" in response_content:
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
        Check if user has exceeded monthly cost limit (shared across providers).

        Args:
            user_id: Django user ID

        Returns:
            True if under limit, False if exceeded
        """
        from datetime import datetime

        month_key = f"ai_cost_{user_id}_{datetime.now().strftime('%Y_%m')}"
        current_usage = cache.get(month_key, 0.0)
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
        Track AI API cost for user (shared across providers).

        Args:
            user_id: Django user ID
            cost: Cost in USD to add
        """
        from datetime import datetime

        month_key = f"ai_cost_{user_id}_{datetime.now().strftime('%Y_%m')}"
        current_usage = cache.get(month_key, 0.0)
        new_usage = current_usage + cost

        now = datetime.now()
        if now.month == 12:
            next_month = datetime(now.year + 1, 1, 1)
        else:
            next_month = datetime(now.year, now.month + 1, 1)

        seconds_until_next_month = int((next_month - now).total_seconds())
        cache.set(month_key, new_usage, seconds_until_next_month)

        logger.info(f"User {user_id} AI cost: ${new_usage:.4f} this month")
