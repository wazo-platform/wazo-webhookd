from datetime import datetime, timezone
from unittest import TestCase

from ..plugin import generate_timestamp


class TestGenerateTimestamp(TestCase):
    def test_generate_timestamp(self):
        pre_time = datetime.now(tz=timezone.utc)
        timestamp = generate_timestamp()
        post_time = datetime.now(tz=timezone.utc)

        assert isinstance(timestamp, str)
        timestamp_datetime = datetime.fromisoformat(timestamp)

        assert timestamp_datetime.tzinfo is timezone.utc
        assert pre_time <= timestamp_datetime <= post_time
