"""
Notes management endpoints
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
import uuid
from datetime import datetime

from ....models.note import Note, NoteCreate, NoteUpdate, NoteResponse
from ....services.ai_service import AIService
from ....core.firebase_config import get_db
from .auth import get_current_user

router = APIRouter()


@router.post("", response_model=NoteResponse)
async def create_note(
    note_data: NoteCreate,
    current_user_id: str = Depends(get_current_user)
):
    """Create a new note"""
    try:
        note_id = str(uuid.uuid4())
        
        # Generate AI insights if content is substantial
        ai_insights = None
        if len(note_data.content) > 50:  # Only for substantial notes
            try:
                ai_service = AIService()
                ai_insights = await ai_service.generate_ai_insights(
                    note_content=note_data.content,
                    book_context="Book context would be retrieved from book_id"
                )
            except:
                # Don't fail note creation if AI insights fail
                pass
        
        note = Note(
            id=note_id,
            book_id=note_data.book_id,
            user_id=current_user_id,
            type=note_data.type,
            content=note_data.content,
            title=note_data.title,
            position=note_data.position,
            style=note_data.style,
            tags=note_data.tags,
            ai_insights=ai_insights,
            created_at=datetime.now()
        )
        
        # Save to Firestore
        db = get_db()
        note_dict = note.dict()
        note_dict['created_at'] = note.created_at
        if note_dict['position']:
            note_dict['position'] = note.position.dict()
        if note_dict['style']:
            note_dict['style'] = note.style.dict()
        if note_dict['ai_insights']:
            note_dict['ai_insights'] = note.ai_insights.dict()
        
        db.collection('notes').document(note_id).set(note_dict)
        
        return NoteResponse(
            id=note.id,
            book_id=note.book_id,
            user_id=note.user_id,
            type=note.type.value,
            content=note.content,
            title=note.title,
            position=note.position,
            tags=note.tags,
            ai_insights=note.ai_insights,
            created_at=note.created_at,
            updated_at=note.updated_at,
            is_shared=note.is_shared
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating note: {str(e)}")


@router.get("/book/{book_id}", response_model=List[NoteResponse])
async def get_notes_for_book(
    book_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """Get all notes for a specific book"""
    try:
        db = get_db()
        
        # Get user's notes for this book
        query = db.collection('notes').where('book_id', '==', book_id).where('user_id', '==', current_user_id)
        docs = query.stream()
        
        notes = []
        for doc in docs:
            note_data = doc.to_dict()
            note_response = NoteResponse(
                id=doc.id,
                book_id=note_data.get('book_id'),
                user_id=note_data.get('user_id'),
                type=note_data.get('type'),
                content=note_data.get('content'),
                title=note_data.get('title'),
                position=note_data.get('position'),
                tags=note_data.get('tags', []),
                ai_insights=note_data.get('ai_insights'),
                created_at=note_data.get('created_at'),
                updated_at=note_data.get('updated_at'),
                is_shared=note_data.get('is_shared', False)
            )
            notes.append(note_response)
        
        return notes
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching notes: {str(e)}")


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """Get a specific note"""
    try:
        db = get_db()
        doc = db.collection('notes').document(note_id).get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Note not found")
        
        note_data = doc.to_dict()
        
        # Check if user owns this note or if it's shared
        if note_data.get('user_id') != current_user_id and not note_data.get('is_shared', False):
            raise HTTPException(status_code=403, detail="Access denied")
        
        return NoteResponse(
            id=doc.id,
            book_id=note_data.get('book_id'),
            user_id=note_data.get('user_id'),
            type=note_data.get('type'),
            content=note_data.get('content'),
            title=note_data.get('title'),
            position=note_data.get('position'),
            tags=note_data.get('tags', []),
            ai_insights=note_data.get('ai_insights'),
            created_at=note_data.get('created_at'),
            updated_at=note_data.get('updated_at'),
            is_shared=note_data.get('is_shared', False)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching note: {str(e)}")


@router.put("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: str,
    note_update: NoteUpdate,
    current_user_id: str = Depends(get_current_user)
):
    """Update a note"""
    try:
        db = get_db()
        doc = db.collection('notes').document(note_id).get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Note not found")
        
        note_data = doc.to_dict()
        
        # Check ownership
        if note_data.get('user_id') != current_user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Update fields
        update_data = {'updated_at': datetime.now()}
        
        if note_update.content is not None:
            update_data['content'] = note_update.content
        if note_update.title is not None:
            update_data['title'] = note_update.title
        if note_update.tags is not None:
            update_data['tags'] = note_update.tags
        if note_update.is_shared is not None:
            update_data['is_shared'] = note_update.is_shared
        
        # Update in Firestore
        db.collection('notes').document(note_id).update(update_data)
        
        # Get updated note
        updated_doc = db.collection('notes').document(note_id).get()
        updated_data = updated_doc.to_dict()
        
        return NoteResponse(
            id=updated_doc.id,
            book_id=updated_data.get('book_id'),
            user_id=updated_data.get('user_id'),
            type=updated_data.get('type'),
            content=updated_data.get('content'),
            title=updated_data.get('title'),
            position=updated_data.get('position'),
            tags=updated_data.get('tags', []),
            ai_insights=updated_data.get('ai_insights'),
            created_at=updated_data.get('created_at'),
            updated_at=updated_data.get('updated_at'),
            is_shared=updated_data.get('is_shared', False)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating note: {str(e)}")


@router.delete("/{note_id}")
async def delete_note(
    note_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """Delete a note"""
    try:
        db = get_db()
        doc = db.collection('notes').document(note_id).get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Note not found")
        
        note_data = doc.to_dict()
        
        # Check ownership
        if note_data.get('user_id') != current_user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Delete note
        db.collection('notes').document(note_id).delete()
        
        return {"message": "Note deleted successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting note: {str(e)}")


@router.get("/shared/{book_id}", response_model=List[NoteResponse])
async def get_shared_notes(book_id: str):
    """Get shared notes for a book"""
    try:
        db = get_db()
        
        # Get shared notes for this book
        query = db.collection('notes').where('book_id', '==', book_id).where('is_shared', '==', True)
        docs = query.stream()
        
        notes = []
        for doc in docs:
            note_data = doc.to_dict()
            note_response = NoteResponse(
                id=doc.id,
                book_id=note_data.get('book_id'),
                user_id=note_data.get('user_id'),
                type=note_data.get('type'),
                content=note_data.get('content'),
                title=note_data.get('title'),
                position=note_data.get('position'),
                tags=note_data.get('tags', []),
                ai_insights=note_data.get('ai_insights'),
                created_at=note_data.get('created_at'),
                updated_at=note_data.get('updated_at'),
                is_shared=note_data.get('is_shared', False)
            )
            notes.append(note_response)
        
        return notes
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching shared notes: {str(e)}")


@router.post("/sync")
async def sync_notes(
    notes: List[NoteCreate],
    current_user_id: str = Depends(get_current_user)
):
    """Sync multiple notes from client"""
    try:
        db = get_db()
        synced_notes = []
        
        for note_data in notes:
            note_id = str(uuid.uuid4())
            
            note = Note(
                id=note_id,
                book_id=note_data.book_id,
                user_id=current_user_id,
                type=note_data.type,
                content=note_data.content,
                title=note_data.title,
                position=note_data.position,
                style=note_data.style,
                tags=note_data.tags,
                created_at=datetime.now()
            )
            
            # Save to Firestore
            note_dict = note.dict()
            note_dict['created_at'] = note.created_at
            if note_dict['position']:
                note_dict['position'] = note.position.dict()
            if note_dict['style']:
                note_dict['style'] = note.style.dict()
            
            db.collection('notes').document(note_id).set(note_dict)
            synced_notes.append(note_id)
        
        return {"message": f"Synced {len(synced_notes)} notes", "note_ids": synced_notes}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error syncing notes: {str(e)}")
