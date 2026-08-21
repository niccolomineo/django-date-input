"""Bound types, and helpers for the bounds that move with the calendar."""

from collections.abc import Callable
from datetime import date, datetime, time

from django.utils.timezone import localdate

type DateBound = date | Callable[[], date] | None
type DateTimeBound = datetime | date | Callable[[], datetime | date] | None
type TimeBound = time | Callable[[], time] | None
type Bound = DateBound | DateTimeBound | TimeBound


def start_of_year(offset: int = 0) -> Callable[[], date]:
    """Return a callable giving 1 January, ``offset`` years from the current year."""
    return lambda: date(localdate().year + offset, 1, 1)


def end_of_year(offset: int = 0) -> Callable[[], date]:
    """Return a callable giving 31 December, ``offset`` years from the current year."""
    return lambda: date(localdate().year + offset, 12, 31)
