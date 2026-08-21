"""Native HTML5 temporal input widgets."""

from datetime import date, datetime, time

from django.forms.utils import to_current_timezone
from django.forms.widgets import DateInput as DjangoDateInput
from django.forms.widgets import DateTimeBaseInput
from django.forms.widgets import DateTimeInput as DjangoDateTimeInput
from django.forms.widgets import TimeInput as DjangoTimeInput

from temporal_inputs.bounds import Bound, DateBound, DateTimeBound, TimeBound

ISO_DATE = "%Y-%m-%d"
ISO_DATETIME = "%Y-%m-%dT%H:%M"
ISO_DATETIME_SECONDS = "%Y-%m-%dT%H:%M:%S"
ISO_TIME = "%H:%M"
ISO_TIME_SECONDS = "%H:%M:%S"


class TemporalInput(DateTimeBaseInput):
    """
    Shared behaviour for the native temporal inputs.

    Each subclass renders one of the HTML input types Django ships no widget for,
    fixes the value at the ISO 8601 format that input type parses, and names the
    pair of bounds it accepts. This class resolves those bounds at render time,
    renders them in the same format — and so at the same precision — as the value
    beside them, and keeps ``step`` in agreement with that precision.
    """

    seconds: bool = False

    def __init__(self, attrs: dict | None = None, *, iso_format: str) -> None:
        """
        Initialise the widget with the ISO format its value is fixed at.

        The format is a keyword argument of this class rather than of Django's,
        whose signature takes it second, so that a ``format`` passed positionally
        raises instead of quietly binding a format string to a bound.
        """
        super().__init__(attrs, iso_format)

    def bounds(self) -> tuple[Bound, Bound]:
        """Return the lower and upper bound, in that order."""
        raise NotImplementedError("Subclasses must name their pair of bounds.")

    def format_bound(self, bound: date | time, *, upper: bool) -> str:
        """Return a resolved bound in the same format as the value."""
        return bound.strftime(self.format)

    def get_context(self, name: str, value: object, attrs: dict | None) -> dict:
        """Return the widget context with the bounds and the precision resolved."""
        context = super().get_context(name, value, attrs)
        widget_attrs = context["widget"]["attrs"]
        for key, bound in zip(("min", "max"), self.bounds(), strict=True):
            if bound is None or key in widget_attrs:
                continue
            resolved = bound() if callable(bound) else bound
            widget_attrs[key] = self.format_bound(resolved, upper=key == "max")
        if self.seconds and "step" not in widget_attrs:
            # The default step is 60, which makes any value carrying seconds a step
            # mismatch: the browser marks the field invalid and constraint
            # validation refuses to submit the form.
            widget_attrs["step"] = "1"
        return context


class DateInput(TemporalInput, DjangoDateInput):
    """
    A native HTML5 date input, with optional lower and upper bounds.

    Django's own ``DateInput`` renders ``type="text"``. This one renders
    ``type="date"``, so browsers supply their date picker, and it fixes the value
    format at ISO 8601 because that is the only format ``<input type="date">``
    accepts — a localised value renders as an empty field. The format is not
    configurable: a non-ISO one would leave the widget silently broken as an
    HTML5 date input, which is the very thing this widget exists to prevent.

    Bounds are optional and may be given per instance or on a subclass. Either
    accepts a ``date`` or a zero-argument callable returning one:

        class BookingDateInput(DateInput):
            min_date = date(2020, 1, 1)
            max_date = end_of_year(5)

        DateInput(min_date=date(2020, 1, 1), max_date=end_of_year(5))

    Callables are resolved at render time, not on instantiation, so a bound
    derived from the current date stays correct in a long-running process
    instead of freezing at whatever it was when the worker booted.

    An explicit ``min`` or ``max`` in ``attrs`` always wins over a bound.
    """

    input_type = "date"
    min_date: DateBound = None
    max_date: DateBound = None

    def __init__(
        self,
        attrs: dict | None = None,
        *,
        min_date: DateBound = None,
        max_date: DateBound = None,
    ) -> None:
        """Initialise the widget, keeping any bounds for render time."""
        super().__init__(attrs, iso_format=ISO_DATE)
        if min_date is not None:
            self.min_date = min_date
        if max_date is not None:
            self.max_date = max_date

    def bounds(self) -> tuple[DateBound, DateBound]:
        """Return the configured date bounds."""
        return self.min_date, self.max_date


class DateTimeInput(TemporalInput, DjangoDateTimeInput):
    """
    A native HTML5 datetime input, with optional lower and upper bounds.

    Django's own ``DateTimeInput`` renders ``type="text"`` and separates the date
    from the time with a space. ``<input type="datetime-local">`` requires a
    ``T``, so unlike the date case that value is unparsable under *every*
    locale, English included — the field renders empty wherever it is used.

    Timezones are Django's job and it already does it: ``DateTimeField``
    converts an aware value to the current timezone before the widget sees it,
    and converts a submitted naive one back. The widget therefore renders, and
    bounds, local wall-clock time.

    Bounds accept a ``datetime``, a ``date``, or a zero-argument callable
    returning either. An aware ``datetime`` is converted to the current timezone
    rather than rendered as it stands, so it bounds the field at the wall clock
    the value beside it is shown in. A plain ``date`` covers the whole of the day
    it names — midnight for a lower bound, the last minute for an upper one —
    because a date silently meaning midnight would exclude that entire day from
    an upper bound.

    Seconds are off by default: the value renders to the minute, which is the
    precision the browser's default ``step`` permits. Pass ``seconds=True`` to
    render and edit them, which also emits ``step="1"``. Leaving it off means a
    stored value's seconds are dropped when the form is resubmitted.
    """

    input_type = "datetime-local"
    min_datetime: DateTimeBound = None
    max_datetime: DateTimeBound = None

    def __init__(
        self,
        attrs: dict | None = None,
        *,
        min_datetime: DateTimeBound = None,
        max_datetime: DateTimeBound = None,
        seconds: bool | None = None,
    ) -> None:
        """Initialise the widget, keeping any bounds for render time."""
        if seconds is not None:
            self.seconds = seconds
        super().__init__(attrs, iso_format=ISO_DATETIME_SECONDS if self.seconds else ISO_DATETIME)
        if min_datetime is not None:
            self.min_datetime = min_datetime
        if max_datetime is not None:
            self.max_datetime = max_datetime

    def bounds(self) -> tuple[DateTimeBound, DateTimeBound]:
        """Return the configured datetime bounds."""
        return self.min_datetime, self.max_datetime

    def format_bound(self, bound: date | time, *, upper: bool) -> str:
        """Return the bound as a naive datetime in the current timezone."""
        if isinstance(bound, date) and not isinstance(bound, datetime):
            last = time(23, 59, 59) if self.seconds else time(23, 59)
            bound = datetime.combine(bound, last if upper else time.min)
        return super().format_bound(to_current_timezone(bound), upper=upper)


class TimeInput(TemporalInput, DjangoTimeInput):
    """
    A native HTML5 time input, with optional lower and upper bounds.

    Django's own ``TimeInput`` renders ``type="text"``. This one renders
    ``type="time"``, so browsers supply their time picker and their own
    formatting of it — a 24-hour value is displayed as the visitor's locale
    writes the time of day, whatever it is stored and submitted as.

    Every locale Django bundles happens to define an ISO-compatible first
    ``TIME_INPUT_FORMATS`` entry, so unlike the date and datetime cases the
    localised value is not usually broken. Fixing the format still rules out the
    case that is: a custom ``TIME_INPUT_FORMATS`` setting, under a language
    Django ships no format module for, is authoritative — and a 12-hour or
    otherwise non-ISO first entry there renders a field the browser cannot parse.

    Bounds accept a ``time`` or a zero-argument callable returning one. Seconds
    are off by default; see ``DateTimeInput`` for what that means.
    """

    input_type = "time"
    min_time: TimeBound = None
    max_time: TimeBound = None

    def __init__(
        self,
        attrs: dict | None = None,
        *,
        min_time: TimeBound = None,
        max_time: TimeBound = None,
        seconds: bool | None = None,
    ) -> None:
        """Initialise the widget, keeping any bounds for render time."""
        if seconds is not None:
            self.seconds = seconds
        super().__init__(attrs, iso_format=ISO_TIME_SECONDS if self.seconds else ISO_TIME)
        if min_time is not None:
            self.min_time = min_time
        if max_time is not None:
            self.max_time = max_time

    def bounds(self) -> tuple[TimeBound, TimeBound]:
        """Return the configured time bounds."""
        return self.min_time, self.max_time
