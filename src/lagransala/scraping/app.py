import logging
from pathlib import Path
from typing import Awaitable, Callable
from uuid import UUID

import aiohttp
import groq
from anthropic import RateLimitError
from langfuse.decorators import observe
from pydantic import HttpUrl, ValidationError
from redis import StrictRedis
from sqlmodel import Session, select
from tqdm.asyncio import tqdm_asyncio

from ..deps import (
    INSTRUCTOR_MODEL,
    initialize_instructor_groq,
    initialize_redis,
    initialize_sqlmodel,
)
from ..models import ContentBlock, Event, ExtractionData, Venue, VenueSpec
from ..scraping.scrapers import ContentBlocksScraper, ScheduleScraper
from .extractors import EventDataExtractor

logger = logging.getLogger(__name__)


async def main1():
    engine = initialize_sqlmodel()
    with Session(engine) as session:
        events = session.exec(select(Event)).all()
        for event in events:
            for schedule in event.schedule:
                if (
                    event.venue.slug in ["sala-berlanga"]
                    and schedule.datetime.year < 2025
                ):
                    print(schedule.datetime.strftime("%Y-%m-%d %H:%M"), event.url)
                    schedule.datetime = schedule.datetime.replace(year=2025)
        session.commit()


@observe
async def event_url_pipeline(
    db_session: Session,
    block_extractor: Callable[[HttpUrl], Awaitable[list[ContentBlock]]],
    event_data_extractor: Callable[
        [HttpUrl, list[ContentBlock]], Awaitable[ExtractionData]
    ],
    url: HttpUrl,
    venue_id: UUID,
) -> list[Event]:
    try:
        content_blocks = await block_extractor(url)
        event_data = await event_data_extractor(url, content_blocks)
    except aiohttp.ClientConnectorError as e:
        logger.error(f"ConnectionError:\nurl: {str(url)}\nError: {str(e)}")
        return []
    except aiohttp.ConnectionTimeoutError as e:
        logger.error(str(e))
        return []
    except groq.BadRequestError as e:
        logger.error(e.message)
        logger.error(e.body)
        return []
    except ValidationError as e:
        msg = f"ValidationError while extracting from {url}:\n"
        for error in e.errors():
            msg += f'- message: {error["msg"]}\n'
            msg += f'  loc:     {error["loc"]}\n'
            msg += f'  input:   {error["input"]}\n'
        logger.error(msg)
        return []
    except RateLimitError as e:
        logger.error(
            f"RateLimitError while extracting from {url}:\n{e.response.json()}"
        )
        return []
    else:
        events = event_data.as_events(url, venue_id)
        for event in events:
            db_session.add(event)
        db_session.commit()
        logger.info(f"Committed {len(events)} events from {url}")
        return events


def get_spec_by_id(specs: list[VenueSpec], venue_id: UUID) -> VenueSpec | None:
    for spec in specs:
        if spec.venue_id == venue_id:
            return spec
    return None


async def extract_events_from_venue(
    http_session: aiohttp.ClientSession,
    db_session: Session,
    redis: StrictRedis,
    event_data_extractor: Callable[
        [HttpUrl, list[ContentBlock]], Awaitable[ExtractionData]
    ],
    venue_spec: VenueSpec,
    event_urls: set[HttpUrl],
):
    schedule_scraper = ScheduleScraper(http_session, redis, venue_spec)
    content_blocks_scraper = ContentBlocksScraper(http_session, redis, venue_spec)
    urls = await schedule_scraper()
    new_urls = urls - event_urls
    logger.info(f"Found {len(new_urls)} new urls for {venue_spec.venue.slug}")
    await tqdm_asyncio.gather(
        *[
            event_url_pipeline(
                db_session,
                content_blocks_scraper,
                event_data_extractor,
                url,
                venue_spec.venue_id,
            )
            for url in new_urls
        ]
    )


async def main(venue_slugs: list[str] | None = None):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%y/%m/%d %H:%M:%S",
    )

    engine = initialize_sqlmodel()
    instructor_client = initialize_instructor_groq()
    redis = initialize_redis()

    event_data_extractor = EventDataExtractor(
        instructor_client, redis, model=INSTRUCTOR_MODEL
    )

    with Session(engine) as db_session:
        Venue.seed_from_yaml(db_session, Path("./seeders/venues.yaml"))
        VenueSpec.seed_from_yaml(db_session, Path("./seeders/specs.yaml"))
        venue_specs = db_session.exec(select(VenueSpec)).all()

        if venue_slugs is not None:
            venue_specs = [
                venue_spec
                for venue_spec in venue_specs
                if venue_spec.venue.slug in venue_slugs
            ]
        event_urls = Event.get_urls(db_session)  # TODO: this could get really big

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
        }

        async with aiohttp.ClientSession(headers=headers) as http_session:
            for venue_spec in venue_specs:
                await extract_events_from_venue(
                    http_session,
                    db_session,
                    redis,
                    event_data_extractor,
                    venue_spec,
                    event_urls,
                )
