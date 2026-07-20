FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY src/ ./src/
COPY tests/ ./tests/
COPY run_ingest.py .
COPY chat.py .

# Default command (can be overridden in docker-compose)
CMD ["python", "-m", "unittest", "tests/test_agent.py"]
