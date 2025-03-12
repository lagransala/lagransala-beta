import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from uuid import UUID

from markdownify import markdownify
from pydantic import BaseModel, HttpUrl
from sqlmodel import Session, select

from ..core.models import Venue


class ContentBlockSpec(BaseModel):
    selector: str
    relevant: str
    irrelevant: str | None = None
    remove_regex: list[str] = []
    strip_elements: list[str] = ["a", "img"]


class ContentBlock(ContentBlockSpec):
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
                "strip": ["script", "style"] + self.strip_elements,
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
        for regex in self.remove_regex:
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


class VenueSpec(BaseModel):
    venue_id: UUID
    block_defs: list[ContentBlockSpec]

    pagination: PaginationType
    event_url_pattern: str

    @property
    def pagination_urls(self) -> list[HttpUrl]:
        return self.pagination.urls()

    def get_venue(self, session: Session) -> Venue:
        venue = session.exec(select(Venue).where(Venue.id == self.venue_id)).first()
        if venue is None:
            raise ValueError(f"Venue with id {self.venue_id} not found")
        return venue
