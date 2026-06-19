"""
Prompt template registry.

Priority (highest wins):
    project  (.tau/prompts/*.md  relative to cwd)
    global   (~/.tau/prompts/*.md)
    builtin  (tau/builtins/prompts/)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from tau.core.registry import Registry
from tau.prompts.types import PromptLoadError, PromptTemplate
from tau.prompts.loader import load_templates_from_dir


class PromptRegistry(Registry[PromptTemplate, PromptLoadError]):
    def _load_from_dir(self, path: Path) -> Any:
        return load_templates_from_dir(path)

    def _get_dir(self, cwd: Path | None = None) -> Path:
        from tau.settings.paths import get_prompts_dir
        return get_prompts_dir(cwd)

    def _builtins_subdir(self) -> str:
        return "prompts"

    def _extract_items(self, result: Any) -> dict[str, PromptTemplate]:
        return result.templates

    def _extract_errors(self, result: Any) -> list[PromptLoadError]:
        return result.errors

    def expand(self, name: str, args_str: str) -> str | None:
        """Expand a prompt template with the given arguments."""
        tmpl = self.get(name)
        if tmpl is None:
            return None
        from tau.prompts.expand import expand as _expand
        return _expand(tmpl.content, args_str)


prompt_registry = PromptRegistry()
