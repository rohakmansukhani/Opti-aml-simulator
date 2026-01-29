FROM python:3.11-slim

# Install system dependencies for Oracle Thin mode + general ops
RUN apt-get update && apt-get install -y \
    libaio1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PORT 10000

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create directory for static files and collect them
# Note: SECRET_KEY is required for collectstatic in some Django setups
# We'll provide a dummy one if it's missing during build
RUN SECRET_KEY=build-time-only-key python manage.py collectstatic --noinput

# Start the application
CMD gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
