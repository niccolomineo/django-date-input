"""Tests for the native datetime input widget."""

import re
from datetime import UTC, date, datetime
from unittest.mock import patch

from django import forms
from django.forms.widgets import DateTimeInput as DjangoDateTimeInput
from django.test import SimpleTestCase, override_settings
from django.utils import timezone, translation

from temporal_inputs import DateTimeInput, end_of_year, start_of_year
from tests.models import Booking

ROME = override_settings(TIME_ZONE="Europe/Rome")


class BookingForm(forms.ModelForm):
    """A model form wiring the widget to a real model ``DateTimeField``."""

    class Meta:
        """Bind the widget to the model's datetime field."""

        model = Booking
        fields = ["starts_at"]
        widgets = {"starts_at": DateTimeInput()}


class DateTimeInputTests(SimpleTestCase):
    """Test the rendered markup and the bound handling."""

    def test_renders_native_datetime_input(self):
        """The widget renders type="datetime-local", not Django's text input."""
        self.assertIn('type="datetime-local"', DateTimeInput().render("when", None))
        self.assertIn('type="text"', DjangoDateTimeInput().render("when", None))

    def test_no_bounds_by_default(self):
        """Without bounds, no min or max attribute is emitted."""
        html = DateTimeInput().render("when", None)
        self.assertNotIn("min=", html)
        self.assertNotIn("max=", html)

    def test_datetime_bounds(self):
        """Datetime bounds render at the same precision as the value."""
        html = DateTimeInput(
            min_datetime=datetime(2020, 1, 1, 9, 0),
            max_datetime=datetime(2030, 12, 31, 17, 30),
        ).render("when", None)
        self.assertIn('min="2020-01-01T09:00"', html)
        self.assertIn('max="2030-12-31T17:30"', html)

    def test_only_one_bound(self):
        """A lower bound alone does not imply an upper bound."""
        html = DateTimeInput(min_datetime=datetime(2020, 1, 1, 9, 0)).render("when", None)
        self.assertIn('min="2020-01-01T09:00"', html)
        self.assertNotIn("max=", html)

    def test_bounds_from_class_attributes(self):
        """Bounds may be declared on a subclass instead of passed in."""

        class ShiftInput(DateTimeInput):
            """A datetime input bounded to the shift window."""

            min_datetime = datetime(2020, 1, 1, 9, 0)
            max_datetime = datetime(2030, 12, 31, 17, 30)

        html = ShiftInput().render("when", None)
        self.assertIn('min="2020-01-01T09:00"', html)
        self.assertIn('max="2030-12-31T17:30"', html)

    def test_explicit_attrs_take_precedence(self):
        """An explicit min or max in attrs wins over the configured bound."""
        html = DateTimeInput(
            attrs={"min": "1999-01-01T00:00", "max": "1999-12-31T23:59"},
            min_datetime=datetime(2020, 1, 1, 9, 0),
            max_datetime=datetime(2030, 12, 31, 17, 30),
        ).render("when", None)
        self.assertIn('min="1999-01-01T00:00"', html)
        self.assertIn('max="1999-12-31T23:59"', html)
        self.assertNotIn("2020-01-01", html)
        self.assertNotIn("2030-12-31", html)

    @ROME
    def test_aware_bound_is_converted_to_the_current_timezone(self):
        """
        An aware bound is rendered at the wall clock the value is rendered at.

        ``DateTimeField.prepare_value`` hands the widget a naive value in the
        current timezone, so a bound left in UTC would sit two hours away from
        the value it is supposed to bound.
        """
        html = DateTimeInput(min_datetime=datetime(2026, 8, 21, 10, 0, tzinfo=UTC)).render(
            "when", None
        )
        self.assertIn('min="2026-08-21T12:00"', html)

    def test_date_bound_covers_the_whole_day(self):
        """
        A plain date bounds the day it names, not midnight that starts it.

        Midnight as an upper bound would exclude the entire day the caller asked
        for, which is a silent off-by-a-day in the direction that hurts.
        """
        html = DateTimeInput(min_datetime=date(2020, 1, 1), max_datetime=date(2030, 12, 31)).render(
            "when", None
        )
        self.assertIn('min="2020-01-01T00:00"', html)
        self.assertIn('max="2030-12-31T23:59"', html)

    def test_callable_bounds_are_resolved_at_every_render(self):
        """The year helpers work here too, expanded to cover their day."""
        widget = DateTimeInput(min_datetime=start_of_year(-1), max_datetime=end_of_year())
        with patch("temporal_inputs.bounds.localdate", return_value=date(2026, 12, 31)):
            html = widget.render("when", None)
            self.assertIn('min="2025-01-01T00:00"', html)
            self.assertIn('max="2026-12-31T23:59"', html)
        with patch("temporal_inputs.bounds.localdate", return_value=date(2027, 1, 1)):
            self.assertIn('max="2027-12-31T23:59"', widget.render("when", None))


class SecondsTests(SimpleTestCase):
    """Test the precision of the value, and the step that has to match it."""

    def test_minute_precision_by_default(self):
        """The value renders to the minute, and no step is emitted."""
        html = DateTimeInput().render("when", datetime(2026, 8, 21, 12, 30, 45))
        self.assertIn('value="2026-08-21T12:30"', html)
        self.assertNotIn("step=", html)

    def test_seconds_are_rendered_with_a_matching_step(self):
        """
        Asking for seconds emits step="1" alongside them.

        The default step is 60, which makes any value carrying seconds a step
        mismatch: the browser marks the field invalid and refuses to submit it.
        """
        html = DateTimeInput(seconds=True).render("when", datetime(2026, 8, 21, 12, 30, 45))
        self.assertIn('value="2026-08-21T12:30:45"', html)
        self.assertIn('step="1"', html)

    def test_explicit_step_takes_precedence(self):
        """An explicit step in attrs wins over the one seconds would emit."""
        html = DateTimeInput(attrs={"step": "900"}, seconds=True).render("when", None)
        self.assertIn('step="900"', html)
        self.assertNotIn('step="1"', html)

    def test_seconds_from_a_class_attribute(self):
        """Seconds may be declared on a subclass, like the bounds."""

        class PreciseInput(DateTimeInput):
            """A datetime input that edits seconds."""

            seconds = True

        html = PreciseInput(max_datetime=date(2030, 12, 31)).render(
            "when", datetime(2026, 8, 21, 12, 30, 45)
        )
        self.assertIn('value="2026-08-21T12:30:45"', html)
        self.assertIn('max="2030-12-31T23:59:59"', html)
        self.assertIn('step="1"', html)


class ValueFormatTests(SimpleTestCase):
    """Test that the value stays in the only format the browser accepts."""

    def test_django_separates_with_a_space_in_every_locale(self):
        """
        Django writes a space where the browser requires a ``T``.

        It is what makes the datetime case worse than the date case: its own
        widget separates with a space under every locale it ships, English
        included, so the field renders empty everywhere rather than only where
        the locale is non-ISO.
        """
        when = datetime(2026, 8, 21, 12, 30)
        self.assertIn('value="2026-08-21T12:30"', DateTimeInput().render("when", when))
        self.assertIn('value="2026-08-21 12:30:00"', DjangoDateTimeInput().render("when", when))

    def test_value_stays_iso_under_a_localised_language(self):
        """Under a non-ISO locale the value must still render as ISO 8601."""
        when = datetime(2026, 8, 21, 12, 30)
        with translation.override("it"):
            ours = DateTimeInput().render("when", when)
            theirs = DjangoDateTimeInput().render("when", when)
        self.assertIn('value="2026-08-21T12:30"', ours)
        self.assertIn('value="21/08/2026 12:30:00"', theirs)

    def test_format_is_not_configurable(self):
        """The format is fixed at ISO 8601 rather than merely defaulted to it."""
        with self.assertRaises(TypeError):
            DateTimeInput(format="%d/%m/%Y %H:%M")

    def test_format_cannot_be_passed_positionally(self):
        """Django's signature takes ``format`` second; ours takes nothing there."""
        with self.assertRaises(TypeError):
            DateTimeInput({}, "%d/%m/%Y %H:%M")


class DateTimeFieldIntegrationTests(SimpleTestCase):
    """Test the whole round trip through a model form, not just the markup."""

    def test_initial_value_from_an_instance_is_iso(self):
        """A form built from an instance renders that instance's value as ISO."""
        form = BookingForm(instance=Booking(starts_at=datetime(2026, 8, 21, 12, 30)))
        self.assertIn('value="2026-08-21T12:30"', str(form["starts_at"]))

    def test_submitted_iso_value_validates(self):
        """The value the browser submits is the value Django parses."""
        form = BookingForm({"starts_at": "2026-08-21T12:30"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["starts_at"],
            timezone.make_aware(datetime(2026, 8, 21, 12, 30)),
        )

    def test_round_trip_under_a_localised_language(self):
        """Render then re-submit under the locale that motivates the package."""
        starts_at = datetime(2026, 8, 21, 12, 30)
        with translation.override("it"):
            html = str(BookingForm(instance=Booking(starts_at=starts_at))["starts_at"])
            rendered = re.search(r'value="([^"]*)"', html)
            self.assertIsNotNone(rendered)
            self.assertEqual(rendered[1], "2026-08-21T12:30")

            form = BookingForm({"starts_at": rendered[1]})
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["starts_at"], timezone.make_aware(starts_at))


@override_settings(DATETIME_INPUT_FORMATS=["%d/%m/%Y %H:%M"])
class DateTimeInputFormatsTests(SimpleTestCase):
    """Test that nothing a project configures can stop ISO from parsing."""

    def test_iso_parses_even_where_the_date_equivalent_would_not(self):
        """
        ``DATETIME_INPUT_FORMATS`` cannot break ISO parsing at all.

        This is the one asymmetry worth knowing about: ``DateTimeField.to_python``
        runs ``parse_datetime()`` — which accepts the ``T`` separator — before it
        ever reaches the input format list, so ISO parses even under a language
        Django ships no format module for, where the same override does break a
        ``DateField``.
        """
        with translation.override("af"):
            form = BookingForm({"starts_at": "2026-08-21T12:30"})
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(
                form.cleaned_data["starts_at"],
                timezone.make_aware(datetime(2026, 8, 21, 12, 30)),
            )
