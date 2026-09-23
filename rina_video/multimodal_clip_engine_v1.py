from __future__ import annotations
import json
from pathlib import Path
from .transcription_engine_v1 import TranscriptionEngineV1
from .visual_scene_analyzer_v1 import VisualSceneAnalyzerV1
from .semantic_clip_selector_v1 import SemanticClipSelectorV1
from .smart_cut_engine_v3 import SmartCutEngineV3
from .visual_hook_engine_v3 import VisualHookEngineV3

class MultimodalClipEngineV1:
    VERSION = "RINA_MULTIMODAL_CLIP_ENGINE_V1"

    def __init__(self):
        self.transcriber = TranscriptionEngineV1()
        self.visual = VisualSceneAnalyzerV1()
        self.semantic = SemanticClipSelectorV1()
        self.cutter = SmartCutEngineV3()
        self.visual_hook = VisualHookEngineV3()

    def _overlap(self, a, b):
        return max(0.0, min(a["end"], b["end"]) - max(a["start"], b["start"]))

    def _visualize(self, scenes, transcript):
        speech = transcript.get("segments", [])
        out = []
        for scene in scenes:
            overlaps = [x for x in speech if self._overlap(scene, x) > 0]
            words = sum(len(str(x.get("text","")).split()) for x in overlaps)
            speech_ratio = min(1.0, words / 18.0)
            score = min(100.0, scene["visual_salience"] * 0.65 + speech_ratio * 35.0)
            item = dict(scene)
            item.update(speech_segments=overlaps, word_count=words,
                        multimodal_score=round(score,2),
                        evidence="visual+speech" if overlaps else "visual_only")
            out.append(item)
        return sorted(out, key=lambda x:(-x["multimodal_score"], x["start"]))

    def run(self, source, transcript=None, threshold=0.28):
        source = Path(source)
        if not source.exists():
            raise FileNotFoundError(source)
        if transcript is None:
            transcript = self.transcriber.transcribe(source)
        visual = self.visual.analyze(source, threshold)
        ranked = self._visualize(visual["scenes"], transcript)
        visual_hook = self.visual_hook.analyze(source)
        visual_candidates = self.visual_hook.candidates(visual_hook)
        transcript_segments = transcript.get("segments", [])
        semantic = self.semantic.select(transcript_segments, max_segments=8,
                                         min_total_seconds=20, max_total_seconds=60)
                # Sparse speech fallback: use real visual shots, never fabricate dialogue.
        if semantic["status"] == "READY":
            candidates = list(semantic["selected_segments"])
            for vc in visual_candidates:
                overlaps=[x for x in transcript_segments if self._overlap(vc,x)>0]
                vc["speech_segments"]=overlaps
                vc["text"]=" ".join(str(x.get("text","")).strip() for x in overlaps).strip()
                candidates.append(vc)
            mode = "multimodal_speech_visual"
        else:
            candidates = []
            for scene in ranked:
                if scene["duration"] < 1.0:
                    continue
                item = {
                    "start": scene["start"], "end": scene["end"],
                    "text": " ".join(x["text"] for x in scene["speech_segments"]).strip(),
                    "score": scene["multimodal_score"],
                    "story_stage": "",
                    "visual_evidence": True,
                    "speech_segments": scene.get("speech_segments", []),
                }
                candidates.append(item)
            candidates.extend(visual_candidates)
            candidates = sorted(candidates, key=lambda x:(-float(x.get("visual_score",x.get("score",0))), x["start"]))[:12]
            candidates.sort(key=lambda x:x["start"])
            mode = "visual_fallback"
        source_duration = max([float(x.get("end",0)) for x in visual.get("scenes", [])] + [float(x.get("end",0)) for x in transcript_segments] + [0.0])
        cut = self.cutter.build(candidates, source_duration, 45.0, 60.0)
        result = {
            "version": self.VERSION, "status": "READY" if cut["status"] == "READY" else cut["status"],
            "source": str(source), "mode": mode,
            "transcript": transcript, "visual": visual,
            "ranked_visual_scenes": ranked, "visual_hook": visual_hook,
            "semantic_selection": semantic, "cut_plan": cut, "fabrication_policy": "NO_INVENTED_SPEECH_OR_STORY",
        }
        out = Path("creator/video/output/jobs")
        out.mkdir(parents=True, exist_ok=True)
        path = out / "multimodal_latest.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        result["manifest_path"] = str(path)
        return result

if __name__ == "__main__":
    import sys
    r = MultimodalClipEngineV1().run(sys.argv[1])
    print("STATUS", r["status"])
    print("MODE", r["mode"])
    print("VISUAL_SCENES", len(r["ranked_visual_scenes"]))
    print("CUTS", len(r["cut_plan"].get("cut_plan", [])))
    print("DURATION", r["cut_plan"].get("total_duration", 0))
