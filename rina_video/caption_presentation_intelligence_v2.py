"""RINA Caption Presentation Intelligence V2. Evidence-only caption styling."""
from __future__ import annotations
from typing import Any

class CaptionPresentationIntelligenceV2:
    VERSION = "RINA_CAPTION_PRESENTATION_INTELLIGENCE_V2"

    def _num(self, v: Any, default=0.0):
        try: return float(v)
        except (TypeError, ValueError): return default

    def present(self, event: dict[str, Any], cut: dict[str, Any]) -> dict[str, Any]:
        e=dict(event)
        start=self._num(e.get("start")); end=self._num(e.get("end"), start)
        duration=max(0.05,end-start)
        words=max(1,len(str(e.get("text","")).split()))
        energy=max(self._num(cut.get("visual_energy")),self._num(cut.get("audio_energy")))
        rhythm=str(cut.get("rhythm","FLOW")).upper()
        factor=self._num(cut.get("rhythm_factor",1.0),1.0)
        emphasis=bool(e.get("emphasis"))
        if rhythm == "ACCELERATE" or factor > 1.08:
            style="POP"; pop=0.10; scale=1.10
        elif rhythm == "HOLD" or factor < 0.96:
            style="HOLD"; pop=0.16; scale=1.00
        else:
            style="FLOW"; pop=0.12; scale=1.04
        if energy >= 70: scale += 0.04
        if emphasis: scale += 0.04
        scale=min(1.22,scale)
        base=50 + min(10,words*1.5)
        if rhythm == "ACCELERATE": base += 3
        fontsize=round(base*scale)
        y=300
        if rhythm == "ACCELERATE": y=330
        elif rhythm == "HOLD": y=285
        return {**e,"presentation_version":self.VERSION,"timing_style":style,
                "font_size":fontsize,"font_scale":round(scale,3),"position_y":y,
                "box_opacity":0.78 if energy>=60 else 0.70,"pop_duration":min(pop,duration),
                "emphasis_scale":1.10 if emphasis else 1.0,"max_lines":3,
                "presentation_evidence":{"energy":round(energy,2),"rhythm":rhythm,
                "factor":factor,"word_count":words,"duration":round(duration,3)}}

    def analyze(self, cuts: list[dict[str,Any]]) -> dict[str,Any]:
        out=[]; count=0
        for cut in cuts:
            c=dict(cut); events=[]
            for event in c.get("caption_events",[]) or []:
                events.append(self.present(event,c)); count+=1
            c["caption_events"]=events; out.append(c)
        return {"version":self.VERSION,"status":"READY","cuts":out,"event_count":count,
                "policy":"evidence_only_actual_transcript"}

__all__=["CaptionPresentationIntelligenceV2"]
