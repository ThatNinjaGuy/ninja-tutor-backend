"""
Bookmarks management endpoints
"""
from typing import List
from fastapi import APIRouter, HTTPException, Depends
import uuid
from datetime import datetime

from ....models.bookmark import Bookmark, BookmarkCreate, BookmarkResponse
from ....core.firebase_config import get_db
from .auth import get_current_user

router = APIRouter()


@router.post("", response_model=BookmarkResponse)
async def create_bookmark(
    bookmark_data: BookmarkCreate,
    current_user_id: str = Depends(get_current_user)
):
    """Create a new bookmark"""
    try:
        db = get_db()
        bookmark_id = str(uuid.uuid4())
        
        # Check if bookmark already exists for this page
        existing = db.collection('bookmarks')\
            .where('book_id', '==', bookmark_data.book_id)\
            .where('user_id', '==', current_user_id)\
            .where('page_number', '==', bookmark_data.page_number)\
            .limit(1)\
            .stream()
        
        existing_list = list(existing)
        if existing_list:
            raise HTTPException(status_code=400, detail="Bookmark already exists for this page")
        
        bookmark = Bookmark(
            id=bookmark_id,
            book_id=bookmark_data.book_id,
            user_id=current_user_id,
            page_number=bookmark_data.page_number,
            note=bookmark_data.note,
            created_at=datetime.now()
        )
        
        # Save to Firestore
        bookmark_dict = bookmark.dict()
        bookmark_dict['created_at'] = bookmark.created_at
        
        db.collection('bookmarks').document(bookmark_id).set(bookmark_dict)
        
        return BookmarkResponse(
            id=bookmark.id,
            book_id=bookmark.book_id,
            user_id=bookmark.user_id,
            page_number=bookmark.page_number,
            created_at=bookmark.created_at,
            note=bookmark.note
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating bookmark: {str(e)}")


@router.get("/book/{book_id}", response_model=List[BookmarkResponse])
async def get_bookmarks_for_book(
    book_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """Get all bookmarks for a specific book"""
    try:
        db = get_db()
        
        # Get user's bookmarks for this book
        query = db.collection('bookmarks')\
            .where('book_id', '==', book_id)\
            .where('user_id', '==', current_user_id)
        docs = query.stream()
        
        bookmarks = []
        for doc in docs:
            bookmark_data = doc.to_dict()
            bookmark_response = BookmarkResponse(
                id=doc.id,
                book_id=bookmark_data.get('book_id'),
                user_id=bookmark_data.get('user_id'),
                page_number=bookmark_data.get('page_number'),
                created_at=bookmark_data.get('created_at'),
                note=bookmark_data.get('note')
            )
            bookmarks.append(bookmark_response)
        
        # Sort by page number
        bookmarks.sort(key=lambda x: x.page_number)
        
        return bookmarks
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching bookmarks: {str(e)}")


@router.get("/book/{book_id}/page/{page_number}", response_model=BookmarkResponse)
async def get_bookmark_for_page(
    book_id: str,
    page_number: int,
    current_user_id: str = Depends(get_current_user)
):
    """Get bookmark for a specific page"""
    try:
        db = get_db()
        
        # Get bookmark for this page
        query = db.collection('bookmarks')\
            .where('book_id', '==', book_id)\
            .where('user_id', '==', current_user_id)\
            .where('page_number', '==', page_number)\
            .limit(1)
        docs = list(query.stream())
        
        if not docs:
            raise HTTPException(status_code=404, detail="Bookmark not found")
        
        doc = docs[0]
        bookmark_data = doc.to_dict()
        
        return BookmarkResponse(
            id=doc.id,
            book_id=bookmark_data.get('book_id'),
            user_id=bookmark_data.get('user_id'),
            page_number=bookmark_data.get('page_number'),
            created_at=bookmark_data.get('created_at'),
            note=bookmark_data.get('note')
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching bookmark: {str(e)}")


@router.delete("/{bookmark_id}")
async def delete_bookmark(
    bookmark_id: str,
    current_user_id: str = Depends(get_current_user)
):
    """Delete a bookmark"""
    try:
        db = get_db()
        doc = db.collection('bookmarks').document(bookmark_id).get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Bookmark not found")
        
        bookmark_data = doc.to_dict()
        
        # Check ownership
        if bookmark_data.get('user_id') != current_user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Delete bookmark
        db.collection('bookmarks').document(bookmark_id).delete()
        
        return {"message": "Bookmark deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting bookmark: {str(e)}")


@router.delete("/book/{book_id}/page/{page_number}")
async def delete_bookmark_by_page(
    book_id: str,
    page_number: int,
    current_user_id: str = Depends(get_current_user)
):
    """Delete bookmark for a specific page"""
    try:
        db = get_db()
        
        # Find bookmark for this page
        query = db.collection('bookmarks')\
            .where('book_id', '==', book_id)\
            .where('user_id', '==', current_user_id)\
            .where('page_number', '==', page_number)\
            .limit(1)
        docs = list(query.stream())
        
        if not docs:
            raise HTTPException(status_code=404, detail="Bookmark not found")
        
        # Delete bookmark
        db.collection('bookmarks').document(docs[0].id).delete()
        
        return {"message": "Bookmark deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting bookmark: {str(e)}")


@router.get("/all", response_model=List[BookmarkResponse])
async def get_all_user_bookmarks(
    current_user_id: str = Depends(get_current_user)
):
    """Get all bookmarks for current user across all books"""
    try:
        db = get_db()
        
        # Get all bookmarks for this user
        query = db.collection('bookmarks').where('user_id', '==', current_user_id)
        docs = query.stream()
        
        bookmarks = []
        for doc in docs:
            bookmark_data = doc.to_dict()
            bookmark_response = BookmarkResponse(
                id=doc.id,
                book_id=bookmark_data.get('book_id'),
                user_id=bookmark_data.get('user_id'),
                page_number=bookmark_data.get('page_number'),
                created_at=bookmark_data.get('created_at'),
                note=bookmark_data.get('note')
            )
            bookmarks.append(bookmark_response)
        
        # Sort by created_at (newest first)
        bookmarks.sort(key=lambda x: x.created_at, reverse=True)
        
        return bookmarks
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching all bookmarks: {str(e)}")

