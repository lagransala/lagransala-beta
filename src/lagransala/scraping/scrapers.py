import logging
import re
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup
from langfuse.decorators.langfuse_decorator import asyncio
from markdownify import markdownify
from pydantic import HttpUrl

from .models import (
    ContentBlock,
    ContentBlockDef,
    ScheduleDef,
    SourcedContentBlocks,
    VenueExtractionDef,
)

logger = logging.getLogger(__name__)


# TODO: Dependency injection for BeautifulSoup
def soup_content_block_scraper(
    soup: BeautifulSoup, spec: ContentBlockDef
) -> ContentBlock:
    if len(soup.select(spec.selector)) > 1:
        logging.info(
            f"More than one block found with selector `{spec.selector}` (using the first)"
        )
    tag = soup.select_one(spec.selector)

    if tag is None:
        logging.info(
            f"Empty block found with selector `{spec.selector}` (relevant `{spec.relevant}`)"
        )

    return ContentBlock(
        selector=spec.selector,
        relevant=spec.relevant,
        remove_regex=spec.remove_regex,
        strip_elements=spec.strip_elements,
        content=None if tag is None else str(tag),
    )


def content_block_html_to_markdown(block: ContentBlock) -> ContentBlock:
    """
    Formats an HTML block into markdown.

    Args:
        blocks: The HTML block to format
    Returns:
        The markdown formatted block
    """
    if block.content is None:
        return block

    markdown_options = {
        "strip": ["script", "style"] + block.strip_elements,
        "heading_style": "ATX",
        "bullets": "-",
    }

    return block.update_content(markdownify(block.content, **markdown_options))


def content_block_markdown_cleaner(block: ContentBlock) -> ContentBlock:
    """
    Cleans up a markdown block, using the remove_regex field to remove unwanted
    elements. Also remo
    """
    for regex in block.remove_regex:
        if block.content is None:
            break
        if block.content == "":
            block = block.update_content(None)
            break
        block = block.update_content(re.sub(regex, "", block.content))
    if block.content is None:
        return block

    # Remove multiple blank lines

    block = block.update_content(re.sub(r"\n\s*\n\s*\n", "\n\n", block.content))
    # Remove trailing whitespace
    assert block.content is not None
    block = block.update_content(
        "\n".join(line.rstrip() for line in block.content.splitlines())
    )
    assert block.content is not None
    block = block.update_content(block.content.strip() + "\n")

    if block.content in ["", " ", "\n"]:
        block = block.update_content(None)
    return block


async def content_blocks_scraper(
    session: aiohttp.ClientSession, url: HttpUrl, extraction_def: VenueExtractionDef
) -> SourcedContentBlocks:
    """
    Fetches the webpage content and extracts the specified content blocks.

    Args:
        document: The webpage content source
        block_specs: The content blocks specifications
    Returns:
        A list of blocks with content in markdown format
    """

    logger.info(f"Scraping content blocks from {url}")
    async with session.get(str(url)) as response:
        soup = BeautifulSoup(await response.text(), "html.parser")

        # Clean up the html soup
        for element in soup.find_all(["script", "style", "nav", "header", "footer"]):
            element.decompose()
        blocks = [
            soup_content_block_scraper(soup, spec) for spec in extraction_def.block_defs
        ]
        blocks = [content_block_html_to_markdown(block) for block in blocks]
        blocks = [content_block_markdown_cleaner(block) for block in blocks]
        return SourcedContentBlocks(
            url=url, venue_id=extraction_def.venue_id, blocks=blocks
        )


async def schedule_page_scraper(
    client: aiohttp.ClientSession, page_url: HttpUrl, event_url_pattern: str
) -> set[HttpUrl]:
    urls = set()
    logger.info(f"Getting event urls from {page_url}")
    async with client.get(str(page_url)) as response:
        soup = BeautifulSoup(await response.text(), "html.parser")
        links = map(lambda tag: tag.get("href"), soup.select("[href]"))
        for link in links:
            if not isinstance(link, str):
                continue
            if re.match(event_url_pattern, link):
                if link.startswith(("http://", "https://")):
                    urls.add(HttpUrl(link))
                else:
                    urls.add(HttpUrl(urljoin(str(page_url), link)))
    return urls


async def schedule_def_scraper(
    client: aiohttp.ClientSession, spec: ScheduleDef
) -> set[HttpUrl]:
    return set().union(
        *await asyncio.gather(
            *[
                schedule_page_scraper(client, url, spec.event_url_pattern)
                for url in spec.urls
            ]
        )
    )
