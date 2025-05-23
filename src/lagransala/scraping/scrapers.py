import logging
import re
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup
from langfuse.decorators.langfuse_decorator import asyncio
from pydantic import HttpUrl, TypeAdapter
from redis import StrictRedis

from lagransala.utils.http_url_key import http_url_key

from ..models import ContentBlock, ContentBlockSpec, VenueSpec

logger = logging.getLogger(__name__)


class ContentBlocksScraper:
    def __init__(
        self, session: aiohttp.ClientSession, redis: StrictRedis, venue_spec: VenueSpec
    ) -> None:
        self.session = session
        self.redis = redis
        self.redis_key = "content_blocks_scraper"
        self.venue_spec = venue_spec

    async def __call__(self, url: HttpUrl) -> list[ContentBlock]:
        key = f"{self.redis_key}:{http_url_key(url)}"
        adapter = TypeAdapter(list[ContentBlock])
        if data := self.redis.get(key):
            logger.debug(f"CacheHit: {key}")
            blocks = adapter.validate_json(data)
        else:
            text = await self._fetch_html(url)
            soup = BeautifulSoup(text, "html.parser")
            blocks = self._extract_content_blocks(soup)
            self.redis.set(key, adapter.dump_json(blocks))
        return [block.clean_markdown for block in blocks]

    def task(self, url: HttpUrl) -> asyncio.Task[list[ContentBlock]]:
        return asyncio.create_task(self(url))

    async def _fetch_html(self, url: HttpUrl) -> str:
        logger.info(f"Fetch html from {url}")
        # TODO: Rate limit with semaphore
        async with self.session.get(str(url)) as response:
            text = await response.text()
            return text

    def _extract_content_blocks(self, soup: BeautifulSoup) -> list[ContentBlock]:
        # Clean up the html soup
        for element in soup.find_all(["script", "style", "nav", "header", "footer"]):
            element.decompose()
        blocks = [
            self._soup_scraper(soup, spec)
            for spec in self.venue_spec.content_block_specs
        ]
        return blocks

    def _soup_scraper(
        self, soup: BeautifulSoup, spec: ContentBlockSpec
    ) -> ContentBlock:
        if len(soup.select(spec.selector)) > 1:
            logger.info(
                f"More than one block found with selector `{spec.selector}` (using the first)"
            )
        tag = soup.select_one(spec.selector)

        if tag is None:
            logger.info(
                f"Empty block found with selector `{spec.selector}` (relevant `{spec.relevant}`)"
            )

        block = ContentBlock(spec=spec, content=None if tag is None else str(tag))
        return block


class ScheduleScraper:
    def __init__(
        self,
        http_session: aiohttp.ClientSession,
        redis: StrictRedis,
        venue_spec: VenueSpec,
    ) -> None:
        self.http_session = http_session
        self.redis = redis
        self.redis_key = "schedule_scraper"
        self.venue_spec = venue_spec

    @property
    def tasks(self) -> list[asyncio.Task[set[HttpUrl]]]:
        return [self._page_task(url) for url in self.pages]

    async def __call__(self) -> set[HttpUrl]:
        url_sets = await asyncio.gather(*self.tasks)
        return set().union(*url_sets)

    @property
    def pages(self) -> list[HttpUrl]:
        return self.venue_spec.pagination_urls

    async def _page_event_urls(self, page_url: HttpUrl) -> set[HttpUrl]:
        key = f"{self.redis_key}:{http_url_key(page_url)}"
        adapter = TypeAdapter(set[HttpUrl])
        if data := self.redis.get(key):
            logger.debug(f"CacheHit: {key}")
            return adapter.validate_json(data)
        logger.info(f"Getting page urls from {page_url}")
        urls: set[HttpUrl] = set()
        # TODO: Rate limit with semaphore
        async with self.http_session.get(str(page_url)) as response:
            soup = BeautifulSoup(await response.text(), "html.parser")
            links = map(lambda tag: tag.get("href"), soup.select("[href]"))
            for link in links:
                if not isinstance(link, str):
                    continue
                if re.match(self.venue_spec.event_url_pattern, link):
                    if link.startswith(("http://", "https://")):
                        urls.add(HttpUrl(link))
                    else:
                        urls.add(HttpUrl(urljoin(str(page_url), link)))
        data = adapter.dump_python(urls)
        self.redis.set(key, adapter.dump_json(urls))
        return urls

    def _page_task(self, page_url: HttpUrl) -> asyncio.Task[set[HttpUrl]]:
        return asyncio.create_task(self._page_event_urls(page_url))
