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
from .fetch import DisallowedError, FetchError, HttpGet, cache_path, load_last_request, save_last_request

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
        try:
            loaded = self._loader.load(url)
        except CrawlStopped:
            raise
        except Exception as e:  # e.g. a Playwright timeout or crash: stop with a message, the cache stays valid
            raise CrawlStopped(f"loading {url} failed: {e}") from e
        finally:
            # The host was hit even if the load raised; the delay counts from the end of this visit.
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


FIXTURE_DIR = config.REPO_ROOT / "tests" / "fixtures" / "catalog"


def main(argv: list[str] | None = None, http_get: HttpGet | None = None, loader_factory=None) -> int:
    """http_get and loader_factory(robots) -> context-managed PageLoader are injectable for tests."""
    import argparse
    import time

    import requests

    if loader_factory is None:
        from .browser import PlaywrightLoader as loader_factory

    parser = argparse.ArgumentParser(prog="owlpath_pipeline.crawl")
    sub = parser.add_subparsers(dest="command", required=True)
    cap = sub.add_parser("capture", help="fetch one catalog page politely and save it as a test fixture")
    cap.add_argument("url")
    cap.add_argument("name")
    cap.add_argument("--expect", required=True, help="text the page must contain")
    for level in config.CATALOGS:
        lv = sub.add_parser(level, help=f"crawl the whole {level} catalog into catalog/{level}/ snapshot files")
        lv.add_argument("--refresh", action="store_true", help="delete this catalog's cached pages first")
    args = parser.parse_args(argv)

    if http_get is None:
        def http_get(url: str, headers: dict[str, str]) -> tuple[int, str]:
            try:
                r = requests.get(url, headers=headers, timeout=60)
            except requests.RequestException as e:
                raise FetchError(f"{url}: {e}") from e
            return r.status_code, r.text

    try:
        robots = read_robots(config.CATALOG_BASE, http_get)
        with loader_factory(robots) as loader:
            crawler = Crawler(config.CACHE_DIR, loader, robots, time.sleep, time.time)
            if args.command in config.CATALOGS:
                from .snapshot import clear_catalog_cache, crawl_level, write_snapshot
                if args.refresh:
                    n = clear_catalog_cache(config.CACHE_DIR, config.catoid(args.command))
                    print(f"cleared {n} cached pages")
                snap = crawl_level(args.command, crawler)
                write_snapshot(snap)
                print(f"{args.command}: {len(snap.courses)} courses, {len(snap.programs)} programs, "
                      f"{len(snap.out_of_scope)} out of scope")
                return 0
            page = crawler.get(args.url, args.expect)
    except (CrawlStopped, FetchError) as e:  # FetchError covers DisallowedError
        print(f"STOPPED: {e}")
        return 1
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    (FIXTURE_DIR / f"{args.name}.html").write_text(page.html, encoding="utf-8")
    (FIXTURE_DIR / f"{args.name}.txt").write_text(page.text, encoding="utf-8")
    print(f"captured {args.url} -> tests/fixtures/catalog/{args.name}.html ({len(page.html)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
