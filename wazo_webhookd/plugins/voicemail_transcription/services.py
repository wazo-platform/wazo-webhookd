# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import requests

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = logging.getLogger(__name__)

UC_SUBSCRIPTION_TYPE = 1


def get_auth_token(auth_config: Mapping[str, Any]) -> str:
    from wazo_auth_client import Client as AuthClient

    config = dict(auth_config)
    config['verify_certificate'] = False
    auth = AuthClient(**config)
    token_data = auth.token.new('wazo_user', expiration=3600)
    return token_data['token']


def user_has_uc_license(
    confd_config: Mapping[str, Any], user_uuid: str, token: str
) -> bool:
    scheme = 'https' if confd_config.get('https') else 'http'
    host = confd_config['host']
    port = confd_config['port']
    url = f'{scheme}://{host}:{port}/1.1/users/{user_uuid}'

    response = requests.get(
        url,
        headers={'X-Auth-Token': token},
        verify=confd_config.get('verify_certificate', False),
    )
    response.raise_for_status()

    user_data = response.json()
    subscription_type = user_data.get('subscription_type')
    has_license = subscription_type == UC_SUBSCRIPTION_TYPE
    logger.debug(
        'User %s subscription_type=%s, has_uc_license=%s',
        user_uuid,
        subscription_type,
        has_license,
    )
    return has_license


def fetch_voicemail_recording(
    calld_config: Mapping[str, Any],
    voicemail_id: int,
    message_id: str,
    token: str,
) -> bytes:
    scheme = 'https' if calld_config.get('https') else 'http'
    host = calld_config['host']
    port = calld_config['port']
    url = (
        f'{scheme}://{host}:{port}/1.0'
        f'/voicemails/{voicemail_id}/messages/{message_id}/recording'
    )

    response = requests.get(
        url,
        headers={'X-Auth-Token': token},
        verify=calld_config.get('verify_certificate', False),
    )
    response.raise_for_status()
    return response.content


def submit_transcription_job(service_url: str, audio_data: bytes) -> str:
    url = f'{service_url}/jobs'
    response = requests.post(
        url,
        data=audio_data,
        headers={'Content-Type': 'application/octet-stream'},
    )
    response.raise_for_status()

    result = response.json()
    return result['job_id']


def get_transcription_result(service_url: str, job_id: str) -> dict[str, Any]:
    url = f'{service_url}/jobs/{job_id}'
    response = requests.get(url)
    response.raise_for_status()
    return response.json()
