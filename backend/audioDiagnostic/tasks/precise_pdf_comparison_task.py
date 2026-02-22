"""
Precise Word-by-Word PDF-to-Transcript Comparison with Timestamp Tracking

This algorithm provides detailed word-level comparison with exact timestamps for:
- Matched sections
- Abnormal sections (mismatches in transcript)  
- Missing sections (in PDF but not transcript)
- Extra sections (in transcript but not PDF)

Algorithm:
1. Word-by-word comparison of PDF vs Transcript
2. When mismatch occurs:
   - Stop on PDF position
   - Continue scanning transcript for next 3-word PDF match
   - If found: mark abnormal region from mismatch to re-match point
   - If not found: advance PDF by 3 words, try again from last match
3. Track all timestamps for abnormal regions using transcription segments
"""
import re
import logging
from celery import shared_task
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def precise_compare_transcription_to_pdf_task(self, audio_file_id, pdf_start_char=None, pdf_end_char=None, transcript_start_char=None, transcript_end_char=None):
    """
    Precise word-by-word comparison with timestamp tracking.
    
    Args:
        audio_file_id: AudioFile ID to compare
        pdf_start_char: Optional starting character position in PDF (for manual selection)
        pdf_end_char: Optional ending character position in PDF (for manual selection)
        transcript_start_char: Optional starting character position in transcript (to skip intro)
        transcript_end_char: Optional ending character position in transcript (to skip outro)
        
    Returns:
        Detailed comparison results with timestamps for all regions
    """
    task_id = self.request.id
    
    try:
        from ..models import AudioFile, TranscriptionSegment
        from ..utils import get_redis_connection
        from PyPDF2 import PdfReader
        
        r = get_redis_connection()
        r.set(f"progress:{task_id}", 5)
        
        # Get audio file and project
        audio_file = AudioFile.objects.select_related('project').get(id=audio_file_id)
        project = audio_file.project
        
        if not project.pdf_file:
            raise ValueError("No PDF file found for this project")
        
        if not audio_file.transcript_text:
            raise ValueError("Audio file has not been transcribed yet")
        
        logger.info(f"Starting precise PDF comparison for audio file {audio_file_id}")
        
        r.set(f"progress:{task_id}", 10)
        
        # Load PDF text
        if not project.pdf_text:
            logger.info("Extracting PDF text")
            reader = PdfReader(project.pdf_file.path)
            pdf_text = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
            project.pdf_text = pdf_text
            project.save(update_fields=['pdf_text'])
        else:
            pdf_text = project.pdf_text
        
        # Apply PDF region selection if provided
        if pdf_start_char is not None and pdf_end_char is not None:
            pdf_text = pdf_text[pdf_start_char:pdf_end_char]
            logger.info(f"Using manual PDF region: chars {pdf_start_char}-{pdf_end_char}")
        elif pdf_start_char is not None:
            pdf_text = pdf_text[pdf_start_char:]
            logger.info(f"Using PDF from char {pdf_start_char} to end")
        
        transcript = audio_file.transcript_text
        
        # Apply transcript region selection if provided
        if transcript_start_char is not None and transcript_end_char is not None:
            transcript = transcript[transcript_start_char:transcript_end_char]
            logger.info(f"Using manual transcript region: chars {transcript_start_char}-{transcript_end_char}")
        elif transcript_start_char is not None:
            transcript = transcript[transcript_start_char:]
            logger.info(f"Using transcript from char {transcript_start_char} to end")
        elif transcript_end_char is not None:
            transcript = transcript[:transcript_end_char]
            logger.info(f"Using transcript from start to char {transcript_end_char}")
        
        r.set(f"progress:{task_id}", 20)
        
        # Load all transcription segments with timestamps
        segments = list(
            TranscriptionSegment.objects
            .filter(audio_file=audio_file)
            .order_by('start_time')
            .values('id', 'text', 'start_time', 'end_time')
        )
        
        logger.info(f"Loaded {len(segments)} transcription segments")
        
        r.set(f"progress:{task_id}", 30)
        
        # Phase 1: Word-by-word comparison
        logger.info("Phase 1: Word-by-word comparison with 3-word lookahead")
        comparison_result = word_by_word_comparison(pdf_text, transcript, segments)
        
        r.set(f"progress:{task_id}", 80)
        
        # Phase 2: Calculate statistics
        logger.info("Phase 2: Calculating statistics")
        statistics = calculate_statistics(comparison_result)
        
        r.set(f"progress:{task_id}", 90)
        
        # Build final results
        final_results = {
            'algorithm': 'precise_word_by_word_v1',
            'pdf_region': {
                'start_char': pdf_start_char or 0,
                'end_char': pdf_end_char or len(project.pdf_text if project.pdf_text else pdf_text),
                'manually_selected': pdf_start_char is not None or pdf_end_char is not None
            },
            'transcript_region': {
                'start_char': transcript_start_char or 0,
                'end_char': transcript_end_char or len(audio_file.transcript_text),
                'manually_selected': transcript_start_char is not None or transcript_end_char is not None
            },
            'matched_regions': comparison_result['matched_regions'],
            'abnormal_regions': comparison_result['abnormal_regions'],
            'missing_content': comparison_result['missing_content'],
            'extra_content': comparison_result['extra_content'],
            'statistics': statistics,
            'summary': {
                'total_matched_words': comparison_result['stats']['matched_words'],
                'total_abnormal_words': comparison_result['stats']['abnormal_words'],
                'total_missing_words': comparison_result['stats']['missing_words'],
                'total_extra_words': comparison_result['stats']['extra_words'],
            }
        }
        
        # Save results
        audio_file.pdf_comparison_results = final_results
        audio_file.pdf_comparison_completed = True
        audio_file.save(update_fields=['pdf_comparison_results', 'pdf_comparison_completed'])
        
        r.set(f"progress:{task_id}", 100)
        
        logger.info(f"Precise PDF comparison completed for audio file {audio_file_id}")
        logger.info(f"Results: {statistics['accuracy_percentage']:.1f}% accuracy, "
                   f"{len(comparison_result['abnormal_regions'])} abnormal regions")
        
        return {
            'status': 'completed',
            'audio_file_id': audio_file_id,
            'comparison_results': final_results
        }
        
    except Exception as e:
        logger.error(f"Precise PDF comparison failed for audio file {audio_file_id}: {str(e)}")
        r = get_redis_connection()
        r.set(f"progress:{task_id}", -1)
        raise


def word_by_word_comparison(pdf_text, transcript, segments):
    """
    Perform precise word-by-word comparison with 3-word lookahead strategy.
    
    Algorithm:
    1. Normalize and tokenize both texts into words
    2. Match word-by-word, tracking timestamps
    3. On mismatch:
       - Stop PDF position
       - Scan forward in transcript for next 3 consecutive PDF words
       - If found: mark abnormal region, continue from there
       - If not found: try next 3 PDF words, repeat from last match
    4. Track all regions with timestamps
    """
    # Normalize and tokenize
    pdf_words = tokenize_text(pdf_text)
    transcript_words = tokenize_text(transcript)
    
    # Build word-to-segment mapping for timestamp lookup
    word_to_segment = build_word_segment_map(segments)
    
    # Initialize tracking
    matched_regions = []
    abnormal_regions = []
    missing_content = []
    extra_content = []
    
    pdf_idx = 0
    trans_idx = 0
    
    current_match_start_pdf = 0
    current_match_start_trans = 0
    current_match_end_pdf = 0
    current_match_end_trans = 0
    
    stats = {
        'matched_words': 0,
        'abnormal_words': 0,
        'missing_words': 0,
        'extra_words': 0
    }
    
    LOOKAHEAD_WORDS = 3
    MAX_ADVANCE_ATTEMPTS = 10
    MAX_TRANSCRIPT_SCAN = 1000  # Don't scan more than 1000 words ahead
    
    logger.info(f"Starting comparison: {len(pdf_words)} PDF words, {len(transcript_words)} transcript words")
    
    while pdf_idx < len(pdf_words) and trans_idx < len(transcript_words):
        # Check if current words match
        if words_match(pdf_words[pdf_idx], transcript_words[trans_idx]):
            # Words match - continue tracking
            pdf_idx += 1
            trans_idx += 1
            stats['matched_words'] += 1
            current_match_end_pdf = pdf_idx
            current_match_end_trans = trans_idx
            
        else:
            # Mismatch detected
            logger.debug(f"Mismatch at PDF:{pdf_idx} ('{pdf_words[pdf_idx]}') vs Trans:{trans_idx} ('{transcript_words[trans_idx]}')")
            
            # Save current matched region if any
            if current_match_start_pdf < pdf_idx:
                matched_region = save_matched_region(
                    pdf_words[current_match_start_pdf:pdf_idx],
                    transcript_words[current_match_start_trans:trans_idx],
                    word_to_segment,
                    current_match_start_trans
                )
                if matched_region:
                    matched_regions.append(matched_region)
            
            # Strategy: Look ahead for next 3 PDF words in transcript
            found_match = False
            abnormal_start_trans = trans_idx
            
            # Get next 3 words from PDF for lookahead
            if pdf_idx + LOOKAHEAD_WORDS <= len(pdf_words):
                pdf_lookahead = pdf_words[pdf_idx:pdf_idx + LOOKAHEAD_WORDS]
                
                # Search in transcript for this 3-word sequence
                scan_limit = min(trans_idx + MAX_TRANSCRIPT_SCAN, len(transcript_words) - LOOKAHEAD_WORDS)
                
                for scan_pos in range(trans_idx, scan_limit):
                    if match_sequence(pdf_lookahead, transcript_words[scan_pos:scan_pos + LOOKAHEAD_WORDS]):
                        # Found match! Mark abnormal region
                        logger.debug(f"Found match after scanning: PDF at {pdf_idx}, Trans jumped {scan_pos - trans_idx} words")
                        
                        abnormal_region = save_abnormal_region(
                            transcript_words[abnormal_start_trans:scan_pos],
                            word_to_segment,
                            abnormal_start_trans,
                            reason='mismatch_with_recovery'
                        )
                        if abnormal_region:
                            abnormal_regions.append(abnormal_region)
                            stats['abnormal_words'] += (scan_pos - abnormal_start_trans)
                        
                        # Resume from match point
                        trans_idx = scan_pos
                        current_match_start_pdf = pdf_idx
                        current_match_start_trans = trans_idx
                        found_match = True
                        break
            
            if not found_match:
                # No match found in transcript - try advancing PDF
                logger.debug(f"No match found, advancing PDF")
                advance_attempts = 0
                advanced = False
                
                while advance_attempts < MAX_ADVANCE_ATTEMPTS and pdf_idx + LOOKAHEAD_WORDS <= len(pdf_words):
                    pdf_idx += 1
                    advance_attempts += 1
                    
                    # Try again with new PDF position
                    pdf_lookahead = pdf_words[pdf_idx:pdf_idx + LOOKAHEAD_WORDS]
                    scan_limit = min(abnormal_start_trans + MAX_TRANSCRIPT_SCAN, len(transcript_words) - LOOKAHEAD_WORDS)
                    
                    for scan_pos in range(abnormal_start_trans, scan_limit):
                        if match_sequence(pdf_lookahead, transcript_words[scan_pos:scan_pos + LOOKAHEAD_WORDS]):
                            logger.debug(f"Match found after advancing PDF by {advance_attempts} words")
                            
                            # Mark missing content in PDF that was skipped
                            if pdf_idx > current_match_end_pdf:
                                missing_region = {
                                    'text': ' '.join(pdf_words[current_match_end_pdf:pdf_idx]),
                                    'word_count': pdf_idx - current_match_end_pdf,
                                    'pdf_position': f'word {current_match_end_pdf}-{pdf_idx}'
                                }
                                missing_content.append(missing_region)
                                stats['missing_words'] += pdf_idx - current_match_end_pdf
                            
                            # Mark abnormal in transcript
                            abnormal_region = save_abnormal_region(
                                transcript_words[abnormal_start_trans:scan_pos],
                                word_to_segment,
                                abnormal_start_trans,
                                reason='pdf_section_skipped'
                            )
                            if abnormal_region:
                                abnormal_regions.append(abnormal_region)
                                stats['abnormal_words'] += (scan_pos - abnormal_start_trans)
                            
                            trans_idx = scan_pos
                            current_match_start_pdf = pdf_idx
                            current_match_start_trans = trans_idx
                            advanced = True
                            break
                    
                    if advanced:
                        break
                
                if not advanced:
                    # Couldn't find match - mark as extra content and advance transcript
                    logger.debug(f"No match found after {MAX_ADVANCE_ATTEMPTS} PDF advances, marking as extra")
                    extra_region = save_abnormal_region(
                        transcript_words[abnormal_start_trans:abnormal_start_trans + 10],
                        word_to_segment,
                        abnormal_start_trans,
                        reason='no_pdf_match_found'
                    )
                    if extra_region:
                        extra_content.append(extra_region)
                        stats['extra_words'] += 10
                    
                    trans_idx = abnormal_start_trans + 10
                    current_match_start_trans = trans_idx
    
    # Handle remaining content
    if current_match_start_pdf < pdf_idx:
        matched_region = save_matched_region(
            pdf_words[current_match_start_pdf:pdf_idx],
            transcript_words[current_match_start_trans:trans_idx],
            word_to_segment,
            current_match_start_trans
        )
        if matched_region:
            matched_regions.append(matched_region)
    
    # Remaining PDF = missing
    if pdf_idx < len(pdf_words):
        missing_content.append({
            'text': ' '.join(pdf_words[pdf_idx:]),
            'word_count': len(pdf_words) - pdf_idx,
            'pdf_position': f'word {pdf_idx} to end'
        })
        stats['missing_words'] += len(pdf_words) - pdf_idx
    
    # Remaining transcript = extra
    if trans_idx < len(transcript_words):
        extra_region = save_abnormal_region(
            transcript_words[trans_idx:],
            word_to_segment,
            trans_idx,
            reason='end_of_pdf_extra_content'
        )
        if extra_region:
            extra_content.append(extra_region)
            stats['extra_words'] += len(transcript_words) - trans_idx
    
    logger.info(f"Comparison complete: {len(matched_regions)} matched, {len(abnormal_regions)} abnormal, "
               f"{len(missing_content)} missing, {len(extra_content)} extra")
    
    return {
        'matched_regions': matched_regions,
        'abnormal_regions': abnormal_regions,
        'missing_content': missing_content,
        'extra_content': extra_content,
        'stats': stats
    }


def tokenize_text(text):
    """Convert text to normalized word tokens."""
    # Remove extra whitespace, normalize
    text = re.sub(r'\s+', ' ', text.strip())
    # Split into words, keeping punctuation attached
    words = text.split()
    return [w.strip() for w in words if w.strip()]


def normalize_word(word):
    """Normalize word for comparison (remove punctuation, lowercase)."""
    return re.sub(r'[^\w]', '', word.lower())


def words_match(word1, word2):
    """Check if two words match (fuzzy matching for minor differences)."""
    norm1 = normalize_word(word1)
    norm2 = normalize_word(word2)
    
    if norm1 == norm2:
        return True
    
    # Allow very similar words (>90% similarity)
    if len(norm1) > 3 and len(norm2) > 3:
        ratio = SequenceMatcher(None, norm1, norm2).ratio()
        return ratio >= 0.9
    
    return False


def match_sequence(seq1, seq2):
    """Check if two word sequences match."""
    if len(seq1) != len(seq2):
        return False
    return all(words_match(w1, w2) for w1, w2 in zip(seq1, seq2))


def build_word_segment_map(segments):
    """Build mapping from word position to segment with timestamps."""
    word_map = {}
    word_idx = 0
    
    for segment in segments:
        words = tokenize_text(segment['text'])
        for _ in words:
            word_map[word_idx] = segment
            word_idx += 1
    
    return word_map


def save_matched_region(pdf_words, trans_words, word_to_segment, start_trans_idx):
    """Save a matched region with timestamps."""
    if not trans_words:
        return None
    
    # Get timestamps from first and last words
    start_seg = word_to_segment.get(start_trans_idx)
    end_seg = word_to_segment.get(start_trans_idx + len(trans_words) - 1)
    
    return {
        'text': ' '.join(trans_words[:50]),  # First 50 words for preview
        'full_text': ' '.join(trans_words),
        'word_count': len(trans_words),
        'start_time': start_seg['start_time'] if start_seg else None,
        'end_time': end_seg['end_time'] if end_seg else None,
        'segments': get_segment_ids(word_to_segment, start_trans_idx, len(trans_words))
    }


def save_abnormal_region(trans_words, word_to_segment, start_trans_idx, reason=''):
    """Save an abnormal region (mismatch) with timestamps."""
    if not trans_words:
        return None
    
    start_seg = word_to_segment.get(start_trans_idx)
    end_seg = word_to_segment.get(start_trans_idx + len(trans_words) - 1)
    
    return {
        'text': ' '.join(trans_words),
        'word_count': len(trans_words),
        'start_time': start_seg['start_time'] if start_seg else None,
        'end_time': end_seg['end_time'] if end_seg else None,
        'reason': reason,
        'segments': get_segment_ids(word_to_segment, start_trans_idx, len(trans_words))
    }


def get_segment_ids(word_to_segment, start_idx, count):
    """Get list of segment IDs for a word range."""
    segment_ids = set()
    for i in range(start_idx, start_idx + count):
        seg = word_to_segment.get(i)
        if seg:
            segment_ids.add(seg['id'])
    return list(segment_ids)


def calculate_statistics(comparison_result):
    """Calculate detailed statistics from comparison results."""
    stats = comparison_result['stats']
    
    total_words = (stats['matched_words'] + stats['abnormal_words'] + 
                   stats['extra_words'])
    
    if total_words == 0:
        accuracy = 0.0
    else:
        accuracy = (stats['matched_words'] / total_words) * 100
    
    # Determine quality
    if accuracy >= 95:
        quality = 'excellent'
    elif accuracy >= 85:
        quality = 'good'
    elif accuracy >= 70:
        quality = 'fair'
    else:
        quality = 'poor'
    
    return {
        'total_transcript_words': total_words,
        'matched_words': stats['matched_words'],
        'abnormal_words': stats['abnormal_words'],
        'missing_words': stats['missing_words'],
        'extra_words': stats['extra_words'],
        'accuracy_percentage': round(accuracy, 2),
        'match_quality': quality,
        'matched_regions_count': len(comparison_result['matched_regions']),
        'abnormal_regions_count': len(comparison_result['abnormal_regions']),
        'missing_sections_count': len(comparison_result['missing_content']),
        'extra_sections_count': len(comparison_result['extra_content'])
    }
