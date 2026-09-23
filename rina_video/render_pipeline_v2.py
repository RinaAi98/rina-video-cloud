import subprocess
import json
from pathlib import Path
from .effects_engine_v1 import EffectsEngineV1


class RenderPipelineV2:
    """RINA Editor V3 bridge: source cuts + motion + captions + audio."""

    VERSION = "RINA_RENDER_PIPELINE_V2_EDITOR_V4"
    WIDTH = 1080
    HEIGHT = 1920

    def __init__(self):
        self.output_dir = Path("creator/video/output/rendered")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.effects = EffectsEngineV1()

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

    def _scene_filter(self, index, cut, caption_path=None, total=1, caption_events=None):
        start = float(cut["start"]); end = float(cut["end"])
        duration = max(0.1, end - start)
        stage = str(cut.get("stage", cut.get("story_stage", "MAIN"))).upper()
        text = self._wrap(cut.get("text", ""), 24 if stage == "HOOK" else 29)
        effect = self.effects.profile(cut if cut.get("micro_cut") else stage, index, total)
        zoom = effect["zoom"]
        speed = effect["pan_speed"]
        # Long continuous shots need stronger micro-pacing, but remain evidence-only.
        if duration >= 20:
            speed *= 1.22
        elif duration >= 10:
            speed *= 1.10
        amp = effect["pan_amp"]
        x = f"(iw-1080)/2+sin(t*{speed})*{amp}"
        y = "(ih-1920)/2+cos(t*0.42)*16"
        fontsize = 58 if stage == "HOOK" else (48 if stage == "PAYOFF" else 44)
        box = "0.88" if stage == "HOOK" else "0.72"
        filters = []
        transition = {"in": False, "out": False} if cut.get("micro_cut") else self.effects.transition(index, total)
        if index == 0:
            filters.append("fade=t=in:st=0:d=0.14")
        elif transition["in"]:
            filters.append("fade=t=in:st=0:d=0.12")
        if caption_events:
            for event in caption_events:
                event_text = self._wrap(event.get("text", ""), 24 if stage == "HOOK" else 29)
                if not event_text: continue
                st = max(0.0, float(event.get("start", 0.0)))
                en = min(duration, float(event.get("end", duration)))
                if en <= st: continue
                escaped = str(event.get("path", "")).replace("\\", "\\\\")
                enable = f"between(t\\,{st:.3f}\\,{en:.3f})"
                pop = f"if(between(t\\,{st:.3f}\\,{min(en, st+0.12):.3f})\\,{fontsize+8}\\,{fontsize})"
                filters.append(f"drawtext=fontfile=/system/fonts/Roboto-Bold.ttf:textfile={escaped}:fontcolor=white:fontsize='{pop}':x=(w-text_w)/2:y=h-text_h-300:line_spacing=10:box=1:boxcolor=black@{box}:boxborderw=20:shadowcolor=black@0.85:shadowx=2:shadowy=2:enable='{enable}'")
        elif text and caption_path:
            filters.append(f"drawtext=fontfile=/system/fonts/Roboto-Bold.ttf:textfile={caption_path}:fontcolor=white:fontsize={fontsize}:x=(w-text_w)/2:y=h-text_h-300:line_spacing=10:box=1:boxcolor=black@{box}:boxborderw=20:shadowcolor=black@0.85:shadowx=2:shadowy=2")
        if index == total - 1:
            filters.append(f"fade=t=out:st={max(0,duration-0.14):.3f}:d=0.14")
        elif transition["out"]:
            filters.append(f"fade=t=out:st={max(0,duration-0.12):.3f}:d=0.12")
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
            speech = cut.get("speech_segments", []) or []
            events = []
            for j, seg in enumerate(speech):
                words = seg.get("words", []) or []
                if words:
                    for k in range(0, len(words), 3):
                        group = words[k:k+3]
                        seg_text = " ".join(str(w.get("word","")).strip() for w in group).strip()
                        st = max(float(cut["start"]), float(group[0].get("start", cut["start"])))
                        en = min(float(cut["end"]), float(group[-1].get("end", cut["end"])))
                        if seg_text and en > st:
                            cp = caption_dir / f"caption_{i}_{j}_{k}.txt"
                            cp.write_text(self._wrap(seg_text, 24), encoding="utf-8")
                            events.append({"path": cp, "start": st - float(cut["start"]), "end": en - float(cut["start"]), "text": seg_text})
                    continue
                seg_text = str(seg.get("text", "")).strip()
                st = max(float(cut["start"]), float(seg.get("start", cut["start"])))
                en = min(float(cut["end"]), float(seg.get("end", cut["end"])))
                if seg_text and en > st:
                    cp = caption_dir / f"caption_{i}_{j}.txt"
                    cp.write_text(self._wrap(seg_text, 24), encoding="utf-8")
                    events.append({"path": cp, "start": st - float(cut["start"]), "end": en - float(cut["start"]), "text": seg_text})
            if events:
                paths.append(events)
            elif text:
                cp = caption_dir / f"caption_{i}.txt"
                cp.write_text(self._wrap(text, 24), encoding="utf-8")
                paths.append([{"path": cp, "start": 0.0, "end": float(cut["end"]) - float(cut["start"]), "text": text}])
            else:
                paths.append([])
        filters = [self._scene_filter(i, c, None, len(cuts), paths[i])
                   for i, c in enumerate(cuts)]
        cv = "".join(f"[v{i}]" for i in range(len(cuts)))
        ca = "".join(f"[a{i}]" for i in range(len(cuts)))
        graph = ";".join(filters) + ";" + f"{cv}concat=n={len(cuts)}:v=1:a=0[outv];"
        graph += f"{ca}concat=n={len(cuts)}:v=0:a=1[outa]"
        cmd = ["ffmpeg", "-y", "-i", str(source), "-filter_complex", graph,
               "-map", "[outv]", "-map", "[outa]", "-c:v", "libx264",
               "-preset", "veryfast", "-crf", "18", "-threads", "0",
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
