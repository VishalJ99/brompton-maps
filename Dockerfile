FROM python:3.10-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application
COPY . .

# Expose port 8080 (Cloud Run default)
EXPOSE 8080

# Use gunicorn for production
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:8080", "app:app"]