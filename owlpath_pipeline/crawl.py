"""Polite catalog crawler core: robots.txt, a shared crawl delay, a disk cache and hard stops.

The browser itself sits behind the PageLoader protocol, so everything here is testable with fakes.
It shares .cache/http/.last-request.json with PoliteFetcher, so the two never hit the host back to back.
"""
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from . import config
from .fetch import DisallowedError, HttpGet, cache_path, load_last_request, save_last_request

# Never requested, whatever robots.txt says.
NEVER_REQUEST = ("/ajax/", "/search_advanced.php", "/portfolio.php", "/portfolio_nopop.php")


@dataclass(frozen=True)
class LoadedPage:
    status: int
    html: str
    text: str


class PageLoader(Protocol):
    def load(self, url: str) -> LoadedPage: ...


class CrawlStopped(Exception):
    """Something unexpected (blocked, unreadable robots.txt, missing content): stop and ask the user."""


def read_robots(origin: str, http_get: HttpGet, user_agent: str = config.USER_AGENT) -> RobotFileParser:
    status, body = http_get(f"{origin}/robots.txt", {"User-Agent": user_agent})
    if status != 200:
        raise CrawlStopped(f"{origin}/robots.txt returned {status}; not crawling this host")
    rp = RobotFileParser()
    rp.parse(body.splitlines())
    return rp


def _forbidden(url: str, robots: RobotFileParser, user_agent: str) -> bool:
    path = urlsplit(url).path
    return any(path.startswith(p) for p in NEVER_REQUEST) or not robots.can_fetch(user_agent, url)


def allow_request(url: str, resource_type: str, robots: RobotFileParser,
                  user_agent: str = config.USER_AGENT) -> bool:
    """Whether the browser may make this request: catalog documents and the bot-check host only."""
    parts = urlsplit(url)
    if (parts.hostname or "").endswith(config.BOT_CHECK_HOST_SUFFIX):
        return True
    if f"{parts.scheme}://{parts.netloc}" != config.CATALOG_BASE or resource_type != "document":
        return False
    return not _forbidden(url, robots, user_agent)


class Crawler:
    def __init__(self, cache_dir: Path, loader: PageLoader, robots: RobotFileParser,
                 sleep: Callable[[float], None], clock: Callable[[], float],
                 origin: str = config.CATALOG_BASE):
        self.cache_dir = Path(cache_dir)
        self._loader = loader
        self._robots = robots
        self._sleep = sleep
        self._clock = clock
        self.origin = origin
        self._last: float | None = None

    def cached(self, url: str) -> LoadedPage | None:
        html_path, text_path = cache_path(self.cache_dir, url), cache_path(self.cache_dir, url, ".txt")
        if not (html_path.exists() and text_path.exists()):
            return None
        return LoadedPage(200, html_path.read_text(encoding="utf-8"), text_path.read_text(encoding="utf-8"))

    def _wait(self) -> None:
        delay = self._robots.crawl_delay(config.USER_AGENT)
        delay = float(delay) if delay is not None else config.DEFAULT_CRAWL_DELAY
        times = [t for t in (load_last_request(self.cache_dir).get(self.origin), self._last) if t is not None]
        if times:
            wait = max(times) + delay - self._clock()
            if wait > 0:
                self._sleep(wait)

    def get(self, url: str, expect: str) -> LoadedPage:
        hit = self.cached(url)
        if hit is not None:
            return hit
        if _forbidden(url, self._robots, config.USER_AGENT):
            raise DisallowedError(f"robots.txt disallows {url}")

        self._wait()
        loaded = self._loader.load(url)
        # The delay counts from the end of this visit.
        self._last = self._clock()
        save_last_request(self.cache_dir, self.origin, self._last)

        if loaded.status != 200:
            raise CrawlStopped(f"{url} ended with status {loaded.status}")
        if expect not in loaded.html:
            raise CrawlStopped(f"{url} lacks the expected content {expect!r} (blocked or changed?)")

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path(self.cache_dir, url).write_text(loaded.html, encoding="utf-8")
        cache_path(self.cache_dir, url, ".txt").write_text(loaded.text, encoding="utf-8")
        cache_path(self.cache_dir, url, ".url").write_text(url + "\n", encoding="utf-8")
        return loaded
