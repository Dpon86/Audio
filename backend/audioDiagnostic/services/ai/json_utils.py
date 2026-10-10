"""
Helpers for pulling JSON out of LLM responses.
"""

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _balanced_object(text: str) -> str:
    """Return the first balanced top-level {...} in text, or '' if none/incomplete."""
    start = text.find('{')
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == '\\':
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        return ''
    return ''


def parse_json_response(response_content: str) -> Dict[str, Any]:
    """
    Parse JSON from an AI response, tolerating markdown fences and surrounding prose.

    Raises:
        ValueError: If JSON cannot be parsed.
    """
    text = (response_content or '').strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    if "```" in text:
        start = text.find("```json")
        start = start + 7 if start != -1 else text.find("```") + 3
        end = text.find("```", start)
        block = text[start:end if end != -1 else len(text)].strip()
        try:
            return json.loads(block)
        except json.JSONDecodeError as e:
            candidate = _balanced_object(block)
            if candidate:
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    pass
            logger.error(f"Failed to parse JSON from code block: {e}")
            raise ValueError(f"Invalid JSON in response: {e}")

    candidate = _balanced_object(text)
    if candidate:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in response: {e}")

    if text.startswith('{'):
        logger.error(
            "AI response looks like JSON but is incomplete (likely truncated at "
            f"max_tokens); length={len(text)}, tail={text[-200:]!r}"
        )
        raise ValueError(
            "AI response was cut off before the JSON was complete "
            "(output token limit reached)"
        )

    logger.error(f"No JSON in AI response; preview={text[:300]!r}")
    raise ValueError(f"No JSON found in response. AI replied: {text[:200]!r}")
