"""Evidence-based audio momentum / beat proxy for RINA video editing."""
from __future__ import annotations
from typing import Any

class AudioMusicIntelligenceV2:
    VERSION = "RINA_AUDIO_MUSIC_INTELLIGENCE_V2"

    def analyze(self, analysis: dict[str, Any]) -> dict[str, Any]:
        peaks = analysis.get("peaks", []) or []
        events = []
        for p in peaks:
            ts = float(p.get("timestamp", 0.0))
            energy = float(p.get("energy", 0.0))
            events.append({
                "timestamp": round(ts, 3),
                "strength": round(min(1.0, energy / 100.0), 3),
                "energy": round(energy, 2),
                "type": "AUDIO_PEAK",
                "evidence": "rms_energy_peak",
            })
        events.sort(key=lambda x: x["timestamp"])
        return {"version": self.VERSION, "events": events,
                "event_count": len(events), "evidence_only": True,
                "method": "rms_energy_peak_beat_proxy"}

    def annotate(self, cuts, music: dict[str, Any]):
        events = music.get("events", []) or []
        out = []
        for c in cuts:
            x = dict(c)
            start, end = float(c["start"]), float(c["end"])
            nearby = [e for e in events if start - 0.75 <= e["timestamp"] <= end + 0.75]
            inside = [e for e in events if start <= e["timestamp"] <= end]
            strongest = max(nearby, key=lambda e: e["strength"]) if nearby else None
            x["audio_momentum"] = round(strongest["strength"], 3) if strongest else 0.0
            x["beat_alignment"] = round(strongest["timestamp"] - start, 3) if strongest else None
            x["beat_event_count"] = len(inside)
            x["beat_evidence"] = "audio_peak" if strongest else "temporal_segment"
            out.append(x)
        return out
