"""
Prompt templates for AI-powered duplicate detection
"""

from typing import Dict, Any, List


class PromptTemplates:
    """Collection of prompt templates for AI tasks"""
    
    @staticmethod
    def duplicate_detection_system_prompt() -> str:
        """System prompt for duplicate detection task"""
        return """You are an expert audiobook editor specializing in identifying and correcting duplicate narration in audio transcripts.

Your task is to analyze transcripts and identify repeated content that should be removed to create a clean, professional audiobook.

Key capabilities:
- Detect semantic duplicates (not just exact text matches)
- Understand context to avoid false positives
- Identify which occurrence to keep (typically the last one)
- Provide confidence scores based on evidence
- Handle variations in phrasing

Output format: Always return valid JSON matching the specified schema."""
    
    @staticmethod
    def duplicate_detection_prompt(
        transcript_data: Dict[str, Any],
        min_words: int = 3,
        similarity_threshold: float = 0.85,
        keep_occurrence: str = 'last'
    ) -> str:
        """
        Generate prompt for sentence-level duplicate detection
        
        Args:
            transcript_data: JSON with segments and words
            min_words: Minimum words to qualify as duplicate
            similarity_threshold: 0-1, how similar to qualify
            keep_occurrence: 'first', 'last', or 'best'
        
        Returns:
            Formatted prompt string
        """
        import json
        
        return f"""Analyze this audio transcript for duplicate narration.

# Task
Identify repeated sentences or phrases that were re-recorded and need to be removed.

# Rules
1. Find duplicates with at least {min_words} words
2. Detect semantic similarity (similarity ≥ {similarity_threshold})
3. Group related duplicates together
4. Default action: Keep {keep_occurrence} occurrence, mark others for deletion
5. Provide confidence scores (0.0-1.0)

# Input Transcript
```json
{json.dumps(transcript_data, indent=2)}
```

# Output Format
Return ONLY valid JSON with this structure:

```json
{{
  "duplicate_groups": [
    {{
      "group_id": "dup_001",
      "duplicate_text": "The text that was repeated",
      "confidence": 0.95,
      "detection_method": "semantic_similarity",
      "reason": "Brief explanation",
      "severity": "high",
      "occurrences": [
        {{
          "occurrence_id": 1,
          "segment_ids": [12, 13],
          "start_time": 45.0,
          "end_time": 48.5,
          "text": "Exact text from transcript",
          "action": "delete",
          "reason": "Earlier take, narrator stumbled"
        }},
        {{
          "occurrence_id": 2,
          "segment_ids": [156, 157],
          "start_time": 480.0,
          "end_time": 483.5,
          "text": "Exact text from transcript",
          "action": "keep",
          "reason": "Cleaner delivery, kept as final version"
        }}
      ]
    }}
  ],
  "summary": {{
    "total_duplicate_groups": 1,
    "total_occurrences": 2,
    "occurrences_to_delete": 1,
    "estimated_time_saved_seconds": 3.5
  }}
}}
```

# Important
- Only return the JSON (no extra text)
- Include all fields shown in the example
- Use actual segment IDs and timestamps from input
- Be conservative: Only flag clear duplicates (high confidence)

Analyze the transcript now:"""
    
    @staticmethod
    def paragraph_expansion_system_prompt() -> str:
        """System prompt for paragraph expansion task"""
        return """You are an expert audiobook editor specializing in identifying complete paragraph-level duplicates.

Your task is to review detected sentence duplicates and determine if entire paragraphs were re-recorded, not just individual sentences.

Key capabilities:
- Analyze context around duplicates
- Identify natural paragraph boundaries
- Expand duplicate regions to include full paragraphs
- Adjust timestamps precisely

Output format: Always return valid JSON matching the specified schema."""
    
    @staticmethod
    def paragraph_expansion_prompt(
        duplicate_groups: List[Dict[str, Any]],
        transcript_segments: List[Dict[str, Any]],
        context_window: int = 5
    ) -> str:
        """
        Generate prompt for paragraph-level expansion
        
        Args:
            duplicate_groups: Results from sentence detection
            transcript_segments: Full transcript segments
            context_window: How many segments to check before/after
        
        Returns:
            Formatted prompt string
        """
        import json
        
        return f"""Review these detected duplicates and expand to full paragraph level if appropriate.

# Task
For each duplicate group, check if the entire surrounding paragraph was duplicated, not just the sentence.

# Context Window
Check {context_window} segments before and after each duplicate.

# Input - Detected Duplicates
```json
{json.dumps(duplicate_groups, indent=2)}
```

# Input - Full Transcript
```json
{json.dumps(transcript_segments, indent=2)}
```

# Output Format
Return ONLY valid JSON:

```json
{{
  "expanded_groups": [
    {{
      "original_group_id": "dup_001",
      "expanded": true,
      "reason": "Full paragraph was repeated",
      "occurrences": [
        {{
          "occurrence_id": 1,
          "original_segment_ids": [12, 13],
          "expanded_segment_ids": [10, 11, 12, 13, 14],
          "original_time_range": [45.0, 48.5],
          "expanded_time_range": [40.0, 52.0],
          "action": "delete",
          "context_before": "Text from segment 10-11",
          "context_after": "Text from segment 14"
        }},
        {{
          "occurrence_id": 2,
          "original_segment_ids": [156, 157],
          "expanded_segment_ids": [154, 155, 156, 157, 158],
          "original_time_range": [480.0, 483.5],
          "expanded_time_range": [475.0, 487.0],
          "action": "keep"
        }}
      ]
    }}
  ],
  "summary": {{
    "total_groups_processed": 1,
    "groups_expanded": 1,
    "average_expansion_seconds": 10.5
  }}
}}
```

Analyze and expand where appropriate:"""
    
    @staticmethod
    def pdf_comparison_system_prompt() -> str:
        """System prompt for PDF comparison task"""
        return """You are an expert audiobook quality control specialist.

Your task is to compare the clean audio transcript (after duplicate removal) against the reference PDF to verify completeness and accuracy.

Key capabilities:
- Align transcript to PDF content
- Identify missing passages
- Identify extra narration not in PDF
- Detect paraphrasing or changes
- Calculate coverage percentage

Output format: Always return valid JSON matching the specified schema."""
    
    @staticmethod
    def pdf_comparison_prompt(
        clean_transcript: str,
        pdf_text: str,
        pdf_metadata: Dict[str, Any]
    ) -> str:
        """
        Generate prompt for PDF comparison
        
        Args:
            clean_transcript: Transcript after duplicate removal
            pdf_text: Text extracted from PDF
            pdf_metadata: PDF info (pages, title, etc.)
        
        Returns:
            Formatted prompt string
        """
        import json
        
        return f"""Compare this audio transcript against the reference PDF to verify completeness.

# Task
1. Align the transcript to the PDF content
2. Identify any missing sections (in PDF but not in audio)
3. Identify any extra content (in audio but not in PDF)
4. Detect paraphrasing or significant changes
5. Calculate coverage percentage

# PDF Metadata
```json
{json.dumps(pdf_metadata, indent=2)}
```

# Clean Transcript (after duplicate removal)
```
{clean_transcript[:10000]}{"..." if len(clean_transcript) > 10000 else ""}
```

# Reference PDF Text
```
{pdf_text[:10000]}{"..." if len(pdf_text) > 10000 else ""}
```

# Output Format
Return ONLY valid JSON:

```json
{{
  "alignment_result": {{
    "aligned_percentage": 95.5,
    "transcript_sections_matched": 18,
    "pdf_sections_matched": 18,
    "total_pdf_sections": 20
  }},
  "discrepancies": [
    {{
      "type": "missing_in_audio",
      "severity": "high",
      "pdf_location": {{
        "page": 5,
        "paragraph": 3,
        "text_preview": "First 100 chars of missing text..."
      }},
      "expected_position_in_audio": "After segment about XYZ",
      "confidence": 0.95,
      "suggested_action": "Review recording - may need re-recording"
    }},
    {{
      "type": "extra_in_audio",
      "severity": "medium",
      "audio_location": {{
        "timestamp": 120.5,
        "text_preview": "First 100 chars of extra text..."
      }},
      "confidence": 0.85,
      "suggested_action": "Verify if this should be removed"
    }},
    {{
      "type": "paraphrased",
      "severity": "low",
      "pdf_text": "Original text from PDF",
      "audio_text": "Paraphrased text from audio",
      "pdf_page": 3,
      "audio_timestamp": 45.0,
      "confidence": 0.90,
      "suggested_action": "Consider if semantic match is acceptable"
    }}
  ],
  "summary": {{
    "coverage_percentage": 95.5,
    "total_discrepancies": 3,
    "high_severity": 1,
    "medium_severity": 1,
    "low_severity": 1,
    "overall_quality": "excellent"
  }}
}}
```

Perform comparison now:"""
