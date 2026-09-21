import json
import shutil
import threading
import uuid
from pathlib import Path
from .multimodal_clip_engine_v1 import MultimodalClipEngineV1
from .render_pipeline_v2 import RenderPipelineV2
from .qc_engine import VideoQCEngine

class VideoPipelineV2:
    VERSION = "RINA_VIDEO_PIPELINE_V2_APK"
    def __init__(self, job_dir=None):
        self.job_dir = Path(job_dir or "creator/video/output/jobs")
        self.job_dir.mkdir(parents=True, exist_ok=True)
        self.engine = MultimodalClipEngineV1()
        self.renderer = RenderPipelineV2()
        self.qc = VideoQCEngine(min_duration=45, max_duration=60)

    def _save(self, job):
        path = self.job_dir / f"{job['job_id']}.json"
        path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def run(self, source, job_id=None):
        source = Path(source)
        job_id = job_id or "rvp2_" + uuid.uuid4().hex[:10]
        job = {"job_id": job_id, "version": self.VERSION, "status": "PROCESSING",
               "stage": "RECEIVED", "input": str(source), "progress": 5}
        self._save(job)
        try:
            job.update(stage="ANALYZING", progress=25)
            self._save(job)
            analysis = self.engine.run(source)
            job["analysis_mode"] = analysis.get("mode")
            job["cut_plan"] = analysis.get("cut_plan", {})
            job.update(stage="RENDERING", progress=55)
            self._save(job)
            render = self.renderer.render(source, analysis["cut_plan"], job_id)
            output = render.get("video") or render.get("output") or render.get("output_path")
            if not output:
                raise RuntimeError("Renderer tidak mengembalikan file output.")
            job.update(stage="QC", progress=90)
            self._save(job)
            qc = self.qc.inspect(output)
            job["qc"] = qc
            if qc.get("status") != "PASS":
                job.update(status="REWORK", stage="QC_FAILED", progress=100)
            else:
                job.update(status="READY", stage="READY", progress=100)
            job["output"] = str(output)
            job["download_name"] = f"RINA_{job_id}.mp4"
            job["result_url"] = f"/video/edit/result/{job_id}"
            job["manifest_path"] = self._save(job)
            return job
        except Exception as exc:
            job.update(status="ERROR", stage="FAILED", progress=100,
                        error=type(exc).__name__, message=str(exc))
            job["manifest_path"] = self._save(job)
            return job

    def run_background(self, source, job_id):
        thread = threading.Thread(target=self.run, args=(source, job_id), daemon=True)
        thread.start()
        return thread
