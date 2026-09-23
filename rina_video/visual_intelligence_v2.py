"""RINA Visual Intelligence V2: motion/visual-change evidence for edit timing."""
from __future__ import annotations
import json, math, subprocess
from pathlib import Path
from typing import Any

class VisualIntelligenceV2:
    VERSION = "RINA_VISUAL_INTELLIGENCE_V2"
    def analyze(self, source: str | Path, fps: float = 2.0, width: int = 96, height: int = 54) -> dict[str, Any]:
        source=Path(source)
        cmd=["ffmpeg","-hide_banner","-loglevel","error","-i",str(source),"-vf",f"fps={fps},scale={width}:{height},format=gray","-f","rawvideo","-"]
        p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        size=width*height; prev=None; samples=[]; idx=0
        while True:
            raw=p.stdout.read(size)
            if len(raw)<size: break
            cur=raw
            if prev is not None:
                diff=sum(abs(a-b) for a,b in zip(cur,prev))/(255.0*size)*100.0
                samples.append({"timestamp":round(idx/fps,3),"motion":round(diff,2)})
            prev=cur; idx+=1
        err=p.stderr.read().decode(errors="ignore"); rc=p.wait()
        if rc: raise RuntimeError(err[-1000:] or "FFmpeg visual analysis failed")
        peaks=[]
        for x in sorted(samples,key=lambda z:z["motion"],reverse=True):
            if all(abs(x["timestamp"]-y["timestamp"])>=2.0 for y in peaks): peaks.append(x)
            if len(peaks)>=8: break
        return {"version":self.VERSION,"fps":fps,"sample_count":len(samples),"samples":samples,
                "motion_peaks":peaks,"evidence_only":True,
                "method":"ffmpeg_grayscale_frame_difference"}

    def annotate_micro_cuts(self, cuts: list[dict[str,Any]], analysis: dict[str,Any]) -> list[dict[str,Any]]:
        peaks=analysis.get("motion_peaks",[]) or []
        out=[]
        for c in cuts:
            x=dict(c); center=(float(c["start"])+float(c["end"]))/2
            nearby=[p for p in peaks if float(c["start"])-1.5<=p["timestamp"]<=float(c["end"])+1.5]
            energy=max([float(p["motion"]) for p in nearby] or [0.0])
            x["visual_motion_peak"]=round(energy,2)
            x["visual_energy"]=round(min(100.0,energy*2.2),2)
            x["visual_evidence"]="motion_peak" if nearby else "temporal_segment"
            out.append(x)
        return out
