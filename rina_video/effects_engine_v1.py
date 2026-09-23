"""RINA Effects Engine V1: subtle evidence-safe visual treatment."""
from __future__ import annotations

class EffectsEngineV1:
    VERSION = "RINA_EFFECTS_V1"

    def profile(self, role: str, index: int, total: int) -> dict:
        if isinstance(role, dict):
            energy=float(role.get("visual_energy",0) or 0)
            rhythm=float(role.get("rhythm_factor",1.0) or 1.0)
            audio=float(role.get("audio_momentum",0) or 0)
            idx=int(role.get("micro_index",index) or index)
            beat_boost=min(0.12, audio*0.12)
            return {"zoom": 1.035 + min(0.035, energy/3000.0) + (idx % 2)*0.008 + max(0.0, rhythm-1.0)*0.015 + beat_boost,
                    "pan_speed": (0.34 + min(0.18, energy/450.0) + audio*0.08) * rhythm,
                    "pan_amp": 12 + min(16, energy/6.0) + max(0.0, rhythm-1.0)*8 + audio*5,
                    "brightness": -0.01}
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
