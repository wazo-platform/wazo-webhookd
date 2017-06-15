# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging
import signal
import sys
import time

from xivo import xivo_logging
from xivo.daemonize import pidfile_context
from xivo.user_rights import change_user

from wazo_webhookd import config

FOREGROUND = True  # Always in foreground systemd takes care of daemonizing

logger = logging.getLogger(__name__)


def _sigterm_handler(signum, frame):
    logger.info('SIGTERM received, terminating')
    sys.exit(0)


def main():
    conf = config.load_config(sys.argv[1:])

    if conf['user']:
        change_user(conf['user'])

    xivo_logging.setup_logging(conf['log_file'], FOREGROUND, conf['debug'], conf['log_level'])
    signal.signal(signal.SIGTERM, _sigterm_handler)

    with pidfile_context(conf['pid_file'], FOREGROUND):
        while True:
            time.sleep(1)
