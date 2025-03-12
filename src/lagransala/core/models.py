import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Sequence
from uuid import UUID, uuid4

import pydantic
import yaml
from pydantic import AwareDatetime, HttpUrl
from sqlmodel import Field, Relationship, Session, SQLModel, select

from ..utils.build_sqlmodel_type import build_sqlmodel_type

logger = logging.getLogger(__name__)


class Venue(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    events: list["Event"] = Relationship(back_populates="venue")
    name: str
    slug: str = pydantic.Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str
    address: str
    location_latitude: float
    location_longitude: float
    website: HttpUrl = Field(sa_type=build_sqlmodel_type(HttpUrl))
    schedule_url: HttpUrl | None = Field(sa_type=build_sqlmodel_type(HttpUrl))

    @classmethod
    def seed_from_yaml(cls, session: Session, yaml_path: Path):
        raw = yaml.safe_load(open(yaml_path))
        for raw_venue in raw:
            result = session.exec(
                select(Venue).where(Venue.id == UUID(hex=raw_venue["id"]))
            ).first()
            if result is None:
                venue = Venue.model_validate(raw_venue)
                session.add(venue)
        session.commit()


class Event(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    schedule: list["EventDateTime"] = Relationship(back_populates="event")
    venue_id: UUID = Field(default=None, foreign_key="venue.id")
    venue: Venue = Relationship(back_populates="events")

    url: HttpUrl = Field(sa_type=build_sqlmodel_type(HttpUrl))
    title: str
    author: str | None
    description: str
    duration: timedelta | None

    @classmethod
    def get_events_in_interval(
        cls, session: Session, start: AwareDatetime, end: AwareDatetime
    ) -> Sequence["Event"]:
        query = (
            select(Event)
            .join(EventDateTime)
            .where(EventDateTime.datetime >= start)
            .where(EventDateTime.datetime <= end)
            .distinct()
            .join(Venue)
        )
        return session.exec(query).all()

    @classmethod
    def get_urls(cls, session: Session) -> set[HttpUrl]:
        return set(map(lambda event: event.url, session.exec(select(Event)).all()))


class EventDateTime(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    event_id: UUID = Field(default=None, foreign_key="event.id")
    event: Event = Relationship(back_populates="schedule")

    datetime: datetime  # TODO: validate aware datetime
