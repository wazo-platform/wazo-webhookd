# Copyright 2017-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from xivo_bus.base import Base
from xivo_bus.mixins import ThreadableMixin, ConsumerMixin


logger = logging.getLogger(__name__)


class BusConsumer(ThreadableMixin, ConsumerMixin, Base):
    pass
