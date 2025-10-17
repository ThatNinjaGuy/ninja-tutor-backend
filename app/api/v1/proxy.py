"""
PDF Proxy endpoint to handle CORS issues with Firebase Storage
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
import httpx
from typing import Optional

router = APIRouter()


@router.get("/pdf")
async def proxy_pdf(url: str = Query(..., description="URL of the PDF to proxy")):
    """
    Proxy PDF requests to avoid CORS issues with Firebase Storage.
    
    This endpoint fetches PDFs from Firebase Storage and streams them
    to the frontend with proper CORS headers.
    """
    try:
        # Validate that the URL is from Firebase Storage
        if not ('firebasestorage.app' in url or 'storage.googleapis.com' in url):
            raise HTTPException(
                status_code=400,
                detail="Only Firebase Storage URLs are allowed"
            )
        
        # Fetch the PDF from Firebase Storage
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            
            # Stream the PDF content with proper headers
            return StreamingResponse(
                iter([response.content]),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": "inline",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type",
                }
            )
    
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Failed to fetch PDF: {str(e)}"
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error connecting to Firebase Storage: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error proxying PDF: {str(e)}"
        )

