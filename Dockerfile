FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY bot.py .

# Create data directory inside container
RUN mkdir -p /data

# Environment variables
ENV DATA_FILE=/data/data.json

# Run bot
CMD ["python", "bot.py"]