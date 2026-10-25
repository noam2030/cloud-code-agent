from functools import lru_cache

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app import config


class Route(BaseModel):
    intent: str = Field(description="'code' if files must be created or changed, otherwise 'answer'")


class FileChange(BaseModel):
    path: str = Field(description="repo-relative path")
    content: str = Field(description="full file content")


class Proposal(BaseModel):
    summary: str = Field(description="one-line commit title, under 70 characters")
    files: list[FileChange]


ROUTER_PROMPT = (
    "Classify the user's request. Answer 'code' if it asks to create, change, fix or add code or files. "
    "Answer 'answer' for questions about architecture, implementation or the codebase."
)
ANSWER_PROMPT = (
    "You are the Answerer, a senior software architect. Answer questions about the repository using the "
    "files provided. Be concise and cite file paths. Do not write files."
)
WRITER_PROMPT = (
    "You are the Writer. Implement the task by returning the complete content of every new or changed file. "
    "Keep changes minimal. Never touch .git. Provide a one-line summary usable as a commit title."
)
REVIEWER_PROMPT = (
    "You are the Reviewer. Review the proposed changes for bugs, security problems and whether they fulfil the task. "
    "The first line must be exactly APPROVE or REQUEST_CHANGES. Then list concrete issues, if any."
)


@lru_cache
def _llm() -> ChatOpenAI:
    return ChatOpenAI(model=config.OPENAI_MODEL, temperature=0)


async def _structured(schema, system: str, human: str):
    out = await _llm().with_structured_output(schema, include_raw=True).ainvoke(
        [("system", system), ("human", human)]
    )
    if out["parsed"] is None:
        raise ValueError(f"model returned no parsable {schema.__name__}")
    return out["parsed"], out["raw"].usage_metadata


async def _text(system: str, human: str):
    msg = await _llm().ainvoke([("system", system), ("human", human)])
    return msg.content, msg.usage_metadata


async def route(message: str):
    return await _structured(Route, ROUTER_PROMPT, message)


async def answer(message: str, context: str):
    return await _text(ANSWER_PROMPT, f"Repository files:\n{context}\n\nQuestion:\n{message}")


async def write(message: str, context: str, review: str | None = None):
    human = f"Repository files:\n{context}\n\nTask:\n{message}"
    if review:
        human += f"\n\nReviewer feedback to address:\n{review}"
    return await _structured(Proposal, WRITER_PROMPT, human)


async def review(message: str, proposal: Proposal):
    changes = "\n\n".join(f"### {f.path}\n{f.content}" for f in proposal.files)
    return await _text(REVIEWER_PROMPT, f"Task:\n{message}\n\nProposed changes:\n{changes}")
