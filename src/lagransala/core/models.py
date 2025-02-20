import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Sequence
from uuid import UUID, uuid4

import pydantic
import yaml
from pydantic import AwareDatetime, HttpUrl, model_validator
from sqlmodel import Field, Relationship, Session, SQLModel, select
from typing_extensions import Self

from ..utils.build_sqlmodel_type import build_sqlmodel_list_type, build_sqlmodel_type

logger = logging.getLogger(__name__)


class Venue(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    cycles: list["Cycle"] = Relationship(back_populates="venue")
    events: list["Event"] = Relationship(back_populates="venue")
    name: str
    slug: str = pydantic.Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str
    address: str
    location_latitude: float
    location_longitude: float
    website: HttpUrl = Field(sa_type=build_sqlmodel_type(HttpUrl))
    schedule_url: HttpUrl | None = Field(sa_type=build_sqlmodel_type(HttpUrl))
    pricing_url: HttpUrl | None = Field(sa_type=build_sqlmodel_type(HttpUrl))

    @classmethod
    def seed_from_yaml(
        cls, session: Session, yaml_path: Path = Path("./seeders/venues.yaml")
    ):
        raw = yaml.safe_load(open(yaml_path))
        for raw_venue in raw:
            result = session.exec(
                select(Venue).where(Venue.id == UUID(hex=raw_venue["id"]))
            ).first()
            if result is None:
                venue = Venue.model_validate(raw_venue)
                session.add(venue)
            else:
                logger.info(f"Venue {result.name} ({result.id}) already exists")
        session.commit()


class Cycle(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    venue_id: int = Field(foreign_key="venue.id")
    venue: Venue = Relationship(back_populates="cycles")
    events: list["Event"] = Relationship(back_populates="cycle")
    name: str
    description: str | None
    url: HttpUrl = Field(sa_type=build_sqlmodel_type(HttpUrl))


class Event(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    schedule: list["EventDateTime"] = Relationship(back_populates="event")
    venue_id: UUID = Field(default=None, foreign_key="venue.id")
    venue: Venue = Relationship(back_populates="events")

    part_maps: list["EventPartMap"] = Relationship(back_populates="event")
    cycle_id: UUID | None = Field(default=None, foreign_key="cycle.id")
    cycle: Cycle | None = Relationship(back_populates="events")

    title: str | None
    description: str | None
    duration: timedelta | None
    url: HttpUrl = Field(sa_type=build_sqlmodel_type(HttpUrl))

    @property
    def parts(self):
        for part_map in self.part_maps:
            if part_map.presentation:
                yield part_map.presentation
            elif part_map.projection:
                yield part_map.projection

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


class Projection(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    event_part_map: "EventPartMap" = Relationship(back_populates="projection")

    title: str
    duration: timedelta | None
    # year: int | None # TODO: add field ¿db migration?
    country: str | None
    original_language: str | None
    subtitled: bool | None
    director: list[str] = Field(sa_type=build_sqlmodel_list_type(str))
    actors: list[str] = Field(sa_type=build_sqlmodel_list_type(str))
    description: str
    comment: str | None
    comment_author: str | None


class Presentation(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    event_part_map: "EventPartMap" = Relationship(back_populates="presentation")
    short_description: str | None
    description: str | None
    speakers: list[str] = Field(sa_type=build_sqlmodel_list_type(str))


class EventPartMap(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    event_id: UUID = Field(default=None, foreign_key="event.id")
    event: Event = Relationship(back_populates="part_maps")
    projection_id: UUID | None = Field(default=None, foreign_key="projection.id")
    projection: Projection | None = Relationship(back_populates="event_part_map")
    presentation_id: UUID | None = Field(default=None, foreign_key="presentation.id")
    presentation: Presentation | None = Relationship(back_populates="event_part_map")

    # TODO: validate only one not null part column
    @model_validator(mode="after")
    def non_empty_map(self) -> Self:
        assert (self.projection_id is None) != (
            self.presentation_id is None
        ), "Need to provide either a projection or a presentation"
        return self
