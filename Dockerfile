# PYTHON
FROM python:3.12-slim

# FFMPEG
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# WORK DIRECTORY
WORKDIR /app

# Required packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bot codes
COPY . .

# Start commands
CMD ["python", "main.py"]