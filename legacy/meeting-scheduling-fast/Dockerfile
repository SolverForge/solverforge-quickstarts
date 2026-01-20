# Use Python 3.12 base image
FROM python:3.12

# Install JDK 21 (required for solverforge-legacy)
RUN apt-get update && \
    apt-get install -y wget gnupg2 && \
    wget -O- https://packages.adoptium.net/artifactory/api/gpg/key/public | gpg --dearmor > /usr/share/keyrings/adoptium-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/adoptium-archive-keyring.gpg] https://packages.adoptium.net/artifactory/deb bookworm main" > /etc/apt/sources.list.d/adoptium.list && \
    apt-get update && \
    apt-get install -y temurin-21-jdk && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy application files
COPY . .

# Install the application
RUN pip install --no-cache-dir -e .

# Expose port 7860
EXPOSE 7860

# Run the application
CMD ["run-app"]
