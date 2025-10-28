"""
Notes management endpoints
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
import uuid
from datetime import datetime
import sys

from ....models.note import Note, NoteCreate, NoteUpdate, NoteResponse, NoteCardResponse
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
        
        print(f"\n✏️  POST /notes - Creating new note")
        print(f"👤 User ID: {current_user_id}")
        print(f"📚 Book ID: {note_data.book_id}")
        print(f"📝 Type: {note_data.type}")
        print(f"📄 Page: {note_data.position.page if note_data.position else 'N/A'}")
        print(f"💬 Content: {note_data.content[:50]}...")
        
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
            created_at=datetime.now(),
            selected_text=note_data.selected_text  # Store selected text from PDF
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
        
        print(f"💾 Saving to Firestore collection: notes, document ID: {note_id}")
        db.collection('notes').document(note_id).set(note_dict)
        print(f"✅ Note saved successfully")
        
        return NoteResponse(
            id=note.id,
            book_id=note.book_id,
            user_id=note.user_id,
            type=note.type,
            content=note.content,
            title=note.title,
            position=note.position,
            tags=note.tags,
            ai_insights=note.ai_insights,
            created_at=note.created_at,
            updated_at=note.updated_at,
            is_shared=note.is_shared,
            is_favorite=note.is_favorite,
            selected_text=note.selected_text  # Include selected text in response
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating note: {str(e)}")


@router.get("/all")
async def get_all_user_notes(
    current_user_id: str = Depends(get_current_user)
):
    """Get all notes for current user across all books (excludes bookmarks)"""
    sys.stderr.write("\n🌍 ========== GET /notes/all ==========\n")
    sys.stderr.write(f"👤 User ID: {current_user_id}\n")
    sys.stderr.write(f"🔍 Starting notes fetch...\n")
    sys.stderr.flush()
    
    try:
        db = get_db()
        sys.stderr.write(f"📦 Got database connection\n")
        sys.stderr.flush()
        
        # Get all notes for this user
        query = db.collection('notes').where('user_id', '==', current_user_id)
        docs = query.stream()
        
        all_docs = list(docs)
        sys.stderr.write(f"📄 Found {len(all_docs)} total documents in notes collection\n")
        sys.stderr.flush()
        
        notes = []
        skipped_bookmarks = 0
        for doc in all_docs:
            note_data = doc.to_dict()
            note_type = note_data.get('type')
            book_id = note_data.get('book_id')
            
            sys.stderr.write(f"  📝 Doc ID: {doc.id}, Book: {book_id}, Type: {note_type}, Content: {note_data.get('content', '')[:30]}...\n")
            sys.stderr.flush()
            
            # Skip bookmark-type notes (they should be in bookmarks collection)
            if note_type == 'bookmark':
                skipped_bookmarks += 1
                sys.stderr.write(f"  ⏭️  Skipping bookmark-type note\n")
                sys.stderr.flush()
                continue
            
            # Return full note response
            try:
                note_response = NoteResponse(
                    id=doc.id,
                    book_id=book_id or '',
                    user_id=note_data.get('user_id') or current_user_id,
                    type=note_type or 'text',
                    content=note_data.get('content') or '',
                    title=note_data.get('title'),
                    position=note_data.get('position'),
                    tags=note_data.get('tags', []),
                    ai_insights=note_data.get('ai_insights'),
                    created_at=note_data.get('created_at', datetime.now()),
                    updated_at=note_data.get('updated_at'),
                    is_shared=note_data.get('is_shared', False),
                    is_favorite=note_data.get('is_favorite', False),
                    selected_text=note_data.get('selected_text')  # Include selected text from PDF
                )
                notes.append(note_response)
            except Exception as note_error:
                sys.stderr.write(f"  ❌ Error creating NoteResponse for doc {doc.id}: {str(note_error)}\n")
                sys.stderr.write(f"  📋 Note data: {note_data}\n")
                sys.stderr.flush()
                continue
        
        # Sort by created_at (newest first)
        notes.sort(key=lambda x: x.created_at, reverse=True)
        
        sys.stderr.write(f"✅ Returning {len(notes)} notes (skipped {skipped_bookmarks} bookmarks)\n")
        sys.stderr.flush()
        
        # Convert to dict for response
        return [note.dict() for note in notes]
        
    except Exception as e:
        sys.stderr.write(f"❌ Error fetching all notes: {str(e)}\n")
        sys.stderr.flush()
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        raise HTTPException(status_code=500, detail=f"Error fetching all notes: {str(e)}")


@router.get("/favorites", response_model=List[NoteCardResponse])
async def get_favorite_notes(
    current_user_id: str = Depends(get_current_user)
):
    """Get all favorite notes for current user"""
    try:
        db = get_db()
        
        # Get favorite notes for this user
        query = db.collection('notes').where('user_id', '==', current_user_id).where('is_favorite', '==', True)
        docs = query.stream()
        
        notes = []
        for doc in docs:
            note_data = doc.to_dict()
            
            note_card = NoteCardResponse(
                id=doc.id,
                book_id=note_data.get('book_id'),
                type=note_data.get('type'),
                content=note_data.get('content'),
                title=note_data.get('title'),
                page_number=note_data.get('position', {}).get('page', 0),
                tags=note_data.get('tags', []),
                is_favorite=note_data.get('is_favorite', False),
                created_at=note_data.get('created_at', datetime.now())
            )
            notes.append(note_card)
        
        # Sort by created_at (newest first)
        notes.sort(key=lambda x: x.created_at, reverse=True)
        
        return notes
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching favorite notes: {str(e)}")


@router.get("/book/{book_id}", response_model=List[NoteResponse])
async def get_notes_for_book(
    book_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """Get all notes for a specific book (excludes bookmarks - they're in separate collection)"""
    try:
        print(f"\n📚 GET /notes/book/{book_id}")
        print(f"👤 User ID: {current_user_id}")
        
        db = get_db()
        
        # Get user's notes for this book, excluding bookmark type
        query = db.collection('notes').where('book_id', '==', book_id).where('user_id', '==', current_user_id)
        docs = query.stream()
        
        all_docs = list(docs)
        print(f"📄 Found {len(all_docs)} total documents in notes collection")
        
        notes = []
        skipped_bookmarks = 0
        for doc in all_docs:
            note_data = doc.to_dict()
            note_type = note_data.get('type')
            
            print(f"  📝 Doc ID: {doc.id}, Type: {note_type}, Content: {note_data.get('content', '')[:50]}...")
            
            # Skip bookmark-type notes (they should be in bookmarks collection)
            if note_type == 'bookmark':
                skipped_bookmarks += 1
                print(f"  ⏭️  Skipping bookmark-type note")
                continue
            
            note_response = NoteResponse(
                id=doc.id,
                book_id=note_data.get('book_id'),
                user_id=note_data.get('user_id'),
                type=note_type,
                content=note_data.get('content'),
                title=note_data.get('title'),
                position=note_data.get('position'),
                tags=note_data.get('tags', []),
                ai_insights=note_data.get('ai_insights'),
                created_at=note_data.get('created_at'),
                updated_at=note_data.get('updated_at'),
                is_shared=note_data.get('is_shared', False),
                is_favorite=note_data.get('is_favorite', False),
                selected_text=note_data.get('selected_text')  # Include selected text from PDF
            )
            notes.append(note_response)
        
        print(f"✅ Returning {len(notes)} notes (skipped {skipped_bookmarks} bookmarks)")
        return notes
        
    except Exception as e:
        print(f"❌ Error fetching notes: {str(e)}")
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
            is_shared=note_data.get('is_shared', False),
            selected_text=note_data.get('selected_text')  # Include selected text from PDF
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
            is_shared=updated_data.get('is_shared', False),
            selected_text=updated_data.get('selected_text')  # Include selected text from PDF
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
                is_shared=note_data.get('is_shared', False),
                is_favorite=note_data.get('is_favorite', False),
                selected_text=note_data.get('selected_text')  # Include selected text from PDF
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


@router.put("/{note_id}/favorite")
async def toggle_favorite(
    note_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """Toggle favorite status of a note"""
    try:
        db = get_db()
        
        # Get note document
        note_doc = db.collection('notes').document(note_id).get()
        if not note_doc.exists:
            raise HTTPException(status_code=404, detail="Note not found")
        
        note_data = note_doc.to_dict()
        
        # Verify ownership
        if note_data.get('user_id') != current_user_id:
            raise HTTPException(status_code=403, detail="Not authorized to modify this note")
        
        # Toggle favorite status
        current_favorite = note_data.get('is_favorite', False)
        new_favorite = not current_favorite
        
        # Update note
        db.collection('notes').document(note_id).update({
            'is_favorite': new_favorite,
            'updated_at': datetime.now()
        })
        
        return {
            "message": "Favorite status updated",
            "note_id": note_id,
            "is_favorite": new_favorite
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error toggling favorite: {str(e)}")


@router.get("/book/{book_id}/bookmarks", response_model=List[NoteResponse])
async def get_bookmarks_for_book(
    book_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """Get all bookmarks for a specific book"""
    try:
        db = get_db()
        
        # Get user's bookmarks for this book
        query = db.collection('notes')\
            .where('book_id', '==', book_id)\
            .where('user_id', '==', current_user_id)\
            .where('type', '==', 'bookmark')
        docs = query.stream()
        
        bookmarks = []
        for doc in docs:
            note_data = doc.to_dict()
            bookmark_response = NoteResponse(
                id=doc.id,
                book_id=note_data.get('book_id'),
                user_id=note_data.get('user_id'),
                type=note_data.get('type'),
                content=note_data.get('content', ''),
                title=note_data.get('title'),
                position=note_data.get('position'),
                tags=note_data.get('tags', []),
                ai_insights=note_data.get('ai_insights'),
                created_at=note_data.get('created_at'),
                updated_at=note_data.get('updated_at'),
                is_shared=note_data.get('is_shared', False),
                is_favorite=note_data.get('is_favorite', False),
                selected_text=note_data.get('selected_text')  # Include selected text from PDF
            )
            bookmarks.append(bookmark_response)
        
        # Sort by page number (from position)
        bookmarks.sort(key=lambda x: x.position.page if x.position else 0)
        
        return bookmarks
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching bookmarks: {str(e)}")


@router.get("/book/{book_id}/page/{page_number}/notes", response_model=List[NoteResponse])
async def get_notes_for_page(
    book_id: str,
    page_number: int,
    current_user_id: str = Depends(get_current_user)
):
    """Get all notes for a specific page in a book (excludes bookmarks)"""
    try:
        db = get_db()
        
        # Get user's notes for this book
        query = db.collection('notes')\
            .where('book_id', '==', book_id)\
            .where('user_id', '==', current_user_id)
        docs = query.stream()
        
        notes = []
        for doc in docs:
            note_data = doc.to_dict()
            
            # Skip bookmark-type notes
            if note_data.get('type') == 'bookmark':
                continue
            
            position = note_data.get('position')
            
            # Filter by page number
            if position and position.get('page') == page_number:
                note_response = NoteResponse(
                    id=doc.id,
                    book_id=note_data.get('book_id'),
                    user_id=note_data.get('user_id'),
                    type=note_data.get('type'),
                    content=note_data.get('content', ''),
                    title=note_data.get('title'),
                    position=note_data.get('position'),
                    tags=note_data.get('tags', []),
                    ai_insights=note_data.get('ai_insights'),
                    created_at=note_data.get('created_at'),
                    updated_at=note_data.get('updated_at'),
                    is_shared=note_data.get('is_shared', False),
                    is_favorite=note_data.get('is_favorite', False),
                    selected_text=note_data.get('selected_text')  # Include selected text from PDF
                )
                notes.append(note_response)
        
        # Sort by created_at (newest first)
        notes.sort(key=lambda x: x.created_at, reverse=True)
        
        return notes
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching page notes: {str(e)}")
