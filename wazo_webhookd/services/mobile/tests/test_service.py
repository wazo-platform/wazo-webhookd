# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import pytest
import requests

from wazo_webhookd.services.helpers import HookRetry

from ..plugin import EMPTY_EXTERNAL_CONFIG, Service

if TYPE_CHECKING:
    from wazo_webhookd.database.models import Subscription


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


def _reset_service_cache():
    Service._auth_cache = None
    Service._auth_cache_expires_at = 0.0
    Service._auth_url_base = None


def _prime_cache(base_url='https://localhost:9497/0.1'):
    mock_client = _make_mock_auth_client(base_url=base_url)
    with patch(
        'wazo_webhookd.services.mobile.plugin.AuthClient', return_value=mock_client
    ):
        Service.get_auth(_make_config())
    return mock_client


class TestGetAuthCaching:
    def setup_method(self):
        _reset_service_cache()

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


class TestIsCachedAuth401:
    """The discriminator used by get_external_data and Service.run."""

    def setup_method(self):
        _reset_service_cache()

    def test_true_when_401_targets_cached_auth_base_url(self):
        _prime_cache(base_url='https://localhost:9497/0.1')
        exc = _make_http_error(401, 'https://localhost:9497/0.1/users/abc')

        assert Service.is_cached_auth_401(exc) is True

    def test_false_when_401_from_unrelated_host(self):
        _prime_cache(base_url='https://localhost:9497/0.1')
        exc = _make_http_error(
            401, 'https://fcm.googleapis.com/v1/projects/x/messages:send'
        )

        assert Service.is_cached_auth_401(exc) is False

    def test_false_when_status_is_not_401(self):
        _prime_cache()
        exc = _make_http_error(500, 'https://localhost:9497/0.1/users/abc')

        assert Service.is_cached_auth_401(exc) is False

    def test_false_when_no_cache_base_url(self):
        # cache never primed -> _auth_url_base is None
        exc = _make_http_error(401, 'https://localhost:9497/0.1/users/abc')

        assert Service.is_cached_auth_401(exc) is False

    def test_false_after_invalidation_even_if_url_matches(self):
        # A 401 escaping from a fresh-mint path (e.g. token.new rejected for
        # bad service credentials) must not be classified as a cached-auth
        # race once the cache has been dropped — otherwise Service.run would
        # raise HookRetry and burn hook_max_attempts against a permanent
        # credential failure.
        _prime_cache(base_url='https://localhost:9497/0.1')
        Service.invalidate_auth_cache()
        exc = _make_http_error(401, 'https://localhost:9497/0.1/token')

        assert Service.is_cached_auth_401(exc) is False

    def test_false_when_url_only_overlaps_prefix(self):
        # base 'https://host/0.1' must NOT match e.g. '/0.10' coexisting
        _prime_cache(base_url='https://localhost:9497/0.1')
        exc = _make_http_error(401, 'https://localhost:9497/0.10/users/abc')

        assert Service.is_cached_auth_401(exc) is False


class TestInvalidateAuthCache:
    def setup_method(self):
        _reset_service_cache()

    def test_clears_state(self):
        _prime_cache()
        assert Service._auth_cache is not None
        assert Service._auth_url_base is not None

        Service.invalidate_auth_cache()

        assert Service._auth_cache is None
        assert Service._auth_cache_expires_at == 0.0
        assert Service._auth_url_base is None


class TestGetExternalData:
    """get_external_data retries inline on cached-auth 401."""

    def setup_method(self):
        _reset_service_cache()

    def test_inline_retries_on_cached_auth_401(self):
        """First call returns 401 from cached auth; cache invalidated; second
        call mints a fresh token and succeeds."""
        stale_client = _prime_cache(base_url='https://localhost:9497/0.1')
        stale_client.external.get.side_effect = _make_http_error(
            401, 'https://localhost:9497/0.1/users/user-1/external/mobile'
        )

        fresh_client = _make_mock_auth_client(jwt='fresh-jwt')
        fresh_client.external.get.return_value = {'token': 'tok'}
        fresh_client.users.get.return_value = {'tenant_uuid': 'tenant-1'}
        fresh_client.external.get_config.side_effect = _make_http_error(
            404, 'https://localhost:9497/0.1/external/mobile/config'
        )

        # After invalidate_auth_cache, get_auth instantiates a new AuthClient.
        with patch(
            'wazo_webhookd.services.mobile.plugin.AuthClient',
            return_value=fresh_client,
        ):
            external_tokens, external_config, jwt = Service.get_external_data(
                _make_config(), 'user-1'
            )

        assert external_tokens == {'token': 'tok'}
        assert external_config == EMPTY_EXTERNAL_CONFIG
        assert jwt == 'fresh-jwt'
        # cache re-primed with fresh client
        assert Service._auth_cache == (fresh_client, 'fresh-jwt')

    def test_persistent_cached_auth_401_propagates(self):
        """Both attempts return 401 → HTTPError propagates; cache cleared."""
        stale_client = _prime_cache(base_url='https://localhost:9497/0.1')
        stale_client.external.get.side_effect = _make_http_error(
            401, 'https://localhost:9497/0.1/users/user-1/external/mobile'
        )

        # Fresh client returned by get_auth's re-mint also fails with 401.
        fresh_client = _make_mock_auth_client()
        fresh_client.external.get.side_effect = _make_http_error(
            401, 'https://localhost:9497/0.1/users/user-1/external/mobile'
        )

        with patch(
            'wazo_webhookd.services.mobile.plugin.AuthClient',
            return_value=fresh_client,
        ):
            with pytest.raises(requests.HTTPError):
                Service.get_external_data(_make_config(), 'user-1')

        # last attempt's failure left the cache primed with the fresh client;
        # an external caller (Service.run -> HookRetry, or send_notification
        # -> task.retry) is responsible for any further recovery.
        assert Service._auth_cache == (fresh_client, 'test-jwt')

    def test_propagates_non_401_without_invalidation(self):
        mock_client = _prime_cache(base_url='https://localhost:9497/0.1')
        mock_client.external.get.side_effect = _make_http_error(
            500, 'https://localhost:9497/0.1/users/user-1/external/mobile'
        )

        with pytest.raises(requests.HTTPError):
            Service.get_external_data(_make_config(), 'user-1')

        # cache still primed
        assert Service._auth_cache is not None

    def test_external_config_404_falls_back_to_empty(self):
        mock_client = _prime_cache()
        mock_client.external.get.return_value = {'token': 'tok'}
        mock_client.users.get.return_value = {'tenant_uuid': 'tenant-1'}
        mock_client.external.get_config.side_effect = _make_http_error(
            404, 'https://localhost:9497/0.1/external/mobile/config'
        )

        external_tokens, external_config, jwt = Service.get_external_data(
            _make_config(), 'user-1'
        )

        assert external_config == EMPTY_EXTERNAL_CONFIG
        assert external_tokens == {'token': 'tok'}
        # cache untouched: 404 is not the cached-auth-401 signal
        assert Service._auth_cache is not None

    def test_external_config_non_404_propagates(self):
        mock_client = _prime_cache()
        mock_client.external.get.return_value = {'token': 'tok'}
        mock_client.users.get.return_value = {'tenant_uuid': 'tenant-1'}
        mock_client.external.get_config.side_effect = _make_http_error(
            500, 'https://localhost:9497/0.1/external/mobile/config'
        )

        with pytest.raises(requests.HTTPError):
            Service.get_external_data(_make_config(), 'user-1')


class TestServiceRunAuthRetry:
    """Service.run converts cached-auth 401 into HookRetry for hook_runner_task."""

    def setup_method(self):
        _reset_service_cache()

    def _run(self):
        task = MagicMock()
        subscription = cast('Subscription', {'events_user_uuid': 'user-1'})
        event = {'name': 'user_missed_call', 'data': {'user_uuid': 'user-1'}}
        return Service.run(task, _make_config(), subscription, event)

    def test_cached_auth_401_raises_hook_retry(self):
        _prime_cache(base_url='https://localhost:9497/0.1')
        with patch.object(
            Service,
            'get_external_data',
            side_effect=_make_http_error(
                401, 'https://localhost:9497/0.1/users/user-1/external/mobile'
            ),
        ):
            with pytest.raises(HookRetry):
                self._run()

    def test_non_cached_auth_401_propagates_as_http_error(self):
        _prime_cache(base_url='https://localhost:9497/0.1')
        with patch.object(
            Service,
            'get_external_data',
            side_effect=_make_http_error(
                401, 'https://fcm.googleapis.com/v1/projects/x/messages:send'
            ),
        ):
            with pytest.raises(requests.HTTPError):
                self._run()

    def test_non_401_http_error_propagates_as_http_error(self):
        _prime_cache()
        with patch.object(
            Service,
            'get_external_data',
            side_effect=_make_http_error(
                500, 'https://localhost:9497/0.1/users/user-1/external/mobile'
            ),
        ):
            with pytest.raises(requests.HTTPError):
                self._run()
