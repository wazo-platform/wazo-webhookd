# Copyright 2023-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from collections.abc import Generator

import pytest
from flask import Flask
from flask_restful import Api

from .rest_api import VERSION


@pytest.fixture(name='api')
def api_app() -> Generator[Api, None, None]:
    app = Flask('wazo-webhookd-test')
    api = Api(app, prefix=f'/{VERSION}')
    app.config.update(
        {
            "TESTING": True,
        }
    )
    yield api
