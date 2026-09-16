import asyncio
import os
import shlex
import signal
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse


ROOT = Path(__file__).parent
MEDIA_DIR = Path(os.getenv("MEDIA_DIR", ROOT)).resolve()
PLAYLIST = Path(os.getenv("PLAYLIST", "media/playlist.m3u"))
if not PLAYLIST.is_absolute():
    PLAYLIST = (ROOT / PLAYLIST).resolve()


class Broadcaster:
    def __init__(self) -> None:
        self.ffmpeg = os.getenv("FFMPEG_BIN", "ffmpeg")
        self.bitrate = os.getenv("BITRATE", "128k")
        self.source = "offline"
        self.current_file: str | None = None
        self.started_at: float | None = None
        self._task: asyncio.Task | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._clients: set[asyncio.Queue[bytes]] = set()
        self._lock = asyncio.Lock()

    async def start(self, source: str) -> None:
        if source not in {"playlist", "mic", "offline"}:
            raise ValueError("source must be playlist, mic, or offline")
        async with self._lock:
            await self._stop_locked()
            self.source = source
            self.current_file = None
            if source != "offline":
                self._task = asyncio.create_task(self._run(source))

    async def stop(self) -> None:
        async with self._lock:
            await self._stop_locked()

    async def _stop_locked(self) -> None:
        if self._task and self._task is not asyncio.current_task():
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
        self._task = None
        if self._process:
            self._process.terminate()
            with suppress(ProcessLookupError, asyncio.TimeoutError):
                await asyncio.wait_for(self._process.wait(), 2)
            if self._process.returncode is None:
                self._process.kill()
        self._process = None
        self.source = "offline"
        self.current_file = None

    async def _run(self, source: str) -> None:
        try:
            if source == "mic":
                await self._run_mic()
            else:
                await self._run_playlist()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"broadcast stopped: {exc}", flush=True)
        finally:
            self._process = None
            if self.source == source:
                self.source = "offline"
                self.current_file = None

    async def _run_mic(self) -> None:
        device = os.getenv("MIC_DEVICE", "")
        if not device:
            raise RuntimeError("MIC_DEVICE is not configured")
        args = [
            self.ffmpeg, "-hide_banner", "-loglevel", "warning",
            "-f", "dshow", "-i", f"audio={device}",
            "-ac", "2", "-ar", "44100", "-c:a", "libmp3lame",
            "-b:a", self.bitrate, "-f", "mp3", "pipe:1",
        ]
        await self._pipe_ffmpeg(args)

    async def _run_playlist(self) -> None:
        while True:
            tracks = self._read_playlist()
            if not tracks:
                raise RuntimeError(f"playlist is empty: {PLAYLIST}")
            for track in tracks:
                if self.source != "playlist":
                    return
                self.current_file = str(track)
                args = [
                    self.ffmpeg, "-hide_banner", "-loglevel", "warning", "-re",
                    "-i", str(track), "-vn", "-sn", "-dn", "-ac", "2",
                    "-ar", "44100", "-c:a", "libmp3lame", "-b:a", self.bitrate,
                    "-f", "mp3", "pipe:1",
                ]
                await self._pipe_ffmpeg(args)

    def _read_playlist(self) -> list[Path]:
        if not PLAYLIST.exists():
            return []
        tracks: list[Path] = []
        for line in PLAYLIST.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            track = Path(line)
            if not track.is_absolute():
                track = (MEDIA_DIR / track).resolve()
            if track.exists() and track.is_file():
                tracks.append(track)
        return tracks

    async def _pipe_ffmpeg(self, args: list[str]) -> None:
        self._process = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        assert self._process.stdout is not None
        while chunk := await self._process.stdout.read(16 * 1024):
            for client in tuple(self._clients):
                if client.full():
                    with suppress(asyncio.QueueEmpty):
                        client.get_nowait()
                with suppress(asyncio.QueueFull):
                    client.put_nowait(chunk)
        await self._process.wait()
        self._process = None

    def subscribe(self) -> asyncio.Queue[bytes]:
        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=64)
        self._clients.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[bytes]) -> None:
        self._clients.discard(queue)

    def status(self) -> dict:
        return {
            "source": self.source,
            "current_file": self.current_file,
            "listeners": len(self._clients),
            "encoding": {"format": "mp3", "bitrate": self.bitrate},
        }


broadcaster = Broadcaster()


def check_admin(token: str | None) -> None:
    expected = os.getenv("ADMIN_TOKEN", "")
    if not expected or token != expected:
        raise HTTPException(status_code=401, detail="admin token required")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await broadcaster.start(os.getenv("SOURCE", "playlist"))
    yield
    await broadcaster.stop()


app = FastAPI(title="MiStation", version="0.1.0", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return """<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'><title>MiStation</title>
    <style>body{font:16px system-ui;max-width:680px;margin:12vh auto;padding:24px;background:#171714;color:#f0eee7}button{padding:14px 20px;background:#d7f04b;border:0;font-weight:700}#state{color:#d7f04b}</style></head>
    <body><h1>MiStation</h1><p id='state'>Checking broadcast…</p><button id='toggle'>LISTEN LIVE</button><audio id='audio' preload='none' src='/live.mp3'></audio>
    <script>const a=document.querySelector('audio'),b=document.querySelector('button'),s=document.querySelector('#state');b.onclick=async()=>{if(a.paused){try{await a.play();b.textContent='PAUSE';}catch(e){s.textContent='Stream unavailable';}}else{a.pause();b.textContent='LISTEN LIVE';}};async function poll(){try{const x=await fetch('/api/status');const d=await x.json();s.textContent=d.source==='offline'?'OFF AIR':`ON AIR · ${d.source} · ${d.listeners} listener(s)`;}catch(e){s.textContent='OFFLINE';}}poll();setInterval(poll,5000);</script></body></html>"""


@app.get("/healthz")
async def health() -> dict:
    return {"ok": True, **broadcaster.status()}


@app.get("/api/status")
async def status() -> dict:
    return broadcaster.status()


@app.get("/live.mp3")
async def live(request: Request) -> StreamingResponse:
    queue = broadcaster.subscribe()

    async def stream() -> AsyncGenerator[bytes, None]:
        try:
            while not await request.is_disconnected():
                yield await queue.get()
        finally:
            broadcaster.unsubscribe(queue)

    return StreamingResponse(stream(), media_type="audio/mpeg", headers={"Cache-Control": "no-store"})


@app.post("/api/source/{source}")
async def switch_source(source: str, x_admin_token: str | None = Header(default=None)) -> dict:
    check_admin(x_admin_token)
    try:
        await broadcaster.start(source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return broadcaster.status()
