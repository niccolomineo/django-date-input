"""Native HTML5 temporal input widgets for Django."""

from temporal_inputs.bounds import (
    Bound,
    DateBound,
    DateTimeBound,
    TimeBound,
    end_of_year,
    start_of_year,
)
from temporal_inputs.widgets import DateInput, DateTimeInput, TimeInput

__version__ = "1.0.0"

__all__ = [
    "Bound",
    "DateBound",
    "DateInput",
    "DateTimeBound",
    "DateTimeInput",
    "TimeBound",
    "TimeInput",
    "end_of_year",
    "start_of_year",
]
