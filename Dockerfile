# Dockerfile for OmniScrape AI
FROM python:3.12-slim

# Prevent Python from buffering stdout/stderr and prevent apt prompts
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies and Google Chrome Stable
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    gnupg \
    unzip \
    ca-certificates \
    fonts-liberation \
    libasound2t64 \
    libnss3 \
    libxss1 \
    libappindicator3-1 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Verify Chrome installation
RUN google-chrome --version

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Create volume mount points for database, run outputs, and screenshots
RUN mkdir -p /app/data /app/outputs /app/screenshots

# Expose ports for Streamlit (8501) and FastAPI (8000)
EXPOSE 8501 8000

# Default command launches the Streamlit UI
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
