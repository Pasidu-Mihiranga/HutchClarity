"""Config resolver with typed keys and kill-switch support."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConfigResolver:
    values: dict[str, Any] = field(default_factory=dict)
    defaults: dict[str, Any] = field(default_factory=dict)
    kill_switches: set[str] = field(default_factory=set)

    def get(self, key: str, default: Any = None) -> Any:
        if key in self.values:
            return self.values[key]
        if key in self.defaults:
            return self.defaults[key]
        return default

    def set(self, key: str, value: Any) -> None:
        self.values[key] = value

    def kill(self, switch: str) -> None:
        self.kill_switches.add(switch)

    def is_killed(self, switch: str) -> bool:
        return switch in self.kill_switches

    def declare_defaults(self, mapping: dict[str, Any]) -> None:
        self.defaults.update(mapping)
