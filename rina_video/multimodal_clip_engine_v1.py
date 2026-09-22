from __future__ import annotations
import json
from pathlib import Path
from .transcription_engine_v1 import TranscriptionEngineV1
from .visual_scene_analyzer_v1 import VisualSceneAnalyzerV1
from .semantic_clip_selector_v1 import SemanticClipSelectorV1
from .smart_cut_engine_v1 import SmartCutEngineV1

class MultimodalClipEngineV1:
    VERSION = "RINA_MULTIMODAL_CLIP_ENGINE_V1"

    def __init__(self):
        self.transcriber = TranscriptionEngineV1()
        self.visual = VisualSceneAnalyzerV1()
        self.semantic = SemanticClipSelectorV1()
        self.cutter = SmartCutEngineV1()

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
        transcript_segments = transcript.get("segments", [])
        semantic = self.semantic.select(transcript_segments, max_segments=8,
                                         min_total_seconds=20, max_total_seconds=60)
                # Sparse speech fallback: use real visual shots, never fabricate dialogue.
        if semantic["status"] == "READY":
            candidates = semantic["selected_segments"]
            mode = "speech_semantic"
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
            candidates = sorted(candidates, key=lambda x:(-x["score"], x["start"]))[:8]
            candidates.sort(key=lambda x:x["start"])
            mode = "visual_fallback"
        cut = self.cutter.build(candidates, 45.0, 60.0)
        result = {
            "version": self.VERSION, "status": "READY" if cut["status"] == "READY" else cut["status"],
            "source": str(source), "mode": mode,
            "transcript": transcript, "visual": visual,
            "ranked_visual_scenes": ranked, "semantic_selection": semantic,
            "cut_plan": cut, "fabrication_policy": "NO_INVENTED_SPEECH_OR_STORY",
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
