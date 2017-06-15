# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging
import signal
import sys
import time

from xivo import xivo_logging
from xivo.daemonize import pidfile_context
from xivo.user_rights import change_user

DEBUG = True
FOREGROUND = True  # Always in foreground systemd takes care of daemonizing
LOGFILE = '/var/log/wazo-webhookd.log'
LOGLEVEL = 'debug'
PIDFILE = '/var/run/wazo-webhookd/wazo-webhookd.pid'
USER = 'wazo-webhookd'

logger = logging.getLogger(__name__)


def _sigterm_handler(signum, frame):
    logger.info('SIGTERM received, terminating')
    sys.exit(0)


def main():
    if USER:
        change_user(USER)

    xivo_logging.setup_logging(LOGFILE, FOREGROUND, DEBUG, LOGLEVEL)
    signal.signal(signal.SIGTERM, _sigterm_handler)

    with pidfile_context(PIDFILE, FOREGROUND):
        while True:
            time.sleep(1)
