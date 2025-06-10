"""Define the configurable parameters for the agent."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Annotated

from langchain_core.runnables import ensure_config
from langgraph.config import get_config

from react_agent import prompts
import os

# API Keys are loaded from .env file
# No need to set them here as they are loaded by load_dotenv() in graph.py

@dataclass(kw_only=True)
class Configuration:
    """The configuration for the agent."""

    system_prompt: str = field(
        default=prompts.SYSTEM_PROMPT,
        metadata={
            "description": "The system prompt to use for the agent's interactions. "
            "This prompt sets the context and behavior for the agent."
        },
    )

    model: Annotated[str, {"__template_metadata__": {"kind": "llm"}}] = field(
        default="groq/llama-3.3-70b-versatile",
        metadata={
            "description": "The name of the language model to use for the agent's main interactions. "
            "Should be in the form: provider/model-name."
        },
    )

    max_search_results: int = field(
        default=10,
        metadata={
            "description": "The maximum number of search results to return for each search query."
        },
    )

    # RAG Configuration
    rag_enabled: bool = field(
        default=True,
        metadata={
            "description": "Whether to enable RAG functionality."
        },
    )

    rag_documents_path: str = field(
        default="documents",
        metadata={
            "description": "Path to the directory containing documents for RAG."
        },
    )

    rag_chunk_size: int = field(
        default=1000,
        metadata={
            "description": "Size of text chunks for document splitting."
        },
    )

    rag_chunk_overlap: int = field(
        default=200,
        metadata={
            "description": "Overlap between text chunks."
        },
    )

    evaluation_enabled: bool = field(
        default=True,
        metadata={
            "description": "Whether to enable RAG evaluation."
        },
    )

    @classmethod
    def from_context(cls) -> Configuration:
        """Create a Configuration instance from a RunnableConfig object."""
        try:
            config = get_config()
        except RuntimeError:
            config = None
        config = ensure_config(config)
        configurable = config.get("configurable") or {}
        _fields = {f.name for f in fields(cls) if f.init}
        return cls(**{k: v for k, v in configurable.items() if k in _fields})
