# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from xivo import xivo_logging
from xivo.config_helper import set_xivo_uuid, UUIDNotFound
from xivo.daemonize import pidfile_context
from xivo.user_rights import change_user
from wazo_webhookd.controller import Controller

from wazo_webhookd import config

logger = logging.getLogger(__name__)

FOREGROUND = True  # Always in foreground systemd takes care of daemonizing


def main():
    conf = config.load_config()

    if conf['user']:
        change_user(conf['user'])

    xivo_logging.setup_logging(
        conf['log_file'], FOREGROUND, conf['debug'], conf['log_level']
    )
    xivo_logging.silence_loggers(['Flask-Cors', 'urllib3', 'amqp'], logging.WARNING)

    try:
        set_xivo_uuid(conf, logger)
    except UUIDNotFound:
        # handled in the controller
        pass

    controller = Controller(conf)
    with pidfile_context(conf['pid_file'], FOREGROUND):
        controller.run()
