from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from ...core.models import Event, EventDateTime, EventPartMap, Presentation, Projection

CURRENT_YEAR = datetime.now().year


class ExtractionProjection(BaseModel):
    title: str = Field(
        description="Title of the content being projected, possibly translated to spanish"
    )
    original_title: str = Field(
        description="Title of the content in the original language"
    )
    duration: timedelta | None = Field(description="Duration of the projection")
    country: str | None = Field(description="Country of origin")
    year: str | None = Field(description="Year of publication")
    original_language: str | None
    subtitled: bool | None
    director: list[str]
    actors: list[str]
    description: str = Field(
        description="Summary or general description of the content"
    )
    extra_description: str | None = Field(
        title="Extra description",
        description="More information about the content. Can be a review or quote.",
    )
    extra_description_author: str | None = Field(
        description="Author of the extra description, if any."
    )

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
            comment=self.extra_description,
            comment_author=self.extra_description_author,
        )

    @property
    def as_event_part_map(self) -> EventPartMap:
        return EventPartMap(projection=self.as_projection)


class ExtractionExtra(BaseModel):
    type: Literal["presentation", "talk", "debate", "lesson", "questions"] | None = (
        Field(title="Type of extra event part")
    )
    description: str | None
    speakers: list[str] = Field(description="List of people presenting or speaking")

    @property
    def as_presentation(self) -> Presentation:
        return Presentation(
            short_description=self.type,
            description=self.description,
            speakers=self.speakers,
        )

    @property
    def as_event_part_map(self) -> EventPartMap:
        return EventPartMap(presentation=self.as_presentation)


class ExtractionEvent(BaseModel):
    schedule: list[datetime] = Field(
        title="Schedule of the event",
        description=(
            "List of dates and times when the event will happen. If the "
            "original content doesn't contain a reference to the year of the "
            f"event, it should be assumed to be equal to {CURRENT_YEAR}."
        ),
    )
    title: str | None = Field(
        title="Title of the event",
        description=(
            "Title of the event. If the event has only one part it should be "
            "equal to the part title"
        ),
    )
    description: str | None
    duration: timedelta | None
    url: HttpUrl
    parts: list[ExtractionProjection | ExtractionExtra] = Field(
        title="Parts of the event",
        description=(
            "List of parts that compose the event. Each part can be a "
            "projection or a presentation."
        ),
    )

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
    content: ExtractionEvent | list[ExtractionEvent]

    def as_events(self, venue_id: UUID, url: HttpUrl) -> list[Event]:
        match self.content:
            case ExtractionEvent():
                return [self.content.as_event(venue_id, url)]
            case list():
                return [event.as_event(venue_id, url) for event in self.content]
