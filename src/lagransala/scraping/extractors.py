import asyncio
import logging
from datetime import date

from instructor import AsyncInstructor
from langfuse import Langfuse
from langfuse.decorators import langfuse_context, observe
from pydantic import HttpUrl
from redis import StrictRedis
from tenacity import AsyncRetrying, stop_after_attempt, wait_random_exponential

from ..models import ContentBlock, SingleExtraction
from ..utils.http_url_key import http_url_key

logger = logging.getLogger(__name__)

langfuse = Langfuse()

extractor_prompt = langfuse.get_prompt("event_extractor")


class EventDataExtractor:
    def __init__(
        self,
        client: AsyncInstructor,
        redis: StrictRedis,
        model: str,
        max_concurrency: int = 1,
    ):
        self.client = client
        self.redis = redis
        self.redis_key = f"event_data_extractor:{model}"
        self.model = model
        self.semaphore = asyncio.Semaphore(max_concurrency)

    @observe(as_type="generation")
    async def __call__(
        self, url: HttpUrl, content_blocks: list[ContentBlock]
    ) -> SingleExtraction:
        key = f"{self.redis_key}:{http_url_key(url)}"
        if data := self.redis.get(key):
            logger.debug(f"CacheHit: {key}")
            extraction_data = SingleExtraction.model_validate_json(data)
        else:
            async with self.semaphore:  # TODO: Make this based on rate limiting
                langfuse_context.update_current_trace(release="v2")

                langfuse_context.update_current_observation(
                    input=content_blocks,
                    model=self.model,
                    prompt=extractor_prompt,
                )
                logger.info(f"Extracting event data from {url}")
                extraction_data, completion = (
                    await self.client.chat.completions.create_with_completion(
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
                        response_model=SingleExtraction,
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
                )
                self.redis.set(key, extraction_data.model_dump_json())
                # langfuse_context.update_current_observation(
                #     usage_details={
                #         "input_tokens": completion.usage.input_tokens,
                #         "output_tokens": completion.usage.output_tokens,
                #     }
                # )
        return extraction_data
