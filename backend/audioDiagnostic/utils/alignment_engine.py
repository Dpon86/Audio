"""
Word-Level Alignment Engine for Audiobook Production Analysis

Uses dynamic programming (Needleman-Wunsch algorithm) to align
PDF text with audio transcript at the word level.
"""

import logging
from typing import List, Dict, Optional, Tuple
from .text_normalizer import normalize_word, calculate_word_similarity, tokenize_words
from .repetition_detector import WordTimestamp

logger = logging.getLogger(__name__)


class AlignmentPoint:
    """Represents one aligned position between PDF and transcript."""
    
    def __init__(self, pdf_word: Optional[str] = None, pdf_index: Optional[int] = None,
                 transcript_word: Optional[str] = None, transcript_index: Optional[int] = None,
                 match_type: str = 'exact', match_score: float = 0.0,
                 timestamp: Optional[Dict] = None):
        self.pdf_word = pdf_word
        self.pdf_index = pdf_index
        self.transcript_word = transcript_word
        self.transcript_index = transcript_index
        self.match_type = match_type  # exact, normalized, phonetic, mismatch, missing, extra
        self.match_score = match_score
        self.timestamp = timestamp  # {'start': float, 'end': float}
    
    def to_dict(self):
        return {
            'pdf_word': self.pdf_word,
            'pdf_index': self.pdf_index,
            'transcript_word': self.transcript_word,
            'transcript_index': self.transcript_index,
            'match_type': self.match_type,
            'match_score': self.match_score,
            'timestamp': self.timestamp
        }


def determine_match_type(pdf_word: str, transcript_word: str, similarity: float) -> str:
    """
    Determine the type of match between two words.
    
    Returns:
        'exact': Exact match
        'normalized': Match after normalization (case, punctuation)
        'phonetic': Phonetically similar
        'mismatch': No match
    """
    if pdf_word == transcript_word:
        return 'exact'
    
    # Normalize both
    norm_pdf = normalize_word(pdf_word)
    norm_transcript = normalize_word(transcript_word)
    
    if norm_pdf == norm_transcript:
        return 'normalized'
    
    if similarity >= 0.7:
        return 'phonetic'
    
    return 'mismatch'


def create_alignment_matrix(pdf_words: List[str], 
                           transcript_words: List[WordTimestamp],
                           match_score: float = 2.0,
                           mismatch_penalty: float = -1.0,
                           gap_penalty: float = -2.0) -> List[List[float]]:
    """
    Create dynamic programming matrix for alignment.
    
    Uses Needleman-Wunsch algorithm for global sequence alignment.
    
    Args:
        pdf_words: List of words from PDF
        transcript_words: List of WordTimestamp objects
        match_score: Score for matching words
        mismatch_penalty: Penalty for mismatched words
        gap_penalty: Penalty for gaps (insertions/deletions)
    
    Returns:
        2D matrix of alignment scores
    """
    m = len(pdf_words)
    n = len(transcript_words)
    
    logger.info(f"Creating alignment matrix: {m} x {n} = {m*n:,} cells")
    
    # Initialize matrix
    dp = [[0.0 for _ in range(n + 1)] for _ in range(m + 1)]
    
    # Initialize first row and column (gaps)
    for i in range(1, m + 1):
        dp[i][0] = i * gap_penalty
    
    for j in range(1, n + 1):
        dp[0][j] = j * gap_penalty
    
    # Fill matrix with progress logging
    progress_interval = max(1, m // 10)  # Log every 10%
    
    for i in range(1, m + 1):
        if i % progress_interval == 0:
            percent = (i / m) * 100
            logger.info(f"Matrix progress: {percent:.0f}% ({i}/{m} rows)")
        
        for j in range(1, n + 1):
            pdf_word = pdf_words[i - 1]
            trans_word = transcript_words[j - 1].word
            
            # Calculate similarity
            similarity = calculate_word_similarity(pdf_word, trans_word)
            
            # Score for match/mismatch
            if similarity >= 0.85:
                align_score = match_score * similarity
            else:
                align_score = mismatch_penalty
            
            # Calculate scores for three possibilities
            match = dp[i - 1][j - 1] + align_score  # Match or mismatch
            delete = dp[i - 1][j] + gap_penalty     # Gap in transcript
            insert = dp[i][j - 1] + gap_penalty     # Gap in PDF
            
            # Take maximum
            dp[i][j] = max(match, delete, insert)
    
    return dp


def backtrack_alignment(dp: List[List[float]], 
                        pdf_words: List[str],
                        transcript_words: List[WordTimestamp],
                        gap_penalty: float = -2.0) -> List[AlignmentPoint]:
    """
    Backtrack through DP matrix to reconstruct optimal alignment.
    
    Args:
        dp: DP matrix from create_alignment_matrix
        pdf_words: List of PDF words
        transcript_words: List of WordTimestamp objects
        gap_penalty: Gap penalty used in DP matrix
    
    Returns:
        List of AlignmentPoint objects (in forward order)
    """
    alignment = []
    
    i = len(pdf_words)
    j = len(transcript_words)
    
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            pdf_word = pdf_words[i - 1]
            trans_word = transcript_words[j - 1].word
            
            # Calculate what move was made
            similarity = calculate_word_similarity(pdf_word, trans_word)
            
            if similarity >= 0.85:
                align_score = 2.0 * similarity
            else:
                align_score = -1.0
            
            # Check which direction we came from
            from_match = dp[i - 1][j - 1] + align_score
            from_delete = dp[i - 1][j] + gap_penalty
            from_insert = dp[i][j - 1] + gap_penalty
            
            current_score = dp[i][j]
            
            # Determine which move was taken (with small tolerance for floating point)
            if abs(current_score - from_match) < 0.001:
                # Match or mismatch
                match_type = determine_match_type(pdf_word, trans_word, similarity)
                
                alignment.append(AlignmentPoint(
                    pdf_word=pdf_word,
                    pdf_index=i - 1,
                    transcript_word=transcript_words[j - 1].original,
                    transcript_index=j - 1,
                    match_type=match_type,
                    match_score=similarity,
                    timestamp={
                        'start': transcript_words[j - 1].start_time,
                        'end': transcript_words[j - 1].end_time
                    }
                ))
                i -= 1
                j -= 1
            elif abs(current_score - from_delete) < 0.001:
                # Gap in transcript (missing word)
                alignment.append(AlignmentPoint(
                    pdf_word=pdf_word,
                    pdf_index=i - 1,
                    transcript_word=None,
                    transcript_index=None,
                    match_type='missing',
                    match_score=0.0,
                    timestamp=None
                ))
                i -= 1
            else:
                # Gap in PDF (extra word in transcript)
                alignment.append(AlignmentPoint(
                    pdf_word=None,
                    pdf_index=None,
                    transcript_word=transcript_words[j - 1].original,
                    transcript_index=j - 1,
                    match_type='extra',
                    match_score=0.0,
                    timestamp={
                        'start': transcript_words[j - 1].start_time,
                        'end': transcript_words[j - 1].end_time
                    }
                ))
                j -= 1
        elif i > 0:
            # Remaining PDF words (all missing from transcript)
            alignment.append(AlignmentPoint(
                pdf_word=pdf_words[i - 1],
                pdf_index=i - 1,
                transcript_word=None,
                transcript_index=None,
                match_type='missing',
                match_score=0.0,
                timestamp=None
            ))
            i -= 1
        else:
            # Remaining transcript words (all extra)
            alignment.append(AlignmentPoint(
                pdf_word=None,
                pdf_index=None,
                transcript_word=transcript_words[j - 1].original,
                transcript_index=j - 1,
                match_type='extra',
                match_score=0.0,
                timestamp={
                    'start': transcript_words[j - 1].start_time,
                    'end': transcript_words[j - 1].end_time
                }
            ))
            j -= 1
    
    # Reverse to get forward order
    return list(reversed(alignment))


def find_transcript_location_in_pdf(pdf_words: List[str], 
                                    transcript_words: List[WordTimestamp],
                                    window_size: int = 100) -> Optional[Tuple[int, int]]:
    """
    Find where the transcript appears in the PDF using a sliding window.
    
    Returns (start_index, end_index) or None if not found.
    """
    if len(transcript_words) < 10:
        return None
    
    # Use first 50 words of transcript as search pattern
    search_words = [w.word for w in transcript_words[:min(50, len(transcript_words))]]
    best_score = 0
    best_position = None
    
    logger.info(f"Searching for transcript location in PDF (window size: {window_size})")
    
    # Slide window through PDF
    for i in range(0, len(pdf_words) - len(search_words), window_size):
        window = pdf_words[i:i + len(search_words)]
        
        # Calculate match score
        matches = sum(1 for j in range(len(search_words)) 
                     if j < len(window) and calculate_word_similarity(search_words[j], window[j]) > 0.85)
        
        score = matches / len(search_words)
        
        if score > best_score:
            best_score = score
            best_position = i
        
        # If we found a very good match, stop searching
        if score > 0.7:
            break
    
    if best_position is not None and best_score > 0.4:
        # Estimate end position
        end_position = min(best_position + len(transcript_words) + 500, len(pdf_words))
        logger.info(f"Found transcript at PDF position {best_position}-{end_position} (score: {best_score:.2%})")
        return (best_position, end_position)
    
    logger.warning(f"Could not locate transcript in PDF (best score: {best_score:.2%})")
    return None


def align_transcript_to_pdf(pdf_text: str, 
                            transcript_words: List[WordTimestamp]) -> List[AlignmentPoint]:
    """
    Main function to align transcript with PDF text.
    
    Args:
        pdf_text: Cleaned PDF text
        transcript_words: List of WordTimestamp objects (final transcript, no repetitions)
    
    Returns:
        List of AlignmentPoint objects
    """
    logger.info("Starting PDF-transcript alignment")
    
    # Tokenize PDF text
    pdf_words = tokenize_words(pdf_text, normalize=True)
    
    logger.info(f"Aligning {len(pdf_words)} PDF words with {len(transcript_words)} transcript words")
    
    # Check if size mismatch is large (transcript much smaller than PDF)
    size_ratio = len(pdf_words) / len(transcript_words) if len(transcript_words) > 0 else float('inf')
    
    if size_ratio > 10:
        logger.warning(f"Large size mismatch: PDF has {len(pdf_words)} words but transcript has {len(transcript_words)} words (ratio: {size_ratio:.1f}:1)")
        logger.info("Using windowed alignment to locate transcript in PDF")
        
        # Try to find where transcript appears in PDF
        location = find_transcript_location_in_pdf(pdf_words, transcript_words)
        
        if location:
            start_idx, end_idx = location
            # Only align the relevant section of the PDF
            pdf_words_subset = pdf_words[start_idx:end_idx]
            logger.info(f"Aligning transcript against PDF subset: {len(pdf_words_subset)} words (positions {start_idx}-{end_idx})")
            
            # Create DP matrix for subset
            dp = create_alignment_matrix(pdf_words_subset, transcript_words)
            alignment = backtrack_alignment(dp, pdf_words_subset, transcript_words)
            
            # Adjust PDF indices to account for subset
            for point in alignment:
                if point.pdf_index is not None:
                    point.pdf_index += start_idx
        else:
            logger.warning("Could not locate transcript in PDF - performing full alignment (this may be slow)")
            # Fall back to full alignment
            dp = create_alignment_matrix(pdf_words, transcript_words)
            alignment = backtrack_alignment(dp, pdf_words, transcript_words)
    else:
        # Normal case - sizes are similar
        # Create DP matrix
        dp = create_alignment_matrix(pdf_words, transcript_words)
        
        # Backtrack to get alignment
        alignment = backtrack_alignment(dp, pdf_words, transcript_words)
    
    logger.info(f"Alignment complete: {len(alignment)} alignment points")
    
    # Log alignment statistics
    exact = sum(1 for a in alignment if a.match_type == 'exact')
    normalized = sum(1 for a in alignment if a.match_type == 'normalized')
    phonetic = sum(1 for a in alignment if a.match_type == 'phonetic')
    mismatch = sum(1 for a in alignment if a.match_type == 'mismatch')
    missing = sum(1 for a in alignment if a.match_type == 'missing')
    extra = sum(1 for a in alignment if a.match_type == 'extra')
    
    logger.info(f"Alignment stats - Exact: {exact}, Normalized: {normalized}, "
                f"Phonetic: {phonetic}, Mismatch: {mismatch}, "
                f"Missing: {missing}, Extra: {extra}")
    
    return alignment


def get_context_words(alignment: List[AlignmentPoint], 
                      index: int, 
                      context_size: int = 10,
                      use_pdf: bool = True) -> str:
    """
    Get context words around a specific alignment point.
    
    Args:
        alignment: List of alignment points
        index: Index in alignment to get context for
        context_size: Number of words before/after
        use_pdf: If True, use PDF words; otherwise use transcript words
    
    Returns:
        Context string
    """
    start_idx = max(0, index - context_size)
    end_idx = min(len(alignment), index + context_size + 1)
    
    words = []
    for i in range(start_idx, end_idx):
        if use_pdf and alignment[i].pdf_word:
            words.append(alignment[i].pdf_word)
        elif not use_pdf and alignment[i].transcript_word:
            words.append(alignment[i].transcript_word)
    
    return ' '.join(words)


def estimate_reading_time(word_count: int, words_per_minute: int = 150) -> str:
    """
    Estimate how long it would take to read a section.
    
    Args:
        word_count: Number of words
        words_per_minute: Average reading speed
    
    Returns:
        Time estimate string (e.g., "1:30")
    """
    minutes = word_count / words_per_minute
    total_seconds = int(minutes * 60)
    
    mins = total_seconds // 60
    secs = total_seconds % 60
    
    return f"{mins}:{secs:02d}"
