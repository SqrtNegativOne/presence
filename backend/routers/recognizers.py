"""
routers/recognizers.py — List available recognizers and switch a user's preference.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import database
from auth.dependencies import get_current_user
from services.face_service import available_recognizers

router = APIRouter(prefix="/api/recognizers", tags=["recognizers"])


class SetPreferredRequest(BaseModel):
    name: str


@router.get("")
async def list_recognizers(user: dict = Depends(get_current_user)):
    """List recognizers + which one this user has picked."""
    return {
        "recognizers": available_recognizers(),
        "preferred": user["preferred_recognizer"],
    }


@router.put("/preferred")
async def set_preferred(body: SetPreferredRequest,
                        user: dict = Depends(get_current_user)):
    known = {r["name"] for r in available_recognizers()}
    if body.name not in known:
        raise HTTPException(status_code=400, detail=f"Unknown recognizer '{body.name}'.")
    database.set_user_recognizer(user["id"], body.name)
    return {"preferred": body.name}
