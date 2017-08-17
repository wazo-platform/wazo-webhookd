# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+


class SubscriptionBusEventHandler:

    def __init__(self, celery_app, subscription_service):
        self._celery_app = celery_app
        self._service = subscription_service

    def subscribe(self, bus_consumer):
        bus_consumer.subscribe_to_all_events(self.on_wazo_event)

    def on_wazo_event(self, event):
        http_task = self._celery_app.tasks['wazo_webhookd.plugins.subscription.celery_tasks.http_callback']
        for subscription in self._service.list():
            if event['name'] in subscription.events:
                if subscription.service == 'http':
                    http_task.apply_async([
                        subscription.config['method'],
                        subscription.config['url'],
                        subscription.config.get('body'),
                        subscription.config.get('verify_certificate'),
                    ])
