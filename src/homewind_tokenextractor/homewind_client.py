"""Find a Homewind on the LAN and add or update a fan token.

Discovery browses ``_http._tcp`` and keeps hosts named ``homewind-…``, then
checks ``GET /api/v1/system/info``. Actions are ``POST`` with ``X-Homewind: 1``.
``discover`` blocks for a few seconds; call it off the UI thread.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Union
from urllib.parse import urlsplit

import requests
from zeroconf import ServiceBrowser, Zeroconf

from .fans import is_valid_token

_LOGGER = logging.getLogger("homewind_tokenextractor.homewind")

DISCOVER_TIMEOUT = 3.0
PROBE_TIMEOUT = 2.0
ACTION_TIMEOUT = 5.0

HEADER = "X-Homewind"
SERVICE_TYPE = "_http._tcp.local."

TOKEN_NOT_ACCEPTED = "Token not accepted"
FIRMWARE_TOO_OLD = "Homewind firmware too old or not a Homewind"
FULL = "Homewind is full (4/4)"
UPDATING = "Homewind is updating, try again later"
STARTING = "Homewind is starting, try again in a moment"
UNREACHABLE = "Homewind not reachable"
NOT_IN_HOMEWIND = "Fan is not in Homewind"
REFUSED = "Homewind refused the request"
ADDED = "Added"

Target = Union["HomewindDevice", str]


class HomewindError(Exception):
    """A Homewind call failed. ``str(exc)`` is the text for the fan tile."""

    def __init__(self, message: str, status: Optional[int] = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class HomewindDevice:
    """One Homewind that answered ``system/info`` with ``name=Homewind`` and ``ready=1``."""

    host: str
    address: str
    hostname: str
    version: str

    @property
    def label(self) -> str:
        ident = _hex_id(self.hostname)
        place = self.address or ("" if ident else self.host)
        if ident and place:
            return f"Homewind {ident} · {place}"
        if ident:
            return f"Homewind {ident}"
        return f"Homewind · {self.address or self.host}"


def probe(
    host: str,
    *,
    hostname: str = "",
    address: str = "",
    timeout: float = PROBE_TIMEOUT,
) -> Optional[HomewindDevice]:
    """Return the device when ``host`` is a ready Homewind, else None."""
    try:
        response = requests.get(f"{_base(host)}/api/v1/system/info", timeout=timeout)
    except requests.RequestException as exc:
        _LOGGER.debug("probe %s failed: %s", host, exc)
        return None
    if response.status_code != 200:
        return None
    info = _parse_info(response.text)
    if info.get("name") != "Homewind" or info.get("ready") != "1":
        return None
    hostname = hostname or _hostname_of(host)
    address = address or _address_of(host)
    return HomewindDevice(host=host, address=address, hostname=hostname, version=info.get("version", ""))


def discover(
    timeout: float = DISCOVER_TIMEOUT,
    browse: Optional[Callable[[float], Iterable[object]]] = None,
) -> List[HomewindDevice]:
    """Browse ``_http._tcp`` for ``timeout`` seconds and probe each ``homewind-`` host."""
    found: List[HomewindDevice] = []
    seen = set()
    for hit in (browse or _browse_http)(timeout):
        host, hostname, address = _hit(hit)
        device = probe(host, hostname=hostname, address=address)
        if device is None:
            continue
        key = (device.address or device.hostname or device.host).lower()
        if key in seen:
            continue
        seen.add(key)
        found.append(device)
    return found


def add(target: Target, token: str, timeout: float = ACTION_TIMEOUT) -> None:
    """``POST /api/v1/action/fan/add``. Raises ``HomewindError`` with a tile message."""
    _post(_host_of(target), "/api/v1/action/fan/add", {"token": _token(token)}, timeout)


def update_token(target: Target, old_token: str, new_token: str, timeout: float = ACTION_TIMEOUT) -> None:
    """``POST /api/v1/action/fan/update``.

    The firmware reads ``oldToken`` and ``newToken`` (the WebUI names). The
    documented ``old_token`` / ``new_token`` query names are ignored.
    """
    _post(
        _host_of(target),
        "/api/v1/action/fan/update",
        {"oldToken": _token(old_token), "newToken": _token(new_token)},
        timeout,
    )


def _post(host: str, path: str, params: dict, timeout: float) -> None:
    try:
        response = requests.post(
            f"{_base(host)}{path}",
            params=params,
            headers={HEADER: "1"},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise HomewindError(UNREACHABLE) from exc
    if response.status_code == 200:
        return
    raise HomewindError(_error_message(response.status_code, response.text), status=response.status_code)


def _error_message(status: int, body: str) -> str:
    if status == 400:
        return TOKEN_NOT_ACCEPTED
    if status == 403:
        return FIRMWARE_TOO_OLD
    if status == 404:
        return NOT_IN_HOMEWIND
    if status == 409:
        # F3: "full" is 409 with ERR:full. Any other 409 is maintenance.
        if "err:full" in body.lower():
            return FULL
        return UPDATING
    if status == 503:
        return STARTING
    return REFUSED


def _token(token: str) -> str:
    token = token.strip().lower()
    if not is_valid_token(token):
        raise HomewindError(TOKEN_NOT_ACCEPTED)
    return token


def _parse_info(text: str) -> dict:
    info = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            info[key.strip()] = value.strip()
    return info


def _browse_http(timeout: float) -> List[tuple]:
    """Listen for ``homewind-`` names, then ask for their addresses.

    Resolving every ``_http._tcp`` device inside the callback blocks the
    listener, so a printer or NAS can use up the whole window and the
    Homewind answer arrives only on the next search. Names are recorded
    immediately. If the first window is empty, listen once more: the first
    question on a cold cache often gets its answer just after that window.
    """
    names: List[str] = []

    class _Listener:
        def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
            if _homewind_hostname(name) and name not in names:
                names.append(name)

        def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
            self.add_service(zc, type_, name)

        def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
            return None

    zc = Zeroconf()
    browser = ServiceBrowser(zc, SERVICE_TYPE, _Listener())
    try:
        time.sleep(timeout)
        if not names:
            time.sleep(timeout)
        hits: List[tuple] = []
        for name in names:
            hit = _service_hit(zc, name)
            if hit is not None:
                hits.append(hit)
        return hits
    finally:
        browser.cancel()
        zc.close()


def _service_hit(zc: Zeroconf, name: str) -> Optional[tuple]:
    try:
        info = zc.get_service_info(SERVICE_TYPE, name, timeout=2000)
    except Exception as exc:  # noqa: BLE001 - one bad reply should not end the browse
        _LOGGER.debug("service info %s failed: %s", name, exc)
        return None
    if info is None:
        return None
    server = info.server or ""
    if isinstance(server, bytes):
        server = server.decode("utf-8", "replace")
    hostname = _homewind_hostname(server, name)
    if not hostname:
        return None
    address = _ipv4(info.parsed_addresses())
    host = address or f"{hostname}.local"
    return host, f"{hostname}.local", address


def _homewind_hostname(*labels: str) -> str:
    """Host label starting with ``homewind-``, or empty."""
    for label in labels:
        host = label.strip().rstrip(".").lower()
        if host.endswith(".local"):
            host = host[: -len(".local")]
        host = host.split("._", 1)[0]
        if host.startswith("homewind-") and len(host) > len("homewind-"):
            return host
    return ""


def _ipv4(addresses: Iterable[str]) -> str:
    for address in addresses:
        if ":" not in address:
            return address
    return ""


def _hit(hit: object) -> tuple:
    if isinstance(hit, str):
        return hit, _hostname_of(hit), _address_of(hit)
    if isinstance(hit, tuple) and len(hit) == 3:
        return hit
    raise TypeError(f"browse yielded {type(hit).__name__}, expected str or (host, hostname, address)")


def _host_of(target: Target) -> str:
    return target.host if isinstance(target, HomewindDevice) else target


def _base(host: str) -> str:
    raw = host.strip()
    if raw.startswith(("http://", "https://")):
        return raw.rstrip("/")
    if ":" in raw and not raw.startswith("[") and raw.count(":") > 1:
        return f"http://[{raw}]"
    return f"http://{raw}"


def _address_of(host: str) -> str:
    bare = host.strip()
    if bare.startswith(("http://", "https://")):
        bare = urlsplit(bare).netloc
    if bare.startswith("["):
        return bare.split("]")[0][1:]
    host_only = bare.rsplit(":", 1)[0] if bare.count(":") == 1 else bare
    if host_only.replace(".", "").isdigit():
        return host_only
    return ""


def _hostname_of(host: str) -> str:
    bare = host.strip()
    if bare.startswith(("http://", "https://")):
        bare = urlsplit(bare).hostname or ""
    else:
        bare = bare.rsplit(":", 1)[0] if bare.count(":") == 1 else bare
    name = _homewind_hostname(bare)
    return f"{name}.local" if name else ""


def _hex_id(hostname: str) -> str:
    name = _homewind_hostname(hostname)
    if not name:
        return ""
    return name.split("-", 1)[1]
