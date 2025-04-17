# Use Python as the base image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        netcat-openbsd \
        curl \
        libpq-dev \
        postgresql-client \
        libc6-dev \
        build-essential \ 
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the .env file and project code
COPY .env .
COPY . .

# Create a startup script with explicit line endings
RUN printf '#!/bin/bash\npython main.py &\ngunicorn --bind 0.0.0.0:5090 api:app\n' > /app/start.sh \
    && chmod +x /app/start.sh \
    && cat /app/start.sh  # This will print the script for debugging

# Create non-root user for security
RUN addgroup --system app && adduser --system --group app \
    && chown -R app:app /app
USER app

# Expose the port the app runs on
EXPOSE 5090

# Use bash directly to run the commands instead of the script file
CMD ["/bin/bash", "-c", "python main.py & gunicorn --bind 0.0.0.0:5090 api:app"]