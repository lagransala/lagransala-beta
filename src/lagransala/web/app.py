from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from babel.dates import format_datetime, get_timezone
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from ..core.models import (
    Event,
    EventDateTime,
    EventPartMap,
    Presentation,
    Projection,
    Venue,
)
from ..deps import initialize_sqlmodel
from .models import PublicPresentation, PublicProjection, PublicScheduledEvent


@asynccontextmanager
async def lifespan(_: FastAPI):
    print("TODO: Set up db")
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
engine = initialize_sqlmodel()
templates = Jinja2Templates(directory="templates")


def today() -> datetime:
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)


def month_end() -> datetime:
    next_month = datetime.now().replace(day=28) + timedelta(days=4)
    return (next_month - timedelta(days=next_month.day)).replace(
        hour=23, minute=59, second=59
    )


def get_public_events(since: datetime, to: datetime) -> list[PublicScheduledEvent]:
    with Session(engine) as session:
        events = session.exec(
            (
                select(Event)
                .join(EventDateTime)
                .join(EventPartMap)
                .join(Presentation, isouter=True)
                .join(Projection, isouter=True)
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
            "request": {"since": since, "to": to},
            "events": grouped_events,
        },
    )
