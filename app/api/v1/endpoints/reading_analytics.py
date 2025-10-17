"""
Reading Analytics API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime
import uuid

from app.models.reading_analytics import PageTimeTracking, Highlight, ReadingSession
from app.api.v1.endpoints.auth import get_current_user
from app.core.firebase_config import get_db, initialize_firebase

router = APIRouter()


@router.post("/page-time")
async def save_page_time(
    page_number: int,
    time_spent_seconds: int,
    active_time_seconds: int,
    book_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """Save time spent on a specific page"""
    
    initialize_firebase()
    db = get_db()
    user_id = current_user_id
    
    # Create page time tracking document
    tracking_id = f"{user_id}_{book_id}_{page_number}"
    tracking_ref = db.collection("page_time_tracking").document(tracking_id)
    
    # Check if tracking exists
    existing_doc = tracking_ref.get()
    
    if existing_doc.exists:
        # Update existing tracking
        existing_data = existing_doc.to_dict()
        tracking_ref.update({
            "time_spent_seconds": existing_data.get("time_spent_seconds", 0) + time_spent_seconds,
            "active_time_seconds": existing_data.get("active_time_seconds", 0) + active_time_seconds,
            "timestamp": datetime.utcnow()
        })
    else:
        # Create new tracking
        tracking = PageTimeTracking(
            id=tracking_id,
            user_id=user_id,
            book_id=book_id,
            page_number=page_number,
            time_spent_seconds=time_spent_seconds,
            active_time_seconds=active_time_seconds
        )
        tracking_ref.set(tracking.dict())
    
    return {"message": "Page time saved successfully"}


@router.post("/highlights")
async def save_highlight(
    page_number: int,
    text: str,
    color: str,
    position_data: Optional[str],
    book_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """Save a user highlight"""
    
    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Highlight text cannot be empty"
        )
    
    initialize_firebase()
    db = get_db()
    user_id = current_user_id
    
    # Create highlight
    highlight_id = str(uuid.uuid4())
    highlight = Highlight(
        id=highlight_id,
        user_id=user_id,
        book_id=book_id,
        page_number=page_number,
        text=text.strip(),
        color=color or "yellow",
        position_data=position_data
    )
    
    # Save to Firebase
    db.collection("highlights").document(highlight_id).set(highlight.dict())
    
    return {
        "message": "Highlight saved successfully",
        "highlight_id": highlight_id
    }


@router.get("/highlights/{book_id}")
async def get_highlights(
    book_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """Get all highlights for a specific book"""
    
    initialize_firebase()
    db = get_db()
    user_id = current_user_id
    
    # Query highlights
    highlights_ref = db.collection("highlights").where("user_id", "==", user_id).where("book_id", "==", book_id)
    highlights_docs = highlights_ref.stream()
    
    highlights = []
    for doc in highlights_docs:
        highlight_data = doc.to_dict()
        highlights.append({
            "id": highlight_data.get("id"),
            "page_number": highlight_data.get("page_number"),
            "text": highlight_data.get("text"),
            "color": highlight_data.get("color"),
            "position_data": highlight_data.get("position_data"),
            "created_at": highlight_data.get("created_at").isoformat() if highlight_data.get("created_at") else None
        })
    
    # Sort by page number
    highlights.sort(key=lambda x: x["page_number"])
    
    return {"highlights": highlights}


@router.delete("/highlights/{highlight_id}")
async def delete_highlight(
    highlight_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """Delete a highlight"""
    
    initialize_firebase()
    db = get_db()
    user_id = current_user_id
    
    # Get highlight
    highlight_ref = db.collection("highlights").document(highlight_id)
    highlight_doc = highlight_ref.get()
    
    if not highlight_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Highlight not found"
        )
    
    # Verify ownership
    highlight_data = highlight_doc.to_dict()
    if highlight_data.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this highlight"
        )
    
    # Delete highlight
    highlight_ref.delete()
    
    return {"message": "Highlight deleted successfully"}


@router.post("/reading-session")
async def start_reading_session(
    book_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """Start a new reading session"""
    
    initialize_firebase()
    db = get_db()
    user_id = current_user_id
    
    # Check if there's an active session
    active_sessions = db.collection("reading_sessions").where("user_id", "==", user_id).where("book_id", "==", book_id).where("end_time", "==", None).stream()
    
    for doc in active_sessions:
        return {"message": "Reading session already active", "session_id": doc.id}
    
    # Create new session
    session_id = str(uuid.uuid4())
    session = ReadingSession(
        id=session_id,
        user_id=user_id,
        book_id=book_id,
        start_time=datetime.utcnow()
    )
    
    db.collection("reading_sessions").document(session_id).set(session.dict())
    
    return {
        "message": "Reading session started",
        "session_id": session_id
    }


@router.put("/reading-session/{session_id}")
async def end_reading_session(
    session_id: str,
    total_pages_read: int,
    total_time_seconds: int,
    active_time_seconds: int,
    current_user_id: str = Depends(get_current_user)
):
    """End a reading session"""
    
    initialize_firebase()
    db = get_db()
    user_id = current_user_id
    
    # Get session
    session_ref = db.collection("reading_sessions").document(session_id)
    session_doc = session_ref.get()
    
    if not session_doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reading session not found"
        )
    
    # Verify ownership
    session_data = session_doc.to_dict()
    if session_data.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this session"
        )
    
    if session_data.get("end_time") is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reading session already ended"
        )
    
    # Update session
    session_ref.update({
        "end_time": datetime.utcnow(),
        "total_pages_read": total_pages_read,
        "total_time_seconds": total_time_seconds,
        "active_time_seconds": active_time_seconds
    })
    
    return {"message": "Reading session ended successfully"}


@router.get("/analytics/{book_id}")
async def get_reading_analytics(
    book_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """Get reading analytics for a book"""
    
    initialize_firebase()
    db = get_db()
    user_id = current_user_id
    
    # Get page time tracking
    page_times_ref = db.collection("page_time_tracking").where("user_id", "==", user_id).where("book_id", "==", book_id)
    page_times_docs = page_times_ref.stream()
    
    page_times = []
    total_time = 0
    total_active_time = 0
    
    for doc in page_times_docs:
        pt_data = doc.to_dict()
        page_times.append({
            "page_number": pt_data.get("page_number"),
            "time_spent_seconds": pt_data.get("time_spent_seconds"),
            "active_time_seconds": pt_data.get("active_time_seconds"),
            "timestamp": pt_data.get("timestamp").isoformat() if pt_data.get("timestamp") else None
        })
        total_time += pt_data.get("time_spent_seconds", 0)
        total_active_time += pt_data.get("active_time_seconds", 0)
    
    # Get highlights
    highlights_ref = db.collection("highlights").where("user_id", "==", user_id).where("book_id", "==", book_id)
    highlights_docs = highlights_ref.stream()
    
    highlights = []
    for doc in highlights_docs:
        h_data = doc.to_dict()
        highlights.append({
            "id": h_data.get("id"),
            "page_number": h_data.get("page_number"),
            "text": h_data.get("text"),
            "color": h_data.get("color"),
            "created_at": h_data.get("created_at").isoformat() if h_data.get("created_at") else None
        })
    
    # Get reading sessions
    sessions_ref = db.collection("reading_sessions").where("user_id", "==", user_id).where("book_id", "==", book_id)
    sessions_docs = sessions_ref.stream()
    
    total_sessions = sum(1 for _ in sessions_docs)
    
    return {
        "book_id": book_id,
        "total_pages_with_time": len(page_times),
        "total_highlights": len(highlights),
        "total_sessions": total_sessions,
        "total_time_seconds": total_time,
        "total_active_time_seconds": total_active_time,
        "page_times": page_times,
        "highlights": highlights
    }