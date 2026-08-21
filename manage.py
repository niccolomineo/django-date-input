"""Django management script for development and testing."""

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")

from django.core.management import execute_from_command_line


def main() -> None:
    """Run administrative tasks."""
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
