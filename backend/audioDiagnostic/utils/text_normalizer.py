"""
Text Normalization Utilities for Audiobook Production Analysis

Provides text normalization, tokenization, and matching utilities
for comparing PDF text with audio transcriptions.
"""

import re
import unicodedata
from typing import List, Dict, Tuple


# Common contractions and their expansions
CONTRACTIONS = {
    "can't": "cannot",
    "won't": "will not",
    "n't": " not",
    "i'm": "i am",
    "you're": "you are",
    "he's": "he is",
    "she's": "she is",
    "it's": "it is",
    "we're": "we are",
    "they're": "they are",
    "i've": "i have",
    "you've": "you have",
    "we've": "we have",
    "they've": "they have",
    "i'd": "i would",
    "you'd": "you would",
    "he'd": "he would",
    "she'd": "she would",
    "we'd": "we would",
    "they'd": "they would",
    "i'll": "i will",
    "you'll": "you will",
    "he'll": "he will",
    "she'll": "she will",
    "we'll": "we will",
    "they'll": "they will",
    "isn't": "is not",
    "aren't": "are not",
    "wasn't": "was not",
    "weren't": "were not",
    "hasn't": "has not",
    "haven't": "have not",
    "hadn't": "had not",
    "doesn't": "does not",
    "don't": "do not",
    "didn't": "did not",
    "couldn't": "could not",
    "shouldn't": "should not",
    "wouldn't": "would not",
    "mightn't": "might not",
    "mustn't": "must not",
}


def expand_contractions(text: str) -> str:
    """
    Expand contractions to their full forms.
    
    Examples:
        "can't" -> "cannot"
        "she's" -> "she is"
    """
    # Sort by length (longest first) to handle overlapping patterns
    for contraction, expansion in sorted(CONTRACTIONS.items(), key=lambda x: len(x[0]), reverse=True):
        # Case-insensitive replacement
        pattern = re.compile(re.escape(contraction), re.IGNORECASE)
        text = pattern.sub(expansion, text)
    
    return text


def remove_punctuation(text: str, keep_apostrophes: bool = False) -> str:
    """
    Remove punctuation from text.
    
    Args:
        text: Input text
        keep_apostrophes: If True, keep apostrophes for contractions
    """
    if keep_apostrophes:
        # Remove all punctuation except apostrophes
        return re.sub(r"[^\w\s']", '', text)
    else:
        # Remove all punctuation
        return re.sub(r'[^\w\s]', '', text)


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace to single spaces.
    """
    # Replace multiple whitespace with single space
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def normalize_unicode(text: str) -> str:
    """
    Normalize unicode characters (e.g., smart quotes to regular quotes).
    """
    # Normalize to NFKD form (compatibility decomposition)
    text = unicodedata.normalize('NFKD', text)
    
    # Replace smart quotes with regular quotes
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace(''', "'").replace(''', "'")
    text = text.replace('—', '-').replace('–', '-')
    
    # Encode to ascii, ignoring non-ascii characters, then decode back
    text = text.encode('ascii', 'ignore').decode('ascii')
    
    return text


def normalize_text(text: str, expand_contractions_flag: bool = True, 
                   remove_punctuation_flag: bool = True,
                   lowercase: bool = True) -> str:
    """
    Comprehensive text normalization.
    
    Steps:
    1. Normalize unicode
    2. Expand contractions (optional)
    3. Convert to lowercase (optional)
    4. Remove punctuation (optional)
    5. Normalize whitespace
    """
    # Normalize unicode first
    text = normalize_unicode(text)
    
    # Expand contractions before removing punctuation
    if expand_contractions_flag:
        text = expand_contractions(text)
    
    # Convert to lowercase
    if lowercase:
        text = text.lower()
    
    # Remove punctuation
    if remove_punctuation_flag:
        text = remove_punctuation(text, keep_apostrophes=False)
    
    # Normalize whitespace
    text = normalize_whitespace(text)
    
    return text


def tokenize_words(text: str, normalize: bool = False) -> List[str]:
    """
    Tokenize text into words.
    
    Args:
        text: Input text
        normalize: If True, normalize before tokenizing
    
    Returns:
        List of word tokens
    """
    if normalize:
        text = normalize_text(text)
    
    # Split on whitespace
    words = text.split()
    
    return words


def normalize_word(word: str) -> str:
    """
    Normalize a single word for comparison.
    
    - Lowercase
    - Remove punctuation
    - Normalize unicode
    """
    word = normalize_unicode(word)
    word = word.lower()
    word = remove_punctuation(word)
    word = word.strip()
    
    return word


def calculate_word_similarity(word1: str, word2: str) -> float:
    """
    Calculate similarity score between two words.
    
    Returns score 0.0 to 1.0:
    - 1.0: exact match
    - 0.9: normalized match (case/punctuation differences)
    - 0.7-0.8: phonetic similarity
    - 0.0: no match
    """
    # Exact match
    if word1 == word2:
        return 1.0
    
    # Normalized match
    norm1 = normalize_word(word1)
    norm2 = normalize_word(word2)
    
    if norm1 == norm2:
        return 0.95
    
    # Check if one is a contraction of the other
    expanded1 = expand_contractions(word1.lower())
    expanded2 = expand_contractions(word2.lower())
    
    if normalize_word(expanded1) == normalize_word(expanded2):
        return 0.9
    
    # Levenshtein distance for phonetic similarity
    distance = levenshtein_distance(norm1, norm2)
    max_len = max(len(norm1), len(norm2))
    
    if max_len == 0:
        return 0.0
    
    similarity = 1.0 - (distance / max_len)
    
    # Only consider it a match if similarity is high enough
    if similarity >= 0.7:
        return similarity * 0.8  # Scale down phonetic matches
    
    return 0.0


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate Levenshtein distance between two strings.
    
    This measures the minimum number of single-character edits
    (insertions, deletions, substitutions) needed to change one string into another.
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost of insertions, deletions, or substitutions
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]


def create_word_variants(word: str) -> List[str]:
    """
    Create list of acceptable variants for a word.
    
    Used for flexible matching in alignment.
    """
    variants = [word]
    
    # Add normalized version
    normalized = normalize_word(word)
    if normalized and normalized not in variants:
        variants.append(normalized)
    
    # Add expanded contraction version
    expanded = expand_contractions(word.lower())
    norm_expanded = normalize_word(expanded)
    if norm_expanded and norm_expanded not in variants:
        variants.append(norm_expanded)
    
    # Add lowercase version
    if word.lower() not in variants:
        variants.append(word.lower())
    
    return variants


def get_ngrams(words: List[str], n: int) -> List[Tuple[str, int]]:
    """
    Extract n-grams from a list of words.
    
    Args:
        words: List of words
        n: N-gram size
    
    Returns:
        List of (ngram_text, start_index) tuples
    """
    ngrams = []
    
    for i in range(len(words) - n + 1):
        ngram = ' '.join(words[i:i+n])
        ngrams.append((ngram, i))
    
    return ngrams


def find_repeated_ngrams(words: List[str], n: int, min_occurrences: int = 2) -> Dict[str, List[int]]:
    """
    Find n-grams that appear multiple times in the text.
    
    Args:
        words: List of words
        n: N-gram size
        min_occurrences: Minimum number of times an n-gram must appear
    
    Returns:
        Dictionary mapping n-gram text to list of start positions
    """
    ngram_positions = {}
    
    # Extract all n-grams with their positions
    for ngram_text, start_pos in get_ngrams(words, n):
        # Normalize the n-gram for comparison
        normalized = normalize_text(ngram_text)
        
        if normalized not in ngram_positions:
            ngram_positions[normalized] = []
        
        ngram_positions[normalized].append(start_pos)
    
    # Filter to only repeated n-grams
    repeated = {
        ngram: positions 
        for ngram, positions in ngram_positions.items() 
        if len(positions) >= min_occurrences
    }
    
    return repeated


def remove_page_numbers(text: str) -> str:
    """
    Remove page numbers from PDF text.
    
    Patterns to remove:
    - Standalone numbers on lines
    - "Page N" or "p. N"
    - Numbers at start/end of lines
    """
    # Remove "Page N" or "p. N" patterns
    text = re.sub(r'\b[Pp]age\s+\d+\b', '', text)
    text = re.sub(r'\bp\.\s*\d+\b', '', text)
    
    # Remove standalone numbers on their own lines
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
    
    # Remove numbers at the end of lines (common page number position)
    text = re.sub(r'\s+\d+\s*$', '', text, flags=re.MULTILINE)
    
    return text


def remove_footnote_markers(text: str) -> str:
    """
    Remove footnote markers like [1], (1), *, etc.
    """
    # Remove bracketed numbers [1], [2], etc.
    text = re.sub(r'\[\d+\]', '', text)
    
    # Remove parenthesized numbers (1), (2), etc.
    text = re.sub(r'\(\d+\)', '', text)
    
    # Remove superscript-style markers like ¹, ², ³
    text = re.sub(r'[¹²³⁴⁵⁶⁷⁸⁹⁰]+', '', text)
    
    # Remove asterisks used as footnote markers
    # But be careful not to remove all asterisks (could be emphasis)
    # Only remove if followed by space or at end of word
    text = re.sub(r'\*+(?=\s|$)', '', text)
    
    return text


def prepare_pdf_for_audiobook(pdf_text: str) -> str:
    """
    Prepare PDF text for audiobook comparison.
    
    This is a specialized version of PDF cleaning that focuses on
    removing elements that wouldn't be read aloud in an audiobook.
    """
    from .pdf_text_cleaner import clean_pdf_text, remove_headers_footers_and_numbers
    
    # Use existing PDF cleaner
    text = clean_pdf_text(pdf_text, remove_headers=True)
    
    # Additional audiobook-specific cleaning
    text = remove_page_numbers(text)
    text = remove_footnote_markers(text)
    
    # Normalize whitespace
    text = normalize_whitespace(text)
    
    return text


def prepare_transcript_for_comparison(transcript_text: str) -> str:
    """
    Prepare transcript text for comparison.
    
    Less aggressive than PDF cleaning - just normalize formatting.
    """
    # Normalize unicode
    text = normalize_unicode(transcript_text)
    
    # Normalize whitespace
    text = normalize_whitespace(text)
    
    return text
