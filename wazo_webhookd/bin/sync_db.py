# Copyright 2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import logging
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, or_
from sqlalchemy.orm import scoped_session, sessionmaker
from wazo_auth_client import Client as AuthClient
from xivo import xivo_logging
from xivo.chain_map import ChainMap
from xivo.config_helper import read_config_file_hierarchy

from wazo_webhookd.config import _DEFAULT_CONFIG, _load_key_file
from wazo_webhookd.database.models import Subscription

logger = logging.getLogger('wazo-webhookd-sync-db')


def parse_cli_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-d',
        '--debug',
        action='store_true',
        help="Log debug messages",
    )
    parser.add_argument(
        '-q',
        '--quiet',
        action='store_true',
        help='Only print warnings and errors',
    )
    parsed_args = parser.parse_args()
    result = {'log_level': logging.INFO}
    if parsed_args.quiet:
        result['log_level'] = logging.WARNING
    elif parsed_args.debug:
        result['log_level'] = logging.DEBUG
    return result


def load_config():
    file_config = read_config_file_hierarchy(ChainMap(_DEFAULT_CONFIG))
    service_key = _load_key_file(ChainMap(file_config, _DEFAULT_CONFIG))
    return ChainMap(service_key, file_config, _DEFAULT_CONFIG)


@contextmanager
def rw_session(Session) -> Generator[scoped_session, None, None]:
    session = Session()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        Session.remove()


def main():
    cli_args = parse_cli_args()
    config = load_config()

    xivo_logging.setup_logging('/dev/null', log_level=cli_args['log_level'])
    xivo_logging.silence_loggers(['stevedore.extension'], logging.WARNING)

    token = AuthClient(**config['auth']).token.new(expiration=300)['token']

    del config['auth']['username']
    del config['auth']['password']
    tenants = AuthClient(token=token, **config['auth']).tenants.list()['items']
    auth_tenants = {str(tenant['uuid']) for tenant in tenants}
    logger.debug('Found %s wazo-auth tenants', len(auth_tenants))

    users = AuthClient(token=token, **config['auth']).users.list(recurse=True)['items']
    auth_users = {str(user['uuid']) for user in users}
    logger.debug('Found %s wazo-auth users', len(auth_users))

    engine = create_engine(
        config['db_uri'],
        pool_size=config['rest_api']['max_threads'],
        pool_pre_ping=True,
    )
    Session = scoped_session(sessionmaker())
    Session.configure(bind=engine)

    with rw_session(Session) as session:
        remove_tenants(session, auth_tenants)
        remove_users(session, auth_users)


def remove_tenants(session, auth_tenants):
    webhookd_tenants = {
        subscription.owner_tenant_uuid
        for subscription in (
            session.query(Subscription)
            .filter(Subscription.owner_user_uuid != None)  # noqa
            .all()
        )
    }
    logger.debug('Found %s webhookd tenants', len(webhookd_tenants))

    removed_tenants = webhookd_tenants - auth_tenants
    for tenant_uuid in removed_tenants:
        remove_tenant(tenant_uuid, session)


def remove_tenant(tenant_uuid, session):
    logger.debug('Removing tenant and its related data: %s', tenant_uuid)

    session.query(Subscription).filter(
        Subscription.owner_tenant_uuid == tenant_uuid
    ).delete()


def remove_users(session, auth_users):
    webhookd_users = {
        user_uuid
        for subscription in (session.query(Subscription).all())
        for user_uuid in (subscription.owner_user_uuid, subscription.events_user_uuid)
        if user_uuid
    }
    logger.debug('Found %s webhookd users', len(webhookd_users))

    removed_users = webhookd_users - auth_users
    for user_uuid in removed_users:
        remove_user(user_uuid, session)


def remove_user(user_uuid, session):
    logger.debug('Removing user and its related data: %s', user_uuid)

    session.query(Subscription).filter(
        or_(
            Subscription.owner_user_uuid == user_uuid,
            Subscription.events_user_uuid == user_uuid,
        )
    ).delete()


if __name__ == '__main__':
    main()
    logger.info(
        'Please note that RabbitMQ bindings were not deleted. '
        'A restart of wazo-webhookd is needed to delete RabbitMQ bindings'
    )
