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
    events = relationship('SubscriptionEvent')
    options = relationship('SubscriptionOption')

    @property
    def config(self):
        return {option.name: option.value for option in self.options}

    @config.setter
    def config(self, config):
        self.options = [SubscriptionOption(name=key, value=value, subscription_uuid=self.uuid)
                        for (key, value) in config.items()]


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
