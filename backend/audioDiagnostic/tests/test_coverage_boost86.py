"""
Wave 86 — Coverage boost
Targets:
  - audioDiagnostic/services/ai/cost_calculator.py (CostCalculator)
  - audioDiagnostic/utils/gap_detector.py (find_missing_sections, calculate_completeness_percentage)
"""
from django.test import TestCase


# ══════════════════════════════════════════════════════════════════
# CostCalculator
# ══════════════════════════════════════════════════════════════════

class CostCalculatorTests(TestCase):

    def test_calculate_cost_anthropic_known(self):
        from audioDiagnostic.services.ai.cost_calculator import CostCalculator
        cost = CostCalculator.calculate_cost(
            provider='anthropic',
            model='claude-3-5-sonnet-20241022',
            input_tokens=1_000_000,
            output_tokens=1_000_000
        )
        # 3.00 + 15.00 = 18.00
        self.assertAlmostEqual(cost, 18.0)

    def test_calculate_cost_openai_known(self):
        from audioDiagnostic.services.ai.cost_calculator import CostCalculator
        cost = CostCalculator.calculate_cost(
            provider='openai',
            model='gpt-4-turbo',
            input_tokens=1_000_000,
            output_tokens=1_000_000
        )
        # 10.00 + 30.00 = 40.00
        self.assertAlmostEqual(cost, 40.0)

    def test_calculate_cost_unknown_model_falls_back(self):
        from audioDiagnostic.services.ai.cost_calculator import CostCalculator
        # Unknown provider/model — should use fallback and not raise
        cost = CostCalculator.calculate_cost(
            provider='unknown',
            model='unknown-model',
            input_tokens=1_000_000,
            output_tokens=0
        )
        self.assertAlmostEqual(cost, 3.0)  # Fallback input rate

    def test_calculate_cost_zero_tokens(self):
        from audioDiagnostic.services.ai.cost_calculator import CostCalculator
        cost = CostCalculator.calculate_cost(
            provider='anthropic',
            model='claude-3-haiku-20240307',
            input_tokens=0,
            output_tokens=0
        )
        self.assertAlmostEqual(cost, 0.0)

    def test_estimate_cost_duplicate_detection(self):
        from audioDiagnostic.services.ai.cost_calculator import CostCalculator
        result = CostCalculator.estimate_cost_for_audio(
            provider='anthropic',
            model='claude-3-5-sonnet-20241022',
            audio_duration_seconds=600.0,  # 10 minutes
            task='duplicate_detection'
        )
        self.assertEqual(result['task'], 'duplicate_detection')
        self.assertIn('estimated_cost_usd', result)
        self.assertIn('estimated_input_tokens', result)
        self.assertGreater(result['estimated_total_tokens'], 0)

    def test_estimate_cost_pdf_comparison(self):
        from audioDiagnostic.services.ai.cost_calculator import CostCalculator
        result = CostCalculator.estimate_cost_for_audio(
            provider='anthropic',
            model='claude-3-5-sonnet-20241022',
            audio_duration_seconds=300.0,
            task='pdf_comparison'
        )
        self.assertEqual(result['task'], 'pdf_comparison')

    def test_estimate_cost_unknown_task(self):
        from audioDiagnostic.services.ai.cost_calculator import CostCalculator
        result = CostCalculator.estimate_cost_for_audio(
            provider='anthropic',
            model='claude-3-5-sonnet-20241022',
            audio_duration_seconds=120.0,
            task='something_else'
        )
        self.assertIn('estimated_cost_usd', result)

    def test_format_cost_summary_small(self):
        from audioDiagnostic.services.ai.cost_calculator import CostCalculator
        result = CostCalculator.format_cost_summary(0.0012, 5000)
        self.assertIn('$', result)
        self.assertIn('5,000', result)

    def test_format_cost_summary_cents(self):
        from audioDiagnostic.services.ai.cost_calculator import CostCalculator
        result = CostCalculator.format_cost_summary(0.05, 10000)
        self.assertIn('$', result)

    def test_format_cost_summary_dollars(self):
        from audioDiagnostic.services.ai.cost_calculator import CostCalculator
        result = CostCalculator.format_cost_summary(5.50, 500000)
        self.assertIn('$', result)
        self.assertIn('500,000', result)

    def test_haiku_is_cheaper_than_sonnet(self):
        from audioDiagnostic.services.ai.cost_calculator import CostCalculator
        haiku = CostCalculator.calculate_cost('anthropic', 'claude-3-haiku-20240307', 100000, 100000)
        sonnet = CostCalculator.calculate_cost('anthropic', 'claude-3-5-sonnet-20241022', 100000, 100000)
        self.assertLess(haiku, sonnet)


# ══════════════════════════════════════════════════════════════════
# find_missing_sections / calculate_completeness_percentage
# ══════════════════════════════════════════════════════════════════

def _make_ap(match_type, pdf_word=None):
    from audioDiagnostic.utils.alignment_engine import AlignmentPoint
    return AlignmentPoint(pdf_word=pdf_word, match_type=match_type)


class FindMissingSectionsTests(TestCase):

    def test_no_missing(self):
        from audioDiagnostic.utils.gap_detector import find_missing_sections
        alignment = [_make_ap('exact', 'word') for _ in range(20)]
        result = find_missing_sections(alignment, min_gap_words=5)
        self.assertEqual(result, [])

    def test_gap_smaller_than_threshold(self):
        from audioDiagnostic.utils.gap_detector import find_missing_sections
        alignment = (
            [_make_ap('exact', 'w') for _ in range(5)]
            + [_make_ap('missing', f'miss{i}') for i in range(3)]  # gap of 3 < min 5
            + [_make_ap('exact', 'w') for _ in range(5)]
        )
        result = find_missing_sections(alignment, min_gap_words=5)
        self.assertEqual(result, [])

    def test_gap_found(self):
        from audioDiagnostic.utils.gap_detector import find_missing_sections
        alignment = (
            [_make_ap('exact', 'word') for _ in range(5)]
            + [_make_ap('missing', f'miss{i}') for i in range(10)]
            + [_make_ap('exact', 'word') for _ in range(5)]
        )
        result = find_missing_sections(alignment, min_gap_words=5)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].word_count, 10)

    def test_gap_at_end(self):
        from audioDiagnostic.utils.gap_detector import find_missing_sections
        alignment = (
            [_make_ap('exact', 'word') for _ in range(5)]
            + [_make_ap('missing', f'miss{i}') for i in range(7)]
        )
        result = find_missing_sections(alignment, min_gap_words=5)
        self.assertEqual(len(result), 1)

    def test_multiple_gaps(self):
        from audioDiagnostic.utils.gap_detector import find_missing_sections
        alignment = (
            [_make_ap('exact', 'w') for _ in range(3)]
            + [_make_ap('missing', f'a{i}') for i in range(6)]
            + [_make_ap('exact', 'w') for _ in range(3)]
            + [_make_ap('missing', f'b{i}') for i in range(6)]
            + [_make_ap('exact', 'w') for _ in range(3)]
        )
        result = find_missing_sections(alignment, min_gap_words=5)
        self.assertEqual(len(result), 2)


class CalculateCompletenessPercentageTests(TestCase):

    def test_fully_complete(self):
        from audioDiagnostic.utils.gap_detector import calculate_completeness_percentage
        alignment = [_make_ap('exact', 'word') for _ in range(10)]
        result = calculate_completeness_percentage(alignment)
        self.assertAlmostEqual(result, 100.0)

    def test_half_missing(self):
        from audioDiagnostic.utils.gap_detector import calculate_completeness_percentage
        alignment = (
            [_make_ap('exact', 'word') for _ in range(5)]
            + [_make_ap('missing', 'word') for _ in range(5)]
        )
        result = calculate_completeness_percentage(alignment)
        self.assertAlmostEqual(result, 50.0)

    def test_empty_alignment(self):
        from audioDiagnostic.utils.gap_detector import calculate_completeness_percentage
        result = calculate_completeness_percentage([])
        self.assertAlmostEqual(result, 0.0)

    def test_extra_words_not_counted_as_pdf(self):
        from audioDiagnostic.utils.gap_detector import calculate_completeness_percentage
        alignment = (
            [_make_ap('extra', None) for _ in range(5)]  # no pdf_word
            + [_make_ap('exact', 'word') for _ in range(5)]
        )
        result = calculate_completeness_percentage(alignment)
        # Only 5 pdf words, all read → 100%
        self.assertAlmostEqual(result, 100.0)
