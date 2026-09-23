"""RINA Caption Intelligence V1: readable timed groups from actual transcript words only."""
from __future__ import annotations
from typing import Any
class CaptionIntelligenceV1:
    VERSION="RINA_CAPTION_INTELLIGENCE_V1"
    def group(self, words:list[dict[str,Any]], max_words:int=4, max_chars:int=28, max_duration:float=2.2):
        events=[]; group=[]; start=None
        for w in words:
            word=str(w.get("word","")).strip()
            if not word: continue
            ws=float(w.get("start",0)); we=float(w.get("end",ws))
            candidate=group+[word]
            too_long=group and (we-float(start))>max_duration
            too_wide=group and len(" ".join(candidate))>max_chars
            if too_long or too_wide or len(group)>=max_words:
                events.append(self._event(group,start,float(group[-1]["end"])))
                group=[]; start=None
            if start is None: start=ws
            group.append({"word":word,"start":ws,"end":we})
        if group: events.append(self._event(group,start,float(group[-1]["end"])))
        return {"version":self.VERSION,"events":events,"evidence_only":True}
    def _event(self,group,start,end):
        text=" ".join(x["word"] for x in group)
        return {"text":text,"start":round(float(start),3),"end":round(float(end),3),
                "word_count":len(group),"emphasis":group[-1]["word"] if len(group)>1 else group[0]["word"]}
