FROM python:3.11-slim

# System dependencies for Playwright / Chromium
RUN apt-get update && apt-get install -y \
    wget curl gnupg ca-certificates \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    libpango-1.0-0 libpangocairo-1.0-0 \
    fonts-liberation libappindicator3-1 \
    --no-install-recommends && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser
RUN python -m playwright install chromium --with-deps

# Copy application code
COPY . .

# Ensure output directory exists
RUN mkdir -p .tmp

EXPOSE 8501

# Streamlit config: headless server, no CORS issues
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV RUNNING_IN_CLOUD=true

# Use shell form so Railway's $PORT env var is expanded at runtime
CMD python -m streamlit run app.py --server.headless=true --server.port=${PORT:-8501} --server.address=0.0.0.0
