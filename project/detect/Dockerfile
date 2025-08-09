FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set GDAL environment variables
ENV GDAL_CONFIG=/usr/bin/gdal-config
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set working directory
WORKDIR /app

# Copy application code
COPY main.py classical.py ml_infer.py .

# Create directories
RUN mkdir -p /app/detect/models

# Set entrypoint
ENTRYPOINT ["python", "main.py"]