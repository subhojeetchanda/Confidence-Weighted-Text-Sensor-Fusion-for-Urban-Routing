FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
# Note: we copy the Dataset, Model, and App directories to ensure 
# the database and models are available if needed.
COPY . .

WORKDIR /app/App

# Run the FastAPI server (uses the PORT environment variable if set by Railway, otherwise 8000)
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
