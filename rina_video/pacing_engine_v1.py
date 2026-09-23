"""RINA Pacing Engine V1: chooses editing tempo without inventing content."""
from __future__ import annotations

class PacingEngineV1:
    VERSION = "RINA_PACING_V2"

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
        # A single continuous shot gets micro-pacing rather than fabricated cuts.
        beats = []
        micro_cuts = []
        if shots == 1 and total >= 24:
            for frac in (0.18, 0.38, 0.60, 0.82):
                beats.append(round(total * frac, 3))
            boundaries = [0.0, *beats, total]
            source = cuts[0]
            for start, end in zip(boundaries, boundaries[1:]):
                micro_cuts.append({
                    **source,
                    "start": round(float(source["start"]) + start, 3),
                    "end": round(float(source["start"]) + end, 3),
                    "micro_cut": True,
                    "micro_index": len(micro_cuts),
                    "micro_total": len(boundaries) - 1,
                })
        return {"version": self.VERSION, "tempo": tempo, "shots": shots,
                "duration": round(total, 3), "micro_beats": beats,
                "micro_cuts": micro_cuts, "caption_group_words": 3,
                "evidence_only": True}

__all__ = ["PacingEngineV1"]
