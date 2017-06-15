# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

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


def main():
    if USER:
        change_user(USER)

    xivo_logging.setup_logging(LOGFILE, FOREGROUND, DEBUG, LOGLEVEL)

    with pidfile_context(PIDFILE, FOREGROUND):
        while True:
            time.sleep(1)
