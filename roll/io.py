from asyncio import Event
from queue import deque
from http import HTTPStatus
from urllib.parse import parse_qs

from biscuits import parse

from .http import STATUSES, HttpCode, HttpError, Multipart

try:
    # In case you use json heavily, we recommend installing
    # https://pypi.python.org/pypi/ujson for better performances.
    import ujson as json
    JSONDecodeError = ValueError
except ImportError:
    import json as json
    from json.decoder import JSONDecodeError



class Body(deque):

    def __init__(self, protocol):
        super().__init__()
        self.protocol = protocol
        self.complete = Event()
        self.unread = Event()

    @property
    def completed(self):
        return self.complete.is_set()

    def put(self, data: bytes):
        self.append(data)
        self.unread.set()
        self.protocol.pause_reading()

    async def get(self):
        await asyncio.wait(self.unread.wait(), self.complete.wait())
        if self.completed:
            return None
        chunk = self.popleft()
        self.unread.clear()
        self.protocol.resume_reading()
        return chunk

    async def __aiter__(self):
        while True:
            chunk = await self.get()
            if chunk is None:
                break
            yield chunk


class Request(dict):
    """A container for the result of the parsing on each request.

    The default parsing is made by `httptools.HttpRequestParser`.
    """
    __slots__ = (
        'app', 'url', 'path', 'query_string', '_query', 'body',
        'method', 'headers', 'route', '_cookies', '_form', '_files',
        'upgrade', 'protocol', '_json', 'queue'
    )

    def __init__(self, app, protocol):
        self.app = app
        self.protocol = protocol
        self.headers = {}
        self.body = Body(protocol)
        self.method = None
        self.upgrade = None
        self._cookies = None
        self._query = None
        self._form = None
        self._files = None
        self._json = None

    @property
    def cookies(self):
        if self._cookies is None:
            self._cookies = parse(self.headers.get('COOKIE', ''))
        return self._cookies

    @property
    def query(self):
        if self._query is None:
            parsed_qs = parse_qs(self.query_string, keep_blank_values=True)
            self._query = self.app.Query(parsed_qs)
        return self._query

    def _parse_multipart(self):
        parser = Multipart(self.app)
        self._form, self._files = parser.initialize(self.content_type)
        try:
            for chunk in self:
                parser.feed_data(chunk)
        except ValueError:
            raise HttpError(HTTPStatus.BAD_REQUEST,
                            'Unparsable multipart body')

    def _parse_urlencoded(self):
        try:
            parsed_qs = parse_qs(self.body.decode(), keep_blank_values=True,
                                 strict_parsing=True)
        except ValueError:
            raise HttpError(HTTPStatus.BAD_REQUEST,
                            'Unparsable urlencoded body')
        self._form = self.app.Form(parsed_qs)

    @property
    def form(self):
        if self._form is None:
            if 'multipart/form-data' in self.content_type:
                self._parse_multipart()
            elif 'application/x-www-form-urlencoded' in self.content_type:
                self._parse_urlencoded()
            else:
                self._form = self.app.Form()
        return self._form

    @property
    def files(self):
        if self._files is None:
            if 'multipart/form-data' in self.content_type:
                self._parse_multipart()
            else:
                self._files = self.app.Files()
        return self._files

    @property
    def json(self):
        if self._json is None:
            try:
                self._json = json.loads(self.body)
            except (UnicodeDecodeError, JSONDecodeError):
                raise HttpError(HTTPStatus.BAD_REQUEST, 'Unparsable JSON body')
        return self._json

    @property
    def content_type(self):
        return self.headers.get('CONTENT-TYPE', '')

    @property
    def host(self):
        return self.headers.get('HOST', '')

    async def read(self):
        await self.body.complete.wait()
        return ''.join(self.body)

    async def __aiter__(self):
        async for chunk in self.body:
            yield chunk


class Response:
    """A container for `status`, `headers` and `body`."""
    __slots__ = ('app', '_status', 'headers', 'body', '_cookies', 'protocol')

    def __init__(self, app, protocol):
        self.app = app
        self.protocol = protocol
        self.body = b''
        self.status = HTTPStatus.OK
        self.headers = {}
        self._cookies = None

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, http_code: HttpCode):
        # Idempotent if `http_code` is already an `HTTPStatus` instance.
        self._status = STATUSES[http_code]

    def json(self, value: dict):
        # Shortcut from a dict to JSON with proper content type.
        self.headers['Content-Type'] = 'application/json; charset=utf-8'
        self.body = json.dumps(value)

    json = property(None, json)

    @property
    def cookies(self):
        if self._cookies is None:
            self._cookies = self.app.Cookies()
        return self._cookies
