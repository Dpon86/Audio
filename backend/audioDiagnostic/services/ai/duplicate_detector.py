"""
AI-powered duplicate detection service
"""

import logging
import json
from typing import Dict, Any, List, Optional
from .anthropic_client import AnthropicClient
from .prompt_templates import PromptTemplates
from .cost_calculator import CostCalculator

logger = logging.getLogger(__name__)


class DuplicateDetector:
    """Service for detecting duplicates using AI"""
    
    def __init__(self):
        """Initialize detector with AI client"""
        self.client = AnthropicClient()
        self.prompts = PromptTemplates()
    
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
        
        # Generate prompt
        system_prompt = self.prompts.duplicate_detection_system_prompt()
        user_prompt = self.prompts.duplicate_detection_prompt(
            transcript_data=transcript_data,
            min_words=min_words,
            similarity_threshold=similarity_threshold,
            keep_occurrence=keep_occurrence
        )
        
        # Call AI
        try:
            response = self.client.call_api(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.0  # Deterministic
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
