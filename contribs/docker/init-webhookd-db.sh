#!/bin/bash

wazo-webhookd-init-db
cd /usr/src/wazo-webhookd
alembic -c alembic.ini upgrade head
