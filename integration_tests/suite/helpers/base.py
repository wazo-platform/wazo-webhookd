# Copyright 2017-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import random
import string
from contextlib import contextmanager

import requests
import yaml
from wazo_test_helpers import until
from wazo_test_helpers.asset_launching_test_case import AssetLaunchingTestCase
from wazo_test_helpers.auth import AuthClient, MockCredentials, MockUserToken
from wazo_test_helpers.bus import BusClient
from wazo_test_helpers.filesystem import FileSystemClient
from wazo_webhookd_client import Client as WebhookdClient

from .wait_strategy import WaitStrategy

WAZO_UUID = '00000000-0000-4000-8000-00003eb8004d'

MASTER_TOKEN = '00000000-0000-4000-8000-000000000101'
MASTER_TENANT = '00000000-0000-4000-8000-000000000201'
MASTER_USER_UUID = '00000000-0000-4000-8000-000000000301'

USERS_TENANT = '00000000-0000-4000-8000-000000000202'
USER_1_UUID = '00000000-0000-4000-8000-000000000302'
USER_1_TOKEN = '00000000-0000-4000-8000-000000000102'
USER_2_UUID = '00000000-0000-4000-8000-000000000303'
USER_2_TOKEN = '00000000-0000-4000-8000-000000000103'

OTHER_TENANT = '00000000-0000-4000-8000-000000000204'
OTHER_USER_UUID = '00000000-0000-4000-8000-000000000304'
OTHER_USER_TOKEN = '00000000-0000-4000-8000-000000000204'

JWT_TENANT_0 = 'master-tenant-jwt-token'
JWT_TENANT_1 = 'first-tenant-jwt-token'
JWT_TENANT_2 = 'second-tenant-jwt-token'

START_TIMEOUT = int(os.environ.get('INTEGRATION_TEST_TIMEOUT', '30'))
PRIVATE_KEY = (
    "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQClXvUW41FSxPQ4"
    "\nA0fZXePX2bMThU1aRQet2jrsItGxpsjUTQJQya12PYvvFzJfonZ1l7H2m/abyXCB\nxftED5l5mBjntvWOWswieKTX9"
    "PZDdLkMPWu1kwPKTxR1IqEQBI+xUicf/sW8jTH+\nEt1jo6dxwigYFjE8VKnlJyt/prqSUMN2lu6M8sHv+5jvUbSpiV4L"
    "rOW5h/9zvDYM\ni9InElVNAC1Sd029/iDaqgJ8eTiX8Bhqop48fi2xPJ90xnvYlmXwJUkhXwFOyp7j\nKFzig9vW07cJL"
    "5zQlGiEZLwJc5pbNo3kVfJUgeofSI6omy0kA/gxC/FwcBX4is+N\niemJvEiHAgMBAAECggEAA+eTEXng8+HzAwn1l1Ww"
    "YuqHLOdrC4rK6WyLeZ0Oc6Ur\nFsAriG0xBRqwHb9GRDXMzQf9senxNhc/UQEaTRTlNcn4KvhwVQhVy5Aq329JC6l+\ne"
    "QiDBr2BS5r3mH07bYP+DimRA1NiDddzniEjf9r5KCZCb7DBptmegIRrpYIlSf3h\nqWpbzOWxsXZ+Q/hWzMge0Yx14KAt"
    "XmT4s8YPRIFfs1g1f/1SgUJSiIFgUJAg271b\n+CoM39fLhKiL2ujHkoRsjsmjFIeGw+zVvw7MDwlC8CR3hnIO5RuEE7S"
    "yEoRPzbJp\nQavGZLE1XT7moYGAiE4Uo7DL6qRXY6WEgIMKJs7RcQKBgQDWL8EVggeeb4vmCA9O\nXy3U1lqz8By47bua"
    "12oSv2fNt1RKx+yx8VQicNxApfTBNnZ93IzQ+WFWkI+dgsLI\ncHh0dZcXHP+Cl2OFXGZ6acueFYDuEjb2NmFuSH8gf8J"
    "0kmOu1PDFZ7pOYYLoL+LS\na/daFe4cLPc4icg/tju4VqMVbwKBgQDFp5ShFP6hArz4efhBPso/YMkKmLznZpyq\nTfyu"
    "vAh2/PQKvjiJCrL2PGwcpA0uca9i6f/spaLzkwQ1SdLZinZwzGpZoPF2ZyG8\nZu+xIdgs2L+qZ/f/tp6lylggv0OCCB5"
    "AwTQg+BhusyxXjl7g9G6qc9GheY+fysrg\nG2jiLZxiaQKBgQDQL6iY1EO9jyTHGWxvO/pbV2LgZXI1mfXxIpLa2Cr4fM"
    "q0yTDb\nIPwrYdHkEKsfJmX0HmzNLqibMHY3noLfutqKMEYE1E3SzH2Sgeal87FT3gjs3s2H\ncgIv5M2UdDo5fpTfueC"
    "xsAoZ55QLRYhOCV1qtcg0oMxHqzz2GJZhrexkhwKBgAdN\nMoNk2Ccwh7SSJOacIDKJK8QVcl0GAGGWMfBuh82FeKpw7n"
    "u5hnTsNH42XTpK/tSj\nmk2urL9cvfoN+RkKMWfnVUJsXJ8oHinsj4w2mNrHQwVTg+jRYTj0qZ7EEgVasWto\n97kEETr"
    "9qXSukLi0ruXjE2poqDKZ9jajLJO2ZaGJAoGBAMQkdVvRIWxqstdPped5\nF+HYgQ2rZP2NgL+ea+cIwoc5IoOQkYrDVZ"
    "8P7GwuDUxB+YixjUKsEMkm7/xll3dA\nHvtK7wIl5mQe2OqP2tnf2Un8ofVPYtAWXL8vRXcgaVgnN7BQamB6820ENy7uX"
    "yZ3\nXVb1NZEIb9zqNmoTihJX33lV\n-----END PRIVATE KEY-----\n"
)

SOME_ROUTING_KEY = 'routing-key'


class BaseIntegrationTest(AssetLaunchingTestCase):
    assets_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'assets')
    )
    service = 'webhookd'
    wait_strategy = WaitStrategy()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        webhookd = cls.make_webhookd(MASTER_TOKEN)
        if cls.asset in ("proxy", "base"):
            cls.configured_wazo_auth()
            cls.docker_exec(['wazo-webhookd-init-amqp', '--host', 'rabbitmq'])
        cls.wait_strategy.wait(webhookd)

    def setUp(self):
        if self.asset == "base":
            webhookd = self.make_webhookd(MASTER_TOKEN)
            subs = webhookd.subscriptions.list(recurse=True)['items']
            for sub in subs:
                webhookd = self.make_webhookd(
                    MASTER_TOKEN, tenant=sub["owner_tenant_uuid"]
                )
                webhookd.subscriptions.delete(sub["uuid"])
                self.ensure_webhookd_not_consume_subscription(sub)

    @classmethod
    def make_webhookd(cls, token, tenant=None, **kwargs):
        return WebhookdClient(
            '127.0.0.1',
            cls.service_port(9300, 'webhookd'),
            prefix=None,
            https=False,
            token=token,
            tenant=tenant,
            **kwargs,
        )

    @classmethod
    def make_auth(cls):
        return AuthClient('127.0.0.1', cls.service_port(9497, 'auth'))

    @classmethod
    def configured_wazo_auth(cls):
        auth = cls.make_auth()
        credential = MockCredentials('webhookd-service', 'webhookd-password')
        auth.set_valid_credentials(credential, MASTER_TOKEN)
        auth.set_token(
            MockUserToken(
                MASTER_TOKEN,
                MASTER_USER_UUID,
                WAZO_UUID,
                {
                    "tenant_uuid": MASTER_TENANT,
                    "uuid": MASTER_USER_UUID,
                    'jwt': JWT_TENANT_0,
                },
            )
        )
        auth.set_token(
            MockUserToken(
                USER_1_TOKEN,
                USER_1_UUID,
                WAZO_UUID,
                {
                    "tenant_uuid": USERS_TENANT,
                    "uuid": USER_1_UUID,
                    'jwt': JWT_TENANT_1,
                },
            )
        )
        auth.set_token(
            MockUserToken(
                USER_2_TOKEN,
                USER_2_UUID,
                WAZO_UUID,
                {
                    "tenant_uuid": USERS_TENANT,
                    "uuid": USER_2_UUID,
                    'jwt': JWT_TENANT_1,
                },
            )
        )
        auth.set_token(
            MockUserToken(
                OTHER_USER_TOKEN,
                OTHER_USER_UUID,
                WAZO_UUID,
                {
                    "tenant_uuid": OTHER_TENANT,
                    "uuid": OTHER_USER_UUID,
                    'jwt': JWT_TENANT_2,
                },
            )
        )
        auth.set_tenants(
            {
                'uuid': MASTER_TENANT,
                'name': 'webhookd-tests-master',
                'parent_uuid': MASTER_TENANT,
            },
            {
                'uuid': USERS_TENANT,
                'name': 'webhookd-tests-users',
                'parent_uuid': MASTER_TENANT,
            },
            {
                'uuid': OTHER_TENANT,
                'name': 'webhookd-tests-other',
                'parent_uuid': MASTER_TENANT,
            },
        )

    def make_bus(self):
        port = self.service_port(5672, 'rabbitmq')
        return BusClient.from_connection_fields(
            host='127.0.0.1',
            port=port,
            exchange_name='wazo-headers',
            exchange_type='headers',
        )

    def make_sentinel(self):
        class Sentinel:
            def __init__(self, url):
                self._url = url

            def bindings(self):
                response = requests.get(self._url, verify=False)
                response.raise_for_status()
                return response.json()['bindings']

            def called(self):
                response = requests.get(self._url, verify=False)
                response.raise_for_status()
                return response.json()['called']

            def reset(self):
                requests.delete(self._url, verify=False)

        url = f'http://127.0.0.1:{self.service_port(9300, "webhookd")}/1.0/sentinel'
        return Sentinel(url)

    def _has_subscription_bindings(self, subscription, bindings):
        events_count = len(subscription['events'])
        bindings_count = len(
            [binding for binding in bindings if binding['uuid'] == subscription['uuid']]
        )
        return bindings_count == events_count

    def ensure_webhookd_consume_subscription(self, subscription):
        sentinel = self.make_sentinel()

        def subscribed():
            try:
                bindings = sentinel.bindings()
            except requests.exceptions.ConnectionError:
                return False

            return self._has_subscription_bindings(subscription, bindings)

        until.true(subscribed, timeout=10, interval=0.5)

    def ensure_webhookd_not_consume_subscription(self, subscription):
        sentinel = self.make_sentinel()

        def unsubscribed():
            try:
                bindings = sentinel.bindings()
            except requests.exceptions.ConnectionError:
                return False

            return not self._has_subscription_bindings(subscription, bindings)

        until.true(unsubscribed, timeout=10, interval=0.5)

    @contextmanager
    def auth_stopped(self):
        self.stop_service('auth')
        yield
        self.start_service('auth')
        auth = self.make_auth()
        until.true(
            auth.is_up, timeout=START_TIMEOUT, message='wazo-auth did not come back up'
        )
        self.configured_wazo_auth()

    @contextmanager
    def rabbitmq_stopped(self):
        self.stop_service('rabbitmq')
        yield
        self.start_service('rabbitmq')
        bus = self.make_bus()
        until.true(
            bus.is_up, timeout=START_TIMEOUT, message='rabbitmq did not come back up'
        )

    @classmethod
    @contextmanager
    def webhookd_with_config(cls, config):
        filesystem = FileSystemClient(
            execute=cls.docker_exec,
            service_name='webhookd',
            root=True,
        )
        name = ''.join(random.choice(string.ascii_lowercase) for _ in range(6))
        config_file = f'/etc/wazo-webhookd/conf.d/10-{name}.yml'
        content = yaml.dump(config)
        try:
            with filesystem.file_(config_file, content=content):
                cls.restart_service('webhookd')
                yield
        finally:
            cls.restart_service('webhookd')
            webhookd = cls.make_webhookd(MASTER_TOKEN)
            cls.wait_strategy.wait(webhookd)

    def _make_http_request(
        self, verb: str, endpoint: str, body: str | None, headers: dict = None
    ):
        port = self.service_port(9300, 'webhookd')
        base_url = f'http://127.0.0.1:{port}/1.0/'
        default_headers = {
            'X-Auth-Token': MASTER_TOKEN,
        }
        req_headers = default_headers if not headers else headers

        match verb.lower():
            case 'patch':
                call = requests.patch
            case 'post':
                call = requests.post
            case 'put':
                call = requests.put
            case _:
                raise ValueError('An unexpected http verb was given')

        return call(
            base_url + endpoint,
            headers=req_headers,
            data=body,
            verify=False,
        )

    def assert_empty_body_returns_400(self, urls: list[tuple[str, str]]):
        for method, url in urls:
            response = self._make_http_request(method, url, '')
            assert response.status_code == 400, f'Error with url: ({method}) {url}'

            response = self._make_http_request(method, url, None)
            assert response.status_code == 400, f'Error with url: ({method}) {url}'
