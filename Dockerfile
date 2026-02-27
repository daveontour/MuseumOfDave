# Stage 1: Build the Go import-processor
FROM golang:1.24-alpine AS go-builder

WORKDIR /app/import-processor

# Copy Go module files
COPY import-processor/go.mod import-processor/go.sum ./
RUN go mod download

# Copy Go source code
COPY import-processor/ ./

# Build the binary for Linux
RUN go build -o import-processor ./cmd/import-processor/main.go

# Stage 2: Final Python image
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (needed for Pillow/HEIF, Postgres, and ImageMagick)
RUN apt-get update && apt-get install -y \
    libheif-dev \
    libde265-dev \
    gcc \
    libpq-dev \
    imagemagick \
    && rm -rf /var/lib/apt/lists/*


# Copy Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the compiled Go binary from Stage 1
COPY --from=go-builder /app/import-processor/import-processor /app/import-processor/import-processor

# Copy the Python application code
COPY src/ ./src
# Copy other necessary files
COPY .env.docker .env
# Copy configuration files referenced by the app
COPY import-processor/email_classifications.json ./import-processor/
COPY import-processor/email_matches.json ./import-processor/
COPY import-processor/exclusions.json ./import-processor/
COPY import-processor/.env ./import-processor/

COPY history.json ./
COPY credentials.json ./
COPY token.json ./

# Ensure the binary is executable
RUN chmod +x /app/import-processor/import-processor

# Expose the port
EXPOSE 8000

# Run the application
CMD ["python", "src/main.py"]