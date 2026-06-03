# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import MagicMock, patch

from ..plugin import Service


def _make_config():
    return {
        'auth': {
            'host': 'localhost',
            'username': 'webhookd-service',
            'password': 'secret',
        }
    }


def _make_mock_auth_client(jwt='test-jwt'):
    mock_client = MagicMock()
    mock_client.token.new.return_value = {
        'token': 'wazo-token-uuid',
        'metadata': {'jwt': jwt},
    }
    return mock_client


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
