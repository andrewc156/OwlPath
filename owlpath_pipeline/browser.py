"""Real page loader: headless Chromium with our honest User-Agent, passing the site's bot check as a normal browser.

Only catalog documents and the bot-check host are allowed (see crawl.allow_request); everything else is aborted.
Playwright is an optional extra ("crawl"), imported only when the loader starts, so CI and tests never need it.
"""
import time
from urllib.robotparser import RobotFileParser

from . import config
from .crawl import CrawlStopped, LoadedPage, allow_request


class PlaywrightLoader:
    def __init__(self, robots: RobotFileParser, user_agent: str = config.USER_AGENT,
                 challenge_timeout: float = config.CRAWL_CHALLENGE_TIMEOUT):
        self._robots = robots
        self._user_agent = user_agent
        self._timeout = challenge_timeout

    def __enter__(self) -> "PlaywrightLoader":
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        context = self._browser.new_context(user_agent=self._user_agent)
        context.route("**/*", self._route)
        self._page = context.new_page()
        return self

    def __exit__(self, *exc) -> None:
        self._browser.close()
        self._pw.stop()

    def _route(self, route) -> None:
        request = route.request
        if allow_request(request.url, request.resource_type, self._robots, self._user_agent):
            route.continue_()
        else:
            route.abort()

    def load(self, url: str) -> LoadedPage:
        """Navigate and wait until the main document's last response is 200 (the bot check passed and reloaded)."""
        statuses: list[int] = []

        def on_response(response) -> None:
            if response.request.is_navigation_request() and response.request.frame == self._page.main_frame:
                statuses.append(response.status)

        self._page.on("response", on_response)
        try:
            try:
                self._page.goto(url, wait_until="domcontentloaded", timeout=self._timeout * 1000)
            except Exception as e:  # a 202 challenge page may be replaced mid-navigation
                if not statuses:
                    raise CrawlStopped(f"could not load {url}: {e}") from e
            deadline = time.monotonic() + self._timeout
            while not (statuses and statuses[-1] == 200):
                if time.monotonic() > deadline:
                    raise CrawlStopped(f"bot check not passed within {self._timeout:.0f} s (statuses {statuses})")
                self._page.wait_for_timeout(250)
            self._page.wait_for_load_state("domcontentloaded")
            return LoadedPage(statuses[-1], self._page.content(), self._page.inner_text("body"))
        finally:
            self._page.remove_listener("response", on_response)
