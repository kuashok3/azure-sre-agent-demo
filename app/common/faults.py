"""Controlled failure injection (demo only).

A ``FaultRegistry`` holds which faults are active and their parameters. Application code asks the
registry questions such as "should this request fail?" or "how long should I delay?".

Safety properties:
  * nothing is active at startup;
  * faults can only be changed through the token-protected admin API (see fault_admin.py),
    which is not even mounted unless FAULTS_ENABLED=true;
  * state is in memory, per process/replica, and disappears on restart.
"""

import random
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class ParamSpec:
    default: float
    minimum: float
    maximum: float
    kind: type = float
    description: str = ""


@dataclass(frozen=True)
class FaultSpec:
    name: str
    description: str
    affects: str
    params: dict[str, ParamSpec] = field(default_factory=dict)


class UnknownFaultError(KeyError):
    pass


class FaultValidationError(ValueError):
    pass


def delay_param(default_ms: int) -> ParamSpec:
    return ParamSpec(default_ms, 0, 30_000, int, "Added delay in milliseconds")


def rate_param(default: float, description: str) -> ParamSpec:
    return ParamSpec(default, 0.0, 1.0, float, description)


class FaultRegistry:
    def __init__(self, specs: dict[str, FaultSpec], rng: random.Random | None = None) -> None:
        self._specs = specs
        self._rng = rng or random.Random()
        self._lock = threading.Lock()
        self._active: dict[str, dict] = {}

    # ---- configuration -------------------------------------------------------------------
    def describe(self) -> list[dict]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "affects": spec.affects,
                "params": {
                    name: {
                        "default": p.default,
                        "min": p.minimum,
                        "max": p.maximum,
                        "description": p.description,
                    }
                    for name, p in spec.params.items()
                },
            }
            for spec in self._specs.values()
        ]

    def is_known(self, name: str) -> bool:
        return name in self._specs

    def validate(self, name: str, params: dict | None) -> dict:
        spec = self._specs.get(name)
        if spec is None:
            raise UnknownFaultError(name)
        params = params or {}
        unknown = set(params) - set(spec.params)
        if unknown:
            raise FaultValidationError(f"Unknown parameter(s) for {name}: {sorted(unknown)}")
        resolved: dict[str, float] = {}
        for pname, pspec in spec.params.items():
            raw = params.get(pname, pspec.default)
            try:
                value = pspec.kind(raw)
            except (TypeError, ValueError) as exc:
                raise FaultValidationError(f"{pname} must be a number") from exc
            if not pspec.minimum <= value <= pspec.maximum:
                raise FaultValidationError(
                    f"{pname} must be between {pspec.minimum} and {pspec.maximum}"
                )
            resolved[pname] = value
        return resolved

    def enable(self, name: str, params: dict | None = None) -> dict:
        resolved = self.validate(name, params)
        entry = {"params": resolved, "enabled_at": datetime.now(UTC).isoformat()}
        with self._lock:
            self._active[name] = entry
        return {"name": name, **entry}

    def disable(self, name: str) -> bool:
        if name not in self._specs:
            raise UnknownFaultError(name)
        with self._lock:
            return self._active.pop(name, None) is not None

    def reset(self) -> list[str]:
        with self._lock:
            names = sorted(self._active)
            self._active.clear()
        return names

    def active(self) -> list[dict]:
        with self._lock:
            return [{"name": n, **e} for n, e in sorted(self._active.items())]

    # ---- runtime questions ---------------------------------------------------------------
    def params(self, name: str) -> dict | None:
        with self._lock:
            entry = self._active.get(name)
            return dict(entry["params"]) if entry else None

    def triggered(self, name: str, rate_param_name: str = "probability") -> bool:
        params = self.params(name)
        if params is None:
            return False
        return self._rng.random() < params.get(rate_param_name, 1.0)

    def delay_seconds(self, name: str) -> float:
        params = self.params(name)
        if params is None or self._rng.random() >= params.get("probability", 1.0):
            return 0.0
        return params.get("delay_ms", 0) / 1000.0
