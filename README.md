# django-temporal-inputs

[![PyPI](https://img.shields.io/pypi/v/django-temporal-inputs?label=pypi)](https://pypi.org/project/django-temporal-inputs/)
[![Python](https://img.shields.io/pypi/pyversions/django-temporal-inputs?label=python)](https://pypi.org/project/django-temporal-inputs/)
[![Django](https://img.shields.io/pypi/frameworkversions/django/django-temporal-inputs?label=django)](https://pypi.org/project/django-temporal-inputs/)
[![CI](https://github.com/niccolomineo/django-temporal-inputs/actions/workflows/ci.yml/badge.svg)](https://github.com/niccolomineo/django-temporal-inputs/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/django-temporal-inputs?label=license)](LICENSE)

Native **HTML5 date, datetime and time input** widgets for Django, with optional
lower and upper bounds.

Requires Python 3.12 or newer and Django 5.2 LTS or newer. Every supported
combination — Python 3.12/3.13/3.14 against Django 5.2/6.0/6.1 — is exercised
by the test suite on every push.

## The gap this fills

Django ships widgets for `text`, `number`, `email`, `url`, `color`, `search`,
`tel`, `password`, `file`, `checkbox`, `select` and `radio`. It ships none for
`date`, `datetime-local` or `time`: those three fields render as text inputs, so
the browser offers no picker, no keyboard, and no validation of its own.

| | Django's widget | this package |
| --- | --- | --- |
| `DateField` | `type="text"`, value localised | `type="date"`, value always ISO 8601 |
| `DateTimeField` | `type="text"`, date and time separated by a space | `type="datetime-local"`, separated by the `T` the browser requires |
| `TimeField` | `type="text"` | `type="time"` |

## Why not just `attrs={"type": "date"}`?

That is the answer you will find everywhere, and it gets you most of the way there:
`forms.DateInput(attrs={"type": "date"})` does render `type="date"`, and the browser
does show its own picker. The trap is the value.

These input types accept **only** ISO 8601, while Django localises the value it
renders. Under an Italian locale the date widget emits `value="21/08/2026"`, the
browser cannot parse it, and the field silently appears empty — with the date
sitting in the database the whole time. Nothing raises; the form just looks blank.

The datetime case is worse, and it is worse *everywhere*. `<input
type="datetime-local">` requires a `T` between the date and the time, and Django
writes a space under every locale it ships, English included:

```python
forms.DateTimeInput().render("starts_at", datetime(2026, 8, 21, 12, 30))
# <input type="text" name="starts_at" value="2026-08-21 12:30:00">
#                                                       ^ not a T, so: empty field
```

## Installation

```bash
pip install django-temporal-inputs
```

No `INSTALLED_APPS` entry is needed — these are widgets, not an application.

## Usage

```python
from datetime import date, datetime, time

from django import forms

from temporal_inputs import DateInput, DateTimeInput, TimeInput, end_of_year


class BookingForm(forms.Form):
    starts_on = forms.DateField(
        widget=DateInput(min_date=date(2020, 1, 1), max_date=end_of_year(5))
    )
    starts_at = forms.DateTimeField(
        widget=DateTimeInput(min_datetime=datetime(2020, 1, 1, 9, 0))
    )
    opens_at = forms.TimeField(
        widget=TimeInput(min_time=time(9, 0), max_time=time(17, 30))
    )
```

Renders as:

```html
<input type="date" name="starts_on" required id="id_starts_on" min="2020-01-01" max="2031-12-31">
<input type="datetime-local" name="starts_at" required id="id_starts_at" min="2020-01-01T09:00">
<input type="time" name="opens_at" required id="id_opens_at" min="09:00" max="17:30">
```

Bounds are optional — omit them and you get a plain native input.

### Bounds

Each widget names the pair it accepts after the thing being bounded, rather than
sharing a generic `min_value`:

| Widget | Bounds | Accepts |
| --- | --- | --- |
| `DateInput` | `min_date`, `max_date` | a `date`, or a callable returning one |
| `DateTimeInput` | `min_datetime`, `max_datetime` | a `datetime`, a `date`, or a callable returning either |
| `TimeInput` | `min_time`, `max_time` | a `time`, or a callable returning one |

They may equally be declared on a subclass:

```python
class BookingDateInput(DateInput):
    min_date = date(2020, 1, 1)
    max_date = end_of_year(5)
```

An explicit `min` or `max` in `attrs` always wins:

```python
DateInput(attrs={"min": "1999-01-01"}, min_date=date(2020, 1, 1))  # min stays 1999-01-01
```

### Relative bounds

A bound may be any zero-argument callable returning the right type. Two helpers
cover the common cases:

| Helper | Returns |
| --- | --- |
| `start_of_year(offset=0)` | 1 January, `offset` years from the current year |
| `end_of_year(offset=0)` | 31 December, `offset` years from the current year |

Callables are resolved **at render time**, not on instantiation. That matters in a
long-running process: a worker booted in December that computed its upper bound once
would keep serving last year's limit after midnight on 1 January.

```python
DateInput(min_date=start_of_year(-1), max_date=end_of_year(5))
```

Both helpers return a `date`, and `DateTimeInput` takes one as covering the whole
of the day it names — midnight for a lower bound, the last minute for an upper
one. A `date` quietly meaning midnight would exclude that entire day from an
upper bound, which is an off-by-a-day in the direction that hurts:

```python
DateTimeInput(max_datetime=end_of_year())  # max="2026-12-31T23:59", not T00:00
```

### Timezones

Nothing to configure: Django already handles this and does it correctly.
`DateTimeField.prepare_value` converts an aware value to the current timezone
before the widget sees it, and `to_python` converts a submitted naive one back —
raising a validation error for a wall clock that DST makes ambiguous or
non-existent. The widget therefore renders local wall-clock time.

An aware `datetime` given as a bound is converted the same way, so it lands on
the same clock as the value it bounds:

```python
# with TIME_ZONE = "Europe/Rome"
DateTimeInput(min_datetime=datetime(2026, 8, 21, 10, 0, tzinfo=UTC))  # min="2026-08-21T12:00"
```

### Seconds

`DateTimeInput` and `TimeInput` render to the minute by default, because that is
the precision the browser's default `step` of 60 permits. A value carrying
seconds under that step is a *step mismatch*: the browser marks the field invalid
and constraint validation refuses to submit the form. Pass `seconds=True` to
render and edit them, which emits the matching `step="1"`:

```python
TimeInput(seconds=True).render("opens_at", time(12, 30, 45))
# <input type="time" name="opens_at" value="12:30:45" step="1">
```

Leaving it off means a stored value's seconds are dropped when the form is
resubmitted. An explicit `step` in `attrs` wins over both.

### The format is fixed

There is no `format` argument on any of the three. Each input type has exactly one
value format, so offering a choice would only offer a way to break the widget:

```python
DateInput(format="%d/%m/%Y")  # TypeError
```

If you want a text input in a localised format, that is Django's own
`forms.DateInput`. These are the HTML5 inputs.

## Notes

- Bounds are a client-side convenience. Browsers block out-of-range values in the
  picker, but a crafted POST will sail past them — validate on the field too, with
  `MinValueValidator` / `MaxValueValidator` or a `clean_*` method.
- Parsing the submitted value back is sturdier than it sounds, and it is sturdy in
  three different ways:
  - `DateTimeField` cannot be broken at all. Its `to_python()` runs
    `parse_datetime()`, which accepts the `T` separator, before it ever consults
    `DATETIME_INPUT_FORMATS`.
  - `DateField` and `TimeField` parse through their format lists, and
    `get_format()` appends its own ISO entries to whatever list a locale format
    module supplies. Django ships such a module for every locale bar a handful, so
    overriding the `DATE_INPUT_FORMATS` or `TIME_INPUT_FORMATS` *setting* usually
    has no effect on ISO parsing at all.
  - The setting only becomes authoritative under a language Django ships no
    `formats.py` for (Afrikaans, Armenian, Malay and a couple of dozen others). If
    that is your `LANGUAGE_CODE` and you override either setting, keep the ISO
    entry.

## License

MIT — see [LICENSE](LICENSE).
