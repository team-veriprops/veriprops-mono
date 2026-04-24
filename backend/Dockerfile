# ---- Base Python Image ----
FROM python:3.11-slim-bullseye

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VIRTUALENVS_CREATE=false

# Set working directory
WORKDIR /app

# Install system dependencies
#RUN apt-get update && apt-get install -y --no-install-recommends \
#    build-essential \
#    gcc \
#    libffi-dev \
#    libpq-dev \
#    curl \
# && apt-get clean \
# && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt && rm -rf ~/.cache/pip /root/.cache /tmp/*

# Copy the rest of the application
COPY . .

# Optional: Use a non-root user for better security
#RUN useradd --create-home appuser && chown -R appuser /app
#USER appuser

# Expose FastAPI port
EXPOSE 8000

# Run FastAPI using Uvicorn
#CMD ["uvicorn", "appodus:fastapi_app", "--host", "0.0.0.0", "--port", "8000"]
