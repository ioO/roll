import asyncio
import os
import uvloop
import sys

from gunicorn.workers.base import Worker


class Worker(Worker):

    def init_process(self):
        self.server = None
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        asyncio.get_event_loop().close()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        super().init_process()

    def run(self):
        self.wsgi.loop = self.loop
        self.loop.run_until_complete(self.wsgi.startup())
        try:
            self.loop.run_until_complete(self._run())
        finally:
            self.loop.close()
        sys.exit()

    async def close(self):
        if self.server:
            server = self.server
            self.server = None
            self.log.info("Stopping server: %s", self.pid)
            server.close()
            await server.wait_closed()
            await self.wsgi.shutdown()

    async def _run(self):
        self.server = await asyncio.start_server(self.wsgi,
                                                 sock=self.sockets[0].sock)

        pid = os.getpid()
        try:
            while self.alive:
                self.notify()
                if pid == os.getpid() and self.ppid != os.getppid():
                    self.log.info("Parent changed, shutting down: %s", self)
                    break
                await asyncio.sleep(1.0, loop=self.loop)

        except BaseException as e:
            print(e)

        await self.close()
