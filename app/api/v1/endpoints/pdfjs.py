"""
PDF.js viewer endpoint
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
import os

router = APIRouter()


@router.get("/{file_path:path}")
async def get_pdfjs_file(file_path: str):
    """
    Serve PDF.js files without X-Frame-Options restriction.
    This allows the viewer to be embedded in iframes.
    """
    # Construct the path to the PDF.js file
    current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    pdfjs_dir = os.path.join(current_dir, "pdfjs")
    
    # Determine content type based on file extension
    if file_path.endswith('.html'):
        media_type = "text/html; charset=utf-8"
        mode = 'r'
        encoding = 'utf-8'
    elif file_path.endswith('.css'):
        media_type = "text/css"
        mode = 'r'
        encoding = 'utf-8'
    elif file_path.endswith('.js'):
        media_type = "application/javascript"
        mode = 'r'
        encoding = 'utf-8'
    else:
        media_type = "application/octet-stream"
        mode = 'rb'
        encoding = None
    
    file_full_path = os.path.join(pdfjs_dir, file_path)
    
    # Security check: ensure file is within pdfjs directory
    if not os.path.abspath(file_full_path).startswith(os.path.abspath(pdfjs_dir)):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if file exists
    if not os.path.exists(file_full_path) or not os.path.isfile(file_full_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Read file content
    with open(file_full_path, mode, encoding=encoding) as f:
        content = f.read()
    
    # Return file content with appropriate headers
    if media_type.startswith('text/') or media_type == 'application/javascript':
        return HTMLResponse(
            content=content,
            headers={
                "Content-Type": media_type,
                # No X-Frame-Options header to allow iframe embedding
            }
        )
    else:
        from fastapi.responses import Response
        return Response(
            content=content if isinstance(content, bytes) else content.encode(),
            media_type=media_type,
            headers={
                # No X-Frame-Options header to allow iframe embedding
            }
        )

