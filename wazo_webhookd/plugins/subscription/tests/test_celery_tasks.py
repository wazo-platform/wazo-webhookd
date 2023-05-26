# Copyright 2017-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that
from unittest import TestCase

from ..celery_tasks import truncated


class TestCeleryTasks(TestCase):
    def test_str_truncated(self):
        assert_that(truncated("foo"), "foo")

    def test_str_not_truncated(self):
        body = "123" * 250
        assert_that(truncated(body), f"{body[:250]} ... [truncated]")

    def test_dict_truncated(self):
        body = "123" * 250
        assert_that(
            truncated({"foo": body}),
            f"{{'foo': {body[:250]}}} ... [truncated]",
        )

    def test_dict_not_truncated(self):
        assert_that(truncated({"foo": "bar"}), "{'foo': 'bar'")

    def test_none(self):
        assert_that(truncated(None), "None")
