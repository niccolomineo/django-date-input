"""Models backing the integration tests."""

from django.db import models


class Booking(models.Model):
    """A booking, for exercising each widget through a real model form."""

    starts_on = models.DateField()
    starts_at = models.DateTimeField()
    opens_at = models.TimeField()

    def __str__(self) -> str:
        """Return the booking's date in ISO 8601."""
        return self.starts_on.isoformat()
