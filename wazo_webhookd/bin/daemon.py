# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import sys

from xivo import xivo_logging
from xivo.daemonize import pidfile_context
from xivo.user_rights import change_user
from wazo_webhookd.controller import Controller

from wazo_webhookd import config

FOREGROUND = True  # Always in foreground systemd takes care of daemonizing


def main():
    conf = config.load_config(sys.argv[1:])

    if conf['user']:
        change_user(conf['user'])

    xivo_logging.setup_logging(conf['log_file'], FOREGROUND, conf['debug'], conf['log_level'])

    controller = Controller(conf)
    with pidfile_context(conf['pid_file'], FOREGROUND):
        controller.run()
