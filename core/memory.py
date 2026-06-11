"""
Memory System — MetaGPT-inspired, manages three types of Agent memory

- Short-term: Current conversation window (sliding window, auto-truncation)
- Working: Current research task context (search terms, read papers, intermediate results)
- Long-term: User preferences + query cache (optional persistence to JSON)
"""

from __future__ import annotations

from typing import Any

from .message import Message


class ShortTermMemory:
    """Short-term memory — sliding-window message queue.

    Auto-truncation strategy:
    - max_tokens estimate uses char_count / 2 (conservative; Chinese ~1.5 char/token)
    - Preserve the last N complete dialogue turns
    - Always retain system message
    """

    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens
        self._messages: list[Message] = []

    def add(self, msg: Message) -> None:
        self._messages.append(msg)
        self._trim()

    def get_all(self) -> list[Message]:
        return list(self._messages)

    def get_recent(self, n: int = 10) -> list[Message]:
        """Get the last n messages."""
        return self._messages[-n:]

    def clear(self, keep_system: bool = True) -> None:
        if keep_system:
            self._messages = [m for m in self._messages if m.role == "system"]
        else:
            self._messages = []

    def _trim(self) -> None:
        """Truncate by estimated token count."""
        while self._estimated_tokens() > self.max_tokens:
            # Skip system message; delete from the second message onward
            if len(self._messages) > 1 and self._messages[0].role == "system":
                self._messages.pop(1)
            elif self._messages:
                self._messages.pop(0)
            else:
                break

    def _estimated_tokens(self) -> int:
        return sum(len(m.content) for m in self._messages) // 2

    def __len__(self) -> int:
        return len(self._messages)


class WorkingMemory:
    """Working memory — current research task context.

    Stores structured state, not dialogue text:
    - search_keywords: Search terms used in this task
    - read_papers: DOIs of papers read/cited
    - retrieved_snippets: Retrieved text snippets
    - intermediate_results: Multi-step reasoning intermediate results
    - task_state: Current task state machine
    """

    def __init__(self):
        self._store: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def append(self, key: str, value: Any) -> None:
        """Append to a list-type field."""
        if key not in self._store:
            self._store[key] = []
        self._store[key].append(value)

    def snapshot(self) -> dict[str, Any]:
        """Return working memory summary for injection into LLM context."""
        return {
            k: v
            for k, v in self._store.items()
            if k in ("search_keywords", "read_papers", "intermediate_results")
        }

    def clear(self) -> None:
        self._store.clear()

    def __repr__(self) -> str:
        keys = list(self._store.keys())
        return f"WorkingMemory({keys})"


class Memory:
    """Unified memory interface.

    Usage:
        mem = Memory()
        mem.short.add(Message.user("Hello"))
        mem.working.set("task_state", "searching")
    """

    def __init__(self, short_max_tokens: int = 8000):
        self.short = ShortTermMemory(max_tokens=short_max_tokens)
        self.working = WorkingMemory()

    def add_message(self, msg: Message) -> None:
        self.short.add(msg)

    def get_conversation(self) -> list[Message]:
        return self.short.get_all()

    def clear(self) -> None:
        self.short.clear()
        self.working.clear()
