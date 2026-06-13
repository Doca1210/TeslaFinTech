"""FastAPI router for the payment screening pipeline (section 5, P0 endpoints).

TODO (T-005): include this router in the unified app (app/main.py) once the
pipeline stages below are implemented, and add `GET /screen/{id}`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_session
from app.payments.pipeline import ScreeningPipeline
from app.payments.schemas import ScreeningDecision

router = APIRouter(tags=["screening"])


@router.post("/screen", response_model=ScreeningDecision)
def screen_payment(payload: dict[str, Any], db: Session = Depends(get_session)) -> ScreeningDecision:
    pipeline = ScreeningPipeline(db)
    return pipeline.screen(payload)
