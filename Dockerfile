# Minimal Dockerfile for curl-mcp server
FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy project files
COPY requirements.txt .
COPY main.py .
COPY __main__.py .
RUN uv pip install --system -r requirements.txt

# Expose default SSE port
EXPOSE 3002

# Default command runs in foreground mode for container use
# Bind to 0.0.0.0 so the container can accept connections from outside
CMD ["uv", "run", "main.py", "--sse", "--host", "0.0.0.0", "--port", "3002"]
