# Use a slim Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py

# Install dependencies
COPY requirements.txt .
# Install requirements + PyJWT (needed by Enphase-API)
RUN pip install --no-cache-dir -r requirements.txt PyJWT

# Copy the application code
COPY . .

# Expose the port Flask runs on
EXPOSE 5000

# Run the application using a production WSGI server (Gunicorn)
# Limit to 1 worker to prevent duplicate APScheduler instances
CMD ["gunicorn", "--workers", "1", "--bind", "0.0.0.0:5000", "app:app"]
