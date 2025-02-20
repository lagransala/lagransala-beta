from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, HttpUrl
from sqlmodel import Session, select

from ..core.models import Venue


class ContentBlockDef(BaseModel):
    selector: str
    relevant: str
    irrelevant: str | None = None
    remove_regex: list[str] = []
    critical: bool = False
    strip_elements: list[str] = ["a", "img"]


class ContentBlock(ContentBlockDef):
    content: str | None  # Content could be None if the block is empty

    def update_content(self, content: str | None) -> "ContentBlock":
        if content == "":
            content = None
        return self.model_copy(update={"content": content})


class SourcedContentBlocks(BaseModel):
    url: HttpUrl
    venue_id: UUID
    blocks: list[ContentBlock]


class Pagination(ABC):
    @abstractmethod
    def urls(self) -> list[HttpUrl]:
        raise NotImplementedError()


class NoPagination(BaseModel, Pagination):
    url: HttpUrl

    def urls(self) -> list[HttpUrl]:
        return [self.url]


class SimplePagination(BaseModel, Pagination):
    url_template: str
    limit: int
    start_from: int = 1

    def urls(self) -> list[HttpUrl]:
        return [
            HttpUrl(self.url_template.format(n=i))
            for i in range(self.start_from, self.limit + self.start_from)
        ]


class DatePagination(BaseModel, Pagination):
    url_template: str
    date_format: str
    limit: int

    def urls(self) -> list[HttpUrl]:
        today = datetime.now().replace(minute=0, hour=0, second=0)
        result: list[HttpUrl] = []
        for i in range(0, self.limit):
            date = today + timedelta(days=i)
            url = HttpUrl(
                self.url_template.format(date=date.strftime(self.date_format))
            )
            result.append(url)
        return result


class MonthPagination(BaseModel, Pagination):
    url_template: str
    month_format: str
    limit: int

    def urls(self) -> list[HttpUrl]:
        month_start = datetime.now().replace(day=1, minute=0, hour=0, second=0)
        current_month = month_start.month
        result: list[HttpUrl] = []
        for i in range(0, self.limit):
            month = month_start.replace(month=current_month + i)
            url = HttpUrl(
                self.url_template.format(month=month.strftime(self.month_format))
            )
            result.append(url)
        return result


type PaginationType = NoPagination | SimplePagination | DatePagination | MonthPagination


class ScheduleDef(BaseModel):
    pagination: PaginationType
    event_url_pattern: str

    @property
    def urls(self) -> list[HttpUrl]:
        return self.pagination.urls()


class VenueExtractionDef(BaseModel):
    venue_id: UUID
    schedule_spec: ScheduleDef
    block_defs: list[ContentBlockDef]

    def get_venue(self, session: Session) -> Venue:
        venue = session.exec(select(Venue).where(Venue.id == self.venue_id)).first()
        if venue is None:
            raise ValueError(f"Venue with id {self.venue_id} not found")
        return venue
