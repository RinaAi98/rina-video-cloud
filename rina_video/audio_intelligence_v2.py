"""RINA Audio Intelligence V2: evidence-based energy timing for edits."""
from __future__ import annotations
from typing import Any
from .audio_energy_engine_v1 import AudioEnergyEngineV1

class AudioIntelligenceV2:
    VERSION = "RINA_AUDIO_INTELLIGENCE_V2"
    def __init__(self): self.engine = AudioEnergyEngineV1()
    def analyze(self, source) -> dict[str,Any]:
        r=self.engine.analyze(source)
        return {"version":self.VERSION,"fps":r.get("fps"),"peaks":r.get("peaks",[]),
                "sample_count":len(r.get("samples",[])),"evidence_only":True,
                "method":"rms_energy_peak"}
    def annotate(self,cuts,analysis):
        peaks=analysis.get("peaks",[]) or []; out=[]
        for c in cuts:
            x=dict(c); nearby=[p for p in peaks if float(c["start"])-1.5<=p["timestamp"]<=float(c["end"])+1.5]
            energy=max([float(p["energy"]) for p in nearby] or [0.0])
            x["audio_energy"]=round(energy,2)
            x["audio_evidence"]="energy_peak" if nearby else "temporal_segment"
            out.append(x)
        return out
