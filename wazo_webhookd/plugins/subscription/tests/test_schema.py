# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from marshmallow import ValidationError
from hamcrest import (
    assert_that,
    calling,
    equal_to,
    not_,
    has_key,
    has_entry,
    raises,
)
from unittest import TestCase
from werkzeug.datastructures import MultiDict

from ..schema import subscription_schema
from ..schema import subscription_list_params_schema

VALID_SUBSCRIPTION = {
    'name': 'test',
    'service': 'http',
    'events': ['test'],
    'config': {
        'url': 'http://example.com/test?test=test',
        'method': 'get',
    }
}


class TestSubscriptionSchema(TestCase):

    def setUp(self):
        self.schema = subscription_schema

    def test_given_uuid_when_load_then_uuid_ignored(self):
        subscription = dict(VALID_SUBSCRIPTION)
        subscription['uuid'] = 'e6a8f1e0-c09f-4f4c-b7de-7e937c7773ee'

        result = self.schema.load(subscription).data

        assert_that(result, not_(has_key('uuid')))

    def test_given_unknown_service_when_load_then_options_are_left_untouched(self):
        subscription = dict(VALID_SUBSCRIPTION)
        subscription['service'] = 'unknown'
        subscription['config'] = {
            'unknown_config': 'value'
        }

        assert_that(subscription_schema.load(subscription).data, has_entry('config', subscription['config']))

    def test_given_unknown_service_and_non_dict_config_when_load_then_raise(self):
        subscription = dict(VALID_SUBSCRIPTION)
        subscription['service'] = 'unknown'
        subscription['config'] = ['element', 'element']

        assert_that(calling(subscription_schema.load).with_args(subscription),
                    raises(ValidationError))

    def test_given_unknown_service_and_non_dict_of_string_config_when_load_then_raise(self):
        subscription = dict(VALID_SUBSCRIPTION)
        subscription['service'] = 'unknown'
        subscription['config'] = {
            'unknown_config': ['element', 'element']
        }

        assert_that(calling(subscription_schema.load).with_args(subscription),
                    raises(ValidationError))

    def test_given_unknown_service_and_config_key_too_long_when_load_then_raise(self):
        subscription = dict(VALID_SUBSCRIPTION)
        subscription['service'] = 'unknown'
        subscription['config'] = {
            'k' * 129: 'value',
        }

        assert_that(calling(subscription_schema.load).with_args(subscription),
                    raises(ValidationError))

    def test_given_unknown_service_and_config_value_too_long_when_load_then_raise(self):
        subscription = dict(VALID_SUBSCRIPTION)
        subscription['service'] = 'unknown'
        subscription['config'] = {
            'unknown_config': 'v' * 2049,
        }

        assert_that(calling(subscription_schema.load).with_args(subscription),
                    raises(ValidationError))

    def test_given_invalid_service_when_load_then_raise(self):
        subscription = dict(VALID_SUBSCRIPTION)
        subscription['service'] = {'invalid': 'invalid'}

        assert_that(calling(subscription_schema.load).with_args(subscription),
                    raises(ValidationError))

    def test_given_http_service_and_url_with_no_dots_when_load_then_pass(self):
        subscription = dict(VALID_SUBSCRIPTION)
        subscription['config'] = dict(VALID_SUBSCRIPTION['config'])
        subscription['config']['url'] = 'http://third-party-http/test'

        assert_that(calling(subscription_schema.load).with_args(subscription),
                    not_(raises(ValidationError)))

    def test_given_http_service_and_verify_certificate_none_when_load_then_pass(self):
        subscription = dict(VALID_SUBSCRIPTION)
        subscription['config'] = dict(VALID_SUBSCRIPTION['config'])
        subscription['config']['verify_certificate'] = 'true'

        assert_that(calling(subscription_schema.load).with_args(subscription),
                    not_(raises(ValidationError)))

    def test_given_http_service_and_verify_certificate_bool_when_load_then_pass(self):
        subscription = dict(VALID_SUBSCRIPTION)
        subscription['config'] = dict(VALID_SUBSCRIPTION['config'])
        subscription['config']['verify_certificate'] = 'true'

        assert_that(calling(subscription_schema.load).with_args(subscription),
                    not_(raises(ValidationError)))

    def test_given_http_service_and_verify_certificate_string_when_load_then_pass(self):
        subscription = dict(VALID_SUBSCRIPTION)
        subscription['config'] = dict(VALID_SUBSCRIPTION['config'])
        subscription['config']['verify_certificate'] = '/some/path'

        assert_that(calling(subscription_schema.load).with_args(subscription),
                    not_(raises(ValidationError)))

    def test_given_http_service_and_verify_certificate_wrong_value_when_load_then_fail(self):
        subscription = dict(VALID_SUBSCRIPTION)
        subscription['config'] = dict(VALID_SUBSCRIPTION['config'])
        subscription['config']['verify_certificate'] = 'wrong'

        assert_that(calling(subscription_schema.load).with_args(subscription),
                    raises(ValidationError))

    def test_given_http_service_and_body_none_when_load_then_body_stripped(self):
        subscription = dict(VALID_SUBSCRIPTION)
        subscription['config'] = dict(VALID_SUBSCRIPTION['config'])
        subscription['config']['body'] = None

        result = subscription_schema.load(subscription)

        assert_that(result.data['config'], not_(has_key('body')))

    def test_given_invalid_method_when_load_then_fail(self):
        subscription = dict(VALID_SUBSCRIPTION)
        subscription['config'] = dict(VALID_SUBSCRIPTION['config'])
        subscription['config']['method'] = 'invalid'

        assert_that(calling(subscription_schema.load).with_args(subscription),
                    raises(ValidationError))

    def test_given_http_service_when_load_then_method_case_ignored(self):
        subscription = dict(VALID_SUBSCRIPTION)
        subscription['config'] = dict(VALID_SUBSCRIPTION['config'])
        subscription['config']['method'] = 'POST'

        result = subscription_schema.load(subscription)

        assert_that(result.data['config'], has_entry('method', 'post'))


class TestSubscriptionListParamsSchema(TestCase):

    def test_given_multiple_search_metadata_when_load_then_one_dict(self):
        params = MultiDict([('search_metadata', 'key1:value1'),
                            ('search_metadata', 'key2:value2')])

        result = subscription_list_params_schema.load(params)

        assert_that(result.data['search_metadata'], equal_to({'key1': 'value1', 'key2': 'value2'}))
