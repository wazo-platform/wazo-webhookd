# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import time

from xivo.daemonize import pidfile_context

FOREGROUND = True  # Always in foreground systemd takes care of daemonizing
PIDFILE = '/var/run/wazo-webhookd/wazo-webhookd.pid'


def main():
    with pidfile_context(PIDFILE, FOREGROUND):
        while True:
            time.sleep(1)
