# Use Python 3.9 slim image as base
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    libfreetype6-dev \
    pkg-config \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Install fonts
RUN mkdir -p /usr/share/fonts/truetype/custom
COPY static/fonts/*.ttf /usr/share/fonts/truetype/custom/
RUN fc-cache -f -v

# Create required directories
RUN mkdir -p uploads temp public/dxf_template

# Set environment variables
ENV FLASK_APP=app.py
ENV PORT=8080
ENV HOST=0.0.0.0

# Expose port
EXPOSE 8080

# Command to run the application
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 0 app:app