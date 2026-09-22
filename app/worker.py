import os, time, tempfile
from pathlib import Path
from urllib.parse import quote
import requests
from rina_video.video_pipeline_v2 import VideoPipelineV2

SUPABASE_URL=os.environ.get("SUPABASE_URL","").rstrip("/")
SUPABASE_KEY=os.environ.get("SUPABASE_SERVICE_ROLE_KEY","")
INPUT_BUCKET=os.environ.get("VIDEO_INPUT_BUCKET","rina-video-inputs")
RESULT_BUCKET=os.environ.get("VIDEO_RESULT_BUCKET","rina-video-results")
JOBS_TABLE=os.environ.get("VIDEO_JOBS_TABLE","video_jobs")
POLL_SECONDS=int(os.environ.get("WORKER_POLL_SECONDS","5"))

def h():
    return {"apikey":SUPABASE_KEY,"Authorization":f"Bearer {SUPABASE_KEY}"}

def get_job():
    url=f"{SUPABASE_URL}/rest/v1/{JOBS_TABLE}"
    params={"status":"eq.QUEUED","order":"created_at.asc","limit":"1","select":"*"}
    r=requests.get(url,headers=h(),params=params,timeout=20)
    r.raise_for_status()
    rows=r.json()
    return rows[0] if rows else None

def update(job_id,**fields):
    url=f"{SUPABASE_URL}/rest/v1/{JOBS_TABLE}"
    r=requests.patch(url,headers={**h(),"Content-Type":"application/json"},
                     params={"id":f"eq.{job_id}"},json=fields,timeout=30)
    r.raise_for_status()

def storage_get(bucket,path,dst):
    safe_path=quote(path.lstrip("/"),safe="/")
    url=f"{SUPABASE_URL}/storage/v1/object/{quote(bucket,safe='')}/{safe_path}"
    with requests.get(url,headers=h(),stream=True,timeout=300) as r:
        if r.status_code >= 400:
            detail=r.text[:500].replace("\\n"," ")
            raise RuntimeError(f"Storage GET {r.status_code}: {detail}")
        with open(dst,"wb") as f:
            for chunk in r.iter_content(1024*1024):
                if chunk: f.write(chunk)

def storage_put(bucket,path,src):
    safe_path=quote(path.lstrip("/"),safe="/")
    url=f"{SUPABASE_URL}/storage/v1/object/{quote(bucket,safe='')}/{safe_path}"
    with open(src,"rb") as f:
        r=requests.post(url,headers={**h(),"Content-Type":"video/mp4"},data=f,timeout=600)
    r.raise_for_status()

def process_one():
    job=get_job()
    if not job: return False
    jid=job["id"]
    # Claim using status filter so two workers cannot process the same row.
    url=f"{SUPABASE_URL}/rest/v1/{JOBS_TABLE}"
    r=requests.patch(url,headers={**h(),"Content-Type":"application/json","Prefer":"return=representation"},
                     params={"id":f"eq.{jid}","status":"eq.QUEUED"},
                     json={"status":"PROCESSING","stage":"ANALYZING","progress":15},
                     timeout=30)
    if r.status_code>=400:
        r.raise_for_status()
    claimed=r.json()
    if len(claimed)!=1:
        return False
    with tempfile.TemporaryDirectory(prefix="rina_video_") as td:
        src=Path(td)/"input.mp4"
        try:
            storage_get(INPUT_BUCKET,job["input_path"],src)
            update(jid,stage="ANALYZING",progress=25,error=None)
            pipeline=VideoPipelineV2(job_dir=Path(td)/"jobs")
            result=pipeline.run(src,jid)
            if result.get("status")!="READY":
                update(jid,status="REWORK",stage="QC_FAILED",progress=100,
                       error=result.get("error") or "QC failed")
                return True
            output=Path(result["output"])
            result_path=f"{jid}/result.mp4"
            update(jid,stage="UPLOADING",progress=95)
            storage_put(RESULT_BUCKET,result_path,output)
            update(jid,status="READY",stage="READY",progress=100,
                   output_path=result_path,error=None)
            return True
        except Exception as exc:
            update(jid,status="ERROR",stage="FAILED",progress=100,
                   error=f"{type(exc).__name__}: {exc}")
            return True

def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY wajib diisi")
    while True:
        try:
            process_one()
        except Exception as exc:
            print(f"worker error: {type(exc).__name__}: {exc}",flush=True)
        time.sleep(POLL_SECONDS)

if __name__=="__main__":
    main()
