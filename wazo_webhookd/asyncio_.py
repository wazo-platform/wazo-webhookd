# Copyright 2022-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import asyncio
import logging

from functools import partial
from threading import Thread
from typing import Coroutine


logger = logging.getLogger(__name__)


class CoreAsyncio:
    def __init__(self):
        self._thread: Thread = None
        self._name: str = 'Asyncio-Thread'
        self._loop = asyncio.new_event_loop()
        self._stopping = asyncio.Event(loop=self._loop)

    @property
    def loop(self):
        return self._loop

    @property
    def stopping(self):
        return self._stopping.is_set()

    def __enter__(self):
        self.start()

    def __exit__(self, *args):
        self.stop()

    def start(self):
        if self._thread and self._thread.is_alive():
            raise RuntimeError('CoreAsyncio thread is already started')
        self._thread = Thread(
            target=self._run, name=self._name, daemon=True, args=(self._loop,)
        )
        self._thread.start()
        logger.info('CoreAsyncio thread started')

    def stop(self):
        if not self._thread or not self._thread.is_alive():
            raise RuntimeError('CoreAsyncio thread is not currently running')
        self._stopping.set()
        self._loop.stop()

    def _run(self, loop):
        asyncio.set_event_loop(loop)
        try:
            loop.run_forever()
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
        logger.info('CoreAsyncio thread terminated')

    def create_task(self, coro: Coroutine) -> asyncio.Task:
        return self._loop.create_task(coro)

    def schedule_coroutine(self, coro: Coroutine) -> None:
        asyncio.run_coroutine_threadsafe(coro, self._loop)

    async def fetch(self, func, *args, **kwargs):
        fn = partial(func, *args, **kwargs)
        return await self._loop.run_in_executor(None, fn)
