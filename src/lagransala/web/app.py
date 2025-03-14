from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from uuid import UUID

from babel.dates import format_datetime
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import TypeAdapter
from sqlmodel import Session, select

from ..deps import INSTRUCTOR_MODEL, initialize_redis, initialize_sqlmodel
from ..models import ContentBlock, Event, EventDateTime, SingleExtraction, Venue
from ..utils.http_url_key import http_url_key
from .models import EventTrace, PublicEvent, PublicScheduledEvent


@asynccontextmanager
async def lifespan(_: FastAPI):
    print("TODO: Set up db")
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

engine = initialize_sqlmodel()
redis = initialize_redis()


def today() -> datetime:
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)


def month_end() -> datetime:
    next_month = datetime.now().replace(day=28) + timedelta(days=4)
    return (next_month - timedelta(days=next_month.day)).replace(
        hour=23, minute=59, second=59
    )


def get_public_event(event_id: UUID) -> PublicEvent | None:
    with Session(engine) as session:
        event = session.exec(
            (
                select(Event)
                .join(EventDateTime)
                .join(Venue)
                .distinct()
                .where(Event.id == event_id)
            )
        ).first()
        return PublicEvent.from_event(event) if event else None


def get_public_event_trace(event_id: UUID) -> EventTrace | None:
    event = get_public_event(event_id)
    if event is None:
        return None
    url = event.url
    event_data_extractor_key = (
        f"event_data_extractor:{INSTRUCTOR_MODEL}:{http_url_key(url)}"
    )
    if data := redis.get(event_data_extractor_key):
        extraction_data = SingleExtraction.model_validate_json(data)
    else:
        extraction_data = None
    content_blocks_scraper_key = f"content_blocks_scraper:{http_url_key(url)}"
    adapter = TypeAdapter(list[ContentBlock])
    if data := redis.get(content_blocks_scraper_key):
        blocks = adapter.validate_json(data)
    else:
        blocks = None
    print(
        f"""
        event: {event}
        extraction_data_key: {event_data_extractor_key}
        extraction_data: {extraction_data}
        content_blocks_key: {content_blocks_scraper_key}
        content_blocks: {len(blocks) if blocks else -1}
          """
    )
    return EventTrace(event=event, extraction_data=extraction_data, blocks=blocks)


def get_public_events(since: datetime, to: datetime) -> list[PublicScheduledEvent]:
    with Session(engine) as session:
        events = session.exec(
            (
                select(Event)
                .join(EventDateTime)
                .join(Venue)
                .distinct()
                .where(EventDateTime.datetime >= since)
                .where(EventDateTime.datetime <= to)
            )
        ).all()
        return list(
            filter(
                lambda e: since <= e.datetime <= to,
                sum(map(PublicScheduledEvent.from_event, events), []),
            )
        )


@app.get("/events/", response_model=list[PublicScheduledEvent])
async def events(
    since: datetime = Query(default_factory=today),
    to: datetime = Query(default_factory=month_end),
) -> list[PublicScheduledEvent]:
    return get_public_events(since, to)


@app.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    since: datetime = Query(default_factory=today),
    to: datetime = Query(default_factory=month_end),
):
    public_events = get_public_events(since, to)
    public_events.sort(key=lambda x: x.datetime)
    grouped_events: dict[str, dict[str, list[PublicScheduledEvent]]] = {}
    for public_event in public_events:
        month = format_datetime(public_event.datetime, format="MMMM", locale="es")
        day = format_datetime(public_event.datetime, format="EEEE d", locale="es")
        if public_event.datetime < since:
            print(public_event.title, public_event.datetime)
        grouped_events.setdefault(month, dict()).setdefault(day, []).append(
            public_event
        )
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "events": grouped_events,
        },
    )


@app.get("/event_trace/{event_id}", response_class=HTMLResponse)
async def event_trace(request: Request, event_id: str):
    try:
        uuid = UUID(hex=event_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    else:
        event_trace = get_public_event_trace(uuid)
        if event_trace is None:
            raise HTTPException(status_code=404, detail="Event not found")
        return templates.TemplateResponse(
            "event_trace.html", {"request": request, "trace": event_trace}
        )
