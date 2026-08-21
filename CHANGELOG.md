# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-08-21

### Added

- `DateInput`, `DateTimeInput` and `TimeInput`: the three HTML5 input types Django ships no widget for, rendering `type="date"`, `type="datetime-local"` and `type="time"` where Django's own widgets render `type="text"`.
- A value fixed at ISO 8601 on all three. Django localises the value it renders and these input types parse nothing else, so under a non-ISO locale the field renders blank while the value sits in the database. The datetime case is worse and locale-independent: Django separates the date from the time with a space, and `<input type="datetime-local">` requires a `T`, so its value is unparsable even in English. The format is not configurable — a non-ISO one would leave the widget silently broken, which is the thing these widgets exist to prevent.
- Optional lower and upper bounds, named after the thing being bounded — `min_date`, `min_datetime`, `min_time` and their `max` counterparts — accepted per instance or declared on a subclass, as either a value or a zero-argument callable returning one. Callables resolve at render time, so a bound derived from the current date stays correct in a long-running process. An explicit `min` or `max` in `attrs` always wins.
- Aware datetime bounds converted to the current timezone. `DateTimeField.prepare_value` hands the widget a naive local value, so a bound left in UTC would sit a timezone offset away from the value it bounds.
- Date bounds on `DateTimeInput` covering the whole of the day they name — midnight for a lower bound, the last minute for an upper one. A date silently meaning midnight would exclude that entire day from an upper bound, and it makes `end_of_year()` usable as a datetime bound.
- `seconds=True` on `DateTimeInput` and `TimeInput`, which renders seconds and emits the `step="1"` they require. The browser's default step is 60, which makes a value carrying seconds a step mismatch: the field is marked invalid and constraint validation refuses to submit the form. Left off, the value renders to the minute.
- `start_of_year` and `end_of_year` helpers for bounds relative to the current year.
- A PEP 561 `py.typed` marker. The package is fully annotated, and without the marker type checkers treat every import from it as `Any`, so none of the annotations — including the bound aliases that document what a callable bound must return — reach the people using it.
- Tests covering all three widgets end to end through model forms: initial value from an instance, submitted value parsed back, and the render-then-resubmit round trip under a localised language. The full Python 3.12–3.14 × Django 5.2/6.0/6.1 matrix runs in CI with the coverage threshold enforced at 100%.
- Tests pinning what the input-format settings actually do, which differs by field. `DateTimeField` cannot be broken at all: its `to_python()` runs `parse_datetime()`, which accepts the `T` separator, before consulting `DATETIME_INPUT_FORMATS`. `DateField` and `TimeField` parse through their format lists, and `get_format()` re-appends its own ISO entries to any list a locale format module supplies — so for all but a handful of bundled locales the setting cannot break ISO parsing either. It is authoritative only under a language Django ships no `formats.py` for.
