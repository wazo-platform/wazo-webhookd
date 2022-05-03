#!/usr/bin/env python3
# Copyright 2021-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from setuptools import setup
from setuptools import find_packages


setup(
    name='wazo-webhookd-client-command-sentinel',
    version='1.0',
    author='Wazo Authors',
    author_email='dev@wazo.community',
    packages=find_packages(),
    entry_points={
        'wazo_webhookd_client.commands': [
            'sentinel_bus = wazo_webhookd_client_sentinel.plugin:SentinelBusCommand'
        ]
    },
)
