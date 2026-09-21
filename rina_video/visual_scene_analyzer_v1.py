from __future__ import annotations
import json
import re
import subprocess
from pathlib import Path

class VisualSceneAnalyzerV1:
    VERSION = "RINA_VISUAL_SCENE_ANALYZER_V1"

    def __init__(self, work_dir="creator/video/output/visual_analysis"):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def _run(self, args):
        p = subprocess.run(args, capture_output=True, text=True)
        if p.returncode:
            raise RuntimeError(p.stderr[-2000:])
        return p.stdout

    def probe(self, source):
        raw = self._run(["ffprobe","-v","error","-show_entries",
            "format=duration:stream=index,codec_type,width,height,r_frame_rate",
            "-of","json",str(source)])
        return json.loads(raw)

    def detect_scenes(self, source, threshold=0.28):
        # FFmpeg scdet emits metadata at actual shot boundaries.
        vf = "scdet=threshold=0:sc_pass=0,metadata=mode=print:file=-"
        raw = self._run(["ffmpeg","-hide_banner","-nostats","-i",str(source),
            "-vf",vf,"-an","-f","null","-"])
        hits = []
        for line in raw.splitlines():
            tm = re.search(r"lavfi\.scd\.time:\s*([0-9.]+)", line)
            sm = re.search(r"lavfi\.scd\.score:\s*([0-9.]+)", line)
            if tm:
                score = float(sm.group(1)) if sm else 0.0
                if score >= float(threshold):
                    hits.append((float(tm.group(1)), score))
        hits = sorted({(t, s) for t, s in hits})
        probe = self.probe(source)
        duration = float(probe.get("format",{}).get("duration") or 0)
        boundaries = [0.0] + [x[0] for x in hits if 0 < x[0] < duration] + [duration]
        scenes = []
        for i,(start,end) in enumerate(zip(boundaries,boundaries[1:])):
            if end-start >= 0.35:
                score = 0.0
                for t,s in hits:
                    if abs(t-end) < 0.05:
                        score = s
                        break
                scenes.append({"index":i+1,"start":round(start,3),
                    "end":round(end,3),"duration":round(end-start,3),
                    "scene_score":round(score,3)})
        return scenes

    def sample_frames(self, source, scenes, max_frames=24):
        selected = []
        step = max(1, len(scenes) // max_frames)
        for scene in scenes[::step][:max_frames]:
            selected.append({"scene_index":scene["index"],
                "timestamp":round(scene["start"] + scene["duration"]/2,3)})
        return selected
    def analyze(self, source, threshold=0.28):
        source = Path(source)
        probe = self.probe(source)
        scenes = self.detect_scenes(source, threshold)
        samples = self.sample_frames(source, scenes)
        durations = [s["duration"] for s in scenes]
        # Lightweight salience: shot length + boundary density. No invented story.
        for s in scenes:
            d = s["duration"]
            cut_score = min(40.0, s.get("scene_score", 0.0) * 10.0)
            s["visual_salience"] = round(min(100.0, 30.0 + min(d,8.0)*5.0 + cut_score),1)
            s["selection_reason"] = "distinct_shot"
        result = {
            "version": self.VERSION,
            "status": "READY",
            "source": str(source),
            "probe": probe,
            "scene_count": len(scenes),
            "scenes": scenes,
            "frame_samples": samples,
            "method": "ffmpeg_scdet",
            "threshold": threshold,
            "speech_fallback_safe": True,
            "note": "Visual evidence only; no narrative or captions are fabricated."
        }
        out = self.work_dir / "latest.json"
        out.write_text(json.dumps(result,ensure_ascii=False,indent=2))
        result["manifest_path"] = str(out)
        return result

if __name__ == "__main__":
    import sys
    r = VisualSceneAnalyzerV1().analyze(sys.argv[1])
    print(json.dumps(r,ensure_ascii=False,indent=2))
