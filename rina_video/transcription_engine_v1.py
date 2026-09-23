import os
import subprocess
import tempfile
from pathlib import Path


class TranscriptionEngineV1:
    VERSION = "RINA_TRANSCRIPTION_ENGINE_V1"
    MODEL = "whisper-large-v3-turbo"
    ENDPOINT = "https://api.groq.com/openai/v1/audio/transcriptions"

    def __init__(self, api_key=None, language="id"):
        if api_key:
            self.api_key = api_key
        else:
            self.api_key = os.getenv("GROQ_API_KEY")
            if not self.api_key:
                try:
                    from config.settings import GROQ_API_KEY
                    self.api_key = GROQ_API_KEY
                except Exception:
                    self.api_key = None
        self.language = language

    def _extract_audio(self, source):
        fd, name = tempfile.mkstemp(suffix=".flac")
        os.close(fd)
        cmd = ["ffmpeg", "-y", "-i", str(source), "-map", "0:a:0",
               "-ar", "16000", "-ac", "1", "-c:a", "flac", name]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode:
            Path(name).unlink(missing_ok=True)
            raise RuntimeError("Ekstraksi audio gagal: " + result.stderr[-1500:])
        return Path(name)

    def transcribe(self, source):
        source = Path(source)
        if not source.exists():
            raise FileNotFoundError(source)
        if not self.api_key:
            return {"status": "WAITING_CREDENTIAL", "reason": "GROQ_API_KEY belum tersedia."}
        try:
            import requests
        except Exception as exc:
            return {"status": "ERROR", "reason": f"requests tidak tersedia: {exc}"}
        audio = self._extract_audio(source)
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            with audio.open("rb") as fh:
                response = requests.post(
                    self.ENDPOINT,
                    headers=headers,
                    files={"file": (audio.name, fh, "audio/flac")},
                    data=[("model", self.MODEL), ("language", self.language),
                          ("response_format", "verbose_json"),
                          ("timestamp_granularities[]", "segment"),
                          ("timestamp_granularities[]", "word"),
                          ("temperature", "0.0")],
                    timeout=180)
            if response.status_code >= 400:
                return {"status": "ERROR", "reason":
                        f"Groq HTTP {response.status_code}: {response.text[:1000]}"}
            result = response.json()
            word_items = result.get("words", []) or []
            segments = []
            for item in result.get("segments", []) or []:
                start = float(item.get("start", 0)); end = float(item.get("end", 0))
                words = [{"start":float(w.get("start",0)), "end":float(w.get("end",0)),
                          "word":str(w.get("word","")).strip()}
                         for w in word_items
                         if float(w.get("end",0)) > start and float(w.get("start",0)) < end]
                segments.append({"start":start, "end":end,
                                 "text":str(item.get("text", "")).strip(), "words":words})
            return {"status": "READY", "model": self.MODEL,
                    "language": self.language, "text": str(result.get("text", "")).strip(),
                    "segments": segments}
        except Exception as exc:
            return {"status": "ERROR", "reason": str(exc)}
        finally:
            audio.unlink(missing_ok=True)


__all__ = ["TranscriptionEngineV1"]
