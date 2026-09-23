"""RINA Pacing Engine V1: chooses editing tempo without inventing content."""
from __future__ import annotations

class PacingEngineV1:
    VERSION = "RINA_PACING_V1"

    def analyze(self, cuts: list[dict]) -> dict:
        durations = [max(0.0, float(c["end"]) - float(c["start"])) for c in cuts]
        total = sum(durations)
        shots = len(durations)
        if shots <= 1:
            tempo = "single_shot"
        elif sum(d < 4 for d in durations) / shots >= 0.5:
            tempo = "fast"
        elif sum(d > 8 for d in durations) / shots >= 0.5:
            tempo = "slow"
        else:
            tempo = "balanced"
        return {"version": self.VERSION, "tempo": tempo, "shots": shots,
                "duration": round(total, 3), "evidence_only": True}

__all__ = ["PacingEngineV1"]
