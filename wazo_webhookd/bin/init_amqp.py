#!/usr/bin/env python3
# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import sys

import kombu


def _parse_cli_args(args):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--username',
        action='store',
        default='guest',
        help="The username to use to connect to RabbitMQ",
    )
    parser.add_argument(
        '--password',
        action='store',
        default='guest',
        help="The password to connect to RabbitMQ",
    )
    parser.add_argument(
        '--port', action='store', default='5672', help="The port of RabbitMQ"
    )
    parser.add_argument(
        '--host', action='store', default='localhost', help="The host of RabbitMQ"
    )
    parser.add_argument(
        '--upstream_exchange_name',
        action='store',
        default='xivo',
        help="The upstream exchange name",
    )
    parser.add_argument(
        '--upstream_exchange_type',
        action='store',
        default='topic',
        help="The upstream exchange type",
    )
    parser.add_argument(
        '--exchange_name',
        action='store',
        default='wazo-headers',
        help="The main exchange name",
    )
    parser.add_argument(
        '--exchange_type',
        action='store',
        default='headers',
        help="The main exchange type",
    )
    return parser.parse_args(args)


def main():
    config = _parse_cli_args(sys.argv[1:])
    bus_url = 'amqp://{username}:{password}@{host}:{port}//'.format(
        username=config.username,
        password=config.password,
        host=config.host,
        port=config.port,
    )
    upstream_exchange = kombu.Exchange(
        config.upstream_exchange_name,
        type=config.upstream_exchange_type,
        auto_delete=False,
        durable=True,
        delivery_mode='persistent',
    )
    exchange = kombu.Exchange(
        config.exchange_name,
        type=config.exchange_type,
        auto_delete=False,
        durable=True,
        delivery_mode='persistent',
    )

    with kombu.Connection(bus_url) as connection:
        upstream_exchange.bind(connection).declare()
        exchange = exchange.bind(connection)
        exchange.declare()
        exchange.bind_to(upstream_exchange, routing_key='#')


if __name__ == '__main__':
    main()
