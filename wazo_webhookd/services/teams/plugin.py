# Copyright 2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import json
import logging

from base64 import b64decode
from typing import Coroutine, Dict
from requests.exceptions import HTTPError

from wazo_auth_client import Client as AuthClient
from wazo_confd_client import Client as ConfdClient
from wazo_webhookd.asyncio_ import CoreAsyncio
from wazo_webhookd.bus import BusConsumer
from wazo_webhookd.services.helpers import HookExpectedError

from .log import TeamsLogAdapter
from .subscriptions import TeamsSubscriptionRewewer


logger = TeamsLogAdapter(logging.getLogger(__name__), {})


class Service:
    _clients = {}

    def load(self, dependencies):
        bus: BusConsumer = dependencies['bus_consumer']
        self._aio: CoreAsyncio = dependencies['core_asyncio']
        self._config: Dict = dependencies['config']

        token_change_subscribe = dependencies['token_change_subscribe']
        token_change_subscribe(self.auth.set_token)
        token_change_subscribe(self.confd.set_token)

        self._synchronizers: Dict[str, TeamsSubscriptionRewewer] = {}

        self._subscribe(
            bus, 'auth_user_external_auth_added', self.on_external_auth_added
        )
        self._subscribe(
            bus, 'auth_user_external_auth_deleted', self.on_external_auth_deleted
        )

    def _subscribe(self, bus: BusConsumer, event_name: str, handler: Coroutine):
        def dispatch(payload):
            self._aio.schedule_coroutine(handler(payload))

        dispatch.__name__ = handler.__name__
        bus.subscribe(event_name, dispatch)

    @property
    def auth(self):
        if 'auth' not in self._clients:
            config = self._config['auth'].copy()
            config['verify_certificate'] = False
            self._clients['auth'] = AuthClient(**config)
        return self._clients['auth']

    @property
    def confd(self):
        if 'confd' not in self._clients:
            if 'confd' not in self._config:
                raise Exception(
                    'wazo-confd is not configured properly for teams integration'
                )
            config = self._config['confd']
            self._clients['confd'] = ConfdClient(**config)
        return self._clients['confd']

    async def on_external_auth_added(self, payload):
        user_uuid, auth_name = payload['data'].values()

        if auth_name != 'microsoft':
            logger.debug('ignoring non-microsoft external auth')
            return

        tenant_uuid = payload['tenant_uuid']

        await asyncio.sleep(1)  # FIXME: avoids race-condition
        try:
            token, config = await self.get_external_data(tenant_uuid, user_uuid)
        except Exception:
            logger.exception('exception occured!')

        try:
            self._synchronizers[user_uuid] = synchronizer = TeamsSubscriptionRewewer(
                config, token
            )
            await synchronizer.start()
        except Exception:
            logger.exception('exception occured!')

    async def on_external_auth_deleted(self, payload):
        user_uuid, auth_name = payload['data'].values()

        if auth_name != 'microsoft':
            logger.debug('ignoring non-microsoft external auth')
            return

        if user_uuid not in self._synchronizers:
            logger.info(f'no synchronizer running for user {user_uuid}')
            return

        try:
            synchronizer = self._synchronizers.pop(user_uuid)
            await synchronizer.stop()
        except Exception:
            logger.exception('exception occured!')

    async def get_external_data(self, tenant_uuid, user_uuid):
        fetch = self._aio.fetch

        try:
            token = await fetch(
                self.auth.external.get, 'microsoft', user_uuid, tenant_uuid
            )
        except HTTPError:
            raise HookExpectedError(
                f'couldn\'t find any `Microsoft` token for user {user_uuid}'
            )

        payload = await self._decode_access_token(token['access_token'])

        try:
            config = await fetch(
                self.auth.external.get_config, 'microsoft', tenant_uuid
            )
        except HTTPError:
            raise HookExpectedError('unable to fetch external config')

        try:
            domains = await fetch(self.confd.ingress_http.list, tenant_uuid=tenant_uuid)
        except HTTPError:
            raise HookExpectedError(
                f'an error occured while fetching domains for tenant {tenant_uuid}'
            )
        domains = [domain['uri'] for domain in domains['items'] if 'uri' in domain]

        config['microsoft_tenant_id'] = payload['tid']
        config['microsoft_app_id'] = payload['appid']
        config['microsoft_user_id'] = payload['oid']
        config['user_uuid'] = user_uuid
        config['tenant_uuid'] = tenant_uuid
        config['domain'] = domains[-1]

        return token['access_token'], config

    async def _decode_access_token(self, access_token: str) -> Dict:
        payload = access_token.split('.')[1].encode('utf-8')
        decoded = b64decode(payload + b'===')
        return json.loads(decoded)
