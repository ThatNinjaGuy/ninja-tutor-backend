"""
Firebase configuration and initialization
"""
import json
import firebase_admin
from firebase_admin import credentials, firestore, storage
from .config import settings


def get_firebase_credentials() -> dict:
    """Get Firebase credentials from environment variables"""
    return {
        "type": "service_account",
        "project_id": settings.FIREBASE_PROJECT_ID,
        "private_key_id": settings.FIREBASE_PRIVATE_KEY_ID,
        "private_key": settings.FIREBASE_PRIVATE_KEY.replace('\\n', '\n'),
        "client_email": settings.FIREBASE_CLIENT_EMAIL,
        "client_id": settings.FIREBASE_CLIENT_ID,
        "auth_uri": settings.FIREBASE_AUTH_URI,
        "token_uri": settings.FIREBASE_TOKEN_URI,
        "auth_provider_x509_cert_url": f"https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{settings.FIREBASE_CLIENT_EMAIL}"
    }


def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    try:
        # Check if Firebase credentials are configured
        if not settings.FIREBASE_PROJECT_ID:
            print("⚠️  Firebase credentials not configured. Skipping Firebase initialization.")
            print("⚠️  Set environment variables to enable Firebase features.")
            return
            
        if not firebase_admin._apps:
            cred_dict = get_firebase_credentials()
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred, {
                'storageBucket': 'ninja-tutor-44dec.firebasestorage.app'
            })
        print("✅ Firebase initialized successfully")
    except Exception as e:
        print(f"❌ Firebase initialization error: {e}")
        print("❌ Firebase features will not be available. Configure environment variables to fix.")
        # Don't raise - allow app to start without Firebase


def get_db():
    """Get Firestore database instance"""
    try:
        return firestore.client()
    except ValueError:
        print("❌ Firebase not initialized. Cannot access Firestore.")
        raise RuntimeError("Firebase not configured. Please set environment variables.")


def get_storage():
    """Get Firebase Storage bucket instance"""
    try:
        return storage.bucket()
    except ValueError:
        print("❌ Firebase not initialized. Cannot access Storage.")
        raise RuntimeError("Firebase not configured. Please set environment variables.")
