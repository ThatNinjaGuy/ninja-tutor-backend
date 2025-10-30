"""
Ninja Tutor Backend API
FastAPI application with Firebase integration
"""
import os
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn

from app.core.config import settings
from app.core.firebase_config import initialize_firebase
from app.core.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from app.api.v1.router import api_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info("🚀 Starting Ninja Tutor Backend...")
    logger.debug(f"Debug mode: {settings.DEBUG}")
    logger.debug(f"Log level: {settings.LOG_LEVEL}")
    
    initialize_firebase()
    logger.info("✅ Firebase initialized")
    
    # Create upload directory
    os.makedirs("uploads", exist_ok=True)
    logger.info("✅ Upload directory ready")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Ninja Tutor Backend...")


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

# Security middleware (order matters - these run first)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, calls=100, period=60)  # 100 requests per minute

# CORS middleware - environment-based configuration
allowed_origins = [
    "http://localhost:3000",  # Flutter web dev server
    "http://127.0.0.1:3000",  # Alternative localhost
    "http://localhost:8080",  # Alternative Flutter port
    "http://127.0.0.1:8080",  # Alternative localhost
    "ninja-tutor-44dec.web.app",
    "www.thatninjaguy.in",
    "thatninjaguy.in",
]

# Add Firebase Hosting URLs for production (supports comma-separated domains)
firebase_urls = os.getenv("FIREBASE_HOSTING_URL", "")
if firebase_urls:
    # Split by comma to support multiple domains
    urls = [url.strip() for url in firebase_urls.split(",")]
    for firebase_url in urls:
        # Handle both with and without protocol prefix
        if firebase_url.startswith("https://"):
            url_without_protocol = firebase_url[8:]  # Remove "https://"
            allowed_origins.append(f"https://{url_without_protocol}")
            allowed_origins.append(f"http://{url_without_protocol}")
        elif firebase_url.startswith("http://"):
            url_without_protocol = firebase_url[7:]  # Remove "http://"
            allowed_origins.append(f"https://{url_without_protocol}")
            allowed_origins.append(f"http://{url_without_protocol}")
        else:
            # No protocol prefix
            allowed_origins.append(f"https://{firebase_url}")
            allowed_origins.append(f"http://{firebase_url}")
    logger.info(f"Added Firebase Hosting URLs to CORS: {firebase_urls}")

# In production, don't use wildcard
if settings.DEBUG:
    logger.warning("⚠️  CORS wildcard enabled - DEBUG mode. Disable in production!")
    allowed_origins.append("*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Static files for uploaded content
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# API routes (must be before PDF.js to catch API routes)
app.include_router(api_router, prefix="/api/v1")

# PDF.js viewer - mount static files
pdfjs_dir = os.path.join(os.path.dirname(__file__), "pdfjs")
if os.path.exists(pdfjs_dir):
    app.mount("/pdfjs", StaticFiles(directory=pdfjs_dir, html=True), name="pdfjs")
    logger.info("✅ PDF.js viewer mounted at /pdfjs")

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Ninja Tutor Backend is running"}


if __name__ == "__main__":
    # Read PORT from environment (Cloud Run sets this)
    port = int(os.getenv("PORT", settings.PORT))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=settings.DEBUG,
        log_level="info",
        access_log=True,
        log_config=None  # Use our custom logging config
    )
