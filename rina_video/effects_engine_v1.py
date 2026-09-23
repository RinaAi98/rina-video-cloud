"""RINA Effects Engine V1: subtle evidence-safe visual treatment."""
from __future__ import annotations

class EffectsEngineV1:
    VERSION = "RINA_EFFECTS_V1"

    def profile(self, role: str, index: int, total: int) -> dict:
        role = str(role or "MAIN").upper()
        if role == "HOOK":
            return {"zoom": 1.10, "pan_speed": 0.58, "pan_amp": 28, "brightness": -0.01}
        if role == "PAYOFF":
            return {"zoom": 1.06, "pan_speed": 0.42, "pan_amp": 18, "brightness": 0.0}
        return {"zoom": 1.04 + (index % 2) * 0.015,
                "pan_speed": 0.38, "pan_amp": 14, "brightness": -0.01}

    def transition(self, index: int, total: int) -> dict:
        if total <= 1:
            return {"type": "none", "duration": 0.0}
        return {"type": "fade", "duration": 0.12,
                "in": index > 0, "out": index < total - 1}

__all__ = ["EffectsEngineV1"]
