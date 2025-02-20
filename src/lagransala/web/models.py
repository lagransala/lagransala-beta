from datetime import datetime, timedelta
from typing import Self

from pydantic import BaseModel, Field, HttpUrl

from ..core.models import Event, Presentation, Projection, Venue


class PublicVenueMetadata(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str

    @classmethod
    def from_venue(cls, venue: Venue) -> Self:
        return cls(slug=venue.slug, name=venue.name)


class PublicPart(BaseModel):
    type: str


class PublicProjection(PublicPart):
    title: str
    duration: timedelta | None
    country: str | None
    original_language: str | None
    subtitled: bool | None
    director: list[str]
    actors: list[str]
    description: str
    comment: str | None
    comment_author: str | None

    @classmethod
    def from_projection(cls, projection: Projection) -> Self:
        return cls(
            type="projection",
            title=projection.title,
            duration=projection.duration,
            country=projection.country,
            original_language=projection.original_language,
            subtitled=projection.subtitled,
            director=projection.director,
            actors=projection.actors,
            description=projection.description,
            comment=projection.comment,
            comment_author=projection.comment_author,
        )


class PublicPresentation(PublicPart):
    short_description: str | None
    description: str | None
    speakers: list[str]

    @classmethod
    def from_presentation(cls, presentation: Presentation) -> Self:
        return cls(
            type="presentation",
            short_description=presentation.short_description,
            description=presentation.description,
            speakers=presentation.speakers,
        )


class PublicScheduledEvent(BaseModel):
    venue: PublicVenueMetadata
    datetime: datetime
    title: str | None
    description: str | None
    duration: timedelta | None
    url: HttpUrl
    parts: list[PublicProjection | PublicPresentation]

    @classmethod
    def from_event(cls, event: Event):
        result: list[PublicScheduledEvent] = []
        parts: list[PublicProjection | PublicPresentation] = []
        for part_map in event.part_maps:
            if part_map.presentation:
                parts.append(
                    PublicPresentation.from_presentation(part_map.presentation)
                )
            elif part_map.projection:
                parts.append(PublicProjection.from_projection(part_map.projection))
        for event_datetime in event.schedule:
            result.append(
                cls(
                    venue=PublicVenueMetadata.from_venue(event.venue),
                    datetime=event_datetime.datetime,
                    title=event.title,
                    description=event.description,
                    duration=event.duration,
                    url=event.url,
                    parts=parts,
                )
            )
        return result
