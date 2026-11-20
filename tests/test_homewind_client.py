"""E1 against a local fake Homewind: system/info and fan actions, including 403 without the header."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from homewind_tokenextractor.homewind_client import (
    DISCOVER_TIMEOUT,
    FIRMWARE_TOO_OLD,
    FULL,
    HEADER,
    NOT_IN_HOMEWIND,
    PROBE_TIMEOUT,
    REFUSED,
    STARTING,
    TOKEN_NOT_ACCEPTED,
    UNREACHABLE,
    UPDATING,
    HomewindError,
    _homewind_hostname,
    add,
    discover,
    probe,
    update_token,
)

TOKEN = "0123456789abcdef0123456789abcdef"
OLD = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
NEW = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
FULL_TOKEN = "f" * 32
MAINT_TOKEN = "a" * 32
START_TOKEN = "5" * 32
FORBIDDEN_TOKEN = "0" * 32
MISSING_TOKEN = "c" * 32
REFUSED_TOKEN = "e" * 32

INFO_READY = b"name=Homewind\nversion=1.8.2\nready=1\n"
INFO_STARTING = b"name=Homewind\nversion=1.8.2\nready=0\n"
INFO_OTHER = b"name=Router\nready=1\n"


class _Server:
    def __init__(self, info: bytes) -> None:
        self.info = info
        self.last = {}
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                if urlsplit(self.path).path == "/api/v1/system/info":
                    self._send(200, outer.info)
                else:
                    self._send(404, b"nope")

            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", "0") or 0)
                if length:
                    self.rfile.read(length)
                parsed = urlsplit(self.path)
                query = parse_qs(parsed.query)
                outer.last = {"path": parsed.path, "header": self.headers.get(HEADER), "query": query}
                if self.headers.get(HEADER) != "1":
                    self._send(403, b"Forbidden")
                    return
                token = (query.get("token") or [""])[0]
                if parsed.path.endswith("/fan/update"):
                    if "oldToken" not in query or "newToken" not in query:
                        self._send(400, b"Missing oldToken or token parameter")
                        return
                    if (query.get("oldToken") or [""])[0] == MISSING_TOKEN:
                        self._send(404, b"not found")
                        return
                    self._send(200, b"OK")
                    return
                self._send(*_add_response(token))

            def _send(self, status: int, body: bytes) -> None:
                self.send_response(status)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, fmt: str, *args) -> None:
                return None

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.host = f"127.0.0.1:{self._httpd.server_address[1]}"
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


def _add_response(token: str):
    if token == FULL_TOKEN:
        return 409, b"ERR:full"
    if token == MAINT_TOKEN:
        return 409, b"Maintenance active"
    if token == START_TOKEN:
        return 503, b"System not ready"
    if token == FORBIDDEN_TOKEN:
        return 403, b"Forbidden"
    if token == REFUSED_TOKEN:
        return 500, b"Failed to add fan"
    if token != TOKEN:
        return 400, b"Invalid fan token"
    return 200, b"OK"


@pytest.fixture()
def homewind():
    server = _Server(INFO_READY)
    try:
        yield server
    finally:
        server.close()


def test_timeouts_match_the_concept():
    assert DISCOVER_TIMEOUT == 3.0
    assert PROBE_TIMEOUT == 2.0


def test_hostname_filter_keeps_only_homewind():
    assert _homewind_hostname("homewind-a1b2c3d4.local.") == "homewind-a1b2c3d4"
    assert _homewind_hostname("HOMEWIND-AABBCCDD.local") == "homewind-aabbccdd"
    assert _homewind_hostname("", "homewind-aabbccdd._http._tcp.local.") == "homewind-aabbccdd"
    assert _homewind_hostname("printer.local.", "Living Room._http._tcp.local.") == ""
    assert _homewind_hostname("homewind-.local") == ""


def test_probe_accepts_a_ready_homewind_and_builds_the_label(homewind):
    device = probe(homewind.host, hostname="homewind-a1b2c3d4.local", address="192.168.1.40")
    assert device is not None
    assert device.version == "1.8.2"
    assert device.label == "Homewind a1b2c3d4 · 192.168.1.40"


def test_probe_rejects_not_ready_or_other_device():
    starting = _Server(INFO_STARTING)
    other = _Server(INFO_OTHER)
    try:
        assert probe(starting.host) is None
        assert probe(other.host) is None
    finally:
        starting.close()
        other.close()


def test_discover_probes_candidates_and_skips_the_unreachable(homewind):
    devices = discover(0.01, browse=lambda _timeout: [homewind.host, "127.0.0.1:1", homewind.host])
    assert [d.host for d in devices] == [homewind.host]


def test_add_sends_the_header_and_token(homewind):
    add(homewind.host, TOKEN.upper())
    assert homewind.last["header"] == "1"
    assert homewind.last["path"].endswith("/fan/add")
    assert homewind.last["query"]["token"] == [TOKEN]


def test_add_error_messages(homewind):
    cases = [
        ("xyz", TOKEN_NOT_ACCEPTED, None),
        (FULL_TOKEN, FULL, 409),
        (MAINT_TOKEN, UPDATING, 409),
        (START_TOKEN, STARTING, 503),
        (FORBIDDEN_TOKEN, FIRMWARE_TOO_OLD, 403),
        (REFUSED_TOKEN, REFUSED, 500),
    ]
    for token, message, status in cases:
        with pytest.raises(HomewindError) as caught:
            add(homewind.host, token)
        assert str(caught.value) == message
        assert caught.value.status == status


def test_post_without_header_is_forbidden(homewind):
    response = requests.post(
        f"http://{homewind.host}/api/v1/action/fan/add",
        params={"token": TOKEN},
        timeout=2,
    )
    assert response.status_code == 403


def test_update_token_uses_the_firmware_parameter_names(homewind):
    update_token(homewind.host, OLD, NEW)
    assert homewind.last["header"] == "1"
    assert homewind.last["query"]["oldToken"] == [OLD]
    assert homewind.last["query"]["newToken"] == [NEW]


def test_update_reports_a_missing_fan(homewind):
    with pytest.raises(HomewindError) as caught:
        update_token(homewind.host, MISSING_TOKEN, NEW)
    assert str(caught.value) == NOT_IN_HOMEWIND
    assert caught.value.status == 404


def test_unreachable_homewind():
    with pytest.raises(HomewindError) as caught:
        add("127.0.0.1:1", TOKEN, timeout=0.5)
    assert str(caught.value) == UNREACHABLE
    assert caught.value.status is None
