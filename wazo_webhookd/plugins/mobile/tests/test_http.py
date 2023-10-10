# Copyright 2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from unittest.mock import sentinel, patch, Mock

import pytest
import requests
from flask_restful import Api
from xivo.rest_api_helpers import APIException

from ....rest_api import VERSION
from ..http import NotificationResource


@patch('wazo_webhookd.plugins.mobile.http.AuthClient')
@patch('wazo_webhookd.plugins.mobile.http.Tenant')
@patch('wazo_webhookd.plugins.mobile.http.get_auth_token_from_request')
def test_verify_user_uuid(
    mock_auth_from_request: Mock, mock_tenant: Mock, mock_auth_client: Mock
) -> None:
    mock_auth_from_request.return_value = sentinel.auth_token
    mock_tenant.autodetect.return_value = Mock(uuid=sentinel.tenant)
    mock_auth_client().users.get.return_value = {'enabled': True}

    resource = NotificationResource({'auth': {}})  # type: ignore
    resource.verify_user_uuid(sentinel.user_uuid)

    mock_auth_client().set_token.assert_called_once_with(sentinel.auth_token)
    mock_auth_client().users.get.assert_called_once_with(sentinel.user_uuid)


@patch('wazo_webhookd.plugins.mobile.http.AuthClient')
@patch('wazo_webhookd.plugins.mobile.http.Tenant')
@patch('wazo_webhookd.plugins.mobile.http.get_auth_token_from_request')
def test_verify_user_uuid_invalid(
    mock_auth_from_request: Mock, mock_tenant: Mock, mock_auth_client: Mock
) -> None:
    mock_auth_from_request.return_value = sentinel.auth_token
    mock_tenant.autodetect.return_value = Mock(uuid=sentinel.tenant)
    mock_auth_client().users.get.side_effect = requests.HTTPError(  # type: ignore
        request=Mock(status_code=401)
    )

    resource = NotificationResource({'auth': {}})  # type: ignore
    with pytest.raises(APIException):
        resource.verify_user_uuid(sentinel.user_uuid)

    mock_auth_client().set_token.assert_called_once_with(sentinel.auth_token)
    mock_auth_client().users.get.assert_called_once_with(sentinel.user_uuid)


@patch('wazo_webhookd.plugins.mobile.http.notification_schema')
@patch('wazo_webhookd.plugins.mobile.http.send_notification')
def test_post(
    mock_send_notification: Mock,
    mock_notification_schema: Mock,
    api: Api,
) -> None:
    mock_verify = Mock()
    mock_notification_schema.load.return_value = {'user_uuid': sentinel.user_uuid}
    test_config = {'auth': {}, 'hook_max_attempts': 1}

    with patch.multiple(
        NotificationResource, verify_user_uuid=mock_verify, method_decorators=[]
    ):
        api.add_resource(
            NotificationResource,
            '/mobile/notifications',
            resource_class_args=[test_config],
        )
        client = api.app.test_client()
        response = client.post(f'/{VERSION}/mobile/notifications', data={})
        assert response.status_code == 204
        assert response.data == b''

    mock_verify.called_once_with(sentinel.user_uuid)
    mock_send_notification.apply_async.called_once_with(
        args=(test_config, {}),
        retry=True,
        retry_policy={'max_retries': 1},
    )
