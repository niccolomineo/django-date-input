"""Tests for the behaviour the three widgets share."""

from django.test import SimpleTestCase

from temporal_inputs.widgets import ISO_DATE, TemporalInput


class TemporalInputTests(SimpleTestCase):
    """Test the base class every widget derives from."""

    def test_bounds_must_be_named_by_a_subclass(self):
        """
        The base class knows how to resolve bounds, not which ones exist.

        Each widget names its own pair — ``min_date``, ``min_datetime``,
        ``min_time`` — because a generic ``min_value`` would read worse at every
        call site than the name of the thing being bounded.
        """
        with self.assertRaises(NotImplementedError):
            TemporalInput(iso_format=ISO_DATE).bounds()
