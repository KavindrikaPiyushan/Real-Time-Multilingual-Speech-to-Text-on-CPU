"""FastAPI application entry point.

Run from the backend folder:  uvicorn app.main:app --port 8000
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .api.websocket import router as ws_router
from .core.config import settings
from .services.asr_service import ASRError, ASRService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("asr.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One model instance for the whole process, loaded once at startup.
    app.state.asr = ASRService(model_id=settings.model_id, num_threads=settings.torch_threads or None)
    app.state.load_error = None
    app.state.streams = {}   # stream_id -> StreamSession for every active stream
    # Limits simultaneous model inferences (see config).
    app.state.infer_slots = asyncio.Semaphore(settings.max_concurrent_inferences)
    try:
        log.info("Loading model %s on CPU ...", settings.model_id)
        await run_in_threadpool(app.state.asr.load)
        log.info("Model loaded in %.1fs", app.state.asr.load_s)
    except ASRError as exc:  # keep the server up so /api/health can report the failure
        app.state.load_error = str(exc)
        log.error("Model failed to load: %s", exc)
    yield


app = FastAPI(title="Real-time multilingual ASR (CPU)", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(router, prefix="/api")
app.include_router(ws_router)
