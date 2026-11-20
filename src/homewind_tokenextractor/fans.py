"""Fan catalog and device filtering for the Homewind Token Extractor."""

from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from .xiaomi_cloud import SERVERS, XiaomiCloudConnector

_LOGGER = logging.getLogger("homewind_tokenextractor.fans")

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
FANS_DIR = ASSETS_DIR / "fans"
PLACEHOLDER_IMAGE = FANS_DIR / "placeholder.svg"

_TOKEN_RE = re.compile(r"^[0-9a-fA-F]{32}$")

# Europe first: most Homewind users have their Mi Home account there.
SERVER_ORDER = ["de", "i2", "us", "sg", "ru", "in", "tw", "cn"]


@dataclass(frozen=True)
class CatalogEntry:
    model: str
    name: str
    image: Path


@dataclass(frozen=True)
class Fan:
    did: str
    name: str          # name the user gave the fan in Mi Home
    model: str
    model_name: str    # product name from the catalog
    token: str
    ip: str
    online: bool
    server: str
    image: Path


class Catalog:
    """Known models plus the prefix rule SmartMiFanAsync uses to accept a fan."""

    def __init__(self, models: Dict[str, CatalogEntry], prefixes: List[str], disabled: List[str]) -> None:
        self.models, self.prefixes, self.disabled = models, prefixes, set(disabled)

    def get(self, model: str) -> Optional[CatalogEntry]:
        if model in self.disabled:
            return None
        if model in self.models:
            return self.models[model]
        if any(model.startswith(p) for p in self.prefixes):
            return CatalogEntry(model=model, name=model, image=PLACEHOLDER_IMAGE)
        return None

    def __contains__(self, model: str) -> bool:
        return self.get(model) is not None


def load_catalog(path: Optional[Path] = None) -> Catalog:
    path = path or FANS_DIR / "catalog.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    models: Dict[str, CatalogEntry] = {}
    disabled: List[str] = []
    for model, entry in raw.get("models", {}).items():
        if not entry.get("enabled", True):
            disabled.append(model)
            continue
        image = FANS_DIR / entry["image"] if entry.get("image") else PLACEHOLDER_IMAGE
        if not image.is_file():
            image = PLACEHOLDER_IMAGE
        models[model] = CatalogEntry(model=model, name=entry.get("name", model), image=image)
    return Catalog(models, raw.get("prefixes", []), disabled)


def is_valid_token(token: object) -> bool:
    return isinstance(token, str) and bool(_TOKEN_RE.match(token))


def filter_fans(devices: Iterable[dict], server: str, catalog: Catalog) -> List[Fan]:
    """Keep only devices whose model Homewind supports and that carry a usable token."""
    fans: List[Fan] = []
    for device in devices:
        model = str(device.get("model", ""))
        entry = catalog.get(model)
        token = device.get("token")
        if entry is None or not is_valid_token(token):
            continue
        fans.append(
            Fan(
                did=str(device.get("did", "")),
                name=str(device.get("name") or entry.name),
                model=model,
                model_name=entry.name,
                token=str(token).lower(),
                ip=str(device.get("localip") or ""),
                online=bool(device.get("isOnline", False)),
                server=server,
                image=entry.image,
            )
        )
    return fans


def _fans_on_server(connector: XiaomiCloudConnector, server: str, catalog: Catalog) -> List[Fan]:
    homes: List[dict] = []
    resp = connector.get_homes(server)
    if resp and resp.get("result"):
        for home in resp["result"].get("homelist") or []:
            homes.append({"home_id": home["id"], "home_owner": connector.userId})
    cnt = connector.get_dev_cnt(server)
    share = (cnt or {}).get("result", {}).get("share") or {}
    for home in share.get("share_family") or []:
        homes.append({"home_id": home["home_id"], "home_owner": home["home_owner"]})
    fans: List[Fan] = []
    for home in homes:
        devices = connector.get_devices(server, home["home_id"], home["home_owner"])
        info = ((devices or {}).get("result") or {}).get("device_info") or []
        fans.extend(filter_fans(info, server, catalog))
    return fans


def collect_fans(
    connector: XiaomiCloudConnector,
    catalog: Catalog,
    servers: Optional[Iterable[str]] = None,
    log: Callable[[str], None] = lambda _m: None,
) -> List[Fan]:
    """Read homes and devices on every server region; one failing region does not stop the others.

    Regions are queried together. A region that never answers used to block the screen on
    "Looking for your fans", because the cloud call had no timeout and the next region waited.
    """
    chosen = [server for server in (servers or SERVER_ORDER) if server in SERVERS]
    total = len(chosen)
    found: Dict[str, Fan] = {}
    outcomes: List[Tuple[str, List[Fan], Optional[BaseException]]] = []
    lock = threading.Lock()
    done = 0

    def run(server: str) -> None:
        nonlocal done
        error: Optional[BaseException] = None
        fans: List[Fan] = []
        try:
            fans = _fans_on_server(connector, server, catalog)
        except Exception as exc:  # noqa: BLE001 - region errors are expected (e.g. no account there)
            error = exc
            _LOGGER.warning("Server %s skipped: %s", server, exc)
        with lock:
            outcomes.append((server, fans, error))
            done += 1
            finished = done
        log(f"Looking for your fans … {finished}/{total}")

    threads = [threading.Thread(target=run, args=(server,), daemon=True) for server in chosen]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    failures = 0
    for _server, fans, error in outcomes:
        if error is not None:
            failures += 1
            continue
        for fan in fans:
            found.setdefault(fan.did or fan.token, fan)
    if chosen and failures == total:
        raise ConnectionError("No connection to Xiaomi. Check your internet connection.")
    return sorted(found.values(), key=lambda f: f.name.lower())
