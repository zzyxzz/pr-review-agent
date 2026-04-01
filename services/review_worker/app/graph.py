import logging
import os

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.prompts import (
    pull_request_review_instructions,
    review_system_prompt,
    summary_instructions,
    summary_system_prompt,
)
from app.schema import OverallState, ReviewAgentState, Reviews, Summary
from app.tools import ChatModel

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def prepare_prompt(pr_data: ReviewAgentState):
    pr_title = pr_data["pr_title"]
    pr_description = pr_data["pr_description"]

    changes = ""
    file = pr_data["file"]
    changes += f"\nFile: {file['filename']}\n"
    changes += f"Previous Filename: {file['previous_filename']}\n"
    changes += f"Status: {file['status']}\n"
    changes += "Changes:\n"
    for change in file["patch_snippet"]:
        if change["sign"] == "@@":
            changes += f"\n{change['content']}\n"
        else:
            changes += f"({change['old_line']}, {change['new_line']}) {change['sign']} {change['content']}\n"
    return pr_title, pr_description, changes


def review_file_node(state: ReviewAgentState):
    logger.debug(f"reviewing codes {state['file']['filename']} ...")

    pr_title, pr_description, changes = prepare_prompt(state)
    prompt = pull_request_review_instructions.format(
        pr_title=pr_title, pr_description=pr_description, changes=changes
    )

    logger.debug(f"\nPROMPT: {prompt}\n")
    review_model = ChatModel.get_model(
        "openai:gpt-4o", Reviews, temperature=0, api_key=OPENAI_API_KEY
    )
    response = review_model.invoke(
        [SystemMessage(content=review_system_prompt), HumanMessage(content=prompt)]
    )
    logger.debug(f"\nResponse: {response}")
    return {"reviews": [response]}


def summary_node(state: OverallState):
    """
    Aggregate all file reviews into final PR review summary.
    """
    summary_model = ChatModel.get_model(
        "openai:gpt-4o", Summary, temperature=0, api_key=OPENAI_API_KEY
    )
    prompt = summary_instructions.format(reviews=state.get("reviews", []))
    logger.debug(f"\nsummary PROMPT: {prompt}\n")
    response = summary_model.invoke(
        [
            SystemMessage(content=summary_system_prompt),
            HumanMessage(content=prompt),
        ]
    )
    logger.debug(f"\nsummary node {state}\n")
    return {"summary": response.summary}


def send_files(state: OverallState):
    return [
        Send(
            "review_file_node",
            {
                "file": f,
                "pr_title": state["pr_title"],
                "pr_description": state["pr_description"],
            },
        )
        for f in state["context_data"]
    ]


def build_graph():
    builder = StateGraph(OverallState)
    builder.add_node("review_file_node", review_file_node)
    builder.add_node("summary_node", summary_node)

    builder.add_conditional_edges(START, send_files, ["review_file_node"])
    builder.add_edge("review_file_node", "summary_node")
    builder.add_edge("summary_node", END)

    graph = builder.compile()
    return graph
