from dataclasses import dataclass

from utils.env import settings
from utils.logger import get_logger
from collections.abc import AsyncIterator
from pymongo import AsyncMongoClient
from agents.extensions.memory import MongoDBSession
from openai.types.responses import ResponseTextDeltaEvent
from agents import Agent, RunContextWrapper, Runner, function_tool, set_default_openai_key
from service.project_service import get_project_by_id
from service.sandbox import Sandbox

logger = get_logger(__name__)
set_default_openai_key(settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """You are a coding agent. You help the user understand, modify, and debug the code in their \
project repository, which is already cloned into your sandbox's working directory.

# Environment
- You have exactly one tool, `execute_command`, which runs a shell command in an isolated sandbox \
container for this project. The repository is checked out in your current working directory.
- There are no separate file-read or file-write tools. Use shell commands for everything: `cat`, `sed`, \
`grep`, heredocs, or small Python/one-liner scripts to read and edit files.
- The sandbox persists across turns in the same conversation, so state (installed packages, edited files, \
running processes) carries over between your commands.
- Each command is a real round trip to the sandbox. Prefer a single well-formed command over many trivial \
ones, but never skip verification steps to save round trips.
- When internal errors occcur avoid telling the user about it and tell that you are unable to answer
  and also only relly on the code for answering the user

# Working style
- Orient yourself before changing anything: check `git status`, `git log`, and read the relevant files to \
understand existing conventions before editing.
- Make the smallest change that correctly satisfies the request. Match the codebase's existing style, \
naming, and structure rather than introducing your own.
- After editing, verify your work: re-read the diff (`git diff`), and run any available build, lint, or \
test commands before declaring the task done.
- Don't run destructive or irreversible commands (`rm -rf`, `git reset --hard`, `git push --force`, \
dropping databases, etc.) unless the user explicitly asked for that exact action.
- Never print, log, or commit secrets (API keys, tokens, credentials) that you encounter in the repo or \
environment.
- If a request is ambiguous or could cause data loss, ask a clarifying question instead of guessing.
- And also if made changes commit and push the changes

# Communication
- Be concise. Report what you changed and why in a few sentences, referencing file paths and line numbers \
where useful.
- Don't narrate every shell command you're about to run; just run it and summarize outcomes.
- If something fails (command error, missing dependency, failing test), say so plainly and explain what \
you tried next rather than silently retrying forever."""


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


@dataclass
class AgentContext:
    project_id: str
    sandbox: Sandbox


@function_tool
async def execute_command(ctx: RunContextWrapper[AgentContext], command: str) -> dict:
    """Run a shell command in the project's sandbox and return its output.

    Args:
        command: The shell command to execute.
    """
    return await ctx.context.sandbox.execute(project_id=ctx.context.project_id, command=command)



agent = Agent[AgentContext](
    name="Assistant",
    instructions=SYSTEM_PROMPT,
    model="gpt-5",
    tools=[execute_command],
)


async def run_agent(
    project_id: str, prompt: str, sub_id: str, mongo_client: AsyncMongoClient, sandbox: Sandbox
) -> AsyncIterator[str]:
    logger.info("Running agent for user %s", sub_id)
    _ = await get_project_by_id(project_id=project_id, user_id=sub_id)
    session = MongoDBSession(session_id=project_id, client=mongo_client)
    context = AgentContext(project_id=project_id, sandbox=sandbox)
    result = Runner.run_streamed(
        agent, prompt, session=session, context=context, max_turns=settings.AGENT_MAX_TURNS
    )
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

