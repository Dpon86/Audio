"""
Repetition Detection for Audiobook Production Analysis

Detects sections that have been read multiple times and identifies
which occurrence to keep (always the last read).
"""

import logging
from typing import List, Dict, Set, Tuple
from .text_normalizer import normalize_text, get_ngrams, tokenize_words

logger = logging.getLogger(__name__)


class WordTimestamp:
    """Represents a word with its timestamp information."""
    
    def __init__(self, word: str, original: str, start_time: float, end_time: float, 
                 segment_id: int, index: int):
        self.word = word  # Normalized word
        self.original = original  # Original word from transcript
        self.start_time = start_time
        self.end_time = end_time
        self.segment_id = segment_id
        self.index = index  # Global position in transcript
        self.excluded = False  # Will be True if part of non-keeper repetition
    
    def to_dict(self):
        return {
            'word': self.word,
            'original': self.original,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'segment_id': self.segment_id,
            'index': self.index,
            'excluded': self.excluded
        }


class Occurrence:
    """Represents one occurrence of a repeated section."""
    
    def __init__(self, start_idx: int, end_idx: int, start_time: float, end_time: float):
        self.start_idx = start_idx
        self.end_idx = end_idx
        self.start_time = start_time
        self.end_time = end_time
        self.keep = False  # Will be True for the last occurrence
    
    def to_dict(self):
        return {
            'start_idx': self.start_idx,
            'end_idx': self.end_idx,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'keep': self.keep
        }


class Repetition:
    """Represents a section that was read multiple times."""
    
    def __init__(self, text: str, length: int, occurrences: List[Occurrence]):
        self.text = text
        self.length = length  # Number of words
        self.occurrences = occurrences
        self.keeper_index = len(occurrences) - 1  # Last occurrence is the keeper
        
        # Mark the keeper
        if occurrences:
            occurrences[self.keeper_index].keep = True
    
    def to_dict(self):
        return {
            'text': self.text,
            'length': self.length,
            'occurrences': [occ.to_dict() for occ in self.occurrences],
            'keeper_index': self.keeper_index
        }


def build_word_map(transcription_segments) -> List[WordTimestamp]:
    """
    Build a word-level map with timestamps from transcription segments.
    
    Args:
        transcription_segments: QuerySet or list of TranscriptionSegment objects
    
    Returns:
        List of WordTimestamp objects
    """
    word_map = []
    global_index = 0
    
    for segment in transcription_segments:
        words = segment.text.split()
        if not words:
            continue
        
        duration = segment.end_time - segment.start_time
        time_per_word = duration / len(words) if len(words) > 0 else 0
        
        for i, word in enumerate(words):
            # Estimate word-level timestamps
            word_start = segment.start_time + (i * time_per_word)
            word_end = segment.start_time + ((i + 1) * time_per_word)
            
            # Normalize word for comparison
            normalized = normalize_text(word, expand_contractions_flag=True, 
                                       remove_punctuation_flag=True, lowercase=True)
            
            word_map.append(WordTimestamp(
                word=normalized,
                original=word,
                start_time=word_start,
                end_time=word_end,
                segment_id=segment.id,
                index=global_index
            ))
            global_index += 1
    
    logger.info(f"Built word map with {len(word_map)} words")
    return word_map


def build_word_map_from_text(transcript_text: str) -> List[WordTimestamp]:
    """
    Build a word-level map from plain text (no timestamps).
    
    This is used when transcription is stored as plain text instead of segments.
    Since we don't have timing information, all timestamps are set to 0.
    
    Args:
        transcript_text: Plain text transcription
    
    Returns:
        List of WordTimestamp objects (with zero timestamps)
    """
    word_map = []
    words = transcript_text.split()
    
    for index, word in enumerate(words):
        # Normalize word for comparison
        normalized = normalize_text(word, expand_contractions_flag=True, 
                                   remove_punctuation_flag=True, lowercase=True)
        
        word_map.append(WordTimestamp(
            word=normalized,
            original=word,
            start_time=0.0,  # No timing info available
            end_time=0.0,    # No timing info available
            segment_id=0,    # No segment available
            index=index
        ))
    
    logger.info(f"Built word map from text with {len(word_map)} words (no timestamps)")
    return word_map


def find_repeated_sequences(word_map: List[WordTimestamp], 
                           min_length: int = 5,
                           max_length: int = 50,
                           similarity_threshold: float = 0.85) -> List[Repetition]:
    """
    Find sequences of words that appear multiple times in the transcript.
    
    Args:
        word_map: List of WordTimestamp objects
        min_length: Minimum number of words in a repeated sequence
        max_length: Maximum number of words in a repeated sequence
        similarity_threshold: How similar sequences must be (0.0-1.0)
    
    Returns:
        List of Repetition objects
    """
    logger.info(f"Searching for repeated sequences (length {min_length}-{max_length})")
    
    # Extract normalized words for efficient searching
    words = [w.word for w in word_map]
    
    repetitions = []
    
    # Try different n-gram lengths, starting with longer ones
    # (longer matches are more significant)
    for n in range(max_length, min_length - 1, -1):
        logger.debug(f"Checking {n}-grams...")
        
        # Find all n-grams and their positions
        ngram_positions = {}
        
        for i in range(len(words) - n + 1):
            # Get the n-gram text
            ngram = ' '.join(words[i:i+n])
            
            if ngram not in ngram_positions:
                ngram_positions[ngram] = []
            
            ngram_positions[ngram].append(i)
        
        # Find n-grams that appear multiple times
        for ngram, positions in ngram_positions.items():
            if len(positions) >= 2:
                # Check if these positions are far enough apart
                # (avoid detecting overlapping matches)
                valid_positions = filter_overlapping_positions(positions, n)
                
                if len(valid_positions) >= 2:
                    # Create Occurrence objects
                    occurrences = []
                    for start_pos in valid_positions:
                        end_pos = start_pos + n - 1
                        
                        occurrences.append(Occurrence(
                            start_idx=start_pos,
                            end_idx=end_pos,
                            start_time=word_map[start_pos].start_time,
                            end_time=word_map[end_pos].end_time
                        ))
                    
                    # Create Repetition object
                    # Use original words for display text
                    original_text = ' '.join(
                        word_map[i].original 
                        for i in range(valid_positions[0], valid_positions[0] + n)
                    )
                    
                    repetitions.append(Repetition(
                        text=original_text,
                        length=n,
                        occurrences=occurrences
                    ))
    
    # Merge overlapping repetitions (keep longer ones)
    repetitions = merge_overlapping_repetitions(repetitions)
    
    logger.info(f"Found {len(repetitions)} repeated sequences")
    
    return repetitions


def filter_overlapping_positions(positions: List[int], length: int) -> List[int]:
    """
    Filter out positions that would create overlapping matches.
    
    Args:
        positions: List of start positions
        length: Length of the sequence
    
    Returns:
        Filtered list of positions with no overlaps
    """
    if len(positions) <= 1:
        return positions
    
    # Sort positions
    sorted_positions = sorted(positions)
    
    # Keep positions that are at least 'length' apart
    filtered = [sorted_positions[0]]
    
    for pos in sorted_positions[1:]:
        if pos >= filtered[-1] + length:
            filtered.append(pos)
    
    # If we filtered out too many, relax the constraint
    # (allow some overlap if it means we catch more repetitions)
    if len(filtered) < 2 and len(sorted_positions) >= 2:
        # Use a more relaxed constraint (50% overlap allowed)
        filtered = [sorted_positions[0]]
        for pos in sorted_positions[1:]:
            if pos >= filtered[-1] + (length // 2):
                filtered.append(pos)
    
    return filtered


def merge_overlapping_repetitions(repetitions: List[Repetition]) -> List[Repetition]:
    """
    Merge overlapping repetitions, keeping the longer ones.
    
    If two repetitions overlap significantly, keep only the longer one.
    """
    if len(repetitions) <= 1:
        return repetitions
    
    # Sort by length (longest first)
    sorted_reps = sorted(repetitions, key=lambda r: r.length, reverse=True)
    
    merged = []
    used_ranges = set()
    
    for rep in sorted_reps:
        # Check if this repetition overlaps significantly with any we've already kept
        overlaps = False
        
        for occ in rep.occurrences:
            range_key = (occ.start_idx, occ.end_idx)
            
            # Check if this range overlaps with any already-used range
            for used_start, used_end in used_ranges:
                overlap_start = max(occ.start_idx, used_start)
                overlap_end = min(occ.end_idx, used_end)
                
                if overlap_start <= overlap_end:
                    # There is overlap
                    overlap_length = overlap_end - overlap_start + 1
                    this_length = occ.end_idx - occ.start_idx + 1
                    
                    # If more than 50% overlap, consider it a duplicate
                    if overlap_length > this_length * 0.5:
                        overlaps = True
                        break
            
            if overlaps:
                break
        
        if not overlaps:
            # This is a new, non-overlapping repetition
            merged.append(rep)
            
            # Mark its ranges as used
            for occ in rep.occurrences:
                used_ranges.add((occ.start_idx, occ.end_idx))
    
    return merged


def mark_excluded_words(word_map: List[WordTimestamp], 
                        repetitions: List[Repetition]) -> None:
    """
    Mark words that should be excluded (non-keeper repetitions).
    
    Modifies word_map in place.
    
    Args:
        word_map: List of WordTimestamp objects
        repetitions: List of Repetition objects
    """
    for rep in repetitions:
        for i, occ in enumerate(rep.occurrences):
            if i != rep.keeper_index:  # Not the keeper
                # Mark these words as excluded
                for idx in range(occ.start_idx, occ.end_idx + 1):
                    if idx < len(word_map):
                        word_map[idx].excluded = True
    
    excluded_count = sum(1 for w in word_map if w.excluded)
    logger.info(f"Marked {excluded_count} words as excluded (non-keeper repetitions)")


def build_final_transcript(word_map: List[WordTimestamp]) -> List[WordTimestamp]:
    """
    Build the final transcript excluding non-keeper repetitions.
    
    Args:
        word_map: List of WordTimestamp objects (with excluded flags set)
    
    Returns:
        Filtered list of WordTimestamp objects (only keepers)
    """
    final = [w for w in word_map if not w.excluded]
    
    logger.info(f"Final transcript has {len(final)} words (removed {len(word_map) - len(final)} repeated words)")
    
    return final


def detect_repetitions(transcription_segments,
                       min_length: int = 5,
                       max_length: int = 50) -> Tuple[List[WordTimestamp], List[Repetition], List[WordTimestamp]]:
    """
    Main function to detect repetitions in transcription.
    
    Args:
        transcription_segments: QuerySet or list of TranscriptionSegment objects
        min_length: Minimum number of words in a repeated sequence
        max_length: Maximum number of words in a repeated sequence
    
    Returns:
        Tuple of (word_map, repetitions, final_transcript):
            - word_map: Full word map with all words
            - repetitions: List of detected repetitions
            - final_transcript: Word map excluding non-keeper repetitions
    """
    logger.info("Starting repetition detection")
    
    # Build word-level map
    word_map = build_word_map(transcription_segments)
    
    # Find repeated sequences
    repetitions = find_repeated_sequences(word_map, min_length, max_length)
    
    # Mark excluded words
    mark_excluded_words(word_map, repetitions)
    
    # Build final transcript
    final_transcript = build_final_transcript(word_map)
    
    logger.info("Repetition detection complete")
    
    return word_map, repetitions, final_transcript
