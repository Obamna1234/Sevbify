"""Server sign-ins: secrets go to the OS secure store when available, with a safe file fallback."""
from core import server_store


class _FakeKeyring:
    def __init__(self):
        self._d = {}
    def set_password(self, service, name, value):
        self._d[(service, name)] = value
    def get_password(self, service, name):
        return self._d.get((service, name))


def test_secret_goes_to_secure_store_not_the_file(tmp_path, monkeypatch):
    fake = _FakeKeyring()
    monkeypatch.setattr(server_store, "_secure_store", lambda: fake)
    servers = [{"id": "abc123", "type": "jellyfin", "url": "https://music.example.com",
                "user": "me", "token": "SECRET-TOKEN", "device_id": "dev"}]
    server_store.save(str(tmp_path), servers)
    raw = open(server_store.path(str(tmp_path)), encoding="utf-8").read()
    assert "SECRET-TOKEN" not in raw                      # not written to the file
    assert fake.get_password("Sevbify music servers", "abc123:token") == "SECRET-TOKEN"
    loaded = server_store.load(str(tmp_path))
    assert loaded[0]["token"] == "SECRET-TOKEN"            # restored from the store


def test_fallback_without_secure_store_keeps_old_behaviour(tmp_path, monkeypatch):
    monkeypatch.setattr(server_store, "_secure_store", lambda: None)
    servers = [{"id": "abc123", "type": "webdav", "url": "https://cloud.example.com",
                "user": "me", "password": "APP-PW"}]
    server_store.save(str(tmp_path), servers)
    raw = open(server_store.path(str(tmp_path)), encoding="utf-8").read()
    assert "APP-PW" in raw                                # unchanged: secret stays in the private file
    assert server_store.load(str(tmp_path))[0]["password"] == "APP-PW"
