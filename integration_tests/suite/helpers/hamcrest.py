import datetime

import hamcrest.core.base_matcher


class ATimestamp(hamcrest.core.base_matcher.BaseMatcher):
    def _matches(self, item):
        try:
            datetime.datetime.fromisoformat(item)
            return True
        except (ValueError, TypeError):
            return False

    def describe_to(self, description):
        description.append_text('a valid iso-formatted date string')


def a_timestamp():
    return ATimestamp()
