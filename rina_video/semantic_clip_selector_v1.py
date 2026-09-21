"""RINA Semantic Clip Selection V1.
Selects transcript segments by semantic value without inventing timestamps.
"""

from __future__ import annotations

import re
from typing import Any


class SemanticClipSelectorV1:
    VERSION = "RINA_SEMANTIC_CLIP_SELECTOR_V1"

    FILLERS = {
        "eee", "emm", "um", "uh", "anu", "jadi", "kayak", "seperti",
        "hmm", "hmmm", "apa ya", "begitu", "gitu", "ya", "nih",
    }
    ATTENTION = {
        "mengapa", "kenapa", "bagaimana", "ternyata", "rahasia", "jangan",
        "kesalahan", "masalah", "hasil", "bukti", "fakta", "ternyata",
        "penting", "berhenti", "ingat", "perhatikan", "cara", "alasan",
    }
    CONTRAST = {"tetapi", "namun", "justru", "sebaliknya", "padahal", "bukan"}

    def _words(self, text: str) -> list[str]:
        return re.findall(r"[A-Za-zÀ-ÿ0-9']+", text.lower())

    def _score(self, text: str, target_stages: set[str]) -> dict[str, Any]:
        words = self._words(text)
        n = len(words)
        if not n:
            return {"score": 0.0, "signals": [], "word_count": 0}
        low = set(words)
        signals: list[str] = []
        score = 40.0
        attention = len(low & self.ATTENTION)
        contrast = len(low & self.CONTRAST)
        fillers = sum(1 for w in words if w in self.FILLERS)
        if "HOOK" in target_stages and ("?" in text or attention):
            score += 20
            signals.append("hook_signal")
        elif attention:
            score += min(12, attention * 4)
            signals.append("attention")
        if contrast:
            score += min(10, contrast * 5)
            signals.append("contrast")
        if 8 <= n <= 32:
            score += 15
            signals.append("dense")
        elif n < 5:
            score -= 15
            signals.append("too_short")
        if fillers:
            score -= min(12, fillers * 3)
            signals.append("filler_penalty")
        if "REVEAL" in target_stages and any(x in low for x in {"hasil", "ternyata", "karena", "sehingga"}):
            score += 10
            signals.append("reveal_signal")
        return {"score": round(max(0, min(100, score)), 2), "signals": signals, "word_count": n}
    def _validate(self, segments: list[dict[str, Any]]) -> None:
        for i, seg in enumerate(segments):
            if not isinstance(seg, dict):
                raise ValueError(f"segment[{i}] harus object")
            if "start" not in seg or "end" not in seg or "text" not in seg:
                raise ValueError(f"segment[{i}] wajib punya start, end, text")
            if float(seg["end"]) <= float(seg["start"]):
                raise ValueError(f"segment[{i}] memiliki timestamp tidak valid")

    def select_story(
        self,
        segments: list[dict[str, Any]],
        story: dict[str, Any],
        max_total_seconds: float = 60.0,
    ) -> dict[str, Any]:
        self._validate(segments)
        if not segments:
            return {"version": self.VERSION, "status": "WAITING_SEGMENTS"}
        stage_text = {str(k).upper(): str(v) for k, v in story.items() if v}
        scored = []
        for idx, seg in enumerate(segments):
            base = self._score(str(seg["text"]), set(stage_text))
            text_words = set(self._words(str(seg["text"])))
            stage_scores = {}
            for stage, target in stage_text.items():
                target_words = set(self._words(target))
                overlap = len(text_words & target_words) / max(1, len(target_words))
                stage_scores[stage] = round(min(1.0, overlap), 3)
            best_stage = max(stage_scores, key=stage_scores.get) if stage_scores else ""
            item = dict(seg)
            item.update(index=idx, duration=round(float(seg["end"])-float(seg["start"]),3),
                        analysis=base, story_stage=best_stage, stage_scores=stage_scores)
            item["score"] = round(min(100, base["score"] + max(stage_scores.values(), default=0)*20), 2)
            scored.append(item)
        selected=[]
        used_stages=set()
        total=0.0
        for item in sorted(scored, key=lambda x:(x["story_stage"] in used_stages, -x["score"])):
            stage=item["story_stage"]
            if stage in used_stages and len(selected) >= 6:
                continue
            if item["score"] < 60 or total + item["duration"] > max_total_seconds:
                continue
            selected.append(item); used_stages.add(stage); total += item["duration"]
        selected.sort(key=lambda x:x["start"])
        return {"version": self.VERSION, "status":"READY" if selected else "NO_CANDIDATES",
                "selected_segments":selected, "total_duration":round(total,3),
                "covered_stages":sorted(used_stages), "story_stage_coverage":len(used_stages)/max(1,len(stage_text))}

    def select(
        self,
        segments: list[dict[str, Any]],
        target_stages: list[str] | None = None,
        max_segments: int = 8,
        min_total_seconds: float = 20.0,
        max_total_seconds: float = 60.0,
    ) -> dict[str, Any]:
        self._validate(segments)
        if not segments:
            return {"version": self.VERSION, "status": "WAITING_SEGMENTS"}
        stages = set(target_stages or ["HOOK", "TENSION", "REVEAL", "PAYOFF"])
        scored = []
        for idx, seg in enumerate(segments):
            item = dict(seg)
            item["index"] = idx
            item["duration"] = round(float(seg["end"]) - float(seg["start"]), 3)
            item["analysis"] = self._score(str(seg["text"]), stages)
            item["score"] = item["analysis"]["score"]
            scored.append(item)
        ranked = sorted(scored, key=lambda x: (-x["score"], x["index"]))
        chosen: list[dict[str, Any]] = []
        total = 0.0
        for item in ranked:
            if len(chosen) >= max_segments or total >= max_total_seconds:
                break
            if any(x["index"] == item["index"] for x in chosen):
                continue
            dur = item["duration"]
            if item["score"] < 60:
                continue
            if total + dur > max_total_seconds:
                continue
            chosen.append(item)
            total += dur
        if total < min_total_seconds:
            for item in sorted(scored, key=lambda x: x["index"]):
                if item["index"] in {x["index"] for x in chosen}:
                    continue
                if len(chosen) >= max_segments or total >= min_total_seconds:
                    break
                if item["score"] < 60:
                    continue
                if total + item["duration"] <= max_total_seconds:
                    chosen.append(item)
                    total += item["duration"]
        chosen.sort(key=lambda x: x["start"])
        coverage = round(sum(x["duration"] for x in chosen) / max(0.001, float(segments[-1]["end"]) - float(segments[0]["start"])) * 100, 2)
        return {
            "version": self.VERSION,
            "status": "READY" if chosen else "NO_CANDIDATES",
            "selected_segments": chosen,
            "ranked_candidates": ranked,
            "total_duration": round(total, 3),
            "coverage_percent": coverage,
            "target_stages": sorted(stages),
            "selection_policy": "semantic_score_then_duration_fill",
        }


__all__ = ["SemanticClipSelectorV1"]
if __name__ == "__main__":
    selector = SemanticClipSelectorV1()
    sample = [
        {"start": 0, "end": 5, "text": "Eee jadi hari ini kita akan membahas hal biasa."},
        {"start": 5, "end": 12, "text": "Kenapa hasil ini bisa berbeda dari yang kamu kira?"},
        {"start": 12, "end": 20, "text": "Banyak orang melakukan kesalahan yang sama tanpa menyadarinya."},
        {"start": 20, "end": 30, "text": "Namun ternyata ada satu alasan penting yang sering dilewatkan."},
        {"start": 30, "end": 42, "text": "Hasil akhirnya berubah karena langkah sederhana ini dilakukan dengan benar."},
    ]
    import json
    print(json.dumps(selector.select(sample), ensure_ascii=False, indent=2))

