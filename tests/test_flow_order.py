"""Flow: a playlist's songs in a nice listening order, as a new playlist."""
from core import flow_order as fo


def song(artist, title, genre="", album=""):
    return {"artist": artist, "title": title, "genre": genre, "album": album}


SONGS = [
    song("A1", "Night Drive", "Synthwave"), song("A2", "Calm Sea", "Ambient"), song("A3", "Iron Storm", "Heavy Metal"),
    song("A4", "Blue Room", "Jazz"), song("A5", "Neon Rush", "Darksynth"), song("A6", "Soft Light", "Chillwave"),
    song("A7", "Highway", "Rock"), song("A8", "Moon", "Smooth Jazz"), song("A9", "Crash", "Death Metal"),
    song("A1", "Sunset Grid", "Synthwave"), song("A2", "Drift", "Ambient"), song("A7", "Engines", "Rock"),
]


class FakeDeezer:
    def __init__(self):
        self.calls = 0

    def search(self, q, limit=25):
        self.calls += 1
        from core.online.models import OnlineTrack
        if "Night Drive" in q:
            return [OnlineTrack(title="Night Drive", artist="A1", source="deezer", source_id="11")]
        return []

    def _get(self, path, params=None, ttl=0):
        self.calls += 1
        return {"bpm": 118.0, "gain": -6.5, "album": {"id": 5}}

    def album_genre(self, album_id):
        return "Electro"


def feats_for(songs):
    return [fo.features(s, None, None, online=False) for s in songs]


def test_styles_tell_calm_from_intense():
    e = {s["genre"]: f["energy"] for s, f in zip(SONGS, feats_for(SONGS))}
    assert e["Ambient"] < e["Jazz"] < e["Rock"] < e["Heavy Metal"]
    assert e["Chillwave"] < e["Synthwave"] < e["Darksynth"]            # synthwave's sub-styles
    assert fo.features(song("X", "Song (Acoustic)", "Rock"), online=False)["energy"] < \
        fo.features(song("X", "Song", "Rock"), online=False)["energy"]


def test_every_mode_keeps_every_song_once():
    feats = feats_for(SONGS)
    for mode in fo.MODES:
        out = fo.order(SONGS, feats, mode)
        assert sorted(out) == list(range(len(SONGS)))


def test_build_rises_and_wind_down_falls():
    feats = feats_for(SONGS)
    up = [feats[i]["energy"] for i in fo.order(SONGS, feats, "build", artists_apart=False)]
    assert up == sorted(up)
    down = [feats[i]["energy"] for i in fo.order(SONGS, feats, "wind_down", artists_apart=False)]
    assert down == sorted(down, reverse=True)


def test_smooth_has_smaller_jumps_than_the_original_order():
    feats = feats_for(SONGS)
    jumps = lambda o: sum(abs(feats[a]["energy"] - feats[b]["energy"]) for a, b in zip(o, o[1:]))
    assert jumps(fo.order(SONGS, feats, "smooth", artists_apart=False)) < jumps(list(range(len(SONGS)))) / 2


def test_waves_go_up_and_down():
    many = [song(f"Ar{i}", f"T{i}", g) for i, g in enumerate(["Ambient", "Jazz", "Rock", "Metal", "Pop", "House"] * 6)]
    feats = feats_for(many)
    e = [feats[i]["energy"] for i in fo.order(many, feats, "waves", artists_apart=False)]
    turns = sum(1 for a, b, c in zip(e, e[1:], e[2:]) if (b - a) * (c - b) < 0)
    assert turns >= 3


def test_genre_groups_stay_together():
    feats = feats_for(SONGS)
    fams = [feats[i]["family"] for i in fo.order(SONGS, feats, "genre", artists_apart=False)]
    changes = sum(1 for a, b in zip(fams, fams[1:]) if a != b)
    assert changes == len(set(fams)) - 1


def test_same_artist_kept_apart():
    songs = [song("Same", f"T{i}", "Rock") for i in range(4)] + [song(f"O{i}", f"U{i}", "Rock") for i in range(4)]
    feats = feats_for(songs)
    out = fo.order(songs, feats, "smooth")
    who = [songs[i]["artist"] for i in out]
    assert all(a != b for a, b in zip(who, who[1:]))


def test_deezer_tempo_and_loudness_used_and_remembered(tmp_path):
    store = fo.FeatureStore(str(tmp_path / "flow_features.json"))
    dz = FakeDeezer()
    f = fo.features(song("A1", "Night Drive"), dz, store)
    assert f["known"] and f["bpm"] == 118 and f["genre"] == "Electro" and f["family"] == "electronic"
    store.save()
    calls = dz.calls
    again = fo.FeatureStore(str(tmp_path / "flow_features.json"))
    assert fo.features(song("A1", "Night Drive"), dz, again) == f and dz.calls == calls      # no new lookups
    unknown = fo.features(song("Nobody", "Nothing", "Jazz"), dz, store)
    assert not unknown["known"] and unknown["family"] == "jazz"                               # placed by genre


def test_summary_reads_like_a_journey():
    feats = feats_for(SONGS)
    s = fo.summary(feats, fo.order(SONGS, feats, "build", artists_apart=False))
    assert s.startswith("calm") and s.endswith("intense")


def test_flow_this_playlist_makes_a_new_playlist_and_leaves_the_original(window, qapp, monkeypatch):
    from conftest import wait_until
    from ui.flow_dialog import FlowDialog
    from core.models import Playlist
    window.user_data.online_enabled = False                         # genre/title only (no network in tests)
    pl = Playlist("Mixed")
    for s in window.songs[:5]:
        pl.add_song(s)
    window.playlists.append(pl)
    before = list(pl.songs)
    menu = window.build_playlist_menu(pl)
    assert any("Sort by energy" in a.text() for a in menu.actions())
    monkeypatch.setattr(FlowDialog, "exec", lambda self: FlowDialog.DialogCode.Accepted)
    window.flow_playlist(pl)
    assert wait_until(qapp, lambda: any(p.name == "Mixed · Energetic to calm" for p in window.playlists))
    new = next(p for p in window.playlists if p.name == "Mixed · Energetic to calm")
    assert pl.songs == before                                       # the original is untouched
    assert sorted(id(s) for s in new.songs) == sorted(id(s) for s in before)
    assert "Energetic → Easing down → Calm" in new.description   # the default


def test_mix_spreads_calm_and_energetic_through_the_playlist():
    many = [song(f"Ar{i}", f"T{i}", g) for i, g in enumerate(["Ambient", "Jazz", "Rock", "Metal", "Pop", "House"] * 4)]
    feats = feats_for(many)
    e = [feats[i]["energy"] for i in fo.order(many, feats, "mix", artists_apart=False, seed=1)]
    half = len(e) // 2
    assert abs(sum(e[:half]) / half - sum(e[half:]) / (len(e) - half)) < 0.15     # no calm half / loud half
    assert fo.order(many, feats, "mix", seed=1) == fo.order(many, feats, "mix", seed=1)
