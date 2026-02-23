"""
Production Report Generator for Audiobook Analysis

Generates comprehensive production readiness reports with editing checklists.
"""

import logging
from typing import List, Dict
from datetime import datetime
from .repetition_detector import Repetition, WordTimestamp
from .alignment_engine import AlignmentPoint
from .quality_scorer import QualitySegment, calculate_overall_quality, determine_overall_status
from .gap_detector import MissingSection, calculate_completeness_percentage, analyze_gap_distribution

logger = logging.getLogger(__name__)


class ChecklistItem:
    """Represents one item in the editing checklist."""
    
    def __init__(self, priority: str, action: str, description: str,
                 timestamp: str = None, text: str = None, context: Dict = None):
        self.priority = priority  # CRITICAL, HIGH, MEDIUM, LOW
        self.action = action  # RECORD, RE-RECORD, DELETE, REVIEW, EDIT
        self.description = description
        self.timestamp = timestamp
        self.text = text
        self.context = context
    
    def to_dict(self):
        return {
            'priority': self.priority,
            'action': self.action,
            'description': self.description,
            'timestamp': self.timestamp,
            'text': self.text,
            'context': self.context
        }


class ProductionReport:
    """Complete production analysis report."""
    
    def __init__(self, project_id: int, audio_file_id: int,
                 overall_status: str, overall_score: float,
                 summary: Dict, repetition_analysis: List[Dict],
                 segment_quality: List[QualitySegment],
                 missing_sections: List[MissingSection],
                 editing_checklist: List[ChecklistItem],
                 statistics: Dict):
        self.project_id = project_id
        self.audio_file_id = audio_file_id
        self.overall_status = overall_status
        self.overall_score = overall_score
        self.summary = summary
        self.repetition_analysis = repetition_analysis
        self.segment_quality = segment_quality
        self.missing_sections = missing_sections
        self.editing_checklist = editing_checklist
        self.statistics = statistics
        self.created_at = datetime.now()
    
    def to_dict(self):
        return {
            'project_id': self.project_id,
            'audio_file_id': self.audio_file_id,
            'overall_status': self.overall_status,
            'overall_score': self.overall_score,
            'summary': self.summary,
            'repetition_analysis': self.repetition_analysis,
            'segment_quality': [s.to_dict() for s in self.segment_quality],
            'missing_sections': [ms.to_dict() for ms in self.missing_sections],
            'editing_checklist': [item.to_dict() for item in self.editing_checklist],
            'statistics': self.statistics,
            'created_at': self.created_at.isoformat()
        }


def format_timestamp(seconds: float) -> str:
    """
    Format timestamp in MM:SS or HH:MM:SS format.
    
    Args:
        seconds: Time in seconds
    
    Returns:
        Formatted timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def format_timestamp_range(start: float, end: float) -> str:
    """Format a timestamp range."""
    return f"{format_timestamp(start)} - {format_timestamp(end)}"


def generate_repetition_analysis(repetitions: List[Repetition]) -> List[Dict]:
    """
    Generate repetition analysis for the report.
    
    Args:
        repetitions: List of Repetition objects
    
    Returns:
        List of repetition analysis dictionaries
    """
    analysis = []
    
    for rep in repetitions:
        timestamps = []
        for i, occ in enumerate(rep.occurrences):
            timestamps.append({
                'attempt': i + 1,
                'start': format_timestamp(occ.start_time),
                'end': format_timestamp(occ.end_time),
                'duration': format_timestamp(occ.end_time - occ.start_time),
                'kept': i == rep.keeper_index
            })
        
        # Truncate text for preview
        text_preview = rep.text if len(rep.text) <= 100 else rep.text[:97] + '...'
        
        analysis.append({
            'text_preview': text_preview,
            'full_text': rep.text,
            'word_count': rep.length,
            'times_read': len(rep.occurrences),
            'total_time_spent': sum(occ.end_time - occ.start_time for occ in rep.occurrences),
            'wasted_time': sum(
                occ.end_time - occ.start_time 
                for i, occ in enumerate(rep.occurrences) 
                if i != rep.keeper_index
            ),
            'timestamps': timestamps
        })
    
    return analysis


def generate_checklist(segments: List[QualitySegment],
                       missing_sections: List[MissingSection],
                       repetitions: List[Repetition]) -> List[ChecklistItem]:
    """
    Generate prioritized editing checklist.
    
    Priority order:
    1. CRITICAL: Missing sections (must record)
    2. HIGH: Poor quality segments (should re-record)
    3. MEDIUM: Repeated sections to delete
    4. LOW: Fair quality segments (review and decide)
    
    Args:
        segments: List of QualitySegment objects
        missing_sections: List of MissingSection objects
        repetitions: List of Repetition objects
    
    Returns:
        Sorted list of ChecklistItem objects
    """
    checklist = []
    
    # 1. Missing sections (CRITICAL)
    for i, ms in enumerate(missing_sections, 1):
        checklist.append(ChecklistItem(
            priority='CRITICAL',
            action='RECORD',
            description=f'Record missing section #{i} ({ms.word_count} words, ~{ms.estimated_duration})',
            timestamp=ms.timestamp_context,
            text=ms.missing_text,
            context={
                'before': ms.context_before,
                'after': ms.context_after
            }
        ))
    
    # 2. Poor quality segments (HIGH)
    for seg in segments:
        if seg.status == 'needs_rerecording':
            checklist.append(ChecklistItem(
                priority='HIGH',
                action='RE-RECORD',
                description=f'Segment #{seg.segment_id} quality too low ({seg.quality_score:.1%}) - {seg.metrics["mismatches"]} errors',
                timestamp=format_timestamp_range(seg.start_time, seg.end_time) if seg.start_time else None,
                text=None,
                context={
                    'errors': len(seg.errors),
                    'missing_words': seg.metrics['missing_words'],
                    'mismatches': seg.metrics['mismatches']
                }
            ))
    
    # 3. Repetitions to remove (MEDIUM)
    for i, rep in enumerate(repetitions, 1):
        for attempt, occ in enumerate(rep.occurrences, 1):
            if attempt - 1 != rep.keeper_index:  # Not the keeper
                checklist.append(ChecklistItem(
                    priority='MEDIUM',
                    action='DELETE',
                    description=f'Delete failed take #{attempt} of {len(rep.occurrences)} (repetition #{i})',
                    timestamp=format_timestamp_range(occ.start_time, occ.end_time),
                    text=rep.text[:100] + '...' if len(rep.text) > 100 else rep.text,
                    context={
                        'keeper_attempt': rep.keeper_index + 1,
                        'total_attempts': len(rep.occurrences)
                    }
                ))
    
    # 4. Review segments (LOW)
    for seg in segments:
        if seg.status == 'needs_review':
            checklist.append(ChecklistItem(
                priority='LOW',
                action='REVIEW',
                description=f'Segment #{seg.segment_id} may need touch-ups ({seg.quality_score:.1%} quality)',
                timestamp=format_timestamp_range(seg.start_time, seg.end_time) if seg.start_time else None,
                text=None,
                context={
                    'errors': len(seg.errors),
                    'missing_words': seg.metrics['missing_words'],
                    'mismatches': seg.metrics['mismatches']
                }
            ))
    
    # 5. Minor edit segments (LOW)
    for seg in segments:
        if seg.status == 'needs_minor_edits' and len(seg.errors) > 0:
            checklist.append(ChecklistItem(
                priority='LOW',
                action='EDIT',
                description=f'Segment #{seg.segment_id} has {len(seg.errors)} minor errors ({seg.quality_score:.1%} quality)',
                timestamp=format_timestamp_range(seg.start_time, seg.end_time) if seg.start_time else None,
                text=None,
                context={
                    'errors': len(seg.errors)
                }
            ))
    
    # Sort by priority
    priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
    checklist.sort(key=lambda x: priority_order[x.priority])
    
    return checklist


def count_repeated_words(repetitions: List[Repetition]) -> int:
    """Count total number of words that were repeated (excluding keepers)."""
    total = 0
    for rep in repetitions:
        # Each repetition has length words, repeated (occurrences - 1) extra times
        total += rep.length * (len(rep.occurrences) - 1)
    return total


def generate_production_report(project_id: int,
                               audio_file_id: int,
                               pdf_text: str,
                               word_map: List[WordTimestamp],
                               repetitions: List[Repetition],
                               final_transcript: List[WordTimestamp],
                               alignment: List[AlignmentPoint],
                               segments: List[QualitySegment],
                               missing_sections: List[MissingSection]) -> ProductionReport:
    """
    Generate comprehensive production report.
    
    Args:
        project_id: Project ID
        audio_file_id: Audio file ID
        pdf_text: Original PDF text
        word_map: Full word map (all words including repetitions)
        repetitions: Detected repetitions
        final_transcript: Final transcript (excluding non-keeper repetitions)
        alignment: Word-by-word alignment
        segments: Quality segments
        missing_sections: Missing sections
    
    Returns:
        ProductionReport object
    """
    logger.info("Generating production report")
    
    # Calculate overall metrics
    overall_score = calculate_overall_quality(segments)
    overall_status = determine_overall_status(overall_score, len(missing_sections), segments)
    
    # Generate summary statistics
    summary = {
        'total_pdf_words': len(pdf_text.split()),
        'total_transcript_words': len(word_map),
        'total_final_words': len(final_transcript),
        'repetitions_found': len(repetitions),
        'total_repeated_words': count_repeated_words(repetitions),
        'missing_sections': len(missing_sections),
        'total_missing_words': sum(ms.word_count for ms in missing_sections),
        'completeness_percentage': calculate_completeness_percentage(alignment),
        'total_audiobook_duration': word_map[-1].end_time if word_map else 0,
        'production_ready_segments': sum(1 for s in segments if s.status == 'production_ready'),
        'segments_needing_work': sum(1 for s in segments if s.status != 'production_ready')
    }
    
    # Generate repetition analysis
    repetition_analysis = generate_repetition_analysis(repetitions)
    
    # Generate editing checklist
    editing_checklist = generate_checklist(segments, missing_sections, repetitions)
    
    # Additional statistics
    gap_stats = analyze_gap_distribution(missing_sections)
    
    statistics = {
        'alignment': {
            'exact_matches': sum(1 for a in alignment if a.match_type == 'exact'),
            'normalized_matches': sum(1 for a in alignment if a.match_type == 'normalized'),
            'phonetic_matches': sum(1 for a in alignment if a.match_type == 'phonetic'),
            'mismatches': sum(1 for a in alignment if a.match_type == 'mismatch'),
            'missing_words': sum(1 for a in alignment if a.match_type == 'missing'),
            'extra_words': sum(1 for a in alignment if a.match_type == 'extra')
        },
        'gaps': gap_stats,
        'time_analysis': {
            'total_recording_time': format_timestamp(word_map[-1].end_time if word_map else 0),
            'wasted_time_on_repetitions': format_timestamp(
                sum(
                    sum(
                        occ.end_time - occ.start_time 
                        for i, occ in enumerate(rep.occurrences) 
                        if i != rep.keeper_index
                    )
                    for rep in repetitions
                )
            )
        }
    }
    
    # Create report
    report = ProductionReport(
        project_id=project_id,
        audio_file_id=audio_file_id,
        overall_status=overall_status,
        overall_score=overall_score,
        summary=summary,
        repetition_analysis=repetition_analysis,
        segment_quality=segments,
        missing_sections=missing_sections,
        editing_checklist=editing_checklist,
        statistics=statistics
    )
    
    logger.info(f"Report generated - Status: {overall_status}, Score: {overall_score:.1%}")
    logger.info(f"Checklist has {len(editing_checklist)} items "
               f"({sum(1 for c in editing_checklist if c.priority == 'CRITICAL')} CRITICAL, "
               f"{sum(1 for c in editing_checklist if c.priority == 'HIGH')} HIGH)")
    
    return report
