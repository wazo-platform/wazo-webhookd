#!/usr/bin/env python3
# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from setuptools import setup
from setuptools import find_packages


NAME = 'wazo-webhookd'
setup(
    name=NAME,
    version='1.0',
    author='Wazo Authors',
    author_email='dev@wazo.community',
    url='http://wazo.community',
    packages=find_packages(),
    package_data={'wazo_webhookd.plugins': ['*/api.yml']},
    install_requires=[
        'wazo_auth_client',
        'xivo',
        'xivo_lib_rest_client',
        'alembic',
        'celery',
        'cheroot',
        'flask-cors',
        'flask-restful',
        'flask',
        'jinja2',
        'kombu',
        'setproctitle',
        'marshmallow',
        'netifaces',
        'psycopg2',
        'python-consul',
        'pyyaml',
        'sqlalchemy',
        'sqlalchemy_utils',
        'stevedore',
        'pyfcm',
        'httpx',
    ],
    entry_points={
        'console_scripts': [
            '{}=wazo_webhookd.bin.daemon:main'.format(NAME),
            '{}-init-db=wazo_webhookd.bin.init_db:main'.format(NAME),
            '{}-init-amqp=wazo_webhookd.bin.init_amqp:main'.format(NAME),
        ],
        'wazo_webhookd.plugins': [
            'api = wazo_webhookd.plugins.api.plugin:Plugin',
            'config = wazo_webhookd.plugins.config.plugin:Plugin',
            'status = wazo_webhookd.plugins.status.plugin:Plugin',
            'subscriptions = wazo_webhookd.plugins.subscription.plugin:Plugin',
            'services = wazo_webhookd.plugins.services.plugin:Plugin',
            'tenant_migration = wazo_webhookd.plugins.tenant_migration.plugin:Plugin',
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
