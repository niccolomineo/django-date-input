"""Tests for the native date input widget."""

import re
from datetime import date
from unittest.mock import patch

from django import forms
from django.forms.widgets import DateInput as DjangoDateInput
from django.test import SimpleTestCase, override_settings
from django.utils import translation

from temporal_inputs import DateInput, end_of_year, start_of_year
from tests.models import Booking


class BookingForm(forms.ModelForm):
    """A model form wiring the widget to a real model ``DateField``."""

    class Meta:
        """Bind the widget to the model's date field."""

        model = Booking
        fields = ["starts_on"]
        widgets = {"starts_on": DateInput()}


class DateInputTests(SimpleTestCase):
    """Test the rendered markup and the bound handling."""

    def test_renders_native_date_input(self):
        """The widget renders type="date" rather than Django's default text input."""
        self.assertIn('type="date"', DateInput().render("when", None))
        self.assertIn('type="text"', DjangoDateInput().render("when", None))

    def test_no_bounds_by_default(self):
        """Without bounds, no min or max attribute is emitted."""
        html = DateInput().render("when", None)
        self.assertNotIn("min=", html)
        self.assertNotIn("max=", html)

    def test_date_bounds(self):
        """Plain date bounds are rendered as ISO dates."""
        html = DateInput(min_date=date(2020, 1, 1), max_date=date(2030, 12, 31)).render(
            "when", None
        )
        self.assertIn('min="2020-01-01"', html)
        self.assertIn('max="2030-12-31"', html)

    def test_only_one_bound(self):
        """A lower bound alone does not imply an upper bound."""
        html = DateInput(min_date=date(2020, 1, 1)).render("when", None)
        self.assertIn('min="2020-01-01"', html)
        self.assertNotIn("max=", html)

    def test_callable_bounds(self):
        """Callable bounds are resolved and rendered."""
        with patch("temporal_inputs.bounds.localdate", return_value=date(2026, 8, 19)):
            html = DateInput(min_date=start_of_year(-1), max_date=end_of_year(5)).render(
                "when", None
            )
        self.assertIn('min="2025-01-01"', html)
        self.assertIn('max="2031-12-31"', html)

    def test_callable_bounds_resolved_at_every_render(self):
        """
        A callable bound tracks the current date across renders.

        This is the whole reason bounds resolve in ``get_context`` rather than in
        ``__init__``: a worker booted in December must not keep serving last
        year's upper bound after midnight on 1 January.
        """
        widget = DateInput(max_date=end_of_year())
        with patch("temporal_inputs.bounds.localdate", return_value=date(2026, 12, 31)):
            self.assertIn('max="2026-12-31"', widget.render("when", None))
        with patch("temporal_inputs.bounds.localdate", return_value=date(2027, 1, 1)):
            self.assertIn('max="2027-12-31"', widget.render("when", None))

    def test_callable_bound_must_return_a_date(self):
        """
        A callable returning anything but a ``date`` fails at render time.

        The type hint is the whole contract — no runtime validation is worth the
        complexity here — so this test is what makes the requirement explicit.
        """
        with self.assertRaises(AttributeError):
            DateInput(max_date=lambda: "2030-12-31").render("when", None)

    def test_bounds_from_class_attributes(self):
        """Bounds may be declared on a subclass instead of passed in."""

        class BookingDateInput(DateInput):
            """A date input bounded to the booking window."""

            min_date = date(2020, 1, 1)
            max_date = date(2030, 12, 31)

        html = BookingDateInput().render("when", None)
        self.assertIn('min="2020-01-01"', html)
        self.assertIn('max="2030-12-31"', html)

    def test_explicit_attrs_take_precedence(self):
        """An explicit min or max in attrs wins over the configured bound."""
        html = DateInput(
            attrs={"min": "1999-01-01", "max": "1999-12-31"},
            min_date=date(2020, 1, 1),
            max_date=date(2030, 12, 31),
        ).render("when", None)
        self.assertIn('min="1999-01-01"', html)
        self.assertIn('max="1999-12-31"', html)
        self.assertNotIn("2020-01-01", html)
        self.assertNotIn("2030-12-31", html)


class ValueFormatTests(SimpleTestCase):
    """Test that the value stays in the only format the browser accepts."""

    def test_value_is_iso_by_default(self):
        """The value renders as ISO 8601."""
        self.assertIn('value="2026-08-19"', DateInput().render("when", date(2026, 8, 19)))

    def test_value_stays_iso_under_a_localised_language(self):
        """
        Under a non-ISO locale the value must still render as ISO 8601.

        ``<input type="date">`` parses nothing else, so a localised value leaves
        the field silently blank. Django's own widget localises it; ours does not.
        """
        with translation.override("it"):
            ours = DateInput().render("when", date(2026, 8, 19))
            theirs = DjangoDateInput().render("when", date(2026, 8, 19))
        self.assertIn('value="2026-08-19"', ours)
        self.assertIn('value="19/08/2026"', theirs)

    def test_format_is_not_configurable(self):
        """
        The format is fixed at ISO 8601 rather than merely defaulted to it.

        Any other format renders a widget that fails as an HTML5 date input,
        which is precisely what this one exists to prevent.
        """
        with self.assertRaises(TypeError):
            DateInput(format="%d/%m/%Y")

    def test_format_cannot_be_passed_positionally(self):
        """
        Django's signature takes ``format`` second; ours takes nothing there.

        The bounds are keyword-only so that a positional format raises instead of
        quietly binding a format string to ``min_date``.
        """
        with self.assertRaises(TypeError):
            DateInput({}, "%d/%m/%Y")


class DateFieldIntegrationTests(SimpleTestCase):
    """
    Test the whole round trip through a model form, not just the markup.

    The package promises more than correct rendering: it promises that Django
    takes the rendered value back again.
    """

    def test_initial_value_from_an_instance_is_iso(self):
        """A form built from an instance renders that instance's date as ISO."""
        form = BookingForm(instance=Booking(starts_on=date(2026, 8, 19)))
        self.assertIn('value="2026-08-19"', str(form["starts_on"]))

    def test_submitted_iso_value_validates(self):
        """The value the browser submits is the value Django parses."""
        form = BookingForm({"starts_on": "2026-08-19"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["starts_on"], date(2026, 8, 19))

    def test_round_trip_under_a_localised_language(self):
        """
        Render then re-submit under the locale that motivates the package.

        Italian is the README's example: Django's own widget would emit
        ``19/08/2026`` here, which no browser can parse back into the field.
        """
        starts_on = date(2026, 8, 19)
        with translation.override("it"):
            html = str(BookingForm(instance=Booking(starts_on=starts_on))["starts_on"])
            rendered = re.search(r'value="([^"]*)"', html)
            self.assertIsNotNone(rendered)
            self.assertEqual(rendered[1], "2026-08-19")

            form = BookingForm({"starts_on": rendered[1]})
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["starts_on"], starts_on)


@override_settings(DATE_INPUT_FORMATS=["%d/%m/%Y"])
class DateInputFormatsTests(SimpleTestCase):
    """
    Test what a custom ``DATE_INPUT_FORMATS`` really does to ISO parsing.

    ``override_settings`` fires ``setting_changed``, which Django wires to
    ``reset_format_cache()`` for every format setting, so the module-level
    format cache cannot leak between these tests.
    """

    def test_iso_survives_a_custom_date_input_formats_setting(self):
        """
        Dropping ISO from the setting does not break parsing, for most languages.

        ``formats.get_format()`` appends its own ``ISO_INPUT_FORMATS`` to any
        list a locale format module supplies, and Django ships a format module
        defining ``DATE_INPUT_FORMATS`` for all but one of its locales. For those
        languages the setting is ignored outright and ISO always parses.
        """
        form = BookingForm({"starts_on": "2026-08-19"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["starts_on"], date(2026, 8, 19))

    def test_iso_must_be_kept_when_the_language_has_no_format_module(self):
        """
        The setting only bites when no format module supplies the key.

        That means a language Django ships no ``formats.py`` for — Afrikaans,
        Armenian, Malay and a couple of dozen others. There the setting is
        authoritative and Django never re-adds ISO, so an ISO-less
        ``DATE_INPUT_FORMATS`` really does break the submitted value.
        """
        with translation.override("af"):
            self.assertFalse(BookingForm({"starts_on": "2026-08-19"}).is_valid())

            form = BookingForm({"starts_on": "19/08/2026"})
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["starts_on"], date(2026, 8, 19))
