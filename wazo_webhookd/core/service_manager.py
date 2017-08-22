# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+


import logging

from stevedore.named import NamedExtensionManager

logger = logging.getLogger(__name__)


def load_services(enabled_services, load_args=None, load_kwargs=None):
    load_args = load_args or []
    load_kwargs = load_kwargs or {}
    logger.debug('Enabled services: %s', enabled_services)
    services = NamedExtensionManager(namespace='wazo_webhookd.services',
                                     names=enabled_services,
                                     name_order=True,
                                     on_load_failure_callback=services_load_fail,
                                     propagate_map_exceptions=True,
                                     invoke_on_load=True)

    try:
        services.map(load_service, load_args, load_kwargs)
    except RuntimeError as e:
        logger.error("Could not load enabled services")
        logger.exception(e)

    return services


def load_service(ext, load_args, load_kwargs):
    logger.debug('Loading dynamic service: %s', ext.name)
    ext.obj.load(*load_args, **load_kwargs)


def services_load_fail(_, entrypoint, exception):
    logger.exception('There is an error with this module: %s', entrypoint)
