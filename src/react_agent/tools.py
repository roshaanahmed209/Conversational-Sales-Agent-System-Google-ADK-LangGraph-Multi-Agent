"""This module provides example tools for web scraping and search functionality.

It includes a basic Tavily search function (as an example)

These tools are intended as free examples to get started. For production use,
consider implementing more robust and specialized tools tailored to your needs.
"""

from typing import Any, Callable, List, Optional, cast

from langchain_tavily import TavilySearch  # type: ignore[import-not-found]
from react_agent.configuration import Configuration
from react_agent.state import State

from langgraph.prebuilt import ToolNode  # ✅ Required for tool execution


async def search(query: str) -> dict:
    """Search the web for the given query using Tavily."""
    configuration = Configuration.from_context()
    wrapped = TavilySearch(max_results=configuration.max_search_results)
    return await wrapped.ainvoke({"query": query})


# ✅ Wrapper to add logging, human review, etc.
async def tools_wrapper(state: State):
    from react_agent.utils import log_step
    log_step(state, "tools")  # Custom logging
    return ToolNode(TOOLS).invoke(state)  # Delegate to default tool handler


# These are the actual tool functions
TOOLS = [search]
