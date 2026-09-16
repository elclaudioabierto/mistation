# MiStation

An open-source internet radio server built around FastAPI and FFmpeg. It does not require Icecast or Liquidsoap.

## Run locally

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app:app --reload
```

Put audio files in `media/` and list them in `media/playlist.m3u`, then open <http://127.0.0.1:8080/>. The stream is available at `/live.mp3` for VLC, browser audio players, and other standard clients.

Set `MIC_DEVICE` and use `POST /api/source/mic` with the `X-Admin-Token` header to switch to a Windows DirectShow microphone. Use `POST /api/source/playlist` to return to the playlist or `/api/source/offline` to stop.

FFmpeg is intentionally an external runtime dependency. It handles device capture and MP3 encoding; FastAPI handles scheduling, fan-out, HTTP streaming, status, and source control.

## Docker

```powershell
docker build -t mistation .
docker run --rm -p 8080:8080 -v "${PWD}/media:/app/media" --env-file .env mistation
```
