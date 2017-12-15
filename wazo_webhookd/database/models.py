# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from sqlalchemy import (Column, ForeignKey, String, text, Text, UniqueConstraint)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Subscription(Base):

    __tablename__ = 'webhookd_subscription'

    uuid = Column(String(38), server_default=text('uuid_generate_v4()'), primary_key=True)
    name = Column(Text())
    service = Column(Text())
    events_user_uuid = Column(String(36))
    events_wazo_uuid = Column(String(36))
    events_rel = relationship('SubscriptionEvent', lazy='joined', cascade='all, delete-orphan')
    options_rel = relationship('SubscriptionOption', lazy='joined', cascade='all, delete-orphan')
    owner_user_uuid = Column(String(36))
    metadata_rel = relationship('SubscriptionMetadatum', lazy='joined', cascade='all, delete-orphan')

    @property
    def config(self):
        return {option.name: option.value for option in self.options_rel}

    @config.setter
    def config(self, config):
        self.options_rel = [SubscriptionOption(name=key, value=value)
                            for (key, value) in config.items()]

    @property
    def events(self):
        return [event.event_name for event in self.events_rel]

    @events.setter
    def events(self, events):
        self.events_rel = [SubscriptionEvent(event_name=event) for event in events]

    @property
    def metadata_(self):
        return {metadatum.key: metadatum.value for metadatum in self.metadata_rel}

    @metadata_.setter
    def metadata_(self, metadata):
        self.metadata_rel = [SubscriptionMetadatum(key=key, value=value)
                             for (key, value) in metadata.items()]

    def clear_relations(self):
        self.events_rel.clear()
        self.options_rel.clear()

    def update(self, **attributes):
        for attribute, value in attributes.items():
            setattr(self, attribute, value)


class SubscriptionEvent(Base):

    __tablename__ = 'webhookd_subscription_event'
    __table_args__ = (
        UniqueConstraint('subscription_uuid', 'event_name'),
    )

    uuid = Column(String(38), server_default=text('uuid_generate_v4()'), primary_key=True)
    subscription_uuid = Column(String(38),
                               ForeignKey('webhookd_subscription.uuid', ondelete='CASCADE'),
                               nullable=False)
    event_name = Column(Text(), nullable=False)


class SubscriptionOption(Base):

    __tablename__ = 'webhookd_subscription_option'
    __table_args__ = (
        UniqueConstraint('subscription_uuid', 'name'),
    )

    uuid = Column(String(38), server_default=text('uuid_generate_v4()'), primary_key=True)
    subscription_uuid = Column(String(38),
                               ForeignKey('webhookd_subscription.uuid', ondelete='CASCADE'),
                               nullable=False)
    name = Column(Text(), nullable=False)
    value = Column(Text())


class SubscriptionMetadatum(Base):

    __tablename__ = 'webhookd_subscription_metadatum'

    uuid = Column(String(38), server_default=text('uuid_generate_v4()'), primary_key=True)
    subscription_uuid = Column(String(38),
                               ForeignKey('webhookd_subscription.uuid', ondelete='CASCADE'),
                               nullable=False)
    key = Column(Text(), nullable=False)
    value = Column(Text())
