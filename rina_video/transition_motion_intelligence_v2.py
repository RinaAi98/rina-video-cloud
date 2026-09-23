"""RINA Transition & Motion Intelligence V2. Evidence-only visual continuity."""
from __future__ import annotations
from typing import Any

class TransitionMotionIntelligenceV2:
    VERSION = "RINA_TRANSITION_MOTION_INTELLIGENCE_V2"

    def _n(self,v,d=0.0):
        try:return float(v)
        except (TypeError,ValueError):return d

    def analyze(self,cuts:list[dict[str,Any]])->dict[str,Any]:
        out=[]; total=len(cuts)
        for i,raw in enumerate(cuts):
            c=dict(raw); dur=max(.1,self._n(c.get("end"))-self._n(c.get("start")))
            energy=max(self._n(c.get("visual_energy")),self._n(c.get("audio_energy")))
            rhythm=str(c.get("rhythm","FLOW")).upper()
            if total<=1: transition="NONE"
            elif i==0: transition="OPEN"
            elif energy>=70 or rhythm=="ACCELERATE": transition="HARD_CUT"
            elif energy<=32 and dur>=6: transition="SOFT_CUT"
            else: transition="CLEAN_CUT"
            motion="PUSH" if rhythm=="ACCELERATE" else ("HOLD" if rhythm=="HOLD" else "DRIFT")
            c.update({"transition_v2":transition,"motion_v2":motion,
                      "motion_strength":round(min(1.0,0.35+energy/180),3),
                      "transition_evidence":{"energy":round(energy,2),"rhythm":rhythm,"duration":round(dur,3)}})
            out.append(c)
        return {"version":self.VERSION,"status":"READY","cuts":out,
                "policy":"evidence_only_no_invented_scene_changes"}

__all__=["TransitionMotionIntelligenceV2"]
