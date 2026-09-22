"""RINA Smart Cut Engine V1: converts semantic segments into a clean cut plan."""
from __future__ import annotations
import re
from typing import Any

class SmartCutEngineV1:
    VERSION = "RINA_SMART_CUT_ENGINE_V1"
    FILLERS = {"eee","emm","um","uh","hmm","anu","kayak","gitu","apa ya"}

    def _words(self, text: str) -> list[str]:
        return re.findall(r"[A-Za-zÀ-ÿ0-9']+", text.lower())

    def _trim_text(self, text: str) -> str:
        words = text.split()
        while words and words[0].lower().strip(",.!?") in self.FILLERS:
            words.pop(0)
        while words and words[-1].lower().strip(",.!?") in self.FILLERS:
            words.pop()
        return " ".join(words).strip()

    def build(self, segments: list[dict[str, Any]], target_min: float = 45.0, target_max: float = 60.0) -> dict[str, Any]:
        if not segments:
            return {"version": self.VERSION, "status":"WAITING_SEGMENTS"}
        ordered=sorted(segments,key=lambda x:float(x["start"]))
        cuts=[]
        for seg in ordered:
            start=float(seg["start"]); end=float(seg["end"])
            text=self._trim_text(str(seg.get("text","")))
            if end<=start or not text: continue
            cuts.append({"start":round(start,3),"end":round(end,3),"duration":round(end-start,3),"text":text,
                         "story_stage":seg.get("story_stage",""),"score":seg.get("score",0),"speech_segments":seg.get("speech_segments",[])})
        merged=[]
        for cut in cuts:
            if merged and cut["start"]-merged[-1]["end"] <= 0.08 and cut.get("story_stage", "") == merged[-1].get("story_stage", ""):
                merged[-1]["end"]=cut["end"]; merged[-1]["duration"]=round(merged[-1]["end"]-merged[-1]["start"],3)
                merged[-1]["text"] += " " + cut["text"]
                merged[-1]["speech_segments"] = merged[-1].get("speech_segments", []) + cut.get("speech_segments", [])
                merged[-1]["story_stage"] += "+" + cut["story_stage"] if cut["story_stage"] else ""
            else: merged.append(cut.copy())
        total=sum(x["duration"] for x in merged)
        # Prefer 45-60s; if already in range, keep the semantic plan intact.
        if total > target_max:
            kept=[]; running=0.0
            for cut in merged:
                if running + cut["duration"] <= target_max:
                    kept.append(cut); running += cut["duration"]
            merged=kept; total=running
        return {"version":self.VERSION,"status":"READY" if merged else "NO_CUTS",
                "cut_plan":merged,"total_duration":round(total,3),
                "target_duration":{"min":target_min,"max":target_max},
                "pacing":"fast_hook_then_story_then_payoff" if merged else ""}

if __name__ == "__main__":
    sample=[
      {"start":0,"end":6,"text":"Eee Pernah bertanya kenapa hasilnya berbeda?","story_stage":"HOOK","score":92},
      {"start":6.15,"end":13,"text":"Awalnya banyak orang melakukan langkah yang salah.","story_stage":"SETUP","score":78},
      {"start":13.1,"end":22,"text":"Masalahnya adalah mereka melewatkan bagian penting.","story_stage":"TENSION","score":84},
      {"start":22.2,"end":32,"text":"Ternyata perubahan kecil ini membuat hasil berbeda.","story_stage":"REVEAL","score":91},
      {"start":32.1,"end":42,"text":"Hasil akhirnya lebih cepat dan konsisten.","story_stage":"PAYOFF","score":87},
      {"start":42.2,"end":49,"text":"Kalau ingin mencoba, lakukan langkah ini sekarang.","story_stage":"CTA","score":80},
    ]
    import json
    print(json.dumps(SmartCutEngineV1().build(sample),ensure_ascii=False,indent=2))
