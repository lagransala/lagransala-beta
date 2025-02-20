import asyncio
import logging
from datetime import date

from instructor import AsyncInstructor
from langfuse import Langfuse
from langfuse.decorators import langfuse_context, observe

from ..scraping.models import SourcedContentBlocks
from .models.v2 import ExtractionModel

logger = logging.getLogger(__name__)

langfuse = Langfuse()

extractor_prompt = langfuse.get_prompt("event_extractor")


@observe(as_type="generation")
async def intermediate_event_instructor_extractor(
    sourced_content_blocks: SourcedContentBlocks,
    client: AsyncInstructor,
    model: str = "claude-3-5-haiku-20241022",
):
    langfuse_context.update_current_trace(release="v2")

    langfuse_context.update_current_observation(
        input=sourced_content_blocks,
        model=model,
        prompt=extractor_prompt,
    )

    logging.info(f"Extracting intermediate event from {sourced_content_blocks.url}")
    async with asyncio.Semaphore(8):  # TODO: Make this based on rate limiting
        intermediate_event, completion_data = (
            await client.chat.completions.create_with_completion(
                model=model,
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
                response_model=ExtractionModel,
                context={
                    "blocks": sourced_content_blocks.blocks,
                    "current_year": date.today().year,
                },
            )
        )
    langfuse_context.update_current_observation(
        usage_details={
            "input_tokens": completion_data.usage.input_tokens,
            "output_tokens": completion_data.usage.output_tokens,
        }
    )
    return intermediate_event
