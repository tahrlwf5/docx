# Use official Python image
FROM python:3.11-slim-bullseye

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose port (not necessary for polling but required for Railway)
EXPOSE 80

# Health check
HEALTHCHECK CMD curl --fail http://localhost:80 || exit 1

# Run the bot
CMD ["python", "bot.py"]
