# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import os

from xivo import config_helper

_CERT_FILE = '/usr/share/xivo-certs/server.crt'
_DEFAULT_HTTPS_PORT = 9300
_PID_DIR = '/run/wazo-webhookd'

_DEFAULT_CONFIG = {
    'config_file': '/etc/wazo-webhookd/config.yml',
    'debug': False,
    'extra_config_files': '/etc/wazo-webhookd/conf.d',
    'log_file': '/var/log/wazo-webhookd.log',
    'log_level': 'info',
    'pid_file': os.path.join(_PID_DIR, 'wazo-webhookd.pid'),
    'user': 'wazo-webhookd',
    'auth': {
        'host': 'localhost',
        'port': 9497,
        'verify_certificate': _CERT_FILE,
        'key_file': '/var/lib/wazo-auth-keys/wazo-webhookd-key.yml',
    },
    'bus': {
        'username': 'guest',
        'password': 'guest',
        'host': 'localhost',
        'port': 5672,
        'exchange_name': 'wazo-headers',
        'exchange_type': 'headers',
    },
    'celery': {
        'broker': 'amqp://guest:guest@localhost:5672',
        'exchange_name': 'celery-webhookd',
        'queue_name': 'celery-webhookd',
        'worker_pid_file': os.path.join(_PID_DIR, 'celery-worker.pid'),
        'worker_min': 3,
        'worker_max': 5,
    },
    'consul': {
        'scheme': 'https',
        'host': 'localhost',
        'port': 8500,
        'verify': '/usr/share/xivo-certs/server.crt',
    },
    'db_uri': 'postgresql://asterisk:proformatique@localhost/asterisk',
    'rest_api': {
        'listen': '0.0.0.0',
        'port': _DEFAULT_HTTPS_PORT,
        'certificate': _CERT_FILE,
        'private_key': '/usr/share/xivo-certs/server.key',
        'cors': {'enabled': True, 'allow_headers': ['Content-Type', 'X-Auth-Token']},
    },
    'service_discovery': {
        'advertise_address': 'auto',
        'advertise_address_interface': 'eth0',
        'advertise_port': _DEFAULT_HTTPS_PORT,
        'enabled': True,
        'ttl_interval': 30,
        'refresh_interval': 27,
        'retry_interval': 2,
        'extra_tags': [],
    },
    'enabled_plugins': {
        'api': True,
        'config': True,
        'services': True,
        'status': True,
        'subscriptions': True,
        'tenant_migration': False,
    },
    'enabled_services': {'http': True, 'mobile': True},
    'hook_max_attempts': 10,
}


def _parse_cli_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-c', '--config-file', action='store', help='The path to the config file'
    )
    parser.add_argument(
        '-d',
        '--debug',
        action='store_true',
        help='Log debug mesages. Override log_level',
    )
    parser.add_argument('-u', '--user', action='store', help='The owner of the process')
    parsed_args = parser.parse_args()

    result = {}
    if parsed_args.config_file:
        result['config_file'] = parsed_args.config_file
    if parsed_args.debug:
        result['debug'] = parsed_args.debug
    if parsed_args.user:
        result['user'] = parsed_args.user

    return result


def load_config():
    return config_helper.load_config(_parse_cli_args(), _DEFAULT_CONFIG)
