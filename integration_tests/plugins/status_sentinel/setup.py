#!/usr/bin/env python3
# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from setuptools import find_packages, setup

setup(
    name='wazo-webhookd-status-sentinel',
    version='1.0',
    author='Wazo Authors',
    author_email='dev@wazo.community',
    packages=find_packages(),
    entry_points={
        'wazo_webhookd.plugins': [
            'status_sentinel = wazo_webhookd_status_sentinel.plugin:Plugin'
        ]
    },
)
