#!/bin/bash

echo "🛑 Stopping all Python backend processes..."
pkill -9 -f "python.*run.py"
pkill -9 -f "uvicorn"
lsof -ti:8000 | xargs kill -9 2>/dev/null

sleep 2

echo "🚀 Starting backend with full logging..."
cd /Users/deadshot/Desktop/Code/ninja-tutor/ninja_tutor_backend
python run.py


