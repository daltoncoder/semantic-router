# Use a base image with Python
FROM python:3.10-slim AS base

# Install Node.js
RUN apt-get update && apt-get install -y curl \
    && curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy requirements and package.json
COPY requirements.txt package.json ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Node.js dependencies
RUN npm install

# Copy project files
COPY . .

# Create a startup script
RUN echo '#!/bin/bash\n\
node decrypt.js\n\
python app.py' > /app/start.sh && \
    chmod +x /app/start.sh

# Expose application port
EXPOSE 8000

# Run a command that starts both Python and Node.js services
CMD ["/app/start.sh"]
