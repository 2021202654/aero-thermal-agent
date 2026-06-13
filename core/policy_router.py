"""
Policy Router + Fallback Manager

Responsibilities:
1. Complexity estimation — uses LLM to classify task complexity (simple / moderate / complex)
2. Model routing — maps complexity to appropriate LLM preset
3. Fallback chain execution — tries primary → user confirms → fallback on failure
4. Fallback record keeping — logs which model was used and why

Usage:
    router = PolicyRouter(llm_interface)
    complexity = await router.estimate_complexity("compare catalytic coefficients of SiO2 and SiC")
    config = router.route(complexity, policy="balanced")  # returns LLMConfig

    manager = FallbackManager(router)
    result = await manager.run_with_fallback(task, primary_config)
    # if fallback triggered, user is prompted before switching
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from .llm import LLMConfig, LLMInterface
from .memory import Message


class Complexity(str, Enum):
    SIMPLE = "simple"       # Single tool, factual lookup / conversion
    MODERATE = "moderate"   # 2-3 steps, some reasoning
    COMPLEX = "complex"     # Multi-step planning, hypothesis generation, critique


@dataclass
class FallbackRecord:
    """Records what happened during a fallback event."""
    original_preset: str
    fallback_preset: str
    reason: str  # e.g. "RateLimitError", "API timeout", "content_filter"
    timestamp: str = ""


@dataclass
class RoutingResult:
    complexity: Complexity
    assigned_preset: str
    assigned_config: LLMConfig
    fallback_chain: list[str]  # e.g. ["bailian", "siliconflow", "ollama"]


# ── Complexity Estimation Prompt ─────────────────────────────────────────────

_COMPLEXITY_PROMPT = """You are a task complexity classifier. Classify the following research task into ONE of three levels:

- **simple**: Single-step factual lookup, unit conversion, direct calculation, or question-answering that requires no more than one tool call.
- **moderate**: Multi-step reasoning (2-3 tool calls), comparison, literature search + synthesis, parameter sweep calculations, or tasks requiring cross-referencing 2-3 sources.
- **complex**: Open-ended research requiring hypothesis generation, multi-step planning (4+ tool calls), literature gap identification, critique-and-revision loops, or tasks where the answer structure is not known in advance.

Task: {task}

Respond with ONLY one word: simple, moderate, or complex."""


# ── Fallback Reason Detection ────────────────────────────────────────────────

_FALLBACK_REASONS = {
    "rate_limit": "RateLimitError — primary model quota exceeded",
    "auth_failure": "AuthenticationError — invalid API key or permission denied",
    "timeout": "TimeoutError — primary model response timed out",
    "content_filter": "ContentFilterError — response blocked by content policy",
    "api_error": "APIError — primary model server error (5xx)",
    "model_not_found": "ModelNotFoundError — model not available on this endpoint",
    "context_overflow": "ContextOverflowError — input exceeds model context limit",
    "unknown": "UnknownError — unexpected failure",
}


def _detect_fallback_reason(exception: Exception) -> str:
    """Map an exception to a human-readable fallback reason."""
    exc_type = type(exception).__name__.lower()
    exc_msg = str(exception).lower()

    if "rate" in exc_type or "rate" in exc_msg or "429" in exc_msg:
        return _FALLBACK_REASONS["rate_limit"]
    if "auth" in exc_type or "401" in exc_msg or "403" in exc_msg:
        return _FALLBACK_REASONS["auth_failure"]
    if "timeout" in exc_type or "timed out" in exc_msg:
        return _FALLBACK_REASONS["timeout"]
    if "filter" in exc_type or "content" in exc_msg:
        return _FALLBACK_REASONS["content_filter"]
    if "5" in exc_type[:3] or "500" in exc_msg or "502" in exc_msg or "503" in exc_msg:
        return _FALLBACK_REASONS["api_error"]
    if "not found" in exc_msg or "404" in exc_msg:
        return _FALLBACK_REASONS["model_not_found"]
    if "context" in exc_type or "length" in exc_msg or "maximum" in exc_msg:
        return _FALLBACK_REASONS["context_overflow"]
    return f"{_FALLBACK_REASONS['unknown']}: {exception}"


# ── Policy Router ──────────────────────────────────────────────────────────────


class PolicyRouter:
    """Estimates task complexity and routes to appropriate LLM preset.

    Does NOT hold LLMInterface — needs it passed in for complexity estimation.
    """

    # Complexity → preset mapping (balanced policy)
    DEFAULT_POLICY: dict[Complexity, str] = {
        Complexity.SIMPLE: "ollama",      # Fast, cheap, local
        Complexity.MODERATE: "siliconflow",  # Good cost-performance
        Complexity.COMPLEX: "bailian",    # Most capable
    }

    # Preset → fallback chain (order = try order)
    DEFAULT_FALLBACK_CHAINS: dict[str, list[str]] = {
        "bailian":     ["siliconflow", "ollama"],
        "siliconflow": ["bailian", "ollama"],
        "vllm_local":  ["bailian", "siliconflow"],
        "ollama":      ["bailian", "siliconflow"],
        "custom":      ["bailian", "siliconflow"],
    }

    def __init__(self, llm: LLMInterface):
        self.llm = llm
        self._complexity_cache: dict[str, Complexity] = {}

    async def estimate_complexity(self, task: str) -> Complexity:
        """Classify task complexity using LLM (with simple caching)."""
        # Normalize for cache key
        cache_key = task.strip().lower()[:100]

        if cache_key in self._complexity_cache:
            return self._complexity_cache[cache_key]

        prompt = _COMPLEXITY_PROMPT.format(task=task)
        try:
            resp = await self.llm.chat([
                Message.system("You are a task complexity classifier. Respond with only one word."),
                Message.user(prompt),
            ])
        except Exception:
            # On any LLM failure, default to complex (safer to use capable model)
            return Complexity.COMPLEX

        raw = (resp.content or "").strip().lower()
        if "simple" in raw:
            result = Complexity.SIMPLE
        elif "moderate" in raw:
            result = Complexity.MODERATE
        else:
            # "complex" or garbage → treat as complex
            result = Complexity.COMPLEX

        self._complexity_cache[cache_key] = result
        return result

    def get_fallback_chain(self, preset: str) -> list[str]:
        """Return the fallback chain for a given preset."""
        return self.DEFAULT_FALLBACK_CHAINS.get(preset, ["bailian", "siliconflow"])

    def route(self, complexity: Complexity, policy: str = "balanced") -> RoutingResult:
        """Route complexity to a preset LLM config.

        Args:
            complexity: Estimated task complexity
            policy: Routing policy name (currently only "balanced")
        """
        preset = self.DEFAULT_POLICY.get(complexity, "bailian")
        fallback_chain = self.get_fallback_chain(preset)

        # Resolve preset name → LLMConfig
        # This is imported here to avoid circular import with config.py
        from config import AgentConfig
        cfg = AgentConfig(llm=preset)
        assigned_config = cfg.llm

        return RoutingResult(
            complexity=complexity,
            assigned_preset=preset,
            assigned_config=assigned_config,
            fallback_chain=[preset] + fallback_chain,
        )


# ── Fallback Manager ──────────────────────────────────────────────────────────


class FallbackManager:
    """Executes LLM calls with user-confirmed fallback on failure.

    Flow:
        1. Try primary LLM
        2. On failure → determine reason → ask user if they want to switch
        3. User confirms → try next in chain → repeat until success or exhaustion
        4. Record all events in fallback_history
    """

    def __init__(
        self,
        router: PolicyRouter,
        get_user_confirmation: Callable[[str, str], asyncio.coroutine] | None = None,
    ):
        """
        Args:
            router: PolicyRouter instance
            get_user_confirmation: async fn(preset: str, reason: str) -> bool
                                  If None, uses a no-op that always returns False (no auto-confirm)
        """
        self.router = router
        self._confirm_fn = get_user_confirmation
        self.fallback_history: list[FallbackRecord] = []

    def _make_default_confirm(self) -> Callable[[str, str], asyncio.coroutine]:
        """Returns a confirmation function that always declines (for programmatic use)."""
        async def _decline(preset: str, reason: str) -> bool:
            return False
        return _decline

    async def _confirm(self, preset: str, reason: str) -> bool:
        """Ask user for fallback confirmation."""
        if self._confirm_fn is not None:
            return await self._confirm_fn(preset, reason)
        return await self._make_default_confirm()(preset, reason)

    def _record_fallback(self, original: str, fallback: str, reason: str):
        from datetime import datetime
        record = FallbackRecord(
            original_preset=original,
            fallback_preset=fallback,
            reason=reason,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        self.fallback_history.append(record)

    async def run_with_fallback(
        self,
        task: str,
        messages: list[Message],
        primary_preset: str,
        tool_schemas=None,
    ) -> tuple[str, str, list[FallbackRecord]]:
        """Execute LLM call with fallback chain and user confirmation.

        Returns:
            (final_content, final_preset, fallback_history)
            final_preset = which preset ultimately succeeded
            fallback_history = all fallback events (empty if no fallback needed)
        """
        chain = self.router.get_fallback_chain(primary_preset)
        chain = [primary_preset] + [p for p in chain if p != primary_preset]

        current_preset = primary_preset
        last_error: Exception | None = None

        for attempt_preset in chain:
            from config import AgentConfig
            cfg = AgentConfig(llm=attempt_preset)

            # Swap LLM config in-place for this attempt
            original_llm_config = self.router.llm.config
            self.router.llm.config = cfg.llm

            try:
                if tool_schemas:
                    resp = await self.router.llm.chat_with_tools(messages, tool_schemas)
                else:
                    resp = await self.router.llm.chat(messages)

                # Success — restore and return
                self.router.llm.config = original_llm_config
                return resp.content or "", attempt_preset, self.fallback_history

            except Exception as e:
                last_error = e
                reason = _detect_fallback_reason(e)
                self._record_fallback(current_preset, attempt_preset, reason)

                # Try next preset in chain?
                next_idx = chain.index(attempt_preset) + 1
                if next_idx < len(chain):
                    next_preset = chain[next_idx]
                    confirmed = await self._confirm(next_preset, reason)
                    if confirmed:
                        current_preset = next_preset
                        continue
                    else:
                        # User declined
                        self.router.llm.config = original_llm_config
                        raise e
                else:
                    # No more fallbacks
                    self.router.llm.config = original_llm_config
                    raise e

        # Should not reach here
        self.router.llm.config = original_llm_config
        raise last_error or RuntimeError("Fallback chain exhausted with no error recorded")
