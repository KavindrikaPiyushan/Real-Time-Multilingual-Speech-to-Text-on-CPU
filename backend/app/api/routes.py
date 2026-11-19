"""REST endpoints. The streaming endpoint lives in websocket.py."""
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool

from ..core.config import settings
from ..services.asr_service import ASRError
from ..services.audio_service import AudioError, load_wav

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    asr = request.app.state.asr
    return {
        "status": "ok" if asr.loaded else "model_not_loaded",
        "model_loaded": asr.loaded,
        "model_id": asr.model_id,
        "load_seconds": round(asr.load_s, 2),
        "error": request.app.state.load_error,
        "active_streams": len(request.app.state.streams),
    }


@router.get("/info")
async def info():
    return {
        "sample_rate": settings.sample_rate,
        "channels": 1,
        "encoding": "pcm_s16le",
        "languages": ["auto", *settings.languages],
        "max_concurrent_inferences": settings.max_concurrent_inferences,
    }


@router.post("/transcribe")
async def transcribe_file(request: Request, file: UploadFile = File(...),
                          language: str | None = Form(None)):
    """Whole-file transcription (not streaming). Handy for testing the model through the API."""
    asr = request.app.state.asr
    if not asr.loaded:
        raise HTTPException(503, "Model is not loaded.")
    if language in (None, "", "auto"):
        language = None
    elif language not in settings.languages:
        raise HTTPException(400, f"Unsupported language '{language}'. Use one of: auto, {', '.join(settings.languages)}.")

    raw = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File larger than {settings.max_upload_mb} MB.")
    try:
        audio, audio_info = load_wav(raw, strict=False)
    except AudioError as exc:
        raise HTTPException(400, str(exc))

    try:
        async with request.app.state.infer_slots:
            res = await run_in_threadpool(asr.transcribe, audio, language)
    except ASRError as exc:
        raise HTTPException(500, str(exc))

    return {
        "text": res.text,
        "language": res.language or language,
        "audio_seconds": round(res.audio_s, 2),
        "inference_seconds": round(res.infer_s, 2),
        "rtf": round(res.rtf, 2),
        "input_conversions": audio_info.notes,
    }
