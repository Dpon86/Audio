"""
AI-powered duplicate detection service
"""

import logging
import json
from typing import Dict, Any, List, Optional
from .anthropic_client import AnthropicClient
from .json_utils import TruncatedResponseError
from .prompt_templates import PromptTemplates
from .cost_calculator import CostCalculator

logger = logging.getLogger(__name__)


class DuplicateDetector:
    """Service for detecting duplicates using AI"""

    # Segments per AI call and overlap between calls; keeps each response within
    # the model's output limit while still catching re-takes that straddle a boundary.
    CHUNK_SEGMENTS = 80
    CHUNK_OVERLAP = 20
    MIN_SPLIT_SEGMENTS = 10
    DETECTION_MAX_TOKENS = 8192
    
    def __init__(self, user=None):
        """
        Initialize detector with an AI client.

        Args:
            user: Optional Django User. If they have saved their own encrypted
                AI provider API key (via the AI Settings page), it is used in
                preference to the server-wide key so their own account is
                billed instead of ours.
        """
        self.client = self._resolve_client(user)
        self.prompts = PromptTemplates()

    @staticmethod
    def _resolve_client(user):
        """Prefer the user's own encrypted API key/provider over the server-wide default."""
        if user is not None and getattr(user, 'is_authenticated', False):
            from accounts.models import UserAPIKey
            stored_key = UserAPIKey.objects.filter(user=user, is_active=True).first()
            if stored_key:
                raw_key = stored_key.get_key()
                if stored_key.provider == 'deepseek':
                    from .deepseek_client import DeepSeekClient
                    return DeepSeekClient(api_key=raw_key)
                if stored_key.provider == 'anthropic':
                    return AnthropicClient(api_key=raw_key)
                # Other providers (e.g. openai) aren't wrapped as a dedicated
                # client yet - fall back to the server-wide default below.

        return AnthropicClient()
    
    def detect_sentence_level_duplicates(
        self,
        transcript_data: Dict[str, Any],
        min_words: int = 3,
        similarity_threshold: float = 0.85,
        keep_occurrence: str = 'last'
    ) -> Dict[str, Any]:
        """
        Detect sentence-level duplicates using AI
        
        Args:
            transcript_data: JSON with segments, words, metadata
            min_words: Minimum words to qualify as duplicate
            similarity_threshold: 0-1, semantic similarity threshold
            keep_occurrence: 'first', 'last', or 'best'
        
        Returns:
            Dict with duplicate_groups and metadata
        
        Raises:
            ValueError: If AI response is invalid
        """
        logger.info("Starting AI duplicate detection (sentence level)")

        segments = transcript_data.get('segments') or []
        results = self._detect_window(
            transcript_data, 0, len(segments), min_words, similarity_threshold, keep_occurrence
        )
        if len(results) == 1:
            return results[0]
        return self._merge_results(results)

    def _detect_window(
        self,
        transcript_data: Dict[str, Any],
        offset: int,
        total: int,
        min_words: int,
        similarity_threshold: float,
        keep_occurrence: str
    ) -> List[Dict[str, Any]]:
        """
        Analyse the transcript in overlapping windows (large transcripts exceed the
        model's output limit in one call). A window whose reply is still cut off is
        split in half and retried.
        """
        segments = transcript_data.get('segments') or []
        if len(segments) > self.CHUNK_SEGMENTS:
            step = self.CHUNK_SEGMENTS - self.CHUNK_OVERLAP
            results = []
            for start in range(0, len(segments), step):
                results.extend(self._detect_window(
                    self._with_segments(transcript_data, segments[start:start + self.CHUNK_SEGMENTS]),
                    offset + start, total, min_words, similarity_threshold, keep_occurrence
                ))
                if start + self.CHUNK_SEGMENTS >= len(segments):
                    break
            return results

        logger.info(
            f"AI detection window: segments {offset}-{offset + len(segments) - 1} of {total}"
        )
        try:
            return [self._detect_chunk(
                transcript_data, min_words, similarity_threshold, keep_occurrence
            )]
        except TruncatedResponseError:
            if len(segments) < self.MIN_SPLIT_SEGMENTS:
                raise
            half = len(segments) // 2
            overlap = self.CHUNK_OVERLAP // 2
            logger.warning(
                f"Window {offset}-{offset + len(segments) - 1} reply was truncated; splitting"
            )
            return (
                self._detect_window(
                    self._with_segments(transcript_data, segments[:half + overlap]),
                    offset, total, min_words, similarity_threshold, keep_occurrence
                )
                + self._detect_window(
                    self._with_segments(transcript_data, segments[half:]),
                    offset + half, total, min_words, similarity_threshold, keep_occurrence
                )
            )

    @staticmethod
    def _with_segments(transcript_data: Dict[str, Any], segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        data = dict(transcript_data)
        data['segments'] = segments
        return data

    @staticmethod
    def _merge_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Combine per-window results, dropping groups already found in an overlap."""
        merged_groups: List[Dict[str, Any]] = []
        seen_signatures = set()
        usage = {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0}
        total_cost = 0.0
        model = None

        for result in results:
            meta = result.get('ai_metadata', {})
            for key in usage:
                usage[key] += meta.get('usage', {}).get(key, 0)
            total_cost += meta.get('cost', 0) or 0
            model = meta.get('model', model)

            for group in result.get('duplicate_groups', []):
                signature = frozenset(
                    int(pk)
                    for occ in group.get('occurrences', [])
                    for pk in (occ.get('segment_ids') or [])
                )
                if signature and signature in seen_signatures:
                    continue
                seen_signatures.add(signature)
                merged_groups.append(group)

        total_occurrences = 0
        to_delete = 0
        time_saved = 0.0
        for index, group in enumerate(merged_groups, start=1):
            group['group_id'] = f"dup_{index:03d}"
            for occ in group.get('occurrences', []):
                total_occurrences += 1
                if occ.get('action') == 'delete':
                    to_delete += 1
                    time_saved += max(
                        0.0, (occ.get('end_time') or 0) - (occ.get('start_time') or 0)
                    )

        return {
            'duplicate_groups': merged_groups,
            'summary': {
                'total_duplicate_groups': len(merged_groups),
                'total_occurrences': total_occurrences,
                'occurrences_to_delete': to_delete,
                'estimated_time_saved_seconds': round(time_saved, 2),
            },
            'ai_metadata': {'model': model, 'usage': usage, 'cost': total_cost},
        }

    def _detect_chunk(
        self,
        transcript_data: Dict[str, Any],
        min_words: int,
        similarity_threshold: float,
        keep_occurrence: str
    ) -> Dict[str, Any]:
        """Run one AI duplicate-detection call over the given transcript data."""
        system_prompt = self.prompts.duplicate_detection_system_prompt()
        user_prompt = self.prompts.duplicate_detection_prompt(
            transcript_data=transcript_data,
            min_words=min_words,
            similarity_threshold=similarity_threshold,
            keep_occurrence=keep_occurrence
        )

        try:
            call_kwargs = {}
            if getattr(self.client, 'provider', None) == 'deepseek':
                call_kwargs['json_mode'] = True
            response = self.client.call_api(
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=self.DETECTION_MAX_TOKENS,
                temperature=0.0,  # Deterministic
                **call_kwargs
            )

            result = self.client.parse_json_response(response['content'])

            result['ai_metadata'] = {
                'model': response['model'],
                'usage': response['usage'],
                'cost': response['cost']
            }

            logger.info(
                f"Duplicate detection complete. "
                f"Found {result.get('summary', {}).get('total_duplicate_groups', 0)} groups. "
                f"Cost: ${response['cost']:.4f}"
            )

            return result

        except Exception as e:
            logger.error(f"AI duplicate detection failed: {e}")
            raise

    def expand_to_paragraph_level(
        self,
        duplicate_groups: List[Dict[str, Any]],
        transcript_segments: List[Dict[str, Any]],
        context_window: int = 5
    ) -> Dict[str, Any]:
        """
        Expand duplicates to paragraph level using AI
        
        Args:
            duplicate_groups: Results from sentence detection
            transcript_segments: Full transcript segments
            context_window: How many segments to check before/after
        
        Returns:
            Dict with expanded_groups and metadata
        """
        logger.info("Starting paragraph-level expansion")
        
        # Generate prompt
        system_prompt = self.prompts.paragraph_expansion_system_prompt()
        user_prompt = self.prompts.paragraph_expansion_prompt(
            duplicate_groups=duplicate_groups,
            transcript_segments=transcript_segments,
            context_window=context_window
        )
        
        # Call AI
        try:
            response = self.client.call_api(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.0
            )
            
            # Parse JSON response
            result = self.client.parse_json_response(response['content'])
            
            # Add metadata
            result['ai_metadata'] = {
                'model': response['model'],
                'usage': response['usage'],
                'cost': response['cost']
            }
            
            logger.info(
                f"Paragraph expansion complete. "
                f"Expanded {result.get('summary', {}).get('groups_expanded', 0)} groups. "
                f"Cost: ${response['cost']:.4f}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Paragraph expansion failed: {e}")
            raise
    
    def compare_with_pdf(
        self,
        clean_transcript: str,
        pdf_text: str,
        pdf_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compare transcript with PDF using AI
        
        Args:
            clean_transcript: Transcript after duplicate removal
            pdf_text: Text extracted from PDF
            pdf_metadata: PDF info (pages, title, etc.)
        
        Returns:
            Dict with alignment_result, discrepancies, metadata
        """
        logger.info("Starting PDF comparison")
        
        # Generate prompt
        system_prompt = self.prompts.pdf_comparison_system_prompt()
        user_prompt = self.prompts.pdf_comparison_prompt(
            clean_transcript=clean_transcript,
            pdf_text=pdf_text,
            pdf_metadata=pdf_metadata
        )
        
        # Call AI
        try:
            response = self.client.call_api(
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=8192,  # Larger for detailed comparison
                temperature=0.0
            )
            
            # Parse JSON response
            result = self.client.parse_json_response(response['content'])
            
            # Add metadata
            result['ai_metadata'] = {
                'model': response['model'],
                'usage': response['usage'],
                'cost': response['cost']
            }
            
            logger.info(
                f"PDF comparison complete. "
                f"Coverage: {result.get('summary', {}).get('coverage_percentage', 0):.1f}%. "
                f"Discrepancies: {result.get('summary', {}).get('total_discrepancies', 0)}. "
                f"Cost: ${response['cost']:.4f}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"PDF comparison failed: {e}")
            raise
    
    def estimate_cost(
        self,
        audio_duration_seconds: float,
        task: str = 'duplicate_detection'
    ) -> Dict[str, Any]:
        """
        Estimate cost for processing audio
        
        Args:
            audio_duration_seconds: Length of audio
            task: 'duplicate_detection' or 'pdf_comparison'
        
        Returns:
            Dict with cost estimate
        """
        return CostCalculator.estimate_cost_for_audio(
            provider='anthropic',
            model=self.client.model,
            audio_duration_seconds=audio_duration_seconds,
            task=task
        )
