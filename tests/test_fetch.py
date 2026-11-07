import pytest

from owlpath_pipeline import config
from owlpath_pipeline.fetch import DisallowedError, EmptyResponseError, FetchError, PoliteFetcher

ROBOTS = "User-agent: *\nCrawl-delay: 120\nDisallow: /ajax/\n"
HOST = "https://catalog.example.edu"


class FakeWeb:
    """Serves robots.txt and pages; records every request and how long the fetcher slept."""

    def __init__(self, pages, robots=ROBOTS):
        self.pages = {f"{HOST}/robots.txt": (200, robots), **pages}
        self.calls, self.slept, self.now = [], [], 0.0

    def http_get(self, url, headers):
        self.calls.append((url, headers))
        return self.pages.get(url, (404, ""))

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds

    def clock(self):
        return self.now

    def fetcher(self, cache_dir):
        return PoliteFetcher(cache_dir, config.USER_AGENT, self.http_get, self.sleep, self.clock)

    def page_calls(self):
        return [u for u, _ in self.calls if not u.endswith("/robots.txt")]


def test_second_fetch_is_served_from_cache(tmp_path):
    web = FakeWeb({f"{HOST}/a": (200, "<p>A</p>")})
    f = web.fetcher(tmp_path)
    assert f.fetch(f"{HOST}/a") == "<p>A</p>"
    assert web.fetcher(tmp_path).fetch(f"{HOST}/a") == "<p>A</p>"  # new fetcher, same disk cache
    assert web.page_calls() == [f"{HOST}/a"]


def test_waits_crawl_delay_between_requests_same_host(tmp_path):
    web = FakeWeb({f"{HOST}/a": (200, "A"), f"{HOST}/b": (200, "B")})
    f = web.fetcher(tmp_path)
    f.fetch(f"{HOST}/a")
    web.now = 10.0
    f.fetch(f"{HOST}/b")
    assert web.slept == [110.0]


def test_default_delay_120_when_robots_has_none(tmp_path):
    web = FakeWeb({f"{HOST}/a": (200, "A"), f"{HOST}/b": (200, "B")}, robots="User-agent: *\nDisallow:\n")
    f = web.fetcher(tmp_path)
    f.fetch(f"{HOST}/a")
    f.fetch(f"{HOST}/b")
    assert web.slept == [120.0]


def test_disallowed_path_raises(tmp_path):
    web = FakeWeb({f"{HOST}/ajax/x": (200, "X")})
    with pytest.raises(DisallowedError):
        web.fetcher(tmp_path).fetch(f"{HOST}/ajax/x")
    assert web.page_calls() == []


def test_empty_body_raises_and_is_not_cached(tmp_path):
    web = FakeWeb({f"{HOST}/a": (200, "  \n")})
    with pytest.raises(EmptyResponseError):
        web.fetcher(tmp_path).fetch(f"{HOST}/a")
    assert list(tmp_path.iterdir()) == []


def test_non_200_raises_fetch_error(tmp_path):
    web = FakeWeb({f"{HOST}/a": (503, "busy")})
    with pytest.raises(FetchError):
        web.fetcher(tmp_path).fetch(f"{HOST}/a")
    assert list(tmp_path.iterdir()) == []


def test_sends_configured_user_agent(tmp_path):
    web = FakeWeb({f"{HOST}/a": (200, "A")})
    web.fetcher(tmp_path).fetch(f"{HOST}/a")
    assert all(h["User-Agent"] == config.USER_AGENT for _, h in web.calls)
