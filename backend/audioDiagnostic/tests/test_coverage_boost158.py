"""
Wave 158: Cover 2 statements in pdf_text_cleaner.py
- Line 105: continue inside 'Page N' pattern (case-insensitive, lowercase 'page N')
- Line 133: pass inside 'Chapter N' pattern (case-insensitive, lowercase 'chapter N')

Root cause of wave 157 miss: "Page 5" and "Chapter 1" (Title Case) are caught by
Pattern 1 (header detection: ^[A-Z][a-zA-Z\s]+\\d$ -> continue at line ~77) before
reaching lines 105/133. Using lowercase bypasses Pattern 1 (requires [A-Z] start)
while still matching the re.IGNORECASE patterns at lines 104 and 128.
"""
from django.test import TestCase
from rest_framework.test import force_authenticate


class PDFTextCleanerLine105Tests(TestCase):
    """Cover line 105: continue inside Page-N pattern check"""

    def test_lowercase_page_number_removed(self):
        """
        'page 5' (lowercase) bypasses Pattern 1 (requires [A-Z] start) but matches
        re.match(r'^\\s*Page\\s+\\d+\\s*$', ..., re.IGNORECASE) at line 104 -> continue at 105.
        """
        from audioDiagnostic.utils.pdf_text_cleaner import remove_headers_footers_and_numbers

        text = "page 5\nThis is the actual story content."
        result = remove_headers_footers_and_numbers(text)
        # 'page 5' line should be removed by the continue at line 105
        self.assertNotIn('page 5', result)
        self.assertIn('actual story content', result)

    def test_page_number_with_spaces_removed(self):
        """
        '  page 10  ' (leading/trailing spaces) also matches the pattern.
        line_stripped = 'page 10' -> matches re.IGNORECASE pattern at line 104.
        """
        from audioDiagnostic.utils.pdf_text_cleaner import remove_headers_footers_and_numbers

        text = "  page 10  \nSome narrative text here."
        result = remove_headers_footers_and_numbers(text)
        self.assertNotIn('page 10', result)
        self.assertIn('narrative text', result)


class PDFTextCleanerLine133Tests(TestCase):
    """Cover line 133: pass inside Chapter/Section/Part pattern check"""

    def test_lowercase_chapter_marker_kept(self):
        """
        'chapter 1' (lowercase) bypasses Pattern 1 (requires [A-Z] start) but matches
        re.match(r'^(Chapter|Section|Part)\\s+\\d+\\s*$', ..., re.IGNORECASE) at line 128
        -> executes pass at line 133 (kept in output, not removed).
        """
        from audioDiagnostic.utils.pdf_text_cleaner import remove_headers_footers_and_numbers

        text = "chapter 1\nThis is the chapter content."
        result = remove_headers_footers_and_numbers(text)
        # Chapter markers are kept (pass means no continue)
        self.assertIn('chapter 1', result)
        self.assertIn('chapter content', result)

    def test_lowercase_section_marker_kept(self):
        """'section 3' also hits line 133 via the same regex (Section alternative)."""
        from audioDiagnostic.utils.pdf_text_cleaner import remove_headers_footers_and_numbers

        text = "section 3\nContent of section three."
        result = remove_headers_footers_and_numbers(text)
        self.assertIn('section 3', result)
        self.assertIn('Content of section', result)

    def test_lowercase_part_marker_kept(self):
        """'part 2' also hits line 133 via the same regex (Part alternative)."""
        from audioDiagnostic.utils.pdf_text_cleaner import remove_headers_footers_and_numbers

        text = "part 2\nContent of part two."
        result = remove_headers_footers_and_numbers(text)
        self.assertIn('part 2', result)
        self.assertIn('Content of part two', result)
