"""Tests for score_deltas() — baseline handling and component signals."""
import unittest

from sep_analyzer import SEPReading, score_deltas


def _reading(**kw):
    """Build a SEPReading with sensible defaults for scoring tests."""
    defaults = dict(
        fed_funds_median_2026=3.5,
        fed_funds_longer_run=3.0,
        gdp_2026=1.8,
        core_pce_2026=2.3,
        unemployment_2026=4.4,
        dots_hike_count=0,
        hawkish_hits=[],
        dovish_hits=[],
        hike_hits=[],
    )
    defaults.update(kw)
    return SEPReading(**defaults)


FULL_BASELINE = {
    "fed_funds_median_2026": 3.625,
    "fed_funds_longer_run":  3.0,
    "gdp_2026":              2.0,
    "core_pce_2026":         2.5,
    "unemployment_2026":     4.5,
}


class TestBaselineHandling(unittest.TestCase):
    def test_empty_baseline_does_not_raise(self):
        # Previously this raised KeyError because safe_delta indexed b[key] directly.
        scores = score_deltas(_reading(), {})
        self.assertEqual(scores["dot_plot_2026"]["note"], "no prior baseline")
        self.assertEqual(scores["dot_plot_2026"]["score"], 0)
        self.assertEqual(scores["gdp_2026"]["note"], "no prior baseline")
        self.assertEqual(scores["unemployment_2026"]["note"], "no prior baseline")

    def test_partial_baseline_mixes_notes(self):
        partial = {"fed_funds_median_2026": 3.5, "gdp_2026": 2.0}
        scores = score_deltas(_reading(), partial)
        # Present keys compute a real delta note.
        self.assertIn("vs prev baseline", scores["dot_plot_2026"]["note"])
        self.assertIn("vs prev baseline", scores["gdp_2026"]["note"])
        # Missing keys report no baseline.
        self.assertEqual(scores["longer_run_rate"]["note"], "no prior baseline")
        self.assertEqual(scores["core_pce_2026"]["note"], "no prior baseline")
        self.assertEqual(scores["unemployment_2026"]["note"], "no prior baseline")

    def test_missing_reading_value_reports_not_found(self):
        reading = _reading(fed_funds_median_2026=None, gdp_2026=None)
        scores = score_deltas(reading, FULL_BASELINE)
        self.assertEqual(scores["dot_plot_2026"]["note"], "not found")
        self.assertEqual(scores["dot_plot_2026"]["score"], 0)
        self.assertEqual(scores["gdp_2026"]["note"], "not found")


class TestDeltaDirection(unittest.TestCase):
    def test_lower_fed_funds_is_bullish(self):
        reading = _reading(fed_funds_median_2026=3.375)  # down from 3.625
        scores = score_deltas(reading, FULL_BASELINE)
        self.assertGreater(scores["dot_plot_2026"]["score"], 0)

    def test_higher_fed_funds_is_bearish(self):
        reading = _reading(fed_funds_median_2026=3.875)  # up from 3.625
        scores = score_deltas(reading, FULL_BASELINE)
        self.assertLess(scores["dot_plot_2026"]["score"], 0)

    def test_higher_gdp_is_bullish(self):
        reading = _reading(gdp_2026=2.3)  # up from 2.0
        scores = score_deltas(reading, FULL_BASELINE)
        self.assertGreater(scores["gdp_2026"]["score"], 0)

    def test_lower_core_pce_is_bullish(self):
        reading = _reading(core_pce_2026=2.2)  # down from 2.5
        scores = score_deltas(reading, FULL_BASELINE)
        self.assertGreater(scores["core_pce_2026"]["score"], 0)


class TestHikeDots(unittest.TestCase):
    def test_hike_dots_present_is_bearish(self):
        scores = score_deltas(_reading(dots_hike_count=2), FULL_BASELINE)
        self.assertEqual(scores["hike_dots"]["score"], -15)

    def test_no_hike_dots_is_neutral(self):
        scores = score_deltas(_reading(dots_hike_count=0), FULL_BASELINE)
        self.assertEqual(scores["hike_dots"]["score"], 0)

    def test_none_hike_dots_is_neutral(self):
        scores = score_deltas(_reading(dots_hike_count=None), FULL_BASELINE)
        self.assertEqual(scores["hike_dots"]["score"], 0)


class TestKeywordScoring(unittest.TestCase):
    def test_dovish_adds_three_per_hit(self):
        reading = _reading(dovish_hits=["patient", "gradual"])
        scores = score_deltas(reading, FULL_BASELINE)
        self.assertEqual(scores["keywords"]["score"], 6)

    def test_hawkish_subtracts_three_per_hit(self):
        reading = _reading(hawkish_hits=["persistent", "upside risks"])
        scores = score_deltas(reading, FULL_BASELINE)
        self.assertEqual(scores["keywords"]["score"], -6)

    def test_hike_signal_subtracts_ten_per_hit(self):
        reading = _reading(hike_hits=["additional tightening"])
        scores = score_deltas(reading, FULL_BASELINE)
        self.assertEqual(scores["keywords"]["score"], -10)


class TestTotal(unittest.TestCase):
    def test_total_sums_components(self):
        scores = score_deltas(_reading(), FULL_BASELINE)
        component_sum = sum(
            v["score"] for k, v in scores.items() if k != "TOTAL"
        )
        self.assertEqual(scores["TOTAL"], component_sum)


if __name__ == "__main__":
    unittest.main()
