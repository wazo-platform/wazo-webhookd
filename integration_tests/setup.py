#!/usr/bin/env python3
# Copyright 2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from setuptools import setup


setup(
    name='wazo_webhookd_test_helpers',
    version='1.0.0',
    description='Wazo webhookd test helpers',
    author='Wazo Authors',
    author_email='dev@wazo.community',
    packages=['wazo_webhookd_test_helpers'],
    package_dir={
        'wazo_webhookd_test_helpers': 'suite/helpers',
    },
)
