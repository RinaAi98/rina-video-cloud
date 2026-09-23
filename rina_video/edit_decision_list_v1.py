"""RINA Edit Decision List V1: explicit, auditable edit plan."""
from __future__ import annotations
from typing import Any

class EditDecisionListV1:
    VERSION="RINA_EDL_V1"
    def build(self, cut_result: dict[str,Any], source: str) -> dict[str,Any]:
        cuts=cut_result.get("cut_plan",[]) or []
        if isinstance(cuts,dict): cuts=cuts.get("cut_plan",[]) or []
        shots=[]
        for i,c in enumerate(cuts):
            shots.append({"index":i,"source":source,"start":float(c["start"]),"end":float(c["end"]),
                          "duration":round(float(c["end"])-float(c["start"]),3),
                          "role":c.get("stage",c.get("story_stage","MAIN")),
                          "hook_score":float(c.get("hook_score",c.get("score",0)) or 0),
                          "text":str(c.get("text","")),"speech_segments":c.get("speech_segments",[]) or []})
        micro_paced = bool(cut_result.get("micro_paced")) and all(c.get("micro_cut") for c in cuts)
        transition = ({"type":"hard_cut","duration":0} if micro_paced else
                      {"type":"fade","duration":0.25} if len(shots)>1 else
                      {"type":"none","duration":0})
        return {"version":self.VERSION,"source":source,"shots":shots,
                "transition":transition,"micro_paced":micro_paced,
                "quality":{"video_codec":"libx264","crf":18,"pixel_format":"yuv420p","audio_codec":"aac","audio_bitrate":"160k","sample_rate":48000},
                "policy":"evidence_only_no_invented_speech_or_story"}

__all__=["EditDecisionListV1"]
if __name__=="__main__":
 import json,sys
 from pathlib import Path
 print(json.dumps(EditDecisionListV1().build(json.loads(Path(sys.argv[2]).read_text()),sys.argv[1]),indent=2,ensure_ascii=False))
