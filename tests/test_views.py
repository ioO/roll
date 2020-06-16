from http import HTTPStatus

import pytest

pytestmark = pytest.mark.asyncio


async def test_simple_get_request(client, app):

    @app.route('/test')
    async def get(req, resp):
        resp.body = 'test response'

    resp = await client.get('/test')
    assert resp.status == HTTPStatus.OK
    assert resp.body == b'test response'


async def test_simple_non_200_response(client, app):

    @app.route('/test')
    async def get(req, resp):
        resp.status = 204

    resp = await client.get('/test')
    assert resp.status == HTTPStatus.NO_CONTENT
    assert resp.body == b''


async def test_not_found_path(client, app):

    @app.route('/test')
    async def get(req, resp):
        ...

    resp = await client.get('/testing')
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_invalid_method(client, app):

    @app.route('/test', methods=['GET'])
    async def get(req, resp):
        ...

    resp = await client.post('/test', body=b'')
    assert resp.status == HTTPStatus.METHOD_NOT_ALLOWED


async def test_post_json(client, app):

    @app.route('/test', methods=['POST'])
    async def post(req, resp):
        resp.body = req.body

    resp = await client.post('/test', body={'key': 'value'})
    assert resp.status == HTTPStatus.OK
    assert resp.body == b'{"key": "value"}'


async def test_post_urlencoded(client, app):

    @app.route('/test', methods=['POST'])
    async def post(req, resp):
        resp.body = req.body

    client.content_type = 'application/x-www-form-urlencoded'
    resp = await client.post('/test', body={'key': 'value'})
    assert resp.status == HTTPStatus.OK
    assert resp.body == b'key=value'


async def test_can_define_twice_a_route_with_different_payloads(client, app):

    @app.route('/test', methods=['GET'])
    async def get(req, resp):
        resp.body = b'GET'

    @app.route('/test', methods=['POST'])
    async def post(req, resp):
        resp.body = b'POST'

    resp = await client.get('/test')
    assert resp.status == HTTPStatus.OK
    assert resp.body == b'GET'

    resp = await client.post('/test', {})
    assert resp.status == HTTPStatus.OK
    assert resp.body == b'POST'


async def test_simple_get_request_with_accent(client, app):

    @app.route('/testé')
    async def get(req, resp):
        resp.body = 'testé response'

    resp = await client.get('/testé')
    assert resp.status == HTTPStatus.OK
    assert resp.body == 'testé response'.encode()


async def test_route_with_different_signatures_on_same_handler(client, app):

    @app.route("/test/", name="collection")
    @app.route("/test/{id}", name="item")
    async def myhandler(request, response, id="default"):
        response.body = id

    assert (await client.get("/test/")).body == b"default"
    assert (await client.get("/test/other")).body == b"other"
