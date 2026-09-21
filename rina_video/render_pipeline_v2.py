import subprocess
import json
from pathlib import Path


class RenderPipelineV2:
    """RINA Editor V3 bridge: source cuts + motion + captions + audio."""

    VERSION = "RINA_RENDER_PIPELINE_V2_EDITOR_V3"
    WIDTH = 1080
    HEIGHT = 1920

    def __init__(self):
        self.output_dir = Path("creator/video/output/rendered")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _escape(text):
        return (str(text).replace("\\", "\\\\")
                .replace("'", "\\'").replace(":", "\\:")
                .replace("%", "\\%"))

    @staticmethod
    def _wrap(text, width=28):
        words = str(text).strip().split()
        lines, line = [], []
        for word in words:
            test = " ".join(line + [word])
            if len(test) > width and line:
                lines.append(" ".join(line)); line = [word]
            else: line.append(word)
        if line: lines.append(" ".join(line))
        return "\n".join(lines[:3])

    def _motion(self, stage, index):
        stage = str(stage).upper()
        if stage == "HOOK": return (1.12, 0.60, 34)
        if stage == "PAYOFF": return (1.08, 0.45, -30)
        zoom = 1.05 + (index % 3) * 0.02
        pan = 0.38 if index % 2 else -0.38
        return (zoom, pan, 20)

    def _scene_filter(self, index, cut, caption_path=None, total=1):
        start = float(cut["start"]); end = float(cut["end"])
        duration = max(0.1, end - start)
        stage = str(cut.get("stage", cut.get("story_stage", "MAIN"))).upper()
        text = self._wrap(cut.get("text", ""), 24 if stage == "HOOK" else 29)
        zoom, speed, amp = self._motion(stage, index)
        x = f"(iw-1080)/2+sin(t*{speed})*{amp}"
        y = "(ih-1920)/2+cos(t*0.42)*16"
        fontsize = 58 if stage == "HOOK" else (48 if stage == "PAYOFF" else 44)
        box = "0.88" if stage == "HOOK" else "0.72"
        filters = []
        if index == 0: filters.append("fade=t=in:st=0:d=0.14")
        if text and caption_path:
            filters.append(f"drawtext=fontfile=/system/fonts/Roboto-Bold.ttf:textfile={caption_path}:fontcolor=white:fontsize={fontsize}:x=(w-text_w)/2:y=h-text_h-320:line_spacing=14:box=1:boxcolor=black@{box}:boxborderw=24:shadowcolor=black@0.8:shadowx=2:shadowy=2")
        if index == total - 1:
            filters.append(f"fade=t=out:st={max(0,duration-0.14):.3f}:d=0.14")
        extra = ("," + ",".join(filters)) if filters else ""
        return (f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS,"
                "scale=1080:1920:force_original_aspect_ratio=increase,"
                f"scale=iw*{zoom}:ih*{zoom},crop=1080:1920:x='{x}':y='{y}',"
                "setsar=1,eq=brightness=-0.02:contrast=1.04:saturation=1.05"
                + extra + f",format=yuv420p[v{index}];"
                f"[0:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS,"
                f"aformat=sample_rates=48000:channel_layouts=stereo[a{index}]")

    def render(self, source, cut_plan, job_id="render_v2"):
        source = Path(source)
        if not source.exists(): raise FileNotFoundError(source)
        cuts = cut_plan.get("cut_plan", cut_plan) if isinstance(cut_plan, dict) else cut_plan
        if not cuts: raise ValueError("cut_plan kosong")
        output = self.output_dir / f"{job_id}.mp4"
        caption_dir = self.output_dir / f"{job_id}_captions"
        caption_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for i, cut in enumerate(cuts):
            text = str(cut.get("text", "")).strip()
            if text:
                cp = caption_dir / f"caption_{i}.txt"
                cp.write_text(self._wrap(text, 24), encoding="utf-8")
                paths.append(cp)
            else: paths.append(None)
        filters = [self._scene_filter(i, c, str(paths[i]) if paths[i] else None, len(cuts))
                   for i, c in enumerate(cuts)]
        cv = "".join(f"[v{i}]" for i in range(len(cuts)))
        ca = "".join(f"[a{i}]" for i in range(len(cuts)))
        graph = ";".join(filters) + ";" + f"{cv}concat=n={len(cuts)}:v=1:a=0[outv];"
        graph += f"{ca}concat=n={len(cuts)}:v=0:a=1[outa]"
        cmd = ["ffmpeg", "-y", "-i", str(source), "-filter_complex", graph,
               "-map", "[outv]", "-map", "[outa]", "-c:v", "libx264",
               "-preset", "veryfast", "-crf", "20", "-threads", "0",
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
               "-ar", "48000", "-movflags", "+faststart", str(output)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError("FFmpeg gagal:\n" + result.stderr[-5000:])
        return {"version": self.VERSION, "video": str(output), "shots": len(cuts),
                "duration": round(sum(float(c["end"])-float(c["start"]) for c in cuts), 3),
                "stages": [c.get("stage", c.get("story_stage", "MAIN")) for c in cuts]}

    def save_manifest(self, result, path):
        target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(target)


__all__ = ["RenderPipelineV2"]
