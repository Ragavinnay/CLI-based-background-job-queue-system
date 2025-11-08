FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY queuectl.py .
COPY job.json .

# Create directory for database
RUN mkdir -p /app/data

# Set environment variable for database location
ENV QUEUECTL_DB=/app/data/queuectl.db

# Make queuectl.py executable
RUN chmod +x queuectl.py

# Create data directory
RUN mkdir -p /app/data

# Default command (can be overridden)
CMD ["python", "queuectl.py", "--help"]

