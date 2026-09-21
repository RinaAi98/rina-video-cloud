# RINA Video Cloud

Cloud backend for the RINA AI APK: upload -> queue -> background render -> QC -> download.

## Architecture
- FastAPI receives MP4 and stores it in Supabase Storage.
- Supabase Postgres stores durable job state.
- A separate worker polls QUEUED jobs and runs the RINA video pipeline.
- FFmpeg runs inside the container, never on the Android phone.
- Final MP4 is stored in a private Supabase Storage bucket.

## Runtime
API: uvicorn app.api:app --host 0.0.0.0 --port 8000
Worker: python -m app.worker

Required environment:
- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY
- GROQ_API_KEY
- VIDEO_INPUT_BUCKET (default rina-video-inputs)
- VIDEO_RESULT_BUCKET (default rina-video-results)
- VIDEO_JOBS_TABLE (default video_jobs)

Do not commit secrets. The service-role key stays server-side only.

## Job contract
POST /video/edit with raw video/mp4 returns HTTP 202 and a job id.
GET /video/edit/status/{job_id} returns stage/progress/status.
GET /video/edit/result/{job_id} streams the final MP4 when status is READY.

## Safety
The Android app must not receive Supabase service-role credentials.
Trading and TikTok posting are outside this service.
