from pathlib import Path


def _make_dummy_ydl(captured: dict[str, object], filename: str):
    """Build a minimal YoutubeDL test double that records options."""

    class DummyYDL:
        def __init__(self, opts):
            captured["opts"] = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, _url, download=True):
            return {"title": "demo", "ext": "mp4"}

        def prepare_filename(self, _info):
            return filename

    return DummyYDL


def test_ydl_download_applies_rate_limit(monkeypatch, tmp_path: Path):
    import importlib

    mod = importlib.import_module("app.core.downloader.ytdlp")
    monkeypatch.setattr(mod, "DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC", 5242880)

    captured: dict[str, object] = {}
    DummyYDL = _make_dummy_ydl(captured, str(tmp_path / "demo.mp4"))

    monkeypatch.setattr(mod.yt_dlp, "YoutubeDL", DummyYDL)

    path, _info = mod._ydl_download("https://example.test/video.mp4", tmp_path)

    assert path == tmp_path / "demo.mp4"
    assert captured["opts"]["ratelimit"] == 5242880


def test_ydl_download_scales_rate_limit_for_hls_fragments(monkeypatch, tmp_path: Path):
    import importlib

    mod = importlib.import_module("app.core.downloader.ytdlp")
    monkeypatch.setattr(mod, "DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC", 5242880)

    captured: dict[str, object] = {}
    DummyYDL = _make_dummy_ydl(captured, str(tmp_path / "demo.mp4"))
    monkeypatch.setattr(mod.yt_dlp, "YoutubeDL", DummyYDL)

    path, _info = mod._ydl_download("https://example.test/master.m3u8", tmp_path)

    assert path == tmp_path / "demo.mp4"
    assert captured["opts"]["concurrent_fragment_downloads"] == 4
    assert captured["opts"]["ratelimit"] == 1310720


def test_ydl_download_omits_rate_limit_when_disabled(monkeypatch, tmp_path: Path):
    import importlib

    mod = importlib.import_module("app.core.downloader.ytdlp")
    monkeypatch.setattr(mod, "DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC", 0)

    captured: dict[str, object] = {}
    DummyYDL = _make_dummy_ydl(captured, str(tmp_path / "demo.mp4"))

    monkeypatch.setattr(mod.yt_dlp, "YoutubeDL", DummyYDL)

    path, _info = mod._ydl_download("https://example.test/video", tmp_path)

    assert path == tmp_path / "demo.mp4"
    assert "ratelimit" not in captured["opts"]


def test_ydl_format_prefers_german_audio_track(monkeypatch, tmp_path: Path):
    import importlib

    import yt_dlp

    mod = importlib.import_module("app.core.downloader.ytdlp")
    captured: dict[str, object] = {}
    monkeypatch.setattr(mod.yt_dlp, "YoutubeDL", _make_dummy_ydl(captured, str(tmp_path / "demo.mkv")))
    mod._ydl_download("https://example.test/master.m3u8", tmp_path)
    monkeypatch.undo()

    def audio(lang):
        return {"format_id": f"a-{lang}", "ext": "mp4", "url": f"https://example.test/{lang}.m3u8",
                "protocol": "m3u8_native", "vcodec": "none", "acodec": "mp4a", "language": lang}

    video = {"format_id": "v720", "ext": "mp4", "url": "https://example.test/v.m3u8",
             "protocol": "m3u8_native", "vcodec": "avc1", "acodec": "none", "height": 720}
    info = {"id": "x", "title": "x", "extractor": "generic", "extractor_key": "Generic",
            "webpage_url": "https://example.test/x", "formats": [audio("en"), audio("de"), video]}
    with yt_dlp.YoutubeDL({"format": captured["opts"]["format"], "quiet": True}) as ydl:
        assert ydl.process_ie_result(info, download=False)["format_id"] == "v720+a-de"
