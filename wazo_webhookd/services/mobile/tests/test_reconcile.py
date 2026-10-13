# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from threading import Event
from unittest.mock import Mock, call, patch

import pytest
from requests.exceptions import HTTPError

from wazo_webhookd.tests.test_bus import FakeSubscriptionService, make_subscription

from ..plugin import RECONCILE_INTERVAL, RECONCILE_PAGE_SIZE, Service

TENANT_A = 'aaaaaaaa-0000-4000-8000-000000000000'
TENANT_B = 'bbbbbbbb-0000-4000-8000-000000000000'


class FakeAuth:
    """wazo-auth as the reconciliation reads it: GET /external/mobile/users
    (user uuids only, no tenant) and GET /users/{uuid}."""

    def __init__(self, mobile_users: dict[str, str]) -> None:
        self.mobile_users = mobile_users
        self.external = Mock()
        self.external.list_connected_users.side_effect = self._list
        self.users = Mock()
        self.users.get.side_effect = lambda uuid: {
            'uuid': uuid,
            'tenant_uuid': self.mobile_users[uuid],
        }

    def _list(self, auth_type, recurse, limit, offset):
        uuids = list(self.mobile_users)
        return {
            'total': len(uuids),
            'filtered': len(uuids),
            'items': [{'uuid': u} for u in uuids[offset : offset + limit]],
        }


def make_service(
    auth: FakeAuth, subscriptions=()
) -> tuple[Service, FakeSubscriptionService]:
    service = Service()
    service._config = {}  # type: ignore[typeddict-item]
    subscription_service = FakeSubscriptionService(list(subscriptions))
    service.subscription_service = subscription_service  # type: ignore[assignment]
    return service, subscription_service


@pytest.fixture
def auth_patch():
    with patch.object(Service, 'get_auth') as get_auth:
        yield get_auth


def mobile_owners(subscription_service: FakeSubscriptionService) -> list[str]:
    return sorted(
        s.owner_user_uuid
        for s in subscription_service.subscriptions
        if s.metadata_.get('mobile') == 'true'
    )


# Criterion 8


def test_reconcile_creates_the_missing_mobile_subscription_and_nothing_else(auth_patch):
    auth = FakeAuth({'u1': TENANT_A, 'u2': TENANT_A, 'u3': TENANT_B})
    auth_patch.return_value = (auth, 'jwt')
    user_made = make_subscription(
        owner_user_uuid='u2', owner_tenant_uuid=TENANT_A, service='http', metadata_={}
    )
    service, subscriptions = make_service(
        auth,
        [
            make_subscription(owner_user_uuid='u1', owner_tenant_uuid=TENANT_A),
            user_made,
        ],
    )

    assert service.reconcile() == 2

    assert mobile_owners(subscriptions) == ['u1', 'u2', 'u3']
    created = {s.owner_user_uuid: s for s in subscriptions.subscriptions[2:]}
    assert created['u3'].owner_tenant_uuid == TENANT_B
    assert created['u2'].events_user_uuid == 'u2'
    assert user_made in subscriptions.subscriptions
    assert auth.users.get.call_args_list == [call('u2'), call('u3')]
    assert service.reconciled_users_created == 2


def test_reconcile_creates_nothing_when_every_mobile_user_has_a_subscription(
    auth_patch,
):
    auth = FakeAuth({'u1': TENANT_A})
    auth_patch.return_value = (auth, 'jwt')
    service, subscriptions = make_service(
        auth, [make_subscription(owner_user_uuid='u1', owner_tenant_uuid=TENANT_A)]
    )
    before = list(subscriptions.subscriptions)

    assert service.reconcile() == 0

    assert subscriptions.subscriptions == before
    auth.users.get.assert_not_called()


def test_reconcile_never_touches_subscriptions_of_users_without_mobile_auth(auth_patch):
    auth = FakeAuth({})
    auth_patch.return_value = (auth, 'jwt')
    others = [
        make_subscription(owner_user_uuid='u9', service='http', metadata_={}),
        make_subscription(owner_user_uuid='u8'),  # mobile, auth since removed
    ]
    service, subscriptions = make_service(auth, others)

    assert service.reconcile() == 0

    assert subscriptions.subscriptions == others


def test_reconcile_repairs_a_user_failed_between_delete_and_create(auth_patch):
    auth = FakeAuth({'u1': TENANT_A})
    auth_patch.return_value = (auth, 'jwt')
    service, subscriptions = make_service(
        auth, [make_subscription(owner_user_uuid='u1', owner_tenant_uuid=TENANT_A)]
    )
    # the app unregisters (delete), and its create never reaches webhookd
    service.on_external_auth_deleted(
        {'data': {'external_auth_name': 'mobile', 'user_uuid': 'u1'}},
        {'tenant_uuid': TENANT_A},
    )
    assert mobile_owners(subscriptions) == []

    assert service.reconcile() == 1

    assert mobile_owners(subscriptions) == ['u1']


def test_reconcile_skips_a_user_whose_tenant_cannot_be_read_and_repairs_the_others(
    auth_patch, caplog
):
    auth = FakeAuth({'gone': TENANT_A, 'u2': TENANT_A})
    auth.users.get.side_effect = lambda uuid: (
        (_ for _ in ()).throw(HTTPError('404 user gone'))
        if uuid == 'gone'
        else {'tenant_uuid': TENANT_A}
    )
    auth_patch.return_value = (auth, 'jwt')
    service, subscriptions = make_service(auth)

    with caplog.at_level(logging.WARNING):
        assert service.reconcile() == 1

    assert mobile_owners(subscriptions) == ['u2']
    assert [r.getMessage() for r in caplog.records] == [
        'webhookd_subscriptions state=reconcile_user_failed error=HTTPError'
    ]


# Criterion 9


def test_reconcile_reads_one_paginated_cross_tenant_listing(auth_patch):
    users = {f'u{i}': TENANT_A for i in range(RECONCILE_PAGE_SIZE + 1)}
    auth = FakeAuth(users)
    auth_patch.return_value = (auth, 'jwt')
    service, _ = make_service(
        auth,
        [
            make_subscription(owner_user_uuid=u, owner_tenant_uuid=TENANT_A)
            for u in users
        ],
    )

    service.reconcile()

    assert RECONCILE_PAGE_SIZE == 500
    assert auth.external.list_connected_users.call_args_list == [
        call('mobile', recurse=True, limit=500, offset=0),
        call('mobile', recurse=True, limit=500, offset=500),
    ]


def test_reconcile_stops_on_an_empty_page_even_if_total_says_more(auth_patch):
    auth = FakeAuth({})
    auth.external.list_connected_users.side_effect = None
    auth.external.list_connected_users.return_value = {'total': 3, 'items': []}
    auth_patch.return_value = (auth, 'jwt')
    service, _ = make_service(auth)

    assert service.reconcile() == 0
    assert auth.external.list_connected_users.call_count == 1


# Contract question 9 and the loop


class StopLoop(Exception):
    pass


def test_loop_waits_for_the_first_full_bind_then_runs_every_five_minutes(auth_patch):
    service, _ = make_service(FakeAuth({}))
    first_full_bind = Mock(spec=Event)
    with patch.object(Service, 'reconcile') as reconcile, patch(
        'wazo_webhookd.services.mobile.plugin.time.sleep',
        side_effect=[None, StopLoop()],
    ) as sleep:
        with pytest.raises(StopLoop):
            service._reconcile_forever(first_full_bind)

    first_full_bind.wait.assert_called_once_with(RECONCILE_INTERVAL)
    assert RECONCILE_INTERVAL == 300
    assert reconcile.call_count == 2
    assert sleep.call_args_list == [call(300), call(300)]


def test_loop_logs_one_warning_when_wazo_auth_is_down_and_carries_on(
    auth_patch, caplog
):
    auth_patch.side_effect = HTTPError('503 auth down')
    service, subscriptions = make_service(FakeAuth({}))
    first_full_bind = Event()
    first_full_bind.set()

    with patch(
        'wazo_webhookd.services.mobile.plugin.time.sleep',
        side_effect=[None, StopLoop()],
    ), caplog.at_level(logging.WARNING):
        with pytest.raises(StopLoop):
            service._reconcile_forever(first_full_bind)

    assert [r.getMessage() for r in caplog.records] == [
        'webhookd_subscriptions state=reconcile_failed error=HTTPError'
    ] * 2
    assert subscriptions.subscriptions == []


def test_status_reports_reconciled_users_created(auth_patch):
    auth_patch.return_value = (FakeAuth({'u1': TENANT_A}), 'jwt')
    service, _ = make_service(FakeAuth({}))
    status: dict = {'subscriptions': {}, 'mobile_reconciliation': {}}

    service.provide_status(status)  # type: ignore[arg-type]
    assert status['subscriptions'] == {'reconciled_users_created': 0}

    service.reconcile()
    service.provide_status(status)  # type: ignore[arg-type]
    assert status['subscriptions'] == {'reconciled_users_created': 1}


def test_load_starts_the_reconciliation_thread_and_the_status_provider():
    bus_consumer = Mock()
    status_aggregator = Mock()
    with patch('wazo_webhookd.services.mobile.plugin.SubscriptionService'), patch(
        'wazo_webhookd.services.mobile.plugin.Thread'
    ) as thread:
        service = Service()
        service.load(
            {  # type: ignore[typeddict-item]
                'bus_consumer': bus_consumer,
                'bus_publisher': Mock(),
                'config': {},
                'status_aggregator': status_aggregator,
            }
        )

    thread.assert_called_once_with(
        target=service._reconcile_forever,
        args=(bus_consumer.first_full_bind,),
        name='mobile-reconcile',
        daemon=True,
    )
    thread.return_value.start.assert_called_once_with()
    status_aggregator.add_provider.assert_called_once_with(service.provide_status)


def test_status_tells_a_denied_reconciliation_from_a_healthy_one(auth_patch):
    # SR-1: without auth.mobile.external.users.read the listing answers 401
    service, _ = make_service(FakeAuth({}))
    first_full_bind = Event()
    first_full_bind.set()
    auth = FakeAuth({})
    auth.external.list_connected_users.side_effect = HTTPError('401 Unauthorized')
    auth_patch.return_value = (auth, 'jwt')

    status: dict = {'subscriptions': {}, 'mobile_reconciliation': {}}
    service.provide_status(status)  # type: ignore[arg-type]
    assert status['mobile_reconciliation'] == {
        'status': 'ok',
        'last_reconcile_at': None,
        'last_reconcile_error': None,
    }

    with patch(
        'wazo_webhookd.services.mobile.plugin.time.sleep', side_effect=StopLoop()
    ), patch(
        'wazo_webhookd.services.mobile.plugin._utcnow', return_value='T1'
    ), pytest.raises(
        StopLoop
    ):
        service._reconcile_forever(first_full_bind)
    service.provide_status(status)  # type: ignore[arg-type]
    assert status['mobile_reconciliation'] == {
        'status': 'fail',
        'last_reconcile_at': 'T1',
        'last_reconcile_error': 'HTTPError',
    }

    auth.external.list_connected_users.side_effect = auth._list
    with patch(
        'wazo_webhookd.services.mobile.plugin.time.sleep', side_effect=StopLoop()
    ), patch(
        'wazo_webhookd.services.mobile.plugin._utcnow', return_value='T2'
    ), pytest.raises(
        StopLoop
    ):
        service._reconcile_forever(first_full_bind)
    service.provide_status(status)  # type: ignore[arg-type]
    assert status['mobile_reconciliation'] == {
        'status': 'ok',
        'last_reconcile_at': 'T2',
        'last_reconcile_error': None,
    }
