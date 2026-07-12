from utils.env import settings
from utils.logger import get_logger
from collections.abc import AsyncIterator
from pymongo import AsyncMongoClient
from agents.extensions.memory import MongoDBSession
from openai.types.responses import ResponseTextDeltaEvent
from agents import Agent, Runner, set_default_openai_key
from service.project_service import get_project_by_id

logger = get_logger(__name__)
set_default_openai_key(settings.OPENAI_API_KEY)
SYSTEM_PROMPT = "You are a helpful assistant with access to web search and local tools. Use them when you need current or specific information."

# example mock tool
# @function_tool
# def get_weather(location: str) -> str:
#     """Get the current weather for a location. Mock implementation for local testing.
#
#     Args:
#         location: City and state, e.g. San Francisco, CA.
#     """
#     logger.info("Running mock get_weather tool")
#     return f"It's sunny and 72°F in {location}."


agent = Agent(
    name="Assistant",
    instructions=SYSTEM_PROMPT,
    model="gpt-5",
    tools=[],
)


async def run_agent(project_id: str, prompt: str, sub_id: str, mongo_client: AsyncMongoClient) -> AsyncIterator[str]:
    logger.info("Running agent for user %s", sub_id)
    _ = await get_project_by_id(project_id=project_id, user_id=sub_id)
    session = MongoDBSession(session_id=project_id, client=mongo_client)
    result = Runner.run_streamed(agent, prompt, session=session)
    async for event in result.stream_events():
        if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
            yield event.data.delta


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") in ("input_text", "output_text")
        )
    return ""


async def get_session_messages(project_id: str, sub_id: str, mongo_client: AsyncMongoClient) -> list[dict]:
    logger.info("Fetching session messages for user %s", sub_id)
    _ = await get_project_by_id(project_id=project_id, user_id=sub_id)
    session = MongoDBSession(session_id=project_id, client=mongo_client)
    items = await session.get_items()

    messages = []
    for item in items:
        role = item.get("role")
        if role not in ("user", "assistant"):
            continue
        text = _extract_text(item.get("content"))
        if text:
            messages.append({"role": role, "content": text})
    return messages

