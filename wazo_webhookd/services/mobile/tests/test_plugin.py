from datetime import datetime, timezone
from unittest import TestCase

from ..plugin import generate_timestamp


class TestGenerateTimestamp(TestCase):
    def test_generate_timestamp(self):
        timestamp = generate_timestamp()

        assert isinstance(timestamp, str)
        timestamp_datetime = datetime.fromisoformat(timestamp)

        assert timestamp_datetime.tzinfo is timezone.utc

    def test_generate_timestamp_from_datetime(self):
        now = datetime.now()
        timestamp = generate_timestamp(now=now)

        assert isinstance(timestamp, str)
        timestamp_datetime = datetime.fromisoformat(timestamp)

        assert timestamp_datetime == now
