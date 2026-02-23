"""
PDF Text Cleaning Utilities

Fixes common issues with PDF text extraction:
- Words split by spaces (e.g., "h e l l o" -> "hello")
- Missing spaces between words
- Irregular spacing
- Hyphenated words across lines
- Headers and footers (using pattern detection)
- Page numbers
"""
import re
from difflib import SequenceMatcher
from collections import Counter
from typing import List, Dict, Set, Optional


def clean_pdf_text(text, remove_headers=True):
    """
    Clean and fix PDF text extraction issues.
    
    Args:
        text: Raw PDF text
        remove_headers: Whether to remove headers, footers, and page numbers
        
    Returns:
        Cleaned text with fixed spacing and merged words
    """
    if not text:
        return text
    
    # First pass: remove headers, footers, page numbers if requested
    if remove_headers:
        text = remove_headers_footers_and_numbers(text)
    
    # Second pass: fix obvious spacing issues
    text = fix_word_spacing(text)
    
    # Third pass: merge hyphenated words across lines
    text = fix_hyphenated_words(text)
    
    # Fourth pass: normalize whitespace
    text = normalize_whitespace(text)
    
    return text


def remove_headers_footers_and_numbers(text):
    """
    Remove common headers, footers, page numbers, and narrator instructions.
    
    Removes:
    - Page headers (book title, chapter names)
    - Page footers (author names)
    - Standalone page numbers
    - Narrator instructions in parentheses
    - Publisher information
    """
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line_stripped = line.strip()
        
        # Skip empty lines (preserve them for now, will clean up later)
        if not line_stripped:
            cleaned_lines.append(line)
            continue
        
        # Pattern 1: Book title + page number (headers on odd pages)
        # e.g., "An Improbable Scheme 123" or just "An Improbable Scheme"
        if re.match(r'^[A-Z][a-zA-Z\s]+(?:\s+\d+)?$', line_stripped) and len(line_stripped) < 50:
            # Could be header - check if it's ALL CAPS or Title Case followed by number
            words = line_stripped.split()
            if len(words) <= 5:  # Headers are usually short
                # Check if last word is a number
                if words[-1].isdigit():
                    continue  # Skip header with page number
                # Check if all words are capitalized (title case header)
                if all(w[0].isupper() for w in words if w):
                    # Might be a header, but could also be start of sentence
                    # Skip only if it matches common patterns
                    if any(keyword in line_stripped.lower() for keyword in ['chapter', 'prologue', 'epilogue']):
                        continue
        
        # Pattern 2: Page number + author name (headers/footers)
        # e.g., "123 LAURA BEERS", "6LAURA BEERS", "LAURA BEERS"
        # Matches: optional digits (with or without space) + all caps text
        if re.match(r'^\d*\s*[A-Z][A-Z\s]{4,30}$', line_stripped):
            # All caps text, possibly with leading page number
            words_only = re.sub(r'^\d+\s*', '', line_stripped)  # Remove leading digits
            if words_only and len(words_only.split()) <= 5:  # Author names are usually 1-3 words
                # Verify it's mostly letters and spaces (author name pattern)
                if re.match(r'^[A-Z\s.]+$', words_only):
                    continue  # Skip this header/footer
        
        # Pattern 3: Standalone page numbers (1-4 digits on their own line)
        if re.match(r'^\d{1,4}$', line_stripped):
            continue
        
        # Pattern 4: Page numbers with surrounding text (e.g., "- 123 -" or "Page 123")
        if re.match(r'^[-–—\s]*\d{1,4}[-–—\s]*$', line_stripped):
            continue
        if re.match(r'^\s*Page\s+\d+\s*$', line_stripped, re.IGNORECASE):
            continue
        
        # Pattern 5: Narrator instructions in parentheses with colons
        # e.g., "(Marian: Please add 3 seconds of room tone before beginning)"
        if re.match(r'^\([^)]*:\s*[^)]+\)$', line_stripped):
            continue
        
        # Pattern 6: Publisher/production information
        publisher_keywords = [
            'dreamscape presents',
            'narrated by',
            'produced by',
            'published by',
            'copyright',
            'all rights reserved',
            '©',
            'audiobook production'
        ]
        if any(keyword in line_stripped.lower() for keyword in publisher_keywords):
            # But keep if it's part of a longer sentence
            if len(line_stripped) < 100 and line_stripped.count(' ') < 10:
                continue
        
        # Pattern 7: Chapter/section markers (if on their own line)
        if re.match(r'^(Chapter|Section|Part)\s+\d+\s*$', line_stripped, re.IGNORECASE):
            # Keep chapter markers as they might be useful for context
            # But you could uncomment the next line to remove them
            # continue
            pass
        
        # Remove inline narrator instructions from the line
        # e.g., "Text here (Marian: instruction) more text"
        line_cleaned = re.sub(r'\([^)]*:\s*[^)]+\)\s*', '', line)
        
        # Add the cleaned line if it has content
        if line_cleaned.strip():
            cleaned_lines.append(line_cleaned)
    
    return '\n'.join(cleaned_lines)


def fix_word_spacing(text):
    """
    Fix words that are incorrectly split with spaces.
    
    Examples:
        "h e l l o w o r l d" -> "hello world"
        "T h e q u i c k b r o w n" -> "The quick brown"
    """
    lines = text.split('\n')
    fixed_lines = []
    
    for line in lines:
        # Check if line has pattern of single letters with spaces
        # Pattern: letter space letter space letter (at least 3 times)
        if re.search(r'(?:^|\s)([a-zA-Z]\s){3,}[a-zA-Z](?:\s|$)', line):
            # This line likely has a broken word
            fixed_line = merge_spaced_letters(line)
            fixed_lines.append(fixed_line)
        else:
            fixed_lines.append(line)
    
    return '\n'.join(fixed_lines)


def merge_spaced_letters(line):
    """
    Merge single letters that are separated by spaces into words.
    
    Example: "T h e q u i c k" -> "The quick"
    """
    # Split into words
    words = line.split()
    merged_words = []
    temp_word = []
    
    for word in words:
        # Check if it's a single letter (possibly with punctuation)
        clean_word = re.sub(r'[^\w]', '', word)
        
        if len(clean_word) == 1:
            # Single letter - add to temp buffer
            temp_word.append(word)
        else:
            # Multi-letter word
            if temp_word:
                # Merge accumulated single letters
                if len(temp_word) >= 3:  # Only merge if we have at least 3 letters
                    merged = ''.join(temp_word)
                    merged_words.append(merged)
                else:
                    # Too few letters, keep them separate
                    merged_words.extend(temp_word)
                temp_word = []
            
            merged_words.append(word)
    
    # Handle any remaining letters
    if temp_word:
        if len(temp_word) >= 3:
            merged = ''.join(temp_word)
            merged_words.append(merged)
        else:
            merged_words.extend(temp_word)
    
    return ' '.join(merged_words)


def fix_hyphenated_words(text):
    """
    Fix words that are hyphenated across line breaks.
    
    Example:
        "The quick brown fox jump-\ned over" -> "The quick brown fox jumped over"
    """
    # Pattern: word ending with hyphen, newline, then continuation
    pattern = r'(\w+)-\s*\n\s*(\w+)'
    
    def merge_hyphenated(match):
        """Merge hyphenated word parts."""
        word1 = match.group(1)
        word2 = match.group(2)
        
        # Check if word2 starts with lowercase (likely continuation)
        if word2[0].islower():
            return word1 + word2 + ' '
        else:
            # New sentence, keep the hyphen and newline
            return match.group(0)
    
    return re.sub(pattern, merge_hyphenated, text)


def normalize_whitespace(text):
    """
    Normalize whitespace in text.
    
    - Replace multiple spaces with single space
    - Remove spaces before punctuation
    - Ensure single space after punctuation
    - Limit consecutive newlines to 2
    """
    # Replace multiple spaces with single space
    text = re.sub(r'  +', ' ', text)
    
    # Remove spaces before punctuation
    text = re.sub(r'\s+([.,;:!?])', r'\1', text)
    
    # Ensure space after punctuation (but not after periods in abbreviations)
    text = re.sub(r'([.,;:!?])([A-Z])', r'\1 \2', text)
    
    # Limit consecutive newlines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove trailing spaces from lines
    lines = text.split('\n')
    text = '\n'.join(line.rstrip() for line in lines)
    
    return text.strip()


def fix_missing_spaces(text):
    """
    Attempt to fix missing spaces between words.
    
    Example: "HelloWorld" -> "Hello World" (if both are valid words)
    
    Note: This is heuristic-based and may not be 100% accurate.
    """
    # This is complex and would require a dictionary of valid words
    # For now, we'll use a simple heuristic: add space before capital letters
    # in the middle of words (CamelCase splitting)
    
    def split_camel_case(match):
        """Split CamelCase words."""
        text = match.group(0)
        # Insert space before uppercase letters (except first one)
        return re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    
    # Find sequences of letters with mixed case
    text = re.sub(r'\b[a-z]+[A-Z][a-zA-Z]*\b', split_camel_case, text)
    
    return text


def detect_repeating_patterns_from_pages(pages_text: List[str], 
                                         header_lines: int = 3,
                                         footer_lines: int = 3,
                                         min_occurrence_ratio: float = 0.4) -> Dict[str, Set[str]]:
    """
    Detect repeating header and footer patterns by analyzing multiple pages.
    
    This analyzes the first/last lines of each page and identifies text that
    appears repeatedly across many pages. Works for ANY book format.
    
    Args:
        pages_text: List of text strings, one per page
        header_lines: Number of lines to check at top of each page
        footer_lines: Number of lines to check at bottom of each page
        min_occurrence_ratio: Minimum ratio of pages that must contain the pattern (0.0-1.0)
                             e.g., 0.4 = pattern must appear on 40% of pages
    
    Returns:
        Dictionary with:
            'header_patterns': Set of header patterns to remove
            'footer_patterns': Set of footer patterns to remove
    """
    if not pages_text or len(pages_text) < 2:
        return {'header_patterns': set(), 'footer_patterns': set()}
    
    header_counter = Counter()
    footer_counter = Counter()
    total_pages = len(pages_text)
    
    for page_text in pages_text:
        lines = [line.strip() for line in page_text.split('\n') if line.strip()]
        
        if not lines:
            continue
        
        # Collect top lines (headers)
        top_lines = lines[:header_lines]
        for line in top_lines:
            # Normalize the line for pattern matching (remove page numbers, etc.)
            normalized = normalize_for_pattern_matching(line)
            if normalized and len(normalized) > 2:  # Skip very short lines
                header_counter[normalized] += 1
        
        # Collect bottom lines (footers)
        bottom_lines = lines[-footer_lines:] if len(lines) > footer_lines else []
        for line in bottom_lines:
            normalized = normalize_for_pattern_matching(line)
            if normalized and len(normalized) > 2:
                footer_counter[normalized] += 1
    
    # Identify patterns that appear frequently enough
    min_occurrences = max(2, int(total_pages * min_occurrence_ratio))
    
    header_patterns = {
        pattern for pattern, count in header_counter.items()
        if count >= min_occurrences
    }
    
    footer_patterns = {
        pattern for pattern, count in footer_counter.items()
        if count >= min_occurrences
    }
    
    return {
        'header_patterns': header_patterns,
        'footer_patterns': footer_patterns
    }


def normalize_for_pattern_matching(text: str) -> str:
    """
    Normalize text for pattern matching by removing page numbers and normalizing whitespace.
    
    This helps identify the same header/footer even when page numbers change.
    Example: "123 CHAPTER ONE" and "456 CHAPTER ONE" both normalize to "CHAPTER ONE"
    """
    # Remove standalone numbers at the beginning or end
    text = re.sub(r'^\d+\s*', '', text)  # Leading numbers
    text = re.sub(r'\s*\d+$', '', text)  # Trailing numbers
    
    # Remove common page number patterns
    text = re.sub(r'\s*[-–—]\s*\d+\s*[-–—]\s*', ' ', text)  # "- 123 -"
    text = re.sub(r'\s*Page\s+\d+\s*', ' ', text, flags=re.IGNORECASE)  # "Page 123"
    
    # Normalize whitespace
    text = ' '.join(text.split())
    
    return text.strip()


def clean_pdf_text_with_pattern_detection(pdf_file_path: str, 
                                          header_lines: int = 3,
                                          footer_lines: int = 3,
                                          min_occurrence_ratio: float = 0.4) -> str:
    """
    Clean PDF text using intelligent pattern detection for headers/footers.
    
    This method:
    1. Extracts text page-by-page
    2. Analyzes pages to find repeating header/footer patterns
    3. Removes those patterns automatically (works for ANY book)
    4. Applies standard text cleaning (spacing, hyphenation, etc.)
    
    Args:
        pdf_file_path: Path to PDF file
        header_lines: Number of lines to analyze at top of each page
        footer_lines: Number of lines to analyze at bottom of each page
        min_occurrence_ratio: Minimum % of pages pattern must appear on to be removed
    
    Returns:
        Cleaned text with headers/footers removed
    """
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        raise ImportError("PyPDF2 is required for PDF pattern detection. Install with: pip install PyPDF2")
    
    # Extract text page by page
    reader = PdfReader(pdf_file_path)
    pages_text = []
    
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            pages_text.append(page_text)
    
    if not pages_text:
        return ""
    
    # Detect repeating patterns
    detected_patterns = detect_repeating_patterns_from_pages(
        pages_text,
        header_lines=header_lines,
        footer_lines=footer_lines,
        min_occurrence_ratio=min_occurrence_ratio
    )
    
    # Combine all pages
    combined_text = "\n".join(pages_text)
    
    # Remove detected patterns
    cleaned_text = remove_detected_patterns(combined_text, detected_patterns)
    
    # Apply standard cleaning (regex rules, spacing fixes, etc.)
    cleaned_text = remove_headers_footers_and_numbers(cleaned_text)
    cleaned_text = fix_word_spacing(cleaned_text)
    cleaned_text = fix_hyphenated_words(cleaned_text)
    cleaned_text = normalize_whitespace(cleaned_text)
    
    return cleaned_text


def remove_detected_patterns(text: str, detected_patterns: Dict[str, Set[str]]) -> str:
    """
    Remove detected header and footer patterns from text.
    
    Args:
        text: Text to clean
        detected_patterns: Dictionary with 'header_patterns' and 'footer_patterns' sets
    
    Returns:
        Text with patterns removed
    """
    lines = text.split('\n')
    cleaned_lines = []
    
    header_patterns = detected_patterns.get('header_patterns', set())
    footer_patterns = detected_patterns.get('footer_patterns', set())
    
    for line in lines:
        line_stripped = line.strip()
        
        if not line_stripped:
            cleaned_lines.append(line)
            continue
        
        # Normalize to check against patterns
        normalized = normalize_for_pattern_matching(line_stripped)
        
        # Skip if matches a detected pattern
        if normalized in header_patterns or normalized in footer_patterns:
            continue
        
        # Keep this line
        cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)


def analyze_pdf_text_quality(text):
    """
    Analyze the quality of PDF text extraction.
    
    Returns:
        dict with statistics about potential issues
    """
    if not text:
        return {
            'total_chars': 0,
            'total_words': 0,
            'issues': []
        }
    
    issues = []
    
    # Check for excessive single-letter "words"
    words = text.split()
    single_letter_count = sum(1 for w in words if len(re.sub(r'[^\w]', '', w)) == 1)
    single_letter_ratio = single_letter_count / len(words) if words else 0
    
    if single_letter_ratio > 0.1:  # More than 10% single letters
        issues.append({
            'type': 'excessive_single_letters',
            'severity': 'high',
            'message': f'{single_letter_count} single-letter words detected ({single_letter_ratio:.1%})',
            'suggestion': 'Text likely has spacing issues - consider re-extraction or manual cleanup'
        })
    
    # Check for words with internal spaces (like "h e l l o")
    spaced_word_pattern = r'(?:^|\s)([a-zA-Z]\s){2,}[a-zA-Z](?:\s|$)'
    spaced_words = len(re.findall(spaced_word_pattern, text))
    
    if spaced_words > 0:
        issues.append({
            'type': 'spaced_letters',
            'severity': 'high',
            'message': f'{spaced_words} instances of spaced letters detected',
            'suggestion': 'Run PDF text cleanup to merge separated letters'
        })
    
    # Check for hyphenated line breaks
    hyphenated_breaks = len(re.findall(r'\w+-\s*\n\s*\w+', text))
    
    if hyphenated_breaks > 0:
        issues.append({
            'type': 'hyphenated_breaks',
            'severity': 'medium',
            'message': f'{hyphenated_breaks} hyphenated word breaks detected',
            'suggestion': 'Run PDF text cleanup to merge hyphenated words'
        })
    
    return {
        'total_chars': len(text),
        'total_words': len(words),
        'single_letter_words': single_letter_count,
        'single_letter_ratio': single_letter_ratio,
        'spaced_words_detected': spaced_words,
        'hyphenated_breaks': hyphenated_breaks,
        'issues': issues,
        'quality_score': calculate_quality_score(single_letter_ratio, spaced_words, hyphenated_breaks)
    }


def calculate_quality_score(single_letter_ratio, spaced_words, hyphenated_breaks):
    """
    Calculate a quality score for PDF text (0-100).
    
    Higher is better.
    """
    score = 100
    
    # Penalize single letter ratio
    score -= single_letter_ratio * 100
    
    # Penalize spaced words
    score -= min(spaced_words * 2, 30)
    
    # Small penalty for hyphenated breaks (these are usually legit)
    score -= min(hyphenated_breaks * 0.5, 10)
    
    return max(0, min(100, score))
