"""Automated QC engine for RINA short-form video output."""
import json
import os
import subprocess
from typing import Any, Dict

class VideoQCEngine:
    VERSION = "RINA_VIDEO_QC_V1"

    def __init__(self, min_duration=20.0, max_duration=90.0):
        self.min_duration = float(min_duration)
        self.max_duration = float(max_duration)

    def _ffprobe(self, path: str) -> Dict[str, Any]:
        cmd = ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path]
        return json.loads(subprocess.check_output(cmd, text=True))

    def inspect(self, path: str) -> Dict[str, Any]:
        result = {"file": path, "qc_version": self.VERSION, "checks": {}, "status": "REWORK"}
        if not os.path.isfile(path):
            result["checks"]["file_exists"] = False
            result["reason"] = "Output file tidak ditemukan."
            return result
        result["checks"]["file_exists"] = True
        try:
            probe = self._ffprobe(path)
        except Exception as exc:
            result["reason"] = f"ffprobe gagal: {exc}"
            return result
        streams = probe.get("streams", [])
        fmt = probe.get("format", {})
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
        duration = float(fmt.get("duration") or 0.0)
        width = int(video.get("width") or 0) if video else 0
        height = int(video.get("height") or 0) if video else 0
        result["media"] = {"duration": round(duration, 3), "width": width, "height": height,
                           "has_video": bool(video), "has_audio": bool(audio),
                           "size_bytes": os.path.getsize(path)}
        result["checks"]["duration"] = self.min_duration <= duration <= self.max_duration
        result["checks"]["vertical"] = height >= width and height > 0
        result["checks"]["resolution"] = width >= 720 and height >= 1280
        result["checks"]["video_stream"] = bool(video)
        result["checks"]["audio_stream"] = bool(audio)
        result["checks"]["file_nonempty"] = os.path.getsize(path) > 10000
        # Decode-integrity QC: ffprobe metadata alone cannot detect corrupted H264/AAC packets.
        try:
            probe_decode = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", path, "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"], capture_output=True, text=True, timeout=180)
            result["checks"]["decode_integrity"] = probe_decode.returncode == 0
            if probe_decode.returncode != 0:
                result["decode_error"] = probe_decode.stderr[-1200:]
        except Exception as exc:
            result["checks"]["decode_integrity"] = False
            result["decode_error"] = str(exc)
        failed = [name for name, ok in result["checks"].items() if not ok]
        result["failed_checks"] = failed
        result["status"] = "PASS" if not failed else "REWORK"
        result["reason"] = ("QC gagal: " + ", ".join(failed)) if failed else "Media dasar valid; lanjut ke QC visual/semantic."
        return result

__all__ = ["VideoQCEngine"]
