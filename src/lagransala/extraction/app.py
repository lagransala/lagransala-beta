import asyncio
import logging

import aiohttp
from anthropic import RateLimitError
from instructor import AsyncInstructor
from langfuse.decorators import observe
from pydantic import HttpUrl, ValidationError
from sqlmodel import Session, select

from lagransala.scraping.models import VenueExtractionDef

from ..core.models import Event, Venue
from ..deps import initialize_instructor_gemini, initialize_sqlmodel
from ..scraping.app import venue_extraction_defs_from_yaml
from ..scraping.scrapers import content_blocks_scraper, schedule_def_scraper
from ..utils.coroutine_with_data import coroutine_with_data
from .extractors import intermediate_event_instructor_extractor

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
    http_session: aiohttp.ClientSession,
    instructor_client: AsyncInstructor,
    url: HttpUrl,
    spec: VenueExtractionDef,
) -> list[Event]:
    try:
        sourced_blocks = await content_blocks_scraper(http_session, url, spec)
        extraction = await intermediate_event_instructor_extractor(
            sourced_blocks, instructor_client
        )
    except aiohttp.ClientConnectorError as e:
        logger.error(f"ConnectionError:\nurl: {str(url)}\nError: {str(e)}")
        return []
    except aiohttp.ConnectionTimeoutError as e:
        logger.error(str(e))
        return []
    except ValidationError as e:
        msg = "ValidationError while extracting from {url}:\n"
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
        # events: list[Event] = []
        # for event in extraction.as_events(spec.venue_id, url):
        #     db_session.add(event)
        #     events.append(event)
        event = extraction.as_event(spec.venue_id, url)
        db_session.add(event)
        events = [event]
        logger.info(f"Committed {len(events)} events from {url}")
        db_session.commit()
        return events


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%y/%m/%d %H:%M:%S",
    )

    engine = initialize_sqlmodel()
    instructor_client = initialize_instructor_gemini()
    with Session(engine) as db_session:

        specs = venue_extraction_defs_from_yaml()
        Venue.seed_from_yaml(db_session)
        event_urls = Event.get_urls(db_session)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
        }

        async with aiohttp.ClientSession(headers=headers) as http_session:
            # TODO: avoid having to wait for all urls to be scraped before starting to extract
            # TODO: Implement delays between webpage loading, per domain
            raw_urls = await asyncio.gather(
                *[
                    asyncio.create_task(
                        coroutine_with_data(
                            schedule_def_scraper(http_session, spec.schedule_spec),
                            spec,
                            lambda urls, spec: [(url, spec) for url in urls],
                        ),
                        name=f"schedule_def_scraper({spec.venue_id})",
                    )
                    for spec in specs
                ]
            )
            urls = [
                (url, spec)
                for urls in raw_urls
                for url, spec in urls
                if url not in event_urls
            ]
            found: set[HttpUrl] = set()
            for url, spec in urls:
                if url in found:
                    urls.remove((url, spec))
                found.add(url)
            print(
                f"Found {len(urls)} new urls (removed {len(found) - len(urls)} duplicates)"
            )

            new_events = [
                event
                for events in await asyncio.gather(
                    *[
                        event_url_pipeline(
                            db_session, http_session, instructor_client, url, spec
                        )
                        for url, spec in urls
                    ]
                )
                for event in events
            ]
            print(f"Added {len(new_events)} new events from {len(urls)} urls")
