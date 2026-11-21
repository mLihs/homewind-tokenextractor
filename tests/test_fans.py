from homewind_tokenextractor.fans import PLACEHOLDER_IMAGE, SESSION_ENDED, collect_fans, filter_fans, load_catalog

TOKEN = "0123456789abcdef0123456789ABCDEF"


def dev(model, token=TOKEN, did="1", name="Fan"):
    return {"model": model, "token": token, "did": did, "name": name, "localip": "192.168.1.5", "isOnline": True}


def test_catalog_skips_disabled_and_uses_placeholder():
    catalog = load_catalog()
    assert "dmaker.fan.p33" in catalog
    assert "dmaker.fan.1c" not in catalog                      # disabled beats the prefix rule
    assert catalog.get("dmaker.fan.p33").image.name == "fan-smart-fan-2-pro.png"
    assert catalog.get("dmaker.fan.p9").image == PLACEHOLDER_IMAGE
    assert catalog.get("xiaomi.fan.p85").image.name == "fan-smart-fan-pro-slim.png"
    assert catalog.get("xiaomi.fan.p70").image.name == "fan-desktop-air-circulation.png"
    assert catalog.get("xiaomi.fan.p76").image.name == "fan-standing-air-circulation.png"


def test_unknown_model_with_supported_prefix_is_shown():
    catalog = load_catalog()
    entry = catalog.get("dmaker.fan.p99")
    assert entry is not None and entry.name == "dmaker.fan.p99"
    assert catalog.get("roborock.vacuum.s5") is None


def test_filter_keeps_the_fans_from_a_real_account_export():
    """Models present in the Token Extractor export for this account."""
    catalog = load_catalog()
    devices = [
        dev("dmaker.fan.p33", did="bike2", name="Bike fan 2"),
        dev("xiaomi.fan.p76", did="bike3", name="Bike fan 3"),
        dev("zhimi.airp.mb5", did="purifier", name="Air Purifier"),
        dev("yeelink.light.lamp4", did="lamp", name="Desk lamp"),
    ]
    fans = filter_fans(devices, "de", catalog)
    assert [f.name for f in fans] == ["Bike fan 2", "Bike fan 3"]


def test_filter_keeps_only_supported_fans_with_token():
    catalog = load_catalog()
    devices = [
        dev("dmaker.fan.p33", did="a"),
        dev("dmaker.fan.1c", did="b"),               # disabled (3 speeds)
        dev("roborock.vacuum.s5", did="c"),          # other device
        dev("zhimi.fan.za5", token="", did="d"),     # shared device without token
        dev("zhimi.fan.za5", token="xyz", did="e"),  # malformed token
    ]
    fans = filter_fans(devices, "de", catalog)
    assert [f.did for f in fans] == ["a"]
    assert fans[0].token == TOKEN.lower()


class FakeConnector:
    userId = 42

    def get_homes(self, server):
        if server == "ru":
            raise ConnectionError("blocked")
        return {"result": {"homelist": [{"id": 1}]}}

    def get_dev_cnt(self, server):
        return {"result": {}}

    def get_devices(self, server, home_id, owner):
        if server in ("de", "us"):  # same fan seen on two regions -> one tile
            return {"result": {"device_info": [dev("dmaker.fan.p30", did="x", name="Wohnzimmer")]}}
        return {"result": {"device_info": []}}


def test_collect_survives_failing_region_and_dedupes():
    fans = collect_fans(FakeConnector(), load_catalog())
    assert len(fans) == 1 and fans[0].name == "Wohnzimmer"


class DownConnector:
    userId = 1

    def get_homes(self, server):
        raise TimeoutError(server)

    def get_dev_cnt(self, server):
        raise TimeoutError(server)

    def get_devices(self, server, home_id, owner):
        raise TimeoutError(server)


def test_collect_reports_when_every_region_is_unreachable():
    try:
        collect_fans(DownConnector(), load_catalog(), servers=["de", "cn"])
    except ConnectionError:
        return
    raise AssertionError("expected ConnectionError")


class ExpiredConnector(DownConnector):
    def get_homes(self, server):
        return None  # Xiaomi answered, but not with HTTP 200


def test_collect_reports_an_ended_sign_in_instead_of_no_fans():
    try:
        collect_fans(ExpiredConnector(), load_catalog(), servers=["de", "cn"])
    except PermissionError as exc:
        assert str(exc) == SESSION_ENDED
        return
    raise AssertionError("expected PermissionError")
