# Copyright 2017-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from six import iteritems
from xivo_bus.base import Base
from xivo_bus.mixins import ThreadableMixin, ConsumerMixin


logger = logging.getLogger(__name__)


# !!DO NOT RENAME!!
# Must be the same name to allow remapping of private (mangled) methods
class _ConsumerMixin(ConsumerMixin):
    def __check_headers_match(self, headers, binding):
        # only perform check if exchange type is headers
        if self.__exchange.type != 'headers':
            return True
        compare = all if binding.arguments.get('x-match', 'all') == 'all' else any
        headers = {k: v for k, v in iteritems(headers) if not k.startswith('x-')}
        arguments = {
            k: v for k, v in iteritems(binding.arguments) if not k.startswith('x-')
        }

        return compare(
            [k in headers and headers[k] == v for k, v in iteritems(arguments)]
        )

    def __dispatch(self, event_name, payload, headers=None):
        with self.__lock:
            subscriptions = self.__subscriptions[event_name].copy()
        for (handler, binding) in subscriptions:
            if not self.__check_headers_match(headers, binding):
                continue
            try:
                handler(payload)
            except Exception:
                self.log.exception(
                    'Handler \'%s\' for event \'%s\' failed',
                    handler.__name__,
                    event_name,
                )
            continue


class BusConsumer(ThreadableMixin, _ConsumerMixin, Base):
    pass
