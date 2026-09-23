"""RINA Visual Hook Engine V3: lightweight temporal visual peak detection."""
from __future__ import annotations
import subprocess
from pathlib import Path
from typing import Any
from .audio_energy_engine_v1 import AudioEnergyEngineV1

class VisualHookEngineV3:
    VERSION = "RINA_VISUAL_HOOK_ENGINE_V3"

    def _probe_duration(self, source: Path) -> float:
        p = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                            "-of","default=nw=1:nk=1",str(source)],capture_output=True,text=True,check=True)
        return float(p.stdout.strip() or 0)

    def _frames(self, source: Path, fps: float = 2.0):
        cmd=["ffmpeg","-hide_banner","-loglevel","error","-i",str(source),"-vf",f"fps={fps},scale=160:90,format=gray",
             "-f","rawvideo","-pix_fmt","gray","-"]
        p=subprocess.Popen(cmd,stdout=subprocess.PIPE)
        size=160*90; idx=0
        while True:
            buf=p.stdout.read(size)
            if len(buf)!=size: break
            yield idx/fps, buf; idx+=1
        p.wait()
    def analyze(self, source: str | Path, fps: float = 2.0) -> dict[str, Any]:
        source=Path(source); duration=self._probe_duration(source)
        audio = AudioEnergyEngineV1().analyze(source)
        prev=None; peaks=[]; samples=[]
        for ts,buf in self._frames(source,fps):
            total=sum(buf); mean=total/len(buf)
            var=sum((x-mean)*(x-mean) for x in buf)/len(buf)
            contrast=min(100.0,(var**0.5)*1.8)
            motion=0.0 if prev is None else sum(abs(a-b) for a,b in zip(buf,prev))/len(buf)
            nearest=min(audio["samples"],key=lambda x:abs(x["timestamp"]-ts),default={"energy":0})
            energy=float(nearest.get("energy",0))
            score=min(100.0,motion*1.05+contrast*0.30+energy*0.35)
            samples.append({"timestamp":round(ts,3),"motion":round(motion,2),"contrast":round(contrast,2),"audio_energy":round(energy,2),"visual_peak":round(score,2)})
            prev=buf
        ranked=sorted(samples,key=lambda x:x["visual_peak"],reverse=True)
        chosen=[]
        for item in ranked:
            if all(abs(item["timestamp"]-x["timestamp"])>=3.0 for x in chosen): chosen.append(item)
            if len(chosen)>=8: break
        return {"version":self.VERSION,"status":"READY","duration":round(duration,3),"fps":fps,
                "samples":samples,"peaks":chosen,"audio_peaks":audio["peaks"],
                "method":"temporal_motion_contrast_audio_energy","evidence_only":True}
    def candidates(self, analysis: dict[str, Any], window: float = 6.0) -> list[dict[str, Any]]:
        duration=float(analysis.get("duration",0)); out=[]
        for peak in analysis.get("peaks",[]):
            center=float(peak["timestamp"]); start=max(0.0,center-window/2); end=min(duration,start+window)
            start=max(0.0,end-window)
            out.append({"start":round(start,3),"end":round(end,3),"text":"",
                        "score":float(peak["visual_peak"]),"visual_score":float(peak["visual_peak"]),
                        "visual_evidence":True,"speech_segments":[],"story_stage":""})
        return out

__all__=["VisualHookEngineV3"]
if __name__=="__main__":
    import sys,json
    e=VisualHookEngineV3(); a=e.analyze(sys.argv[1]); print(json.dumps({"peaks":a["peaks"],"candidates":e.candidates(a)},indent=2))
