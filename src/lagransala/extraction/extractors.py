import asyncio
import logging
from datetime import date

from instructor import AsyncInstructor
from langfuse import Langfuse
from langfuse.decorators import langfuse_context, observe
from pydantic import HttpUrl
from tenacity import AsyncRetrying, stop_after_attempt, wait_random_exponential

from ..scraping.models import ContentBlock
from .models import EventData

logger = logging.getLogger(__name__)

langfuse = Langfuse()

extractor_prompt = langfuse.get_prompt("event_extractor")


class EventDataExtractor:
    def __init__(self, client: AsyncInstructor, model: str, max_concurrency: int = 1):
        self.client = client
        self.model = model
        self.semaphore = asyncio.Semaphore(max_concurrency)

    @observe(as_type="generation")
    async def __call__(self, content_blocks: list[ContentBlock]) -> EventData:
        langfuse_context.update_current_trace(release="v2")

        langfuse_context.update_current_observation(
            input=content_blocks,
            model=self.model,
            prompt=extractor_prompt,
        )

        async with self.semaphore:  # TODO: Make this based on rate limiting
            intermediate_event = await self.client.chat.completions.create(
                model=self.model,
                max_tokens=2048,
                messages=[
                    {
                        "role": "system",
                        "content": extractor_prompt.prompt,
                    },
                    {
                        "role": "user",
                        "content": """
                        {% for block in blocks %}
                        <block>
                            <relevant>{{ block.relevant }}</relevant>
                            {% if block.irrelevant %}
                            <irrelevant>{{ block.irrelevant }}</irrelevant>
                            {% endif %}
                            <content>{{ block.content }}</content>
                        </block>
                        {% endfor %}
                        """,
                    },
                ],
                response_model=EventData,
                context={
                    "blocks": content_blocks,
                    "current_year": date.today().year,
                },
                max_retries=AsyncRetrying(
                    wait=wait_random_exponential(multiplier=10, min=5, max=120),
                    stop=stop_after_attempt(3),
                    reraise=True,
                ),
            )
        # langfuse_context.update_current_observation(
        #     usage_details={
        #         "input_tokens": completion_data.usage.input_tokens,
        #         "output_tokens": completion_data.usage.output_tokens,
        #     }
        # )
        return intermediate_event
