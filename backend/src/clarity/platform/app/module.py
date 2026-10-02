"""Module protocol and AppBuilder — the composition root."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from fastapi import APIRouter, FastAPI

from clarity.kernel.events import EventType
from clarity.kernel.principal import Permission


@dataclass(frozen=True, slots=True)
class ConfigKey:
    key: str
    default: Any
    description: str = ""


class Module(Protocol):
    name: str
    schema: str

    def permissions(self) -> list[Permission]: ...

    def config_keys(self) -> list[ConfigKey]: ...

    def register(self, app: AppBuilder) -> None: ...


EventHandler = Callable[[dict[str, Any]], None]
JobFn = Callable[[], None]


@dataclass
class AppBuilder:
    """Composition root. Modules register routes, handlers, jobs and facades."""

    profile: str
    settings: Any
    _providers: dict[type[Any], Any] = field(default_factory=dict)
    _routers: list[tuple[APIRouter, str]] = field(default_factory=list)
    _handlers: dict[EventType, list[EventHandler]] = field(default_factory=dict)
    _jobs: dict[str, tuple[str, JobFn]] = field(default_factory=dict)
    _permissions: list[Permission] = field(default_factory=list)
    _config_keys: list[ConfigKey] = field(default_factory=list)
    _modules: list[Module] = field(default_factory=list)

    def provide(self, protocol: type[Any], implementation: Any) -> None:
        self._providers[protocol] = implementation

    def resolve(self, protocol: type[Any]) -> Any:
        if protocol not in self._providers:
            raise KeyError(f"no provider registered for {protocol!r}")
        return self._providers[protocol]

    def routes(self, router: APIRouter, *, prefix: str, audience: str = "internal") -> None:
        _ = audience
        self._routers.append((router, prefix))

    def on_event(self, event_type: EventType, handler: EventHandler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def job(self, name: str, *, cron: str, fn: JobFn) -> None:
        self._jobs[name] = (cron, fn)

    def register_module(self, module: Module) -> None:
        self._modules.append(module)
        self._permissions.extend(module.permissions())
        self._config_keys.extend(module.config_keys())
        module.register(self)

    def build_fastapi(self, *, title: str = "Hutch Clarity") -> FastAPI:
        app = FastAPI(title=title, version="0.2.0")
        app.state.builder = self
        app.state.profile = self.profile
        app.state.settings = self.settings
        for router, prefix in self._routers:
            app.include_router(router, prefix=prefix)

        @app.get("/health")
        def health() -> dict[str, Any]:
            return {
                "status": "ok",
                "profile": self.profile,
                "modules": [m.name for m in self._modules],
            }

        return app

    def dispatch(self, event_type: EventType, payload: dict[str, Any]) -> None:
        for handler in self._handlers.get(event_type, []):
            handler(payload)
