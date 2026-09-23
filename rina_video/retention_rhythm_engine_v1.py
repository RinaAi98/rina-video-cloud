"""RINA Retention Rhythm Engine V1.
Evidence-only pacing guidance from actual audio/visual/speech signals.
"""
from __future__ import annotations

from typing import Any


class RetentionRhythmEngineV1:
    VERSION = "RINA_RETENTION_RHYTHM_ENGINE_V1"

    def _num(self, value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def analyze(self, cuts: list[dict[str, Any]]) -> dict[str, Any]:
        if not cuts:
            return {"version": self.VERSION, "status": "WAITING_CUTS", "cuts": []}
        out = []
        total = len(cuts)
        for index, raw in enumerate(cuts):
            cut = dict(raw)
            duration = max(0.01, self._num(cut.get("end")) - self._num(cut.get("start")))
            visual = min(100.0, max(0.0, self._num(cut.get("visual_energy", cut.get("visual_score", 0)))))
            audio = min(100.0, max(0.0, self._num(cut.get("audio_energy", 0))))
            hook = min(100.0, max(0.0, self._num(cut.get("hook_score", 0))))
            words = len(str(cut.get("text", "")).split())
            speech_density = min(100.0, words / duration * 14.0)
            energy = visual * 0.40 + audio * 0.35 + hook * 0.15 + speech_density * 0.10
            if energy >= 68:
                rhythm = "ACCELERATE"
                factor = 1.18
            elif energy <= 32:
                rhythm = "HOLD"
                factor = 0.92
            else:
                rhythm = "FLOW"
                factor = 1.0
            # Never shorten source material here: this is guidance for motion/caption intensity.
            cut.update({
                "rhythm_index": index,
                "rhythm_total": total,
                "rhythm_energy": round(energy, 2),
                "rhythm": rhythm,
                "rhythm_factor": factor,
                "speech_density": round(speech_density, 2),
                "rhythm_evidence": [
                    x for x, value in (("visual", visual), ("audio", audio),
                                       ("hook", hook), ("speech", speech_density))
                    if value >= 50
                ],
            })
            out.append(cut)
        avg = sum(x["rhythm_energy"] for x in out) / len(out)
        return {"version": self.VERSION, "status": "READY", "cuts": out,
                "average_energy": round(avg, 2),
                "policy": "evidence_only_no_source_timing_invention"}


__all__ = ["RetentionRhythmEngineV1"]
