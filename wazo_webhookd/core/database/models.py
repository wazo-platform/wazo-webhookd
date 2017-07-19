# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from sqlalchemy import (Column, ForeignKey, String, text, Text)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Subscription(Base):

    __tablename__ = 'webhookd_subscription'

    uuid = Column(String(38), server_default=text('uuid_generate_v4()'), primary_key=True)
    name = Column(Text())
    service = Column(Text())
    events_rel = relationship('SubscriptionEvent', lazy='joined')
    options_rel = relationship('SubscriptionOption', lazy='joined')

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


class SubscriptionEvent(Base):

    __tablename__ = 'webhookd_subscription_event'

    uuid = Column(String(38), server_default=text('uuid_generate_v4()'), primary_key=True)
    subscription_uuid = Column(String(38), ForeignKey('webhookd_subscription.uuid', ondelete='CASCADE'))
    event_name = Column(Text(), nullable=False)


class SubscriptionOption(Base):

    __tablename__ = 'webhookd_subscription_option'

    uuid = Column(String(38), server_default=text('uuid_generate_v4()'), primary_key=True)
    subscription_uuid = Column(String(38), ForeignKey('webhookd_subscription.uuid', ondelete='CASCADE'))
    name = Column(Text(), nullable=False)
    value = Column(Text())
