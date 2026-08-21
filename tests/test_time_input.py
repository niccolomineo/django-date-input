"""Tests for the native time input widget."""

import re
from datetime import time

from django import forms
from django.forms.widgets import TimeInput as DjangoTimeInput
from django.test import SimpleTestCase, override_settings
from django.utils import translation

from temporal_inputs import TimeInput
from tests.models import Booking


class BookingForm(forms.ModelForm):
    """A model form wiring the widget to a real model ``TimeField``."""

    class Meta:
        """Bind the widget to the model's time field."""

        model = Booking
        fields = ["opens_at"]
        widgets = {"opens_at": TimeInput()}


class TimeInputTests(SimpleTestCase):
    """Test the rendered markup and the bound handling."""

    def test_renders_native_time_input(self):
        """The widget renders type="time" rather than Django's default text input."""
        self.assertIn('type="time"', TimeInput().render("when", None))
        self.assertIn('type="text"', DjangoTimeInput().render("when", None))

    def test_no_bounds_by_default(self):
        """Without bounds, no min or max attribute is emitted."""
        html = TimeInput().render("when", None)
        self.assertNotIn("min=", html)
        self.assertNotIn("max=", html)

    def test_time_bounds(self):
        """Time bounds render at the same precision as the value."""
        html = TimeInput(min_time=time(9, 0), max_time=time(17, 30)).render("when", None)
        self.assertIn('min="09:00"', html)
        self.assertIn('max="17:30"', html)

    def test_only_one_bound(self):
        """A lower bound alone does not imply an upper bound."""
        html = TimeInput(min_time=time(9, 0)).render("when", None)
        self.assertIn('min="09:00"', html)
        self.assertNotIn("max=", html)

    def test_callable_bounds(self):
        """A bound may be any zero-argument callable returning a time."""
        html = TimeInput(max_time=lambda: time(17, 30)).render("when", None)
        self.assertIn('max="17:30"', html)

    def test_bounds_from_class_attributes(self):
        """Bounds may be declared on a subclass instead of passed in."""

        class OpeningHoursInput(TimeInput):
            """A time input bounded to opening hours."""

            min_time = time(9, 0)
            max_time = time(17, 30)

        html = OpeningHoursInput().render("when", None)
        self.assertIn('min="09:00"', html)
        self.assertIn('max="17:30"', html)

    def test_explicit_attrs_take_precedence(self):
        """An explicit min or max in attrs wins over the configured bound."""
        html = TimeInput(
            attrs={"min": "00:15", "max": "23:45"},
            min_time=time(9, 0),
            max_time=time(17, 30),
        ).render("when", None)
        self.assertIn('min="00:15"', html)
        self.assertIn('max="23:45"', html)
        self.assertNotIn("09:00", html)
        self.assertNotIn("17:30", html)


class SecondsTests(SimpleTestCase):
    """Test the precision of the value, and the step that has to match it."""

    def test_minute_precision_by_default(self):
        """The value renders to the minute, and no step is emitted."""
        html = TimeInput().render("when", time(12, 30, 45))
        self.assertIn('value="12:30"', html)
        self.assertNotIn("step=", html)

    def test_seconds_are_rendered_with_a_matching_step(self):
        """Asking for seconds emits step="1" alongside them."""
        html = TimeInput(seconds=True, max_time=time(17, 30, 15)).render("when", time(12, 30, 45))
        self.assertIn('value="12:30:45"', html)
        self.assertIn('max="17:30:15"', html)
        self.assertIn('step="1"', html)


class ValueFormatTests(SimpleTestCase):
    """Test that the value stays in the only format the browser accepts."""

    def test_value_is_iso_by_default(self):
        """The value renders as ISO 8601."""
        self.assertIn('value="12:30"', TimeInput().render("when", time(12, 30)))

    def test_the_bundled_locales_happen_not_to_break_django_here(self):
        """
        Unlike the date and datetime cases, localisation alone is not the bug.

        Every locale Django bundles defines an ISO-compatible first
        ``TIME_INPUT_FORMATS`` entry, so its own widget emits a value
        ``<input type="time">`` can parse. What this widget rules out is the
        configuration that does break it, tested below.
        """
        with translation.override("it"):
            self.assertIn('value="12:30"', TimeInput().render("when", time(12, 30)))
            self.assertIn('value="12:30:00"', DjangoTimeInput().render("when", time(12, 30)))

    @override_settings(TIME_INPUT_FORMATS=["%I:%M %p"])
    def test_a_non_iso_setting_breaks_django_but_not_this_widget(self):
        """
        A 12-hour first format renders a value the browser cannot parse.

        Under a language Django ships no format module for, the setting is
        authoritative and no ISO format is appended to it — so Django's widget
        emits ``12:30 PM`` while this one still emits ``12:30``.
        """
        with translation.override("af"):
            self.assertIn('value="12:30"', TimeInput().render("when", time(12, 30)))
            self.assertIn('value="12:30 PM"', DjangoTimeInput().render("when", time(12, 30)))

    def test_format_is_not_configurable(self):
        """The format is fixed at ISO 8601 rather than merely defaulted to it."""
        with self.assertRaises(TypeError):
            TimeInput(format="%I:%M %p")

    def test_format_cannot_be_passed_positionally(self):
        """Django's signature takes ``format`` second; ours takes nothing there."""
        with self.assertRaises(TypeError):
            TimeInput({}, "%I:%M %p")


class TimeFieldIntegrationTests(SimpleTestCase):
    """Test the whole round trip through a model form, not just the markup."""

    def test_initial_value_from_an_instance_is_iso(self):
        """A form built from an instance renders that instance's time as ISO."""
        form = BookingForm(instance=Booking(opens_at=time(9, 30)))
        self.assertIn('value="09:30"', str(form["opens_at"]))

    def test_submitted_iso_value_validates(self):
        """The value the browser submits is the value Django parses."""
        form = BookingForm({"opens_at": "09:30"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["opens_at"], time(9, 30))

    def test_round_trip_under_a_localised_language(self):
        """Render then re-submit under a localised language."""
        opens_at = time(9, 30)
        with translation.override("it"):
            html = str(BookingForm(instance=Booking(opens_at=opens_at))["opens_at"])
            rendered = re.search(r'value="([^"]*)"', html)
            self.assertIsNotNone(rendered)
            self.assertEqual(rendered[1], "09:30")

            form = BookingForm({"opens_at": rendered[1]})
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["opens_at"], opens_at)


@override_settings(TIME_INPUT_FORMATS=["%I:%M %p"])
class TimeInputFormatsTests(SimpleTestCase):
    """Test what a custom ``TIME_INPUT_FORMATS`` really does to ISO parsing."""

    def test_iso_survives_a_custom_time_input_formats_setting(self):
        """
        Dropping ISO from the setting does not break parsing, for most languages.

        ``formats.get_format()`` appends its own ISO input formats to any list a
        locale format module supplies, and Django ships one for all but a handful
        of its locales. For those languages the setting is ignored outright.
        """
        form = BookingForm({"opens_at": "09:30"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["opens_at"], time(9, 30))

    def test_iso_must_be_kept_when_the_language_has_no_format_module(self):
        """
        Time parses like a date, not like a datetime.

        ``TimeField.to_python`` has no ISO fast path of the kind
        ``DateTimeField`` gets from ``parse_datetime()``, so under a language
        with no format module an ISO-less setting really does break the submitted
        value — keep the ISO entry if that is your ``LANGUAGE_CODE``.
        """
        with translation.override("af"):
            self.assertFalse(BookingForm({"opens_at": "09:30"}).is_valid())

            form = BookingForm({"opens_at": "09:30 AM"})
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["opens_at"], time(9, 30))
