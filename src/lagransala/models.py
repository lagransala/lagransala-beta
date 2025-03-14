import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Self, Sequence
from uuid import UUID, uuid4

import pydantic
import yaml
from markdownify import markdownify
from pydantic import AwareDatetime, BaseModel, HttpUrl, field_validator, model_validator
from sqlmodel import Field, Relationship, Session, SQLModel, select

from .utils.build_sqlmodel_type import build_sqlmodel_list_type, build_sqlmodel_type

logger = logging.getLogger(__name__)


class Venue(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    events: list["Event"] = Relationship(back_populates="venue")
    specs: list["VenueSpec"] = Relationship(back_populates="venue")

    name: str
    slug: str = pydantic.Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str
    address: str
    location_latitude: float
    location_longitude: float
    website: HttpUrl = Field(sa_type=build_sqlmodel_type(HttpUrl))
    schedule_url: HttpUrl | None = Field(sa_type=build_sqlmodel_type(HttpUrl))

    @classmethod
    def seed_from_yaml(cls, session: Session, yaml_path: Path) -> None:
        with open(yaml_path) as f:
            raw = yaml.safe_load(f)
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


class ContentBlockSpec(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    venue_spec: "VenueSpec" = Relationship(back_populates="content_block_specs")
    venue_spec_id: UUID = Field(foreign_key="venuespec.id")

    selector: str
    relevant: str
    irrelevant: str | None = None
    remove_regex: list[str] = Field(sa_type=build_sqlmodel_list_type(str), default=[])
    strip_elements: list[str] = Field(
        sa_type=build_sqlmodel_list_type(str), default=["a", "img"]
    )


class ContentBlock(BaseModel):
    spec: ContentBlockSpec
    content: str | None  # Content could be None if the block is empty
    is_markdown: bool = False

    def update_content(self, content: str | None) -> "ContentBlock":
        if content == "":
            content = None
        return self.model_copy(update={"content": content})

    @property
    def markdown(self) -> "ContentBlock":
        if self.content is None:
            return self
        if self.is_markdown:
            return self
        else:
            markdown_options = {
                "strip": ["script", "style"] + self.spec.strip_elements,
                "heading_style": "ATX",
                "bullets": "-",
            }
            return self.model_copy(
                update={
                    "content": markdownify(self.content, **markdown_options),
                    "is_markdown": True,
                }
            )

    @property
    def clean_markdown(self) -> "ContentBlock":
        block = self.markdown.model_copy()
        for regex in self.spec.remove_regex:
            if block.content is None:
                break
            if block.content == "":
                block = block.update_content(None)
                break
            assert block.content is not None
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


class PaginationType(Enum):
    NONE = "none"
    SIMPLE = "simple"
    DAY = "day"
    MONTH = "month"


class VenueSpec(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    venue: Venue = Relationship(back_populates="specs")
    venue_id: UUID = Field(foreign_key="venue.id")
    content_block_specs: list[ContentBlockSpec] = Relationship(
        back_populates="venue_spec"
    )

    event_url_pattern: str

    pagination_type: PaginationType | None = None
    pagination_url: str
    pagination_limit: int | None = None
    pagination_simple_start_from: int | None = None
    pagination_date_format: str | None = None

    @model_validator(mode="after")
    def validate_pagination(self) -> Self:
        match self.pagination_type:
            case PaginationType.NONE | None:
                assert (
                    self.pagination_limit is None
                ), "Pagination limit must be None for PaginationType.NONE"
                assert (
                    self.pagination_simple_start_from is None
                ), "Pagination start from must be None for PaginationType.NONE"
                assert (
                    self.pagination_date_format is None
                ), "Date format must be None for PaginationType.NONE"
            case PaginationType.SIMPLE:
                assert (
                    "{n}" in self.pagination_url
                ), "Simple pagination URL must contain '{n}'"
                assert (
                    self.pagination_simple_start_from is not None
                ), "Simple pagination start from must be set"
                assert (
                    self.pagination_limit is not None
                ), "Simple pagination limit must be set"
            case PaginationType.DAY:
                assert (
                    "{date}" in self.pagination_url
                ), "Day pagination URL must contain '{date}'"
                assert (
                    self.pagination_date_format is not None
                ), "Date format must be set for Day pagination"
                assert (
                    self.pagination_limit is not None
                ), "Day pagination limit must be set"
            case PaginationType.MONTH:
                assert (
                    "{month}" in self.pagination_url
                ), "Month pagination URL must contain '{month}'"
                assert (
                    self.pagination_date_format is not None
                ), "Date format must be set for Month pagination"
                assert (
                    self.pagination_limit is not None
                ), "Month pagination limit must be set"
        return self

    @property
    def pagination_urls(self) -> list[HttpUrl]:
        match self.pagination_type:
            case PaginationType.NONE | None:
                return [HttpUrl(self.pagination_url)]
            case PaginationType.SIMPLE:
                assert self.pagination_simple_start_from is not None
                assert self.pagination_limit is not None
                return [
                    HttpUrl(self.pagination_url.format(n=i))
                    for i in range(
                        self.pagination_simple_start_from,
                        self.pagination_limit + self.pagination_simple_start_from,
                    )
                ]
            case PaginationType.DAY:
                assert self.pagination_date_format is not None
                assert self.pagination_limit is not None
                today = datetime.now().replace(minute=0, hour=0, second=0)
                result: list[HttpUrl] = []
                for i in range(0, self.pagination_limit):
                    date = today + timedelta(days=i)
                    url = HttpUrl(
                        self.pagination_url.format(
                            date=date.strftime(self.pagination_date_format)
                        )
                    )
                    result.append(url)
                return result
            case PaginationType.MONTH:
                assert self.pagination_date_format is not None
                assert self.pagination_limit is not None
                month_start = datetime.now().replace(day=1, minute=0, hour=0, second=0)
                current_month = month_start.month
                result: list[HttpUrl] = []
                for i in range(0, self.pagination_limit):
                    month = month_start.replace(month=current_month + i)
                    url = HttpUrl(
                        self.pagination_url.format(
                            date=month.strftime(self.pagination_date_format)
                        )
                    )
                    result.append(url)
                return result

    @classmethod
    def seed_from_yaml(cls, session: Session, yaml_path: Path) -> None:
        with open(yaml_path) as f:
            raw = yaml.safe_load(f)
        for raw_spec in raw:
            result = session.exec(
                select(VenueSpec).where(
                    VenueSpec.venue_id == UUID(hex=raw_spec["venue_id"])
                )
            ).first()
            if result is None:
                spec = VenueSpec.model_validate(raw_spec)
                block_specs: list[ContentBlockSpec] = []
                for block_spec_raw in raw_spec["content_block_specs"]:
                    block_spec_raw["venue_spec_id"] = spec.id
                    block_specs.append(ContentBlockSpec.model_validate(block_spec_raw))
                spec.content_block_specs = block_specs
                session.add(spec)
        session.commit()


class EventData(BaseModel):
    schedule: list[datetime] = Field(..., description="List of event datetimes")
    title: str = Field(
        ...,
        description="Title of the event. Be careful not to include other information like the cycle or festival name.",
    )
    author: str | None = Field(..., description="Author of the event")
    description: str = Field(..., description="Description of the event")
    duration: timedelta | None = Field(
        ..., description='Duration of the event in number of minutes. (e.g. "93")'
    )

    @field_validator("duration", mode="before")
    @classmethod
    def parse_duration(cls, value: str | int | None) -> timedelta | str | None:
        if isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                pass
        if isinstance(value, int):
            return timedelta(minutes=value)
        return value

    def as_event(self, url: HttpUrl, venue_id: UUID):
        return Event(
            title=self.title,
            schedule=[EventDateTime(datetime=datetime) for datetime in self.schedule],
            author=self.author,
            description=self.description,
            duration=self.duration,
            url=url,
            venue_id=venue_id,
        )


class ExtractionError(Enum):
    EMPTY_PAGE = "Empty page"
    MISSING_DATA = "Missing data"
    MALFORMED_DATA = "Malformed data"


class ExtractionData(ABC):
    extraction_error: ExtractionError | None

    @abstractmethod
    def as_events(self, url: HttpUrl, venue_id: UUID) -> list[Event]:
        raise NotImplementedError()


class SingleExtraction(ExtractionData, BaseModel):
    event_data: EventData | None = Field(
        ...,
        description="Event data extracted from the page. If no data could be extracted, the field should be null.",
    )
    extraction_error: ExtractionError | None = Field(
        ..., description="Error that occurred during extraction"
    )

    def as_events(self, url: HttpUrl, venue_id: UUID) -> list[Event]:
        return [self.event_data.as_event(url, venue_id)] if self.event_data else []


class MultipleExtraction(ExtractionData, BaseModel):
    event_data: list[EventData] = Field(
        ...,
        description="Event data extracted from the page. If no data could be extracted, the list should be empty.",
    )
    extraction_error: ExtractionError | None = Field(
        ..., description="Error that occurred during extraction"
    )

    def as_events(self, url: HttpUrl, venue_id: UUID) -> list[Event]:
        return [event_data.as_event(url, venue_id) for event_data in self.event_data]
