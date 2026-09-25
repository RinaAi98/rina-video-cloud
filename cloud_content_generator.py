import os
import json
import re
import subprocess
from pathlib import Path
from datetime import datetime, timezone
import requests

ROOT = Path(__file__).resolve().parent
WORK = Path("/tmp/rina_content")
ASSETS = WORK / "assets"
OUT = WORK / "out"
WORK.mkdir(parents=True, exist_ok=True)
ASSETS.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

GROQ = os.environ["GROQ_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")
MODEL = os.getenv("RINA_CONTENT_MODEL", "openai/gpt-oss-20b")

TOPICS = [
    ("science", "Fenomena sains sehari-hari yang terlihat biasa tetapi punya penjelasan mengejutkan"),
    ("technology", "Teknologi AI yang mengubah cara manusia bekerja sehari-hari"),
    ("finance", "Kebiasaan uang sederhana yang sering diabaikan orang muda"),
    ("history", "Fakta sejarah Nusantara yang bisa diceritakan seperti mini dokumenter"),
    ("story", "Kisah manusia singkat dengan konflik dan pelajaran yang kuat"),
    ("lifestyle", "Kebiasaan kecil yang membuat hidup sehari-hari lebih efektif"),
]
STOP = {"yang","dan","atau","dari","untuk","dengan","ini","itu","kita","akan","bisa","cara","tentang","karena","adalah","sebuah","dalam","pada","the","dan"}
def tokens(text):
    return {x for x in re.findall(r"[a-z0-9]+", str(text).lower()) if len(x) >= 4 and x not in STOP}

def groq_plan(theme_hint, seed):
    system = """Kamu adalah Creative Director RINA AI. Buat video vertikal 45-60 detik yang terasa seperti mini documentary, bukan slideshow.
WAJIB: setiap scene harus punya hubungan visual langsung dengan kalimat narasinya. Jangan memakai visual generik jika ada subjek spesifik.
Buat 6 scene: HOOK, SETUP, TENSION, DEVELOPMENT, REVEAL, PAYOFF. CTA ditambahkan di akhir.
Gunakan bahasa Indonesia natural, kalimat pendek, ritme berubah, dan hindari template berulang.
Visual query WAJIB berupa frasa kata kunci BAHASA INGGRIS yang konkret dan dapat dicari sebagai foto/video nyata: objek, tempat, aktivitas, atau fenomena yang disebut scene. Jangan memakai kalimat panjang.
Jangan mengarang fakta spesifik yang tidak perlu. Jika topik faktual, gunakan framing edukatif dan hindari angka/detail yang tidak yakin."""
    user = f"""Tema rotasi: {theme_hint}
Seed hari ini: {seed}
Kembalikan JSON saja:
{{
"title":"...",
"theme":"science|technology|finance|history|story|lifestyle",
"hook":"...",
"scenes":[
{{"stage":"HOOK","narration":"...","visual_subject":"...","visual_query":"...","caption":"..."}},
{{"stage":"SETUP","narration":"...","visual_subject":"...","visual_query":"...","caption":"..."}},
{{"stage":"TENSION","narration":"...","visual_subject":"...","visual_query":"...","caption":"..."}},
{{"stage":"DEVELOPMENT","narration":"...","visual_subject":"...","visual_query":"...","caption":"..."}},
{{"stage":"REVEAL","narration":"...","visual_subject":"...","visual_query":"...","caption":"..."}},
{{"stage":"PAYOFF","narration":"...","visual_subject":"...","visual_query":"...","caption":"..."}}
],
"cta":"...",
"caption":"...",
"hashtags":["#...","#...","#..."]
}}"""
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ}", "Content-Type": "application/json"},
        json={"model": MODEL, "temperature": 0.85,
              "messages":[{"role":"system","content":system},{"role":"user","content":user}],
              "response_format":{"type":"json_object"}},
        timeout=90,
    )
    r.raise_for_status()
    data = r.json()
    return json.loads(data["choices"][0]["message"]["content"])

def validate_plan(plan):
    scenes = plan.get("scenes") or []
    required = ["HOOK","SETUP","TENSION","DEVELOPMENT","REVEAL","PAYOFF"]
    if len(scenes) != 6 or [s.get("stage") for s in scenes] != required:
        raise ValueError("story_structure_invalid")
    if len(tokens(plan.get("title"))) < 2:
        raise ValueError("title_too_weak")
    if not str(plan.get("cta","")).strip():
        plan["cta"] = "Kalau kamu suka cerita seperti ini, follow RINA untuk video berikutnya."
    if not str(plan.get("caption","")).strip():
        plan["caption"] = plan.get("title","RINA AI")
    if not isinstance(plan.get("hashtags"), list):
        plan["hashtags"] = ["#RINAAI", "#edukasi", "#fakta"]
    for s in scenes:
        if len(tokens(s.get("narration"))) < 5:
            raise ValueError(f"scene_narration_too_short:{s.get('stage')}")
        if len(tokens(s.get("visual_query"))) < 2:
            raise ValueError(f"scene_query_too_short:{s.get('stage')}")
        subject = tokens(s.get("visual_subject"))
        query = tokens(s.get("visual_query"))
        narration = tokens(s.get("narration"))
        if subject and not (subject & query or subject & narration):
            raise ValueError(f"visual_subject_mismatch:{s.get('stage')}")
    return True
def pexels_candidates(query):
    if not PEXELS_API_KEY:
        return []
    r=requests.get("https://api.pexels.com/videos/search",
                   headers={"Authorization":PEXELS_API_KEY},
                   params={"query":query,"orientation":"portrait","size":"medium","per_page":8},
                   timeout=30)
    r.raise_for_status()
    out=[]
    for v in r.json().get("videos",[]):
        files=sorted(v.get("video_files",[]), key=lambda x: abs((x.get("width") or 0)-1080))
        if files:
            f=files[0]
            out.append({"title":v.get("url","Pexels video"),"url":f.get("link"),
                        "mime":"video/mp4","source":"Pexels","search_text":query})
    return [x for x in out if x.get("url")]

def pixabay_candidates(query):
    if not PIXABAY_API_KEY:
        return []
    r=requests.get("https://pixabay.com/api/videos/",
                   params={"key":PIXABAY_API_KEY,"q":query,"per_page":8},
                   timeout=30)
    r.raise_for_status()
    out=[]
    for v in r.json().get("hits",[]):
        files=v.get("videos",{})
        f=files.get("large") or files.get("medium") or files.get("small")
        if f and f.get("url"):
            out.append({"title":v.get("pageURL","Pixabay video"),"url":f["url"],
                        "mime":"video/mp4","source":"Pixabay","search_text":str(v.get("tags", ""))})
    return out

def wikimedia_candidates(query):
    params = {
        "action":"query","generator":"search","gsrsearch":query,
        "gsrnamespace":"6","gsrlimit":"8","prop":"imageinfo",
        "iiprop":"url|mime|size","iiurlwidth":"640","format":"json"
    }
    r = requests.get("https://commons.wikimedia.org/w/api.php", params=params, timeout=30, headers={"User-Agent":"RINA-AI-Cloud/1.0 (content-generator)"})
    r.raise_for_status()
    pages = r.json().get("query",{}).get("pages",{})
    out=[]
    for p in pages.values():
        info=(p.get("imageinfo") or [{}])[0]
        url=info.get("thumburl") or info.get("url")
        mime=str(info.get("mime",""))
        if url and (mime.startswith("image/") or mime.startswith("video/")):
            out.append({"title":p.get("title",""),"url":url,"mime":mime,"source":"Wikimedia Commons","search_text":p.get("title","")})
    return out

def select_visual(scene):
    query = scene["visual_query"]
    desired = tokens(query) | tokens(scene["visual_subject"]) | tokens(scene["narration"])
    candidates=[]
    source_errors=[]
    for source_fn in (pexels_candidates, pixabay_candidates, wikimedia_candidates):
        try:
            candidates.extend(source_fn(query))
        except Exception as exc:
            source_errors.append(type(exc).__name__)
    if not candidates:
        for source_fn in (pexels_candidates, pixabay_candidates, wikimedia_candidates):
            try:
                candidates.extend(source_fn(scene["visual_subject"]))
            except Exception as exc:
                source_errors.append(type(exc).__name__)
    ranked=[]
    for c in candidates:
        score = len(desired & tokens(c.get("search_text", c.get("title",""))))
        ranked.append((score,c))
    ranked.sort(key=lambda x:x[0], reverse=True)
    if not ranked:
        return None, 0
    return ranked[0][1], ranked[0][0]

def download(url, path):
    headers={"User-Agent":"RINA-AI-Cloud/1.0 (content-generator)"}
    last=None
    for attempt in range(5):
        try:
            r=requests.get(url, timeout=60, stream=True, headers=headers)
            if r.status_code == 429:
                import time
                time.sleep(2 ** attempt)
                last=RuntimeError("visual_source_rate_limited")
                continue
            r.raise_for_status()
            with open(path,"wb") as f:
                for chunk in r.iter_content(1024*128):
                    if chunk: f.write(chunk)
            if path.stat().st_size < 5000:
                raise ValueError("visual_file_too_small")
            return path
        except Exception as exc:
            last=exc
            if attempt < 4:
                import time
                time.sleep(2 ** attempt)
    raise last
def make_fallback_visual(scene, index, theme, path):
    from PIL import Image, ImageDraw, ImageFont
    palettes = {
        "science": ((12,28,54),(34,105,160)),
        "technology": ((20,18,52),(94,45,145)),
        "finance": ((18,48,38),(30,125,92)),
        "history": ((62,40,24),(150,94,42)),
        "story": ((50,24,46),(145,52,92)),
        "lifestyle": ((34,45,58),(78,125,150)),
    }
    a,b=palettes.get(theme,palettes["lifestyle"])
    img=Image.new("RGB",(1080,1920),a)
    d=ImageDraw.Draw(img)
    for step in range(12):
        x1=40+step*90
        y1=160+((step*137)%1200)
        r=90+((index*17+step*13)%100)
        d.ellipse((x1-r,y1-r,x1+r,y1+r),fill=b)
    font_big=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",72)
    font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",46)
    stage=str(scene["stage"])
    subject=str(scene["visual_subject"]).strip()
    caption=str(scene["caption"]).strip()
    d.rounded_rectangle((70,110,1010,430),radius=36,fill=(0,0,0))
    d.text((110,150),f"RINA • {stage}",font=font_big,fill=(255,255,255))
    d.text((110,270),subject[:55],font=font,fill=(230,240,255))
    d.rounded_rectangle((70,1390,1010,1810),radius=36,fill=(0,0,0))
    d.text((110,1460),caption[:70],font=font,fill=(255,255,255))
    img.save(path,quality=92)
    return path

def make_voice(text, output):
    try:
        import edge_tts
        voice = os.getenv("RINA_EDGE_VOICE","id-ID-GadisNeural")
        subprocess.run(["python","-m","edge_tts","--voice",voice,"--text",text,"--write-media",str(output)],
                       check=True, timeout=90)
    except Exception:
        # Cloud fallback: gTTS has no local Android dependency.
        from gtts import gTTS
        gTTS(text=text, lang="id", slow=False).save(str(output))
    return output

def duration(path):
    r=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                      "-of","default=noprint_wrappers=1:nokey=1",str(path)],
                     capture_output=True,text=True,check=True)
    return float(r.stdout.strip())

def render_scene(image, caption, seconds, index, output):
    # Ken-Burns style motion makes still visuals active instead of static slides.
    textfile=output.with_suffix(".txt")
    textfile.write_text(caption[:90], encoding="utf-8")
    frames=max(1,int(round(seconds*30)))
    zoom=(f"min(1+0.0007*on,1.12)" if index % 2 == 0
          else f"max(1.12-0.0007*on,1.0)")
    vf=(
      "scale=1080:1920:force_original_aspect_ratio=increase,"
      "crop=1080:1920,"
      f"zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
      f"d={frames}:s=1080x1920:fps=30,"
      "eq=contrast=1.04:saturation=1.06,"
      f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
      f"textfile='{textfile}':fontcolor=white:fontsize=52:"
      "x=(w-text_w)/2:y=h-text_h-280:box=1:boxcolor=black@0.62:boxborderw=26,"
      "format=yuv420p"
    )
    cmd=["ffmpeg","-y","-loop","1","-i",str(image),
         "-vf",vf,"-frames:v",str(frames),"-an","-c:v","libx264",
         "-preset","veryfast","-crf","21","-pix_fmt","yuv420p",str(output)]
    try:
        subprocess.run(cmd,check=True,timeout=120,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as exc:
        # Cloud FFmpeg builds can differ in zoompan behavior; retry with a conservative filter.
        safe_vf=("scale=1080:1920:force_original_aspect_ratio=increase,"
                 "crop=1080:1920,"
                 f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                 f"textfile='{textfile}':fontcolor=white:fontsize=52:"
                 "x=(w-text_w)/2:y=h-text_h-280:box=1:boxcolor=black@0.62:boxborderw=26,"
                 "format=yuv420p")
        safe_cmd=["ffmpeg","-y","-loop","1","-i",str(image),"-vf",safe_vf,
                  "-frames:v",str(frames),"-an","-c:v","libx264","-preset","veryfast",
                  "-crf","21","-pix_fmt","yuv420p",str(output)]
        subprocess.run(safe_cmd,check=True,timeout=120,stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE)

def concat_videos(parts, output):
    listing=WORK/"concat.txt"
    listing.write_text("".join(f"file '{p}'\n" for p in parts),encoding="utf-8")
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(listing),
                    "-c","copy","-movflags","+faststart",str(output)],check=True,timeout=180,
                   stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)

def mux_voice(video, voice, output):
    subprocess.run(["ffmpeg","-y","-i",str(video),"-i",str(voice),
                    "-filter_complex","[1:a]loudnorm=I=-16:TP=-1.5:LRA=7[a]",
                    "-map","0:v","-map","[a]","-c:v","copy","-c:a","aac","-b:a","160k",
                    "-shortest","-movflags","+faststart",str(output)],check=True,timeout=180,
                   stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
def upload_supabase(local, remote_path, content_type):
    url=f"{SUPABASE_URL}/storage/v1/object/rina-video-results/{remote_path}"
    headers={"apikey":SUPABASE_KEY,"Authorization":f"Bearer {SUPABASE_KEY}",
             "Content-Type":content_type,"x-upsert":"true"}
    with open(local,"rb") as f:
        r=requests.post(url,headers=headers,data=f,timeout=180)
    r.raise_for_status()
    return f"{SUPABASE_URL}/storage/v1/object/public/rina-video-results/{remote_path}"

def main():
    now=datetime.now(timezone.utc)
    theme, theme_hint = TOPICS[now.timetuple().tm_yday % len(TOPICS)]
    seed=now.strftime("%Y-%m-%d")
    last_error=None
    for attempt in range(3):
        try:
            plan=groq_plan(theme_hint, f"{seed}-{attempt}")
            validate_plan(plan)
            break
        except Exception as exc:
            last_error=exc
            plan=None
    if not plan:
        raise RuntimeError(f"creative_plan_failed:{last_error}")

    full_text=" ".join([plan["hook"]] + [s["narration"] for s in plan["scenes"]] + [plan["cta"]])
    voice=WORK/"voice.mp3"
    make_voice(full_text,voice)
    voice_dur=duration(voice)
    if voice_dur < 45.0 or voice_dur > 60.0:
        target_voice=45.0 if voice_dur < 45.0 else 60.0
        factor=voice_dur/target_voice
        normalized=WORK/"voice_normalized.m4a"
        subprocess.run(["ffmpeg","-y","-i",str(voice),"-filter:a",f"atempo={factor:.6f}",
                        "-c:a","aac","-b:a","160k",str(normalized)],check=True,timeout=120,
                       stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        voice=normalized
        voice_dur=duration(voice)

    scene_words=[max(1,len(tokens(s["narration"]))) for s in plan["scenes"]]
    total_words=sum(scene_words)
    target=max(45.0,min(60.0,voice_dur))
    scene_durations=[target*w/total_words for w in scene_words]

    parts=[]
    evidence=[]
    for i,(scene,seconds) in enumerate(zip(plan["scenes"],scene_durations)):
        chosen,score=select_visual(scene)
        img=ASSETS/f"scene_{i+1}.jpg"
        if chosen and score >= 1:
            try:
                download(chosen["url"],img)
                evidence.append({"stage":scene["stage"],"visual_source":chosen["title"],
                                 "visual_url":chosen["url"],"alignment_score":score,
                                 "query":scene["visual_query"],"fallback":False})
            except Exception as visual_error:
                make_fallback_visual(scene,i,theme,img)
                evidence.append({"stage":scene["stage"],"visual_source":"RINA_GENERATED_MOTION_CARD",
                                 "visual_url":None,"alignment_score":1,
                                 "query":scene["visual_query"],"fallback":True,
                                 "external_error":type(visual_error).__name__})
        else:
            make_fallback_visual(scene,i,theme,img)
            evidence.append({"stage":scene["stage"],"visual_source":"RINA_GENERATED_MOTION_CARD",
                             "visual_url":None,"alignment_score":1,
                             "query":scene["visual_query"],"fallback":True})
        part=OUT/f"scene_{i+1}.mp4"
        render_scene(img,scene["caption"],seconds,i,part)
        parts.append(part)

    silent=OUT/"silent.mp4"
    concat_videos(parts,silent)
    final=OUT/"RINA_daily_cloud.mp4"
    mux_voice(silent,voice,final)
    final_dur=duration(final)
    if not (44.0 <= final_dur <= 61.0):
        raise RuntimeError(f"duration_qc_failed:{final_dur}")

    stamp=now.strftime("%Y%m%d_%H%M%S")
    remote=f"generated/rina_daily_{stamp}.mp4"
    meta_remote=f"generated/rina_daily_{stamp}.json"
    manifest={
        "version":"RINA_CLOUD_GENERATOR_V1",
        "generated_at":now.isoformat(),
        "device_render":"NONE",
        "render_location":"GitHub Actions cloud runner",
        "theme":theme,"plan":plan,"evidence":evidence,
        "duration_seconds":round(final_dur,2),
        "status":"READY_FOR_REVIEW",
        "storage_path":remote
    }
    video_url=upload_supabase(final,remote,"video/mp4")
    meta=WORK/"manifest.json"
    meta.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    upload_supabase(meta,meta_remote,"application/json")
    print(json.dumps({"status":"READY_FOR_REVIEW","video_url":video_url,
                      "manifest":manifest},ensure_ascii=False))

if __name__=="__main__":
    main()
