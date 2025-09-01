"""
Ninja Tutor Backend API
FastAPI application with Firebase integration
"""
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn

from app.core.config import settings
from app.core.firebase_config import initialize_firebase
from app.api.v1.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    print("🚀 Starting Ninja Tutor Backend...")
    await initialize_firebase()
    print("✅ Firebase initialized")
    
    # Create upload directory
    os.makedirs("uploads", exist_ok=True)
    print("✅ Upload directory ready")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down Ninja Tutor Backend...")


# Create FastAPI app
app = FastAPI(
    title="Ninja Tutor API",
    description="Backend API for Ninja Tutor educational platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Ensure upload directory exists before mounting static files
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for uploaded content
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# API routes
app.include_router(api_router, prefix="/api/v1")

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Ninja Tutor Backend is running"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
