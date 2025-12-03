# Copyright 2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase

from ..plugin import build_content_type_header, parse_content_type


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

        assert result == 'text/plain'


class TestParseContentType(TestCase):
    CONTENT_TYPES = [
        # with charset
        (
            'text/html; charset=utf-8',
            ('text/html', {'charset': 'utf-8'}),
        ),
        # with boundary
        (
            'multipart/form-data; boundary=ExampleBoundaryString',
            ('multipart/form-data', {'boundary': 'ExampleBoundaryString'}),
        ),
        # weird casing
        (
            'TEXT/html; CHarSeT=utf-8',
            ('text/html', {'charset': 'utf-8'}),
        ),
        # multiple parameters
        (
            'multipart/form-data; boundary=ExampleBoundaryString; charset=utf-8',
            (
                'multipart/form-data',
                {'boundary': 'ExampleBoundaryString', 'charset': 'utf-8'},
            ),
        ),
    ]

    def test_parse_content_type(self):
        for header, (expected_content_type, expected_params) in self.CONTENT_TYPES:
            content_type, params = parse_content_type(header)
            assert content_type == expected_content_type
            assert params == expected_params
