"""RINA Audio Energy Engine V1: evidence-only temporal energy peaks."""
from __future__ import annotations
import subprocess
from pathlib import Path
from typing import Any

class AudioEnergyEngineV1:
    VERSION = "RINA_AUDIO_ENERGY_ENGINE_V1"
    def analyze(self, source: str | Path, fps: float = 4.0) -> dict[str, Any]:
        source=Path(source)
        cmd=["ffmpeg","-hide_banner","-loglevel","error","-i",str(source),"-vn","-ac","1","-ar","8000","-f","s16le","-"]
        p=subprocess.Popen(cmd,stdout=subprocess.PIPE)
        frame=max(1,int(8000/fps))*2; samples=[]
        idx=0
        while True:
            raw=p.stdout.read(frame)
            if not raw: break
            vals=[]
            for i in range(0,len(raw)-1,2): vals.append(int.from_bytes(raw[i:i+2],"little",signed=True))
            if vals:
                rms=(sum(x*x for x in vals)/len(vals))**0.5
                db=max(-60.0,min(0.0,20.0*__import__("math").log10(max(rms,1)/32768.0)))
                energy=max(0.0,min(100.0,(db+60.0)/60.0*100.0))
                samples.append({"timestamp":round(idx/fps,3),"db":round(db,2),"energy":round(energy,2)})
            idx+=1
        rc=p.wait()
        if rc: raise RuntimeError("FFmpeg audio analysis failed")
        peaks=[]
        for x in sorted(samples,key=lambda z:z["energy"],reverse=True):
            if all(abs(x["timestamp"]-y["timestamp"])>=2.0 for y in peaks): peaks.append(x)
            if len(peaks)>=8: break
        return {"version":self.VERSION,"fps":fps,"samples":samples,"peaks":peaks,"evidence_only":True}

__all__=["AudioEnergyEngineV1"]
if __name__=="__main__":
    import sys,json
    print(json.dumps(AudioEnergyEngineV1().analyze(sys.argv[1]),indent=2))
