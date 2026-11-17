"""Signed updates: the computer app only installs an update signed with Sevbify's release key."""
import hashlib
import io
import json
import os
import zipfile

import pytest

from core import app_update, update_sign


@pytest.fixture
def test_key(monkeypatch):
    from Cryptodome.PublicKey import ECC
    seed = os.urandom(32).hex()
    monkeypatch.setattr(update_sign, "PUBLIC_KEY_HEX", update_sign.public_from_seed(seed))
    return seed


def _zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Sevbify/Sevbify.exe", b"app")
        z.writestr("Sevbify/_internal/x.txt", b"x")
    return buf.getvalue()


class Resp(io.BytesIO):
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


URL = "https://github.com/Obamna1234/Sevbify/releases/download/v9.9.9/Sevbify-Windows.zip"
SIG = "https://github.com/Obamna1234/Sevbify/releases/download/v9.9.9/Sevbify-update-signatures.json"


def _web(files):
    def opener(url):
        if url not in files:
            raise OSError("404")
        return Resp(files[url])
    return opener


def _sigs(seed, tag, name, data):
    sha = hashlib.sha256(data).hexdigest()
    return json.dumps({"tag": tag, "files": {name: {"sha256": sha, "signature": update_sign.sign(seed, tag, name, sha)}}}).encode()


def test_a_signed_update_installs(tmp_path, test_key):
    data = _zip()
    got = app_update.prepare(URL, str(tmp_path), opener=_web({URL: data, SIG: _sigs(test_key, "v9.9.9", "Sevbify-Windows.zip", data)}))
    assert os.path.isfile(os.path.join(got, "Sevbify.exe"))


@pytest.mark.parametrize("case", ["missing", "other_key", "swapped_file", "other_tag", "garbage"])
def test_anything_unsigned_is_refused(tmp_path, test_key, case):
    data = _zip()
    sigs = _sigs(test_key, "v9.9.9", "Sevbify-Windows.zip", data)
    files = {URL: data, SIG: sigs}
    if case == "missing":
        del files[SIG]
    elif case == "other_key":
        files[SIG] = _sigs(os.urandom(32).hex(), "v9.9.9", "Sevbify-Windows.zip", data)
    elif case == "swapped_file":
        files[URL] = _zip() + b"evil"
    elif case == "other_tag":
        files[SIG] = _sigs(test_key, "v1.0.0", "Sevbify-Windows.zip", data)
    else:
        files[SIG] = b"{not json" * 10
    with pytest.raises(app_update.UpdateError):
        app_update.prepare(URL, str(tmp_path), opener=_web(files))
    assert not os.path.exists(os.path.join(str(tmp_path), "update", "new"))       # nothing unpacked


def test_the_app_key_is_a_real_public_key():
    assert len(bytes.fromhex(update_sign.PUBLIC_KEY_HEX)) == 32
    update_sign._verifier()                                                    # loads


def test_installers_are_never_picked_by_the_updater(monkeypatch):
    from core import updates

    class Net:
        def get_json(self, *a, **k):
            return [{"tag_name": "v9.9.9", "prerelease": True, "assets": [
                {"name": "Sevbify-Windows-Setup.exe", "browser_download_url": "https://x/setup.exe"},
                {"name": "Sevbify-Mac.dmg", "browser_download_url": "https://x/mac.dmg"},
                {"name": "Sevbify-Windows.zip", "browser_download_url": "https://x/win.zip"},
                {"name": "Sevbify-macOS.zip", "browser_download_url": "https://x/mac.zip"}]}]
    assert updates.check_app(Net(), current="5.0.0-beta.1", plat="windows")["url"] == "https://x/win.zip"
    assert updates.check_app(Net(), current="5.0.0-beta.1", plat="macos")["url"] == "https://x/mac.zip"
