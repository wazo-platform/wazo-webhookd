# Copyright 2022-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import iso8601
import logging
import requests

from datetime import datetime, timezone, timedelta
from functools import partial
from requests.exceptions import HTTPError

from .log import TeamsLogAdapter

MICROSOFT_GRAPH = 'https://graph.microsoft.com/v1.0'
DEFAULT_EXPIRATION = 3600  # 1hr
DEFAULT_LEEWAY = 600  # 10m


logger = TeamsLogAdapter(logging.getLogger(__name__), {})


class HTTPHelper:
    @classmethod
    async def _crud(cls, method, url, *, json=None, headers=None):
        loop = asyncio.get_event_loop()
        fn = partial(getattr(requests, method), url, json=json, headers=headers)

        response = await loop.run_in_executor(None, fn)
        return response

    @classmethod
    async def get(cls, url, headers=None):
        return await cls._crud('get', url, headers=headers)

    @classmethod
    async def post(cls, url, json, headers=None):
        return await cls._crud('post', url, json=json, headers=headers)

    @classmethod
    async def patch(cls, url, json, headers=None):
        return await cls._crud('patch', url, json=json, headers=headers)

    @classmethod
    async def delete(cls, url, json, headers=None):
        return await cls._crud('delete', url, json=json, headers=headers)


class TeamsSubscriptionRewewer:
    def __init__(self, config, microsoft_token):
        self._token = microsoft_token
        self._subscription_id = None
        self._expiration = 0
        self._stopped = asyncio.Event()
        self._task = None
        self._domain = config['domain']
        self._teams = {
            'userid': config['microsoft_user_id'],
            'tenantid': config['microsoft_tenant_id'],
            'appid': config['microsoft_app_id'],
        }
        self._wazo = {
            'user_uuid': config['user_uuid'],
            'tenant_uuid': config['tenant_uuid'],
        }

    @property
    def _headers(self):
        return {
            'Authorization': f'Bearer {self._token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

    def notification_url(self, user_uuid):
        return f'https://{self._domain}/api/chatd/1.0/users/{user_uuid}/teams/presence'

    def url(self, *fragments):
        return '/'.join([MICROSOFT_GRAPH, *fragments])

    def remaining_time(self):
        if not self._expiration:
            return 0
        now = datetime.now(timezone.utc)
        expires_at = iso8601.parse_date(self._expiration)
        return (expires_at - now).total_seconds()

    async def start(self):
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._run(expiration=60, leeway=15))
        logger.info(
            f'subscription renewer started for user `{self._wazo["user_uuid"]}`'
        )

    async def stop(self):
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            logger.debug(
                f'subscription renewer cancelled for user `{self._wazo["user_uuid"]}`'
            )
        await self.unsubscribe()
        logger.info(
            f'subscription renewer terminated for user `{self._wazo["user_uuid"]}`'
        )

    async def _run(self, *, expiration=DEFAULT_EXPIRATION, leeway=DEFAULT_LEEWAY):
        try:
            await self.subscribe(expiration=expiration)
        except HTTPError:
            logger.error(
                f'subscription renewer failed to create subscription for user `{self._wazo["user_uuid"]}, cancelling...'
            )
            return

        while True:
            duration = self.remaining_time() - leeway
            if duration > 0:
                await asyncio.sleep(duration)
            try:
                await self.renew(expiration=expiration)
            except HTTPError:
                logger.error(
                    f'subscription renewer failed to renew subscription for user `{self._wazo["user_uuid"]}`'
                )
                return

    async def set_presence(self, state):
        pass

    async def get_presence(self):
        pass

    async def reset_presence(self):
        pass

    async def subscribe(self, *, expiration=DEFAULT_EXPIRATION):
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expiration)
        data = {
            'changeType': 'updated',
            'resource': f'/communications/presences/{self._teams["userid"]}',
            'notificationUrl': self.notification_url(self._wazo['user_uuid']),
            'expirationDateTime': expires_at.isoformat().replace('+00:00', 'Z'),
            'clientState': 'wazo-teams-integration',
        }

        response = await HTTPHelper.post(
            self.url('subscriptions'), json=data, headers=self._headers
        )

        if response.status_code == 409:  # subscription already exists
            return await self.find_subscription()

        if response.status_code == 400:
            logger.error(
                'failed to create subscription (stack is not accessible from the internet)'
            )
        response.raise_for_status()

        payload = response.json()
        self._subscription_id = payload['id']
        self._expiration = payload['expirationDateTime']
        logger.debug(
            f'created subscription `{self._subscription_id}` (expires in {self.remaining_time()})'
        )

    async def renew(self, *, expiration=DEFAULT_EXPIRATION):
        if not self._subscription_id:
            raise ValueError('requires a valid subscription_id')

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expiration)
        data = {'expirationDateTime': expires_at.isoformat().replace('+00:00', 'Z')}

        url = self.url('subscriptions', self._subscription_id)
        response = await HTTPHelper.patch(url, data, headers=self._headers)

        if response.status_code != 200:  # something happened, handle it!
            response.raise_for_status()

        logger.debug(
            f'renewed subscription `{self._subscription_id}` (expires in {self.remaining_time()})'
        )
        self._expiration = response.json()['expirationDateTime']

        return response.status_code == 200

    async def unsubscribe(self):
        if not self._subscription_id:
            return

        url = self.url('subscriptions', self._subscription_id)
        response = await HTTPHelper.delete(url, headers=self._headers)

        if response.status_code != 204:
            response.raise_for_status()
        logger.debug(f'removed subscription `{self._subscription_id}`')

    async def find_subscription(self):
        url = self.url('subscriptions')
        response = await HTTPHelper.get(url, headers=self._headers)

        if response.status_code != 200:
            response.raise_for_status()

        data = response.json()['value'][0]
        self._subscription_id = data['id']
        self._expiration = data['expirationDateTime']
        logger.debug(
            f'using subscription `{self._subscription_id}` (expires in {self.remaining_time()})'
        )
