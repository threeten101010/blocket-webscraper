# Base image
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed for Playwright browser execution
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser executables and system libraries for Chromium
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy scraper code
COPY . .

# Run the crawler continuously
CMD ["python3", "main.py", "--continuous"]
