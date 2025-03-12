from datetime import datetime, timedelta
from typing import Self

from pydantic import BaseModel, Field, HttpUrl

from ..core.models import Event, Venue


class PublicVenueMetadata(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str

    @classmethod
    def from_venue(cls, venue: Venue) -> Self:
        return cls(slug=venue.slug, name=venue.name)


class PublicScheduledEvent(BaseModel):
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
                venue=PublicVenueMetadata.from_venue(event.venue),
                datetime=datetime.datetime,
                title=event.title,
                description=event.description,
                duration=event.duration,
                url=event.url,
            )
            for datetime in event.schedule
        ]
