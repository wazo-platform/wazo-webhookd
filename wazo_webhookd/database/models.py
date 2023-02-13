# Copyright 2017-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import itertools

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    text,
    Text,
    UniqueConstraint,
    orm,
)
from sqlalchemy_utils import JSONType
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship


Base = declarative_base()

_NOTSET = object()


class SubscriptionEvent(Base):
    __tablename__ = 'webhookd_subscription_event'
    __table_args__ = (UniqueConstraint('subscription_uuid', 'event_name'),)

    uuid = Column(
        String(38), server_default=text('uuid_generate_v4()'), primary_key=True
    )
    subscription_uuid = Column(
        String(38),
        ForeignKey('webhookd_subscription.uuid', ondelete='CASCADE'),
        nullable=False,
    )
    event_name = Column(Text(), nullable=False)


class SubscriptionOption(Base):
    __tablename__ = 'webhookd_subscription_option'
    __table_args__ = (UniqueConstraint('subscription_uuid', 'name'),)

    uuid = Column(
        String(38), server_default=text('uuid_generate_v4()'), primary_key=True
    )
    subscription_uuid = Column(
        String(38),
        ForeignKey('webhookd_subscription.uuid', ondelete='CASCADE'),
        nullable=False,
    )
    name = Column(Text(), nullable=False)
    value = Column(Text())


class SubscriptionMetadatum(Base):
    __tablename__ = 'webhookd_subscription_metadatum'

    uuid = Column(
        String(38), server_default=text('uuid_generate_v4()'), primary_key=True
    )
    subscription_uuid = Column(
        String(38),
        ForeignKey('webhookd_subscription.uuid', ondelete='CASCADE'),
        nullable=False,
    )
    key = Column(Text(), nullable=False)
    value = Column(Text())


class SubscriptionLog(Base):
    __tablename__ = 'webhookd_subscription_log'

    uuid = Column(String(36), primary_key=True)
    subscription_uuid = Column(
        String(38),
        ForeignKey('webhookd_subscription.uuid', ondelete='CASCADE'),
        nullable=False,
    )

    status = Column(Enum("success", "failure", "error", name='status_types'))
    started_at = Column(DateTime(timezone=True))
    ended_at = Column(DateTime(timezone=True))
    attempts = Column(Integer(), primary_key=True)
    max_attempts = Column(Integer())
    event = Column(JSONType)
    detail = Column(JSONType)


class Subscription(Base):
    __tablename__ = 'webhookd_subscription'
    uuid = Column(
        String(38), server_default=text('uuid_generate_v4()'), primary_key=True
    )
    name = Column(Text())
    service = Column(Text())
    events_user_uuid = Column(String(36))
    events_wazo_uuid = Column(String(36))
    owner_user_uuid = Column(String(36))
    owner_tenant_uuid = Column(String(36), nullable=False)

    events_rel = relationship(
        "SubscriptionEvent", lazy='joined', cascade='all, delete-orphan'
    )
    options_rel = relationship(
        "SubscriptionOption", lazy='joined', cascade='all, delete-orphan'
    )
    metadata_rel = relationship(
        "SubscriptionMetadatum", lazy='joined', cascade='all, delete-orphan'
    )

    def make_transient(self):
        for instance in itertools.chain(
            [self], self.events_rel, self.options_rel, self.metadata_rel
        ):
            orm.session.make_transient(instance)

    @property
    def config(self):
        return {option.name: option.value for option in self.options_rel}

    @property
    def metadata_(self):
        return {metadatum.key: metadatum.value for metadatum in self.metadata_rel}

    @property
    def events(self):
        return [event.event_name for event in self.events_rel]

    def clear_relations(self):
        # FIXME(sileht): We should delete all orm objects explictly instead of
        # relying on delete-orphan magic
        self.options_rel.clear()
        self.events_rel.clear()
        self.metadata_rel.clear()

    def from_schema(
        self,
        name,
        service,
        config,
        events,
        metadata_=None,
        events_wazo_uuid=_NOTSET,
        events_user_uuid=_NOTSET,
        owner_user_uuid=_NOTSET,
        owner_tenant_uuid=_NOTSET,
    ):
        self.name = name
        self.service = service

        for name, value in config.items():
            self.options_rel.append(SubscriptionOption(name=name, value=value))

        for name in events:
            self.events_rel.append(SubscriptionEvent(event_name=name))

        if metadata_:
            for key, value in metadata_.items():
                self.metadata_rel.append(SubscriptionMetadatum(key=key, value=value))

        if events_user_uuid is not _NOTSET:
            self.events_user_uuid = events_user_uuid
        if events_wazo_uuid is not _NOTSET:
            self.events_wazo_uuid = events_wazo_uuid
        if owner_user_uuid is not _NOTSET:
            self.owner_user_uuid = owner_user_uuid
        if owner_tenant_uuid is not _NOTSET:
            self.owner_tenant_uuid = owner_tenant_uuid
