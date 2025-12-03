# Copyright 2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from ..plugin import build_content_type_header, parse_content_type


def test_build_content_type_header_with_single_option():
    mimetype = 'application/json'
    options = {'charset': 'utf-8'}

    result = build_content_type_header(mimetype, options)

    assert result == 'application/json; charset=utf-8'


def test_build_content_type_header_with_multiple_options():
    mimetype = 'multipart/form-data'
    options = {
        'charset': 'utf-8',
        'boundary': 'test-boundary-123',
        'version': '1.0',
    }

    result = build_content_type_header(mimetype, options)

    assert result == (
        'multipart/form-data; charset=utf-8; boundary=test-boundary-123; version=1.0'
    )


def test_build_content_type_header_with_empty_options():
    mimetype = 'text/plain'
    options: dict[str, str] = {}

    result = build_content_type_header(mimetype, options)

    assert result == 'text/plain'


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
    # valueless parameters are ignored
    (
        'text/html; charset',
        ('text/html', {}),
    ),
]


@pytest.mark.parametrize('header,expected', CONTENT_TYPES)
def test_parse_content_type(header, expected):
    expected_content_type, expected_params = expected
    content_type, params = parse_content_type(header)
    assert content_type == expected_content_type
    assert params == expected_params
