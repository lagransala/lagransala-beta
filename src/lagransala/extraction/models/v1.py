from datetime import datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, HttpUrl

from ...core.models import Event, EventDateTime, EventPartMap, Presentation, Projection


class ExtractionProjection(BaseModel):
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

    @property
    def as_projection(self) -> Projection:
        return Projection(
            title=self.title,
            duration=self.duration,
            country=self.country,
            original_language=self.original_language,
            subtitled=self.subtitled,
            director=self.director,
            actors=self.actors,
            description=self.description,
            comment=self.comment,
            comment_author=self.comment_author,
        )

    @property
    def as_event_part_map(self) -> EventPartMap:
        return EventPartMap(projection=self.as_projection)


class ExtractionPresentation(BaseModel):
    short_description: str | None
    description: str | None
    speakers: list[str]

    @property
    def as_presentation(self) -> Presentation:
        return Presentation(
            short_description=self.short_description,
            description=self.description,
            speakers=self.speakers,
        )

    @property
    def as_event_part_map(self) -> EventPartMap:
        return EventPartMap(presentation=self.as_presentation)


class ExtractionEvent(BaseModel):
    schedule: list[datetime]
    title: str | None
    description: str | None
    duration: timedelta | None
    url: HttpUrl
    parts: list[ExtractionProjection | ExtractionPresentation]

    def as_event(self, venue_id: UUID, url: HttpUrl) -> Event:
        return Event(
            schedule=[EventDateTime(datetime=datetime) for datetime in self.schedule],
            venue_id=venue_id,
            title=self.title,
            description=self.description,
            duration=self.duration,
            url=url,
            part_maps=[part.as_event_part_map for part in self.parts],
        )


class ExtractionModel(BaseModel):
    content: ExtractionEvent
