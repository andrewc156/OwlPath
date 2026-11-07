"""Polite, caching HTTP fetcher: obeys robots.txt and its crawl delay, caches every page on disk.

CLI: .venv/bin/python -m owlpath_pipeline.fetch <url>   (prints the cache file path)
"""
import hashlib
import sys
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from . import config

HttpGet = Callable[[str, dict[str, str]], tuple[int, str]]


class FetchError(Exception):
    """A page couldn't be fetched (non-200 status, network failure)."""


class DisallowedError(FetchError):
    """robots.txt disallows this URL for our user agent."""


class EmptyResponseError(FetchError):
    """The server returned an empty body, e.g. bot protection. Never cached."""


class PoliteFetcher:
    def __init__(self, cache_dir: Path, user_agent: str, http_get: HttpGet,
                 sleep: Callable[[float], None], clock: Callable[[], float]):
        self.cache_dir = Path(cache_dir)
        self.user_agent = user_agent
        self._http_get = http_get
        self._sleep = sleep
        self._clock = clock
        self._robots: dict[str, RobotFileParser] = {}
        self._last_request: dict[str, float] = {}

    @classmethod
    def default(cls) -> "PoliteFetcher":
        import requests

        def http_get(url: str, headers: dict[str, str]) -> tuple[int, str]:
            try:
                r = requests.get(url, headers=headers, timeout=60)
            except requests.RequestException as e:
                raise FetchError(f"{url}: {e}") from e
            return r.status_code, r.text

        return cls(config.CACHE_DIR, config.USER_AGENT, http_get, time.sleep, time.monotonic)

    def cache_path(self, url: str) -> Path:
        return self.cache_dir / f"{hashlib.sha256(url.encode()).hexdigest()}.html"

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": self.user_agent}

    def _robots_for(self, origin: str) -> RobotFileParser:
        if origin not in self._robots:
            status, body = self._http_get(f"{origin}/robots.txt", self._headers())
            rp = RobotFileParser()
            if status == 200:
                rp.parse(body.splitlines())
            elif 400 <= status < 500:
                rp.parse([])  # no robots.txt: everything allowed, default delay still applies
            else:
                raise FetchError(f"{origin}/robots.txt returned {status}; not fetching from this host")
            self._robots[origin] = rp
        return self._robots[origin]

    def fetch(self, url: str) -> str:
        path = self.cache_path(url)
        if path.exists():
            return path.read_text(encoding="utf-8")

        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        robots = self._robots_for(origin)
        if not robots.can_fetch(self.user_agent, url):
            raise DisallowedError(f"robots.txt disallows {url}")

        delay = robots.crawl_delay(self.user_agent)
        delay = float(delay) if delay is not None else config.DEFAULT_CRAWL_DELAY
        last = self._last_request.get(origin)
        if last is not None:
            wait = last + delay - self._clock()
            if wait > 0:
                self._sleep(wait)

        self._last_request[origin] = self._clock()
        status, body = self._http_get(url, self._headers())
        if status != 200:
            raise FetchError(f"{url} returned {status}")
        if not body.strip():
            raise EmptyResponseError(f"{url} returned an empty body (blocked?)")

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        path.with_suffix(".url").write_text(url + "\n", encoding="utf-8")
        return body


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m owlpath_pipeline.fetch <url>", file=sys.stderr)
        return 2
    fetcher = PoliteFetcher.default()
    try:
        fetcher.fetch(argv[0])
    except FetchError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(fetcher.cache_path(argv[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
