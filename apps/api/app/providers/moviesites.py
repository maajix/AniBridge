"""
FilmPalast and Filmo movie lookups.

Search and page scraping come from aniworld's maintained site models; the
hoster embed (VOE, ...) is resolved by AniBridge itself, like the megakino flow.
Only German audio is used.
"""

from __future__ import annotations

from typing import Optional, Tuple

from loguru import logger

from app.config import PROVIDER_ORDER
from app.hosts import resolve_host_url
from app.utils.aniworld_compat import prepare_aniworld_home
from app.utils.movie_year import extract_year_from_query

MOVIE_SITES = ("filmpalast", "filmo")
_LANGUAGE = "German Dub"


def _site(site: str):
    # aniworld pulls in niquests/curl_cffi; import only when a movie site is used
    prepare_aniworld_home()
    from aniworld.models.filmo_to import FilmoEpisode
    from aniworld.models.filmpalast_to import FilmPalastEpisode
    from aniworld.search import query_filmo, query_filmpalast

    return {
        "filmpalast": (query_filmpalast, FilmPalastEpisode, "https://filmpalast.to/stream/{}"),
        "filmo": (query_filmo, FilmoEpisode, "https://filmo.to/movies/{}"),
    }[site]


def _german_providers(episode) -> list[str]:
    # FilmPalast's available_providers() silently falls back to English audio
    prepare_aniworld_home()
    from aniworld.config import Audio, Subtitles

    data = episode.provider_data
    sources = data.get((Audio.GERMAN, Subtitles.NONE)) if data else None
    return list(sources or {})


def search(site: str, query: str) -> Optional[Tuple[str, str]]:
    """Return (slug, title) of the best German match whose year fits the query."""
    from app.utils.title_resolver import (
        _MIN_TITLE_MATCH_SCORE,
        _match_tokens,
        _normalize_alnum,
        _score_title_candidate,
    )

    query_fn, model, _ = _site(site)
    year = extract_year_from_query(query)
    # The sites' search finds nothing for "Title 2024"; search the title alone
    keyword = (query.rsplit(str(year), 1)[0].strip() if year else "") or query
    results = query_fn(keyword=keyword) or []
    q_tokens, q_norm = _match_tokens(query), _normalize_alnum(query)
    scored = sorted(
        ((_score_title_candidate(q_tokens, q_norm, r["title"]), r) for r in results),
        key=lambda item: item[0],
        reverse=True,
    )
    for score, result in scored[:3]:
        if score < _MIN_TITLE_MATCH_SCORE:
            break
        episode = model(result["url"], selected_language=_LANGUAGE)
        page_year = episode.release_year
        if year and page_year and abs(int(page_year) - year) > 1:
            logger.info("{} '{}' is from {}, query asks for {}; skipping", site, result["title"], page_year, year)
            continue
        if not _german_providers(episode):
            logger.info("{} '{}' has no German audio; skipping", site, result["title"])
            continue
        slug = result["url"].rstrip("/").rsplit("/", 1)[-1]
        return slug, result["title"]
    return None


def resolve_direct_url(
    site: str, slug: str, preferred_host: Optional[str] = None
) -> Tuple[str, str]:
    """Resolve a direct media URL and host name for a movie slug."""
    _, model, url_template = _site(site)
    url = url_template.format(slug)
    providers = _german_providers(model(url, selected_language=_LANGUAGE))
    rank = {name.lower(): i for i, name in enumerate(PROVIDER_ORDER)}
    providers.sort(
        key=lambda p: (p.lower() != (preferred_host or "").lower(), rank.get(p.lower(), len(rank)))
    )
    for provider in providers:
        episode = model(url, selected_language=_LANGUAGE, selected_provider=provider)
        try:
            embed = episode.redirect_url
        except ValueError as exc:
            logger.debug("{} {} via {}: {}", site, slug, provider, exc)
            continue
        direct, host_name = resolve_host_url(embed)
        if direct:
            return direct, host_name
    raise ValueError(f"No German {site} stream resolved for '{slug}'")


def movie_client(site: str):
    """Client for a movie-capable site (megakino, FilmPalast, Filmo), else None."""
    if site in MOVIE_SITES:
        return MovieSiteClient(site)
    if "megakino" in site:
        from app.providers.megakino.client import get_default_client

        return get_default_client()
    return None


class MovieSiteClient:
    """megakino-client shaped adapter for the download flow."""

    def __init__(self, site: str) -> None:
        self.site = site

    def load_index(self) -> dict:
        return {}

    def resolve_direct_url(self, slug: str, preferred_host: Optional[str] = None) -> Tuple[str, str]:
        return resolve_direct_url(self.site, slug, preferred_host)
