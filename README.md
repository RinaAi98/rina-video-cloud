# RINA Video Cloud

Cloud video clipping pipeline for RINA AI. The APK uploads a source video, the API stores it in private Supabase Storage, a free GitHub Actions runner processes one queued job, and the APK downloads the private result through the API.

## Zero-cost architecture

1. RINA APK -> POST /video/edit
2. API -> private Supabase bucket rina-video-inputs
3. API -> public.video_jobs status QUEUED
4. GitHub Actions -> polls every 5 minutes and processes one queued job
5. FFmpeg + RINA pipeline -> clip, render, QC
6. Worker -> private bucket rina-video-results
7. APK -> GET /video/edit/status/{job_id}
8. APK -> GET /video/edit/result/{job_id}

The worker is not a Render Background Worker. Standard GitHub-hosted runners are free for public repositories. Scheduled workflows have a minimum interval of 5 minutes.

## Required GitHub repository secrets

- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY
- GROQ_API_KEY (optional; without it, the pipeline can use visual fallback)

Never put any secret in source code or the APK.

## Supabase

Required private buckets:
- rina-video-inputs
- rina-video-results

Required table:
- public.video_jobs

The API and worker use the Supabase service-role key server-side only.

## Local checks

python3 -m py_compile app/*.py rina_video/*.py

python3 -c "from app.api import app; from app.worker_once import process_one; from rina_video.video_pipeline_v2 import VideoPipelineV2; print('OK')"

FFmpeg is installed by the GitHub Actions worker and by the Docker image.

## Limits for the free phase

The API default upload limit is 250 MB. Processing is one job per scheduled runner to keep the system simple and prevent concurrent heavy renders.

This service does not perform TikTok posting and does not touch RINA trading.
