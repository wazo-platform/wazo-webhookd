#!/usr/bin/env python3
# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from setuptools import find_packages, setup

setup(
    name='wazo-webhookd-celery-task-sentinel',
    version='1.0',
    author='Wazo Authors',
    author_email='dev@wazo.community',
    packages=find_packages(),
    entry_points={
        'wazo_webhookd.celery_tasks': [
            'celery_task_sentinel = wazo_webhookd_celery_task_sentinel.celery_tasks',
        ],
        'wazo_webhookd.plugins': [
            'celery_task_sentinel = wazo_webhookd_celery_task_sentinel.plugin:Plugin',
        ],
    },
)
