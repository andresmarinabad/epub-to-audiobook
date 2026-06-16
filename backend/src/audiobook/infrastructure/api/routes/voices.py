"""Route for listing available Edge TTS voices."""
from fastapi import APIRouter, Depends

from ..auth import require_api_key
from ..deps import get_tts_engine
from ..schemas import VoiceItem

router = APIRouter(prefix="/api/voices", tags=["voices"])


@router.get("", response_model=list[VoiceItem], dependencies=[Depends(require_api_key)])
async def list_voices() -> list[VoiceItem]:
    """Return all Edge TTS voices, sorted by locale then name."""
    engine = get_tts_engine()
    voices = await engine.list_voices()
    return sorted(
        [VoiceItem(**v) for v in voices],
        key=lambda v: (v.locale, v.short_name),
    )
