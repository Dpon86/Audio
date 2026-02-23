"""
Quality Scoring System for Audiobook Production Analysis

Analyzes alignment segments and determines production readiness.
"""

import logging
from typing import List, Dict, Optional
from .alignment_engine import AlignmentPoint, get_context_words

logger = logging.getLogger(__name__)


class ErrorDetail:
    """Represents a specific error in the transcript."""
    
    def __init__(self, error_type: str, position: int, pdf_word: Optional[str] = None,
                 transcript_word: Optional[str] = None, timestamp: Optional[Dict] = None,
                 context: Optional[str] = None):
        self.error_type = error_type  # mismatch, missing, extra
        self.position = position
        self.pdf_word = pdf_word
        self.transcript_word = transcript_word
        self.timestamp = timestamp
        self.context = context
    
    def to_dict(self):
        return {
            'error_type': self.error_type,
            'position': self.position,
            'pdf_word': self.pdf_word,
            'transcript_word': self.transcript_word,
            'timestamp': self.timestamp,
            'context': self.context
        }


class QualitySegment:
    """Represents a segment of the audiobook with quality metrics."""
    
    def __init__(self, segment_id: int, start_time: Optional[float], end_time: Optional[float],
                 quality_score: float, status: str, metrics: Dict, errors: List[ErrorDetail]):
        self.segment_id = segment_id
        self.start_time = start_time
        self.end_time = end_time
        self.quality_score = quality_score
        self.status = status  # production_ready, needs_minor_edits, needs_review, needs_rerecording
        self.metrics = metrics
        self.errors = errors
    
    def to_dict(self):
        return {
            'segment_id': self.segment_id,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'quality_score': self.quality_score,
            'status': self.status,
            'metrics': self.metrics,
            'errors': [e.to_dict() for e in self.errors]
        }


def extract_errors(segment_alignment: List[AlignmentPoint], 
                   full_alignment: List[AlignmentPoint],
                   start_idx: int) -> List[ErrorDetail]:
    """
    Extract specific errors from an alignment segment.
    
    Args:
        segment_alignment: Alignment points for this segment
        full_alignment: Full alignment (for context)
        start_idx: Starting index of this segment in full alignment
    
    Returns:
        List of ErrorDetail objects
    """
    errors = []
    
    for i, point in enumerate(segment_alignment):
        if point.match_type in ['mismatch', 'missing', 'extra']:
            # Get context around this error
            global_idx = start_idx + i
            context = get_context_words(full_alignment, global_idx, context_size=5, use_pdf=True)
            
            errors.append(ErrorDetail(
                error_type=point.match_type,
                position=i,
                pdf_word=point.pdf_word,
                transcript_word=point.transcript_word,
                timestamp=point.timestamp,
                context=context
            ))
    
    return errors


def calculate_segment_quality(segment_alignment: List[AlignmentPoint]) -> float:
    """
    Calculate quality score for a segment.
    
    Scoring:
    - Exact match: 1.0
    - Normalized match: 0.95
    - Phonetic match: 0.8
    - Mismatch: 0.0
    - Missing: 0.0 (with penalty)
    - Extra: 0.0 (with penalty)
    
    Returns:
        Quality score from 0.0 to 1.0
    """
    if not segment_alignment:
        return 0.0
    
    total_score = 0.0
    total_words = len(segment_alignment)
    
    for point in segment_alignment:
        if point.match_type == 'exact':
            total_score += 1.0
        elif point.match_type == 'normalized':
            total_score += 0.95
        elif point.match_type == 'phonetic':
            total_score += 0.8
        # mismatch, missing, extra all contribute 0
    
    return total_score / total_words if total_words > 0 else 0.0


def determine_segment_status(quality_score: float, 
                             missing_count: int,
                             mismatch_count: int) -> str:
    """
    Determine production status based on quality metrics.
    
    Returns:
        'production_ready': 95%+ quality, no missing content
        'needs_minor_edits': 85-95% quality
        'needs_review': 70-85% quality
        'needs_rerecording': <70% quality
    """
    # Any missing content means not production ready
    if missing_count > 0:
        if quality_score >= 0.85:
            return 'needs_minor_edits'
        elif quality_score >= 0.70:
            return 'needs_review'
        else:
            return 'needs_rerecording'
    
    # No missing content, check quality
    if quality_score >= 0.95:
        return 'production_ready'
    elif quality_score >= 0.85:
        return 'needs_minor_edits'
    elif quality_score >= 0.70:
        return 'needs_review'
    else:
        return 'needs_rerecording'


def analyze_segments(alignment: List[AlignmentPoint], 
                     segment_size: int = 50) -> List[QualitySegment]:
    """
    Break alignment into segments and analyze quality.
    
    Args:
        alignment: Full alignment
        segment_size: Number of alignment points per segment
    
    Returns:
        List of QualitySegment objects
    """
    logger.info(f"Analyzing alignment in segments of {segment_size} words")
    
    segments = []
    
    for i in range(0, len(alignment), segment_size):
        segment_alignment = alignment[i:i + segment_size]
        
        # Calculate metrics
        total_words = len(segment_alignment)
        exact_matches = sum(1 for a in segment_alignment if a.match_type == 'exact')
        normalized_matches = sum(1 for a in segment_alignment if a.match_type == 'normalized')
        phonetic_matches = sum(1 for a in segment_alignment if a.match_type == 'phonetic')
        mismatches = sum(1 for a in segment_alignment if a.match_type == 'mismatch')
        missing = sum(1 for a in segment_alignment if a.match_type == 'missing')
        extra = sum(1 for a in segment_alignment if a.match_type == 'extra')
        
        # Calculate quality score
        quality_score = calculate_segment_quality(segment_alignment)
        
        # Determine status
        status = determine_segment_status(quality_score, missing, mismatches)
        
        # Get timestamp range (from transcript words)
        timestamps = [a.timestamp for a in segment_alignment if a.timestamp]
        start_time = min(t['start'] for t in timestamps) if timestamps else None
        end_time = max(t['end'] for t in timestamps) if timestamps else None
        
        # Extract errors
        errors = extract_errors(segment_alignment, alignment, i)
        
        segments.append(QualitySegment(
            segment_id=i // segment_size,
            start_time=start_time,
            end_time=end_time,
            quality_score=quality_score,
            status=status,
            metrics={
                'total_words': total_words,
                'exact_matches': exact_matches,
                'normalized_matches': normalized_matches,
                'phonetic_matches': phonetic_matches,
                'mismatches': mismatches,
                'missing_words': missing,
                'extra_words': extra
            },
            errors=errors
        ))
    
    logger.info(f"Created {len(segments)} quality segments")
    
    # Log summary
    production_ready = sum(1 for s in segments if s.status == 'production_ready')
    needs_minor = sum(1 for s in segments if s.status == 'needs_minor_edits')
    needs_review = sum(1 for s in segments if s.status == 'needs_review')
    needs_rerecording = sum(1 for s in segments if s.status == 'needs_rerecording')
    
    logger.info(f"Segment status distribution - "
                f"Production ready: {production_ready}, "
                f"Needs minor edits: {needs_minor}, "
                f"Needs review: {needs_review}, "
                f"Needs re-recording: {needs_rerecording}")
    
    return segments


def calculate_overall_quality(segments: List[QualitySegment]) -> float:
    """
    Calculate overall quality score across all segments.
    
    Returns:
        Overall quality score from 0.0 to 1.0
    """
    if not segments:
        return 0.0
    
    total_score = sum(s.quality_score for s in segments)
    return total_score / len(segments)


def determine_overall_status(overall_score: float, 
                            missing_sections_count: int,
                            segments: List[QualitySegment]) -> str:
    """
    Determine overall production status.
    
    Returns:
        'PRODUCTION READY ✓': Ready for release
        'NEEDS MINOR EDITING': Small fixes needed
        'NEEDS SIGNIFICANT WORK': Major issues to address
    """
    # Count segments by status
    needs_rerecording = sum(1 for s in segments if s.status == 'needs_rerecording')
    needs_review = sum(1 for s in segments if s.status == 'needs_review')
    
    # If there are missing sections, not production ready
    if missing_sections_count > 0:
        return 'NEEDS SIGNIFICANT WORK'
    
    # If any segments need re-recording, significant work needed
    if needs_rerecording > 0:
        return 'NEEDS SIGNIFICANT WORK'
    
    # If many segments need review, significant work
    if needs_review > len(segments) * 0.2:  # More than 20% need review
        return 'NEEDS SIGNIFICANT WORK'
    
    # Check overall score
    if overall_score >= 0.95:
        return 'PRODUCTION READY ✓'
    elif overall_score >= 0.85:
        return 'NEEDS MINOR EDITING'
    else:
        return 'NEEDS SIGNIFICANT WORK'


def compile_all_errors(alignment: List[AlignmentPoint]) -> List[ErrorDetail]:
    """
    Compile all errors from the full alignment.
    
    Returns:
        List of all errors with context
    """
    errors = []
    
    for i, point in enumerate(alignment):
        if point.match_type in ['mismatch', 'missing', 'extra']:
            context = get_context_words(alignment, i, context_size=5, use_pdf=True)
            
            errors.append(ErrorDetail(
                error_type=point.match_type,
                position=i,
                pdf_word=point.pdf_word,
                transcript_word=point.transcript_word,
                timestamp=point.timestamp,
                context=context
            ))
    
    return errors
