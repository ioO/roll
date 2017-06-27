import pytest

from . import Request


@pytest.fixture
def req(app, event_loop):
    app.loop = event_loop
    app.loop.run_until_complete(app.startup())

    async def _(path, method='GET'):
        req = Request()
        req.path = path
        req.method = method
        return await app.respond(req)

    return _
