import os, uuid, tempfile
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
import requests

SUPABASE_URL=os.environ.get("SUPABASE_URL","").rstrip("/")
SUPABASE_KEY=os.environ.get("SUPABASE_SERVICE_ROLE_KEY","")
INPUT_BUCKET=os.environ.get("VIDEO_INPUT_BUCKET","rina-video-inputs")
RESULT_BUCKET=os.environ.get("VIDEO_RESULT_BUCKET","rina-video-results")
JOBS_TABLE=os.environ.get("VIDEO_JOBS_TABLE","video_jobs")
MAX_UPLOAD=int(os.environ.get("VIDEO_MAX_UPLOAD_BYTES","262144000"))

app=FastAPI(title="RINA Video Cloud",version="1.1.0")

def sb_headers():
    return {"apikey":SUPABASE_KEY,"Authorization":f"Bearer {SUPABASE_KEY}"}

def sb_upload(bucket,path,data,content_type="video/mp4"):
    url=f"{SUPABASE_URL}/storage/v1/object/{bucket}/{path}"
    h={**sb_headers(),"Content-Type":content_type,"x-upsert":"false"}
    if hasattr(data,"read"):
        r=requests.post(url,headers=h,data=data,timeout=900)
    else:
        r=requests.post(url,headers=h,data=data,timeout=900)
    r.raise_for_status()

def sb_insert(row):
    url=f"{SUPABASE_URL}/rest/v1/{JOBS_TABLE}"
    h={**sb_headers(),"Content-Type":"application/json","Prefer":"return=representation"}
    r=requests.post(url,headers=h,json=row,timeout=30)
    r.raise_for_status()
    return r.json()[0]

def sb_get(job_id):
    url=f"{SUPABASE_URL}/rest/v1/{JOBS_TABLE}"
    r=requests.get(url,headers=sb_headers(),
                   params={"id":f"eq.{job_id}","select":"*"},timeout=20)
    r.raise_for_status()
    rows=r.json()
    return rows[0] if rows else None

@app.get("/health")
def health():
    return {"status":"OK","service":"RINA Video Cloud","version":"1.1.0"}

@app.post("/video/edit")
async def create_video_job(request: Request):
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(503,"Cloud storage belum dikonfigurasi")
    length=request.headers.get("content-length")
    if length and int(length)>MAX_UPLOAD:
        raise HTTPException(413,"Video terlalu besar")
    job_id="rvcloud_"+uuid.uuid4().hex[:12]
    input_path=f"{job_id}/input.mp4"
    temp_name=None
    total=0
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp4",delete=False) as tmp:
            temp_name=tmp.name
            async for chunk in request.stream():
                total += len(chunk)
                if total>MAX_UPLOAD:
                    raise HTTPException(413,"Video terlalu besar")
                tmp.write(chunk)
        if total==0:
            raise HTTPException(400,"Video kosong")
        with open(temp_name,"rb") as fh:
            sb_upload(INPUT_BUCKET,input_path,fh)
        sb_insert({"id":job_id,"status":"QUEUED","stage":"QUEUED",
                   "progress":5,"input_path":input_path,
                   "output_path":None,"error":None})
        return JSONResponse({"status":"QUEUED","job_id":job_id,
                             "stage":"QUEUED","progress":5,
                             "status_url":f"/video/edit/status/{job_id}",
                             "result_url":f"/video/edit/result/{job_id}"},status_code=202)
    finally:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)

@app.get("/video/edit/status/{job_id}")
def video_status(job_id:str):
    row=sb_get(job_id)
    if not row:
        raise HTTPException(404,"Job tidak ditemukan")
    return row

@app.get("/video/edit/result/{job_id}")
def video_result(job_id:str):
    row=sb_get(job_id)
    if not row:
        raise HTTPException(404,"Job tidak ditemukan")
    if row.get("status")!="READY" or not row.get("output_path"):
        raise HTTPException(409,"Hasil belum siap")
    url=f"{SUPABASE_URL}/storage/v1/object/{RESULT_BUCKET}/{row['output_path']}"
    upstream=requests.get(url,headers=sb_headers(),stream=True,timeout=900)
    if upstream.status_code != 200:
        raise HTTPException(502,"Hasil video tidak dapat diambil dari storage")
    headers={"Content-Disposition":f'attachment; filename="RINA_{job_id}.mp4"'}
    return StreamingResponse(upstream.iter_content(1024*1024),
                             headers=headers,media_type="video/mp4")

def worker_once():
    from .worker import process_one
    return process_one()

if __name__=="__main__":
    import uvicorn
    uvicorn.run(app,host="0.0.0.0",port=int(os.environ.get("PORT","8000")))
