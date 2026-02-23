"""
Gap Detection for Audiobook Production Analysis

Identifies missing sections in the transcript that need to be recorded.
"""

import logging
from typing import List, Optional, Dict
from .alignment_engine import AlignmentPoint, get_context_words, estimate_reading_time

logger = logging.getLogger(__name__)


class MissingSection:
    """Represents a section of PDF text that is missing from the transcript."""
    
    def __init__(self, pdf_start_index: int, pdf_end_index: int, missing_text: str,
                 word_count: int, context_before: str, context_after: str,
                 estimated_duration: str, timestamp_context: Optional[str] = None):
        self.pdf_start_index = pdf_start_index
        self.pdf_end_index = pdf_end_index
        self.missing_text = missing_text
        self.word_count = word_count
        self.context_before = context_before
        self.context_after = context_after
        self.estimated_duration = estimated_duration
        self.timestamp_context = timestamp_context
    
    def to_dict(self):
        return {
            'pdf_start_index': self.pdf_start_index,
            'pdf_end_index': self.pdf_end_index,
            'missing_text': self.missing_text,
            'word_count': self.word_count,
            'context_before': self.context_before,
            'context_after': self.context_after,
            'estimated_duration': self.estimated_duration,
            'timestamp_context': self.timestamp_context
        }


def find_context_before_gap(alignment: List[AlignmentPoint], 
                            gap_start_idx: int,
                            context_words: int = 10) -> str:
    """
    Find context words before a gap.
    
    Args:
        alignment: Full alignment
        gap_start_idx: Index where gap starts
        context_words: Number of words to include
    
    Returns:
        Context string
    """
    words = []
    count = 0
    
    # Work backwards from gap
    for i in range(gap_start_idx - 1, -1, -1):
        if alignment[i].pdf_word:
            words.append(alignment[i].pdf_word)
            count += 1
            if count >= context_words:
                break
    
    # Reverse to get correct order
    return ' '.join(reversed(words))


def find_context_after_gap(alignment: List[AlignmentPoint],
                           gap_end_idx: int,
                           context_words: int = 10) -> str:
    """
    Find context words after a gap.
    
    Args:
        alignment: Full alignment
        gap_end_idx: Index where gap ends
        context_words: Number of words to include
    
    Returns:
        Context string
    """
    words = []
    count = 0
    
    # Work forwards from gap end
    for i in range(gap_end_idx + 1, len(alignment)):
        if alignment[i].pdf_word:
            words.append(alignment[i].pdf_word)
            count += 1
            if count >= context_words:
                break
    
    return ' '.join(words)


def get_timestamp_context_for_gap(alignment: List[AlignmentPoint],
                                  gap_start_idx: int,
                                  gap_end_idx: int) -> Optional[str]:
    """
    Get timestamp context for where the missing section should be.
    
    Looks for the last transcript word before the gap and the first after.
    
    Returns:
        Timestamp context string like "After 15:32, before 16:45" or None
    """
    # Find last transcript timestamp before gap
    time_before = None
    for i in range(gap_start_idx - 1, -1, -1):
        if alignment[i].timestamp:
            time_before = alignment[i].timestamp['end']
            break
    
    # Find first transcript timestamp after gap
    time_after = None
    for i in range(gap_end_idx + 1, len(alignment)):
        if alignment[i].timestamp:
            time_after = alignment[i].timestamp['start']
            break
    
    if time_before and time_after:
        # Format as MM:SS
        before_mins = int(time_before // 60)
        before_secs = int(time_before % 60)
        after_mins = int(time_after // 60)
        after_secs = int(time_after % 60)
        
        return f"After {before_mins}:{before_secs:02d}, before {after_mins}:{after_secs:02d}"
    elif time_before:
        mins = int(time_before // 60)
        secs = int(time_before % 60)
        return f"After {mins}:{secs:02d}"
    elif time_after:
        mins = int(time_after // 60)
        secs = int(time_after % 60)
        return f"Before {mins}:{secs:02d}"
    else:
        return None


def find_missing_sections(alignment: List[AlignmentPoint],
                          min_gap_words: int = 10,
                          context_words: int = 10) -> List[MissingSection]:
    """
    Find contiguous sections of PDF text not found in transcript.
    
    Args:
        alignment: Full alignment
        min_gap_words: Minimum number of consecutive missing words to count as a gap
        context_words: Number of context words to include before/after
    
    Returns:
        List of MissingSection objects
    """
    logger.info(f"Searching for missing sections (min {min_gap_words} words)")
    
    missing_sections = []
    current_gap = []
    gap_start_idx = None
    
    for i, point in enumerate(alignment):
        if point.match_type == 'missing':
            # This word is missing from transcript
            if not current_gap:
                gap_start_idx = i
            current_gap.append(point)
        else:
            # Not missing, check if we had a gap
            if len(current_gap) >= min_gap_words:
                gap_end_idx = gap_start_idx + len(current_gap) - 1
                
                # Extract missing text
                missing_text = ' '.join(p.pdf_word for p in current_gap if p.pdf_word)
                
                # Get context
                context_before = find_context_before_gap(alignment, gap_start_idx, context_words)
                context_after = find_context_after_gap(alignment, gap_end_idx, context_words)
                
                # Get timestamp context
                timestamp_context = get_timestamp_context_for_gap(alignment, gap_start_idx, gap_end_idx)
                
                # Create MissingSection
                missing_sections.append(MissingSection(
                    pdf_start_index=gap_start_idx,
                    pdf_end_index=gap_end_idx,
                    missing_text=missing_text,
                    word_count=len(current_gap),
                    context_before=context_before,
                    context_after=context_after,
                    estimated_duration=estimate_reading_time(len(current_gap)),
                    timestamp_context=timestamp_context
                ))
            
            # Reset gap
            current_gap = []
            gap_start_idx = None
    
    # Check for gap at end of alignment
    if len(current_gap) >= min_gap_words:
        gap_end_idx = gap_start_idx + len(current_gap) - 1
        
        missing_text = ' '.join(p.pdf_word for p in current_gap if p.pdf_word)
        context_before = find_context_before_gap(alignment, gap_start_idx, context_words)
        context_after = ""  # No context after (end of book)
        timestamp_context = get_timestamp_context_for_gap(alignment, gap_start_idx, gap_end_idx)
        
        missing_sections.append(MissingSection(
            pdf_start_index=gap_start_idx,
            pdf_end_index=gap_end_idx,
            missing_text=missing_text,
            word_count=len(current_gap),
            context_before=context_before,
            context_after=context_after,
            estimated_duration=estimate_reading_time(len(current_gap)),
            timestamp_context=timestamp_context
        ))
    
    logger.info(f"Found {len(missing_sections)} missing sections")
    
    # Log details about missing sections
    if missing_sections:
        total_missing_words = sum(ms.word_count for ms in missing_sections)
        logger.info(f"Total missing words: {total_missing_words}")
        
        for i, ms in enumerate(missing_sections):
            logger.info(f"Missing section {i+1}: {ms.word_count} words, "
                       f"estimated {ms.estimated_duration} to record")
    
    return missing_sections


def calculate_completeness_percentage(alignment: List[AlignmentPoint]) -> float:
    """
    Calculate what percentage of the PDF has been read.
    
    Returns:
        Percentage from 0.0 to 100.0
    """
    total_pdf_words = sum(1 for a in alignment if a.pdf_word)
    missing_words = sum(1 for a in alignment if a.match_type == 'missing')
    
    if total_pdf_words == 0:
        return 0.0
    
    read_words = total_pdf_words - missing_words
    return (read_words / total_pdf_words) * 100.0


def analyze_gap_distribution(missing_sections: List[MissingSection]) -> Dict:
    """
    Analyze the distribution and characteristics of gaps.
    
    Returns:
        Dictionary with gap statistics
    """
    if not missing_sections:
        return {
            'total_gaps': 0,
            'total_missing_words': 0,
            'average_gap_size': 0,
            'largest_gap': 0,
            'smallest_gap': 0
        }
    
    word_counts = [ms.word_count for ms in missing_sections]
    
    return {
        'total_gaps': len(missing_sections),
        'total_missing_words': sum(word_counts),
        'average_gap_size': sum(word_counts) / len(word_counts),
        'largest_gap': max(word_counts),
        'smallest_gap': min(word_counts)
    }
