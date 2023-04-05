#!/usr/bin/env python3
# Copyright 2017-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from setuptools import setup
from setuptools import find_packages


NAME = 'wazo-webhookd'
setup(
    name=NAME,
    version='1.0',
    author='Wazo Authors',
    author_email='dev@wazo.community',
    url='https://wazo-platform.org',
    packages=find_packages(),
    package_data={'wazo_webhookd.plugins': ['*/api.yml']},
    entry_points={
        'console_scripts': [
            f'{NAME} = wazo_webhookd.bin.daemon:main',
            f'{NAME}-init-db = wazo_webhookd.bin.init_db:main',
            f'{NAME}-init-amqp=wazo_webhookd.bin.init_amqp:main',
        ],
        'wazo_webhookd.plugins': [
            'api = wazo_webhookd.plugins.api.plugin:Plugin',
            'config = wazo_webhookd.plugins.config.plugin:Plugin',
            'status = wazo_webhookd.plugins.status.plugin:Plugin',
            'subscriptions = wazo_webhookd.plugins.subscription.plugin:Plugin',
            'services = wazo_webhookd.plugins.services.plugin:Plugin',
        ],
        'wazo_webhookd.services': [
            'http = wazo_webhookd.services.http.plugin:Service',
            'mobile = wazo_webhookd.services.mobile.plugin:Service',
        ],
        'wazo_purge_db.purgers': [
            'webhookd-logs = wazo_webhookd.database.purger:SubscriptionLogsPurger'
        ],
    },
)
