# Copyright 2017-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase

from ..plugin import build_content_type_header


class TestBuildContentTypeHeader(TestCase):
    def test_with_single_option(self):
        mimetype = 'application/json'
        options = {'charset': 'utf-8'}

        result = build_content_type_header(mimetype, options)

        assert result == 'application/json; charset=utf-8'

    def test_with_multiple_options(self):
        mimetype = 'multipart/form-data'
        options = {
            'charset': 'utf-8',
            'boundary': 'test-boundary-123',
            'version': '1.0',
        }

        result = build_content_type_header(mimetype, options)

        assert (
            result
            == 'multipart/form-data; charset=utf-8; boundary=test-boundary-123; version=1.0'
        )

    def test_with_empty_options(self):
        mimetype = 'text/plain'
        options: dict[str, str] = {}

        result = build_content_type_header(mimetype, options)

        assert result == 'text/plain; '
