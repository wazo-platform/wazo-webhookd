# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import MagicMock, patch

import requests
from celery.signals import task_failure

from ..plugin import Service


def _make_config():
    return {
        'auth': {
            'host': 'localhost',
            'username': 'webhookd-service',
            'password': 'secret',
        }
    }


def _make_mock_auth_client(jwt='test-jwt', base_url='https://localhost:9497/0.1'):
    mock_client = MagicMock()
    mock_client.token.new.return_value = {
        'token': 'wazo-token-uuid',
        'metadata': {'jwt': jwt},
    }
    mock_client.url.return_value = base_url
    return mock_client


def _make_http_error(status_code, url):
    response = requests.Response()
    response.status_code = status_code
    response.url = url
    return requests.HTTPError(response=response)


class TestGetAuthCaching:
    def setup_method(self):
        Service._auth_cache = None
        Service._auth_cache_expires_at = 0.0

    def test_get_auth_creates_token_on_first_call(self):
        mock_client = _make_mock_auth_client()
        with patch(
            'wazo_webhookd.services.mobile.plugin.AuthClient', return_value=mock_client
        ):
            auth, jwt = Service.get_auth(_make_config())

        mock_client.token.new.assert_called_once_with('wazo_user', expiration=3600)
        assert jwt == 'test-jwt'
        assert auth is mock_client

    def test_get_auth_reuses_cached_token_within_ttl(self):
        mock_client = _make_mock_auth_client()
        with patch(
            'wazo_webhookd.services.mobile.plugin.AuthClient', return_value=mock_client
        ):
            auth1, jwt1 = Service.get_auth(_make_config())
            auth2, jwt2 = Service.get_auth(_make_config())

        mock_client.token.new.assert_called_once()
        assert auth1 is auth2
        assert jwt1 == jwt2

    def test_get_auth_refreshes_token_after_expiry(self):
        mock_client = _make_mock_auth_client()
        with patch(
            'wazo_webhookd.services.mobile.plugin.AuthClient', return_value=mock_client
        ):
            Service.get_auth(_make_config())  # call 1: cache miss → new token
            Service.get_auth(_make_config())  # call 2: cache hit → no new token
            Service._auth_cache_expires_at = 0.0  # simulate expiry
            Service.get_auth(_make_config())  # call 3: expired → new token

        # 2 new tokens: call 1 and call 3; call 2 was served from cache
        assert mock_client.token.new.call_count == 2


class TestAuthCacheInvalidation:
    def setup_method(self):
        Service._auth_cache = None
        Service._auth_cache_expires_at = 0.0
        Service._auth_url_base = None

    def _prime_cache(self, base_url='https://localhost:9497/0.1'):
        mock_client = _make_mock_auth_client(base_url=base_url)
        with patch(
            'wazo_webhookd.services.mobile.plugin.AuthClient', return_value=mock_client
        ):
            Service.get_auth(_make_config())
        return mock_client

    def test_invalidate_auth_cache_clears_state(self):
        self._prime_cache()
        assert Service._auth_cache is not None

        Service.invalidate_auth_cache()

        assert Service._auth_cache is None
        assert Service._auth_cache_expires_at == 0.0

    def test_task_failure_invalidates_cache_on_auth_401(self):
        self._prime_cache(base_url='https://localhost:9497/0.1')
        exc = _make_http_error(401, 'https://localhost:9497/0.1/users/abc')

        task_failure.send(sender=None, exception=exc)

        assert Service._auth_cache is None

    def test_task_failure_ignores_401_from_other_host(self):
        self._prime_cache(base_url='https://localhost:9497/0.1')
        # 401 from FCM (Google OAuth2 bearer rejected) — not our service token
        exc = _make_http_error(
            401, 'https://fcm.googleapis.com/v1/projects/x/messages:send'
        )

        task_failure.send(sender=None, exception=exc)

        assert Service._auth_cache is not None

    def test_task_failure_ignores_non_401_status(self):
        self._prime_cache()
        exc = _make_http_error(500, 'https://localhost:9497/0.1/users/abc')

        task_failure.send(sender=None, exception=exc)

        assert Service._auth_cache is not None

    def test_task_failure_ignores_non_http_error(self):
        self._prime_cache()

        task_failure.send(sender=None, exception=ValueError('boom'))

        assert Service._auth_cache is not None

    def test_task_failure_no_cache_no_crash(self):
        assert Service._auth_cache is None
        exc = _make_http_error(401, 'https://localhost:9497/0.1/users/abc')

        task_failure.send(sender=None, exception=exc)

        assert Service._auth_cache is None
