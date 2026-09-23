"""RINA Smart Cut Engine V3: hook-first, evidence-only clip selection."""
from __future__ import annotations
import re
from typing import Any

class SmartCutEngineV3:
    VERSION = "RINA_SMART_CUT_ENGINE_V3"
    ATTENTION = {"kenapa","mengapa","bagaimana","ternyata","rahasia","jangan","kesalahan","masalah","hasil","bukti","fakta","penting","ingat","perhatikan","cara","alasan"}
    CONTRAST = {"tetapi","namun","justru","sebaliknya","padahal","bukan"}

    def _words(self, text: str) -> list[str]:
        return re.findall(r"[A-Za-zÀ-ÿ0-9']+", text.lower())

    def _anchor_score(self, item: dict[str, Any]) -> float:
        text = str(item.get("text","")).strip()
        words = self._words(text)
        if not words: return float(item.get("score",0) or 0) * 0.35
        low = set(words)
        score = float(item.get("score",0) or 0) * 0.45
        score += min(28, len(low & self.ATTENTION) * 8)
        score += min(12, len(low & self.CONTRAST) * 6)
        if "?" in text: score += 12
        if 6 <= len(words) <= 30: score += 8
        return round(min(100, score),2)

    def _window(self, anchor: dict[str, Any], source_duration: float, target_min: float, target_max: float) -> tuple[float,float]:
        duration = max(0.0, float(source_duration))
        target = min(target_max, max(target_min, duration))
        if duration <= target: return 0.0, round(duration,3)
        center = (float(anchor["start"]) + float(anchor["end"])) / 2.0
        start = max(0.0, center - target * 0.32)
        start = min(start, duration - target)
        return round(start,3), round(start + target,3)
    def build(self, candidates: list[dict[str, Any]], source_duration: float,
              target_min: float = 45.0, target_max: float = 60.0) -> dict[str, Any]:
        duration = float(source_duration)
        if duration <= 0:
            return {"version":self.VERSION,"status":"WAITING_DURATION"}
        valid = []
        for i, item in enumerate(candidates or []):
            start, end = float(item.get("start",0)), float(item.get("end",0))
            if end <= start: continue
            x = dict(item)
            x["hook_score"] = self._anchor_score(x)
            x["anchor_index"] = i
            valid.append(x)
        valid.sort(key=lambda x:(-x["hook_score"], x["start"]))
        anchor = valid[0] if valid else {"start":0.0,"end":min(duration,3.0),"text":"","hook_score":0.0}
        start, end = self._window(anchor, duration, target_min, target_max)
        inside = [x for x in valid if float(x["start"]) >= start and float(x["end"]) <= end]
        speech = []
        for x in inside:
            speech.extend(x.get("speech_segments",[]) or [])
        plan = {"start":start,"end":end,"duration":round(end-start,3),
                "text":" ".join(str(x.get("text","")).strip() for x in inside if str(x.get("text","")).strip()).strip(),
                "score":anchor.get("hook_score",0),"hook_score":anchor.get("hook_score",0),
                "story_stage":anchor.get("story_stage",""),"speech_segments":speech,
                "source":"evidence_only","anchor_start":float(anchor["start"]),"anchor_end":float(anchor["end"])}
        return {"version":self.VERSION,"status":"READY","mode":"hook_first_evidence_only",
                "cut_plan":[plan],"total_duration":plan["duration"],"anchor":anchor,
                "candidate_count":len(valid),"in_window_candidates":len(inside),
                "fabrication_policy":"NO_INVENTED_SPEECH_OR_STORY"}

__all__ = ["SmartCutEngineV3"]
if __name__ == "__main__":
    import json
    sample=[{"start":0,"end":4,"text":"Hai semua."},{"start":8,"end":14,"text":"Kenapa hasilnya berbeda?"}]
    print(json.dumps(SmartCutEngineV3().build(sample,49.6),ensure_ascii=False,indent=2))
