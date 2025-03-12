from datetime import datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator

from ..core.models import Event, EventDateTime


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
    def parse_duration(cls, value: str | int | None) -> timedelta | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = int(value)
        return timedelta(minutes=value)

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
