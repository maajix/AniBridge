from aniworld.config import Audio, Subtitles

from app.providers import moviesites

BASE = "https://filmpalast.to/stream/"
YEARS = {"der-plan": 2011, "battlestar-galactica-der-plan": 2009, "the-plan": 2011}


class FakeEpisode:
    def __init__(self, url, selected_language=None, selected_provider=None):
        slug = url.rsplit("/", 1)[-1]
        self.release_year = YEARS[slug]
        audio = Audio.ENGLISH if slug == "the-plan" else Audio.GERMAN
        self.provider_data = {(audio, Subtitles.NONE): {"VOE": f"https://voe.sx/e/{slug}"}}
        self.redirect_url = self.provider_data[(audio, Subtitles.NONE)][selected_provider or "VOE"]


def _fake_site(results, keywords=None):
    def query(keyword):
        if keywords is not None:
            keywords.append(keyword)
        return results

    return lambda site: (query, FakeEpisode, BASE + "{}")


def test_search_prefers_title_match_with_fitting_year(monkeypatch):
    keywords = []
    monkeypatch.setattr(moviesites, "_site", _fake_site([
        {"title": "Battlestar Galactica - Der Plan", "url": BASE + "battlestar-galactica-der-plan"},
        {"title": "Der Plan", "url": BASE + "der-plan"},
    ], keywords))
    assert moviesites.search("filmpalast", "Der Plan 2011") == ("der-plan", "Der Plan")
    assert keywords == ["Der Plan"]
    assert moviesites.search("filmpalast", "Der Plan 1995") is None


def test_search_skips_english_only_pages(monkeypatch):
    monkeypatch.setattr(moviesites, "_site", _fake_site([
        {"title": "The Plan", "url": BASE + "the-plan"},
    ]))
    assert moviesites.search("filmpalast", "The Plan 2011") is None


def test_resolve_direct_url_uses_german_hoster(monkeypatch):
    monkeypatch.setattr(moviesites, "_site", _fake_site([]))
    monkeypatch.setattr(
        moviesites, "resolve_host_url", lambda url: (url + "/master.m3u8", "VOE")
    )
    assert moviesites.resolve_direct_url("filmpalast", "der-plan") == (
        "https://voe.sx/e/der-plan/master.m3u8",
        "VOE",
    )
