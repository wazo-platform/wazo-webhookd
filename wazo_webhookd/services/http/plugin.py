# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from . import celery_tasks


class Service:

    def load(self, dependencies):
        celery_app = dependencies['celery']
        self._callback = celery_tasks.load(celery_app)

    def callback(self):
        return self._callback
