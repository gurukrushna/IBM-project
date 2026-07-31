# Use lightweight official Python image
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Prevent Python from writing .pyc files and enable live log output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend file and frontend directory into container
COPY backend.py ./
COPY frontend/ ./frontend/

# Expose port 8080 for web traffic
EXPOSE 8080

# Run Uvicorn server referencing backend.py
CMD ["uvicorn", "backend:app", "--host", "0.0.0.0", "--port", "8080"]