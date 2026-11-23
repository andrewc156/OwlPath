import pytest

from owlpath_pipeline import config
from owlpath_pipeline.crawl import (Crawler, CrawlStopped, LoadedPage, allow_request, read_robots)
from owlpath_pipeline.fetch import DisallowedError, PoliteFetcher, cache_path, load_last_request
from urllib.robotparser import RobotFileParser

ROBOTS = "User-agent: *\nCrawl-delay: 120\nDisallow: /ajax/\n"
HOST = config.CATALOG_BASE
CAT = config.CATALOG_BASE


def page(html="<p>Credit Hour</p>", status=200):
    return LoadedPage(status, html, "text of " + html)


class Clock:
    def __init__(self):
        self.now, self.slept = 0.0, []

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds

    def __call__(self):
        return self.now


class FakeLoader:
    """url -> LoadedPage; records calls. Advances the clock by `visit` seconds per load."""

    def __init__(self, pages, clock=None, visit=0.0, fail_on=None):
        self.pages, self.calls, self.clock, self.visit, self.fail_on = pages, [], clock, visit, fail_on

    def load(self, url):
        self.calls.append(url)
        if self.fail_on is not None and len(self.calls) == self.fail_on:
            return page(status=202)
        if self.clock:
            self.clock.now += self.visit
        return self.pages.get(url, page())


def robots(text=ROBOTS):
    rp = RobotFileParser()
    rp.parse(text.splitlines())
    return rp


def crawler(tmp_path, loader, clock):
    return Crawler(tmp_path, loader, robots(), clock.sleep, clock)


def test_disallowed_url_is_never_loaded(tmp_path):
    clock, loader = Clock(), FakeLoader({})
    with pytest.raises(DisallowedError):
        crawler(tmp_path, loader, clock).get(f"{HOST}/ajax/x", "Credit Hour")
    assert loader.calls == []


def test_waits_crawl_delay_between_pages_and_across_crawlers(tmp_path):
    clock = Clock()
    loader = FakeLoader({}, clock, visit=7.0)
    crawler(tmp_path, loader, clock).get(f"{HOST}/a", "Credit Hour")
    crawler(tmp_path, loader, clock).get(f"{HOST}/b", "Credit Hour")
    assert clock.slept == [120.0]
    assert load_last_request(tmp_path)[HOST] == clock.now


def test_polite_fetcher_honours_crawler_last_request(tmp_path):
    clock = Clock()
    crawler(tmp_path, FakeLoader({}, clock, visit=5.0), clock).get(f"{HOST}/a", "Credit Hour")
    fetcher = PoliteFetcher(tmp_path, config.USER_AGENT,
                            lambda url, h: (200, ROBOTS if url.endswith("/robots.txt") else "B"),
                            clock.sleep, clock)
    fetcher.fetch(f"{HOST}/b")
    assert clock.slept == [120.0]


def test_cached_page_is_not_loaded_again(tmp_path):
    clock = Clock()
    loader = FakeLoader({f"{HOST}/a": page("<b>Credit Hour</b>")}, clock)
    first = crawler(tmp_path, loader, clock).get(f"{HOST}/a", "Credit Hour")
    second = crawler(tmp_path, loader, clock).get(f"{HOST}/a", "Credit Hour")
    assert loader.calls == [f"{HOST}/a"]
    assert second == first and second.html == "<b>Credit Hour</b>" and second.text == first.text
    assert crawler(tmp_path, loader, clock).cached(f"{HOST}/a") == first
    assert crawler(tmp_path, loader, clock).cached(f"{HOST}/zzz") is None
    assert cache_path(tmp_path, f"{HOST}/a", ".txt").exists()
    assert cache_path(tmp_path, f"{HOST}/a", ".url").exists()


def test_non_200_stops_and_caches_nothing(tmp_path):
    clock = Clock()
    loader = FakeLoader({f"{HOST}/a": page(status=202)})
    with pytest.raises(CrawlStopped):
        crawler(tmp_path, loader, clock).get(f"{HOST}/a", "Credit Hour")
    assert not cache_path(tmp_path, f"{HOST}/a").exists()
    assert list(tmp_path.glob("*.txt")) == [] and list(tmp_path.glob("*.url")) == []


def test_missing_expected_content_stops(tmp_path):
    clock = Clock()
    loader = FakeLoader({f"{HOST}/a": page("<p>nothing here</p>")})
    with pytest.raises(CrawlStopped):
        crawler(tmp_path, loader, clock).get(f"{HOST}/a", "Credit Hour")
    assert not cache_path(tmp_path, f"{HOST}/a").exists()


def test_unreadable_robots_stops():
    with pytest.raises(CrawlStopped):
        read_robots(HOST, lambda url, headers: (503, ""))


def test_read_robots_parses_a_200():
    seen = []

    def get(url, headers):
        seen.append((url, headers))
        return 200, ROBOTS

    rp = read_robots(HOST, get)
    assert seen == [(f"{HOST}/robots.txt", {"User-Agent": config.USER_AGENT})]
    assert rp.crawl_delay(config.USER_AGENT) == 120


def test_stop_midway_keeps_cache_and_resumes(tmp_path):
    urls = [f"{HOST}/p{i}" for i in range(1, 5)]
    clock = Clock()
    broken = FakeLoader({}, clock, fail_on=3)
    with pytest.raises(CrawlStopped):
        c = crawler(tmp_path, broken, clock)
        for u in urls:
            c.get(u, "Credit Hour")
    healthy = FakeLoader({}, clock)
    c = crawler(tmp_path, healthy, clock)
    for u in urls:
        c.get(u, "Credit Hour")
    assert healthy.calls == [urls[2], urls[3]]


def test_allow_request_rules():
    rp = robots()
    assert allow_request(f"{CAT}/content.php?catoid=84", "document", rp)
    assert not allow_request(f"{CAT}/js/jquery.js", "script", rp)
    assert not allow_request(f"{CAT}/ajax/preview_course.php", "document", rp)
    assert allow_request("https://x.y.us-east-1.token.awswaf.com/a/challenge.js", "script", rp)
    assert not allow_request("https://ssl.google-analytics.com/ga.js", "script", rp)
    assert not allow_request("https://evil.com/?x=.token.awswaf.com", "script", rp)


def test_never_requests_listed_paths_even_without_robots_rules():
    rp = robots("User-agent: *\nDisallow:\n")
    for path in ("/ajax/x", "/search_advanced.php", "/portfolio.php", "/portfolio_nopop.php"):
        assert not allow_request(f"{CAT}{path}", "document", rp)


def test_loader_exception_becomes_stop_and_still_records_last_request(tmp_path):
    class Boom:
        def load(self, url):
            clock.now += 3.0
            raise TimeoutError("bot check")

    clock = Clock()
    with pytest.raises(CrawlStopped, match="bot check"):
        crawler(tmp_path, Boom(), clock).get(f"{HOST}/a", "Credit Hour")
    assert load_last_request(tmp_path)[HOST] == 3.0
    assert not cache_path(tmp_path, f"{HOST}/a").exists()


def test_robots_network_failure_is_one_line_stop(monkeypatch, capsys):
    import requests
    from owlpath_pipeline.crawl import main

    def boom(*a, **k):
        raise requests.ConnectionError("no route")

    monkeypatch.setattr(requests, "get", boom)
    assert main(["undergraduate"], loader_factory=lambda r: None) == 1
    out = capsys.readouterr().out
    assert out.startswith("STOPPED:") and len(out.splitlines()) == 1


def test_loader_error_becomes_crawl_stopped(tmp_path):
    class Boom:
        def load(self, url):
            raise TimeoutError("page took too long")

    with pytest.raises(CrawlStopped, match=r"x\.html.*page took too long"):
        crawler(tmp_path, Boom(), Clock()).get(f"{HOST}/x.html", "Credit Hour")
    assert load_last_request(tmp_path)  # the visit was still recorded


def test_main_reports_loader_error_as_stop(tmp_path, monkeypatch, capsys):
    from contextlib import nullcontext
    from owlpath_pipeline.crawl import main

    class Boom:
        def load(self, url):
            raise TimeoutError("slow")

    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    assert main(["undergraduate"], http_get=lambda u, h: (200, "User-agent: *\nCrawl-delay: 0\n"),
                loader_factory=lambda r: nullcontext(Boom())) == 1
    out = capsys.readouterr().out
    assert out.startswith("STOPPED:") and len(out.splitlines()) == 1
