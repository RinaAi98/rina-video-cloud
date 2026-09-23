"""RINA Semantic Editor Intelligence V1.
Evidence-only ranking and selection of real source segments.
"""
from __future__ import annotations

import re
from typing import Any


class SemanticEditorIntelligenceV1:
    VERSION = "RINA_SEMANTIC_EDITOR_INTELLIGENCE_V1"

    SIGNAL_WORDS = {
        "kenapa", "mengapa", "bagaimana", "ternyata", "rahasia", "jangan",
        "kesalahan", "masalah", "hasil", "bukti", "fakta", "penting", "ingat",
        "perhatikan", "cara", "alasan", "karena", "sehingga", "namun", "tetapi",
    }
    FILLERS = {"eee", "emm", "um", "uh", "hmm", "anu", "kayak", "gitu"}

    def _words(self, text: str) -> list[str]:
        return re.findall(r"[A-Za-zÀ-ÿ0-9']+", text.lower())

    def _num(self, value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _score(self, cut: dict[str, Any], max_duration: float) -> dict[str, Any]:
        text = str(cut.get("text", "")).strip()
        words = self._words(text)
        unique = set(words)
        duration = max(0.01, self._num(cut.get("end")) - self._num(cut.get("start")))
        visual = self._num(cut.get("visual_energy", cut.get("visual_score", 0)))
        audio = self._num(cut.get("audio_energy", 0))
        hook = self._num(cut.get("hook_score", 0))
        base = self._num(cut.get("score", 0))
        speech_density = min(100.0, len(words) / duration * 14.0)
        signal = min(100.0, len(unique & self.SIGNAL_WORDS) * 16.0)
        filler_penalty = min(20.0, sum(w in self.FILLERS for w in words) * 5.0)
        duration_score = 100.0 if duration <= max_duration else max(0.0, 100.0 - (duration - max_duration) * 8.0)
        score = (
            visual * 0.25 + audio * 0.20 + hook * 0.20 +
            base * 0.10 + speech_density * 0.10 + signal * 0.10 + duration_score * 0.05
            - filler_penalty
        )
        reasons = []
        if visual >= 60: reasons.append("visual_energy")
        if audio >= 60: reasons.append("audio_energy")
        if hook >= 60: reasons.append("hook_signal")
        if speech_density >= 35: reasons.append("speech_density")
        if signal > 0: reasons.append("semantic_signal")
        if filler_penalty > 0: reasons.append("filler_penalty")
        confidence = min(1.0, max(0.0, (visual + audio + hook + base) / 400.0))
        return {"score": round(max(0.0, min(100.0, score)), 2),
                "confidence": round(confidence, 3), "reasons": reasons,
                "duration": round(duration, 3), "word_count": len(words)}

    def analyze(self, cuts: list[dict[str, Any]], max_duration: float = 12.0) -> dict[str, Any]:
        scored = []
        for index, cut in enumerate(cuts or []):
            item = dict(cut)
            item["editor_index"] = index
            item["editor_analysis"] = self._score(item, max_duration)
            item["keep_score"] = item["editor_analysis"]["score"]
            scored.append(item)
        return {"version": self.VERSION, "status": "READY" if scored else "WAITING_CUTS",
                "candidates": scored, "candidate_count": len(scored),
                "policy": "evidence_only_no_invented_story"}

    def select(self, cuts: list[dict[str, Any]], min_seconds: float = 45.0,
               max_seconds: float = 60.0) -> dict[str, Any]:
        analysis = self.analyze(cuts)
        scored = analysis["candidates"]
        if not scored:
            return {**analysis, "selection": [], "total_duration": 0.0,
                    "status": "WAITING_CUTS"}
        total = sum(x["editor_analysis"]["duration"] for x in scored)
        if total <= max_seconds:
            selected = list(scored)
            policy = "retain_all_within_duration_budget"
        else:
            ranked = sorted(scored, key=lambda x: (-x["keep_score"], x["editor_index"]))
            selected, running = [], 0.0
            for item in ranked:
                dur = item["editor_analysis"]["duration"]
                if running + dur <= max_seconds:
                    selected.append(item); running += dur
            if running < min_seconds:
                for item in ranked:
                    if item in selected: continue
                    dur = item["editor_analysis"]["duration"]
                    if running + dur <= max_seconds:
                        selected.append(item); running += dur
                    if running >= min_seconds: break
            selected.sort(key=lambda x: x["editor_index"])
            policy = "ranked_evidence_selection"
        total_selected = round(sum(x["editor_analysis"]["duration"] for x in selected), 3)
        return {**analysis, "selection": selected, "selected_count": len(selected),
                "total_duration": total_selected, "selection_policy": policy,
                "coverage_percent": round(total_selected / max(0.001, total) * 100, 2)}


__all__ = ["SemanticEditorIntelligenceV1"]
