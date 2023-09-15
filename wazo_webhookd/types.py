# Copyright 2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from collections.abc import Callable, Collection
from typing import TypedDict, Union, Protocol, Any, TYPE_CHECKING

from flask_restful import Api
from wazo_auth_client.client import AuthClient
from stevedore.named import NamedExtensionManager

from .bus import BusConsumer

if TYPE_CHECKING:
    from .database.models import Subscription
    from .plugins.subscription.celery_tasks import ServiceTask


TokenRenewalCallback = Callable[[Collection[str]], None]


class AuthConfigDict(TypedDict):
    host: str
    port: int
    prefix: Union[str, None]
    https: bool
    key_file: str


class BusConfigDict(TypedDict):
    username: str
    password: str
    host: str
    port: int
    exchange_name: str
    exchange_type: str


class CeleryConfigDict(TypedDict):
    broker: str
    exchange_name: str
    queue_name: str
    worker_pid_file: str
    worker_min: int
    worker_max: int


class RestApiCorsConfigDict(TypedDict):
    enabled: bool
    allow_headers: list[str]


class RestApiConfigDict(TypedDict):
    listen: str
    port: int
    certificate: Union[str, None]
    private_key: Union[str, None]
    cors: RestApiCorsConfigDict
    max_threads: int


class EnabledPluginConfigDict(TypedDict):
    api: bool
    config: bool
    mobile: bool
    services: bool
    status: bool
    subscriptions: bool


class EnabledServiceConfigDict(TypedDict):
    http: bool
    mobile: bool


class ServiceDiscoveryConfigDict(TypedDict):
    enabled: bool
    advertise_address: str
    advertise_address_interface: str
    advertise_port: int
    ttl_interval: int
    refresh_interval: int
    retry_interval: int
    extra_tags: list[str]


class ConsulConfigDict(TypedDict):
    scheme: str
    port: int


class WebhookdConfigDict(TypedDict):
    config_file: str
    extra_config_files: str
    debug: bool
    user: str
    log_level: str
    log_file: str
    auth: AuthConfigDict
    bus: BusConfigDict
    celery: CeleryConfigDict
    consul: ConsulConfigDict
    db_uri: str
    hook_max_attempts: int
    rest_api: RestApiConfigDict
    enabled_plugins: EnabledPluginConfigDict
    enabled_services: EnabledServiceConfigDict
    mobile_apns_call_topic: str
    mobile_apns_default_topic: str
    mobile_apns_host: str
    mobile_apns_port: int
    mobile_fcm_notification_send_jwt_token: bool
    mobile_fcm_notification_end_point: str
    service_discovery: ServiceDiscoveryConfigDict


class BasePluginDependencyDict(TypedDict):
    api: Api
    bus_consumer: BusConsumer
    config: WebhookdConfigDict


class ServicePluginDependencyDict(BasePluginDependencyDict):
    auth_client: AuthClient


class PluginDependencyDict(BasePluginDependencyDict):
    service_manager: NamedExtensionManager
    next_token_change_subscribe: Callable[[TokenRenewalCallback], None]


class Plugin(Protocol):
    def load(self, dependencies: PluginDependencyDict) -> None:
        ...


class ServicePlugin(Protocol):
    def load(self, dependencies: ServicePluginDependencyDict) -> None:
        ...

    def run(
        self,
        task: ServiceTask,
        config: WebhookdConfigDict,
        subscription: Subscription,
        event: dict[str, Any],
    ) -> Any:
        ...
