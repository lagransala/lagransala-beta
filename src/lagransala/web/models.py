from datetime import datetime, timedelta
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from ..models import ContentBlock, Event, SingleExtraction, Venue


class PublicVenueMetadata(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str

    @classmethod
    def from_venue(cls, venue: Venue) -> Self:
        return cls(slug=venue.slug, name=venue.name)


class PublicEvent(BaseModel):
    id: str
    venue: PublicVenueMetadata
    schedule: list[datetime]
    title: str | None
    description: str | None
    duration: timedelta | None
    url: HttpUrl

    @classmethod
    def from_event(cls, event: Event) -> Self:
        return cls(
            id=event.id.hex,
            venue=PublicVenueMetadata.from_venue(event.venue),
            schedule=[datetime.datetime for datetime in event.schedule],
            title=event.title,
            description=event.description,
            duration=event.duration,
            url=event.url,
        )


class EventTrace(BaseModel):
    event: PublicEvent
    extraction_data: SingleExtraction | None
    blocks: list[ContentBlock] | None


class PublicScheduledEvent(BaseModel):
    id: str
    venue: PublicVenueMetadata
    datetime: datetime
    title: str | None
    description: str | None
    duration: timedelta | None
    url: HttpUrl

    @classmethod
    def from_event(cls, event: Event) -> list[Self]:
        return [
            cls(
                id=event.id.hex,
                venue=PublicVenueMetadata.from_venue(event.venue),
                datetime=datetime.datetime,
                title=event.title,
                description=event.description,
                duration=event.duration,
                url=event.url,
            )
            for datetime in event.schedule
        ]
