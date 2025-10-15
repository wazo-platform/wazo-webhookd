# Copyright 2023-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from unittest.mock import Mock, patch, sentinel

import pytest
import requests
from flask_restful import Api
from xivo.rest_api_helpers import APIException

from ....rest_api import VERSION
from ..http import NotificationResource


@patch('wazo_webhookd.plugins.mobile.http.Tenant')
def test_verify_user_uuid(mock_tenant: Mock) -> None:
    mock_tenant.autodetect.return_value = Mock(uuid=sentinel.tenant)
    mock_auth_client = Mock()
    mock_auth_client.users.get.return_value = {
        'enabled': True,
        'tenant_uuid': sentinel.tenant,
    }

    resource = NotificationResource({'auth': {}}, mock_auth_client)  # type: ignore
    resource.verify_user_uuid(sentinel.user_uuid)

    mock_auth_client.users.get.assert_called_once_with(sentinel.user_uuid)


@patch('wazo_webhookd.plugins.mobile.http.Tenant')
def test_verify_user_wrong_tenant_uuid(mock_tenant: Mock) -> None:
    mock_tenant.autodetect.return_value = Mock(uuid=sentinel.tenant)
    mock_auth_client = Mock()
    mock_auth_client.users.get.return_value = {
        'enabled': True,
        'tenant_uuid': 'invalid-tenant',
    }

    resource = NotificationResource({'auth': {}}, mock_auth_client)  # type: ignore
    with pytest.raises(APIException):
        resource.verify_user_uuid(sentinel.user_uuid)

    mock_auth_client.users.get.assert_called_once_with(sentinel.user_uuid)


@patch('wazo_webhookd.plugins.mobile.http.Tenant')
def test_verify_user_uuid_invalid(mock_tenant: Mock) -> None:
    mock_tenant.autodetect.return_value = Mock(uuid=sentinel.tenant)
    mock_auth_client = Mock()
    mock_auth_client.users.get.side_effect = requests.HTTPError(  # type: ignore
        request=Mock(status_code=401)
    )

    resource = NotificationResource({'auth': {}}, mock_auth_client)  # type: ignore
    with pytest.raises(APIException):
        resource.verify_user_uuid(sentinel.user_uuid)

    mock_auth_client.users.get.assert_called_once_with(sentinel.user_uuid)


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
            resource_class_args=[test_config, Mock()],
        )
        client = api.app.test_client()
        response = client.post(
            f'/{VERSION}/mobile/notifications',
            json={},
        )
        assert response.status_code == 204, response.text
        assert response.data == b''

    mock_verify.called_once_with(sentinel.user_uuid)
    mock_send_notification.apply_async.called_once_with(
        args=(test_config, {}),
        retry=True,
        retry_policy={'max_retries': 1},
    )
