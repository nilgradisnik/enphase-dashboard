# Use a slim Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py

# Install dependencies
# We copy the requirements file from the app directory
COPY enphase-dashboard/requirements.txt .
# Install requirements + PyJWT (needed by Enphase-API)
RUN pip install --no-cache-dir -r requirements.txt PyJWT

# Copy the library dependency first to match the expected relative path in app.py
# We expect the build context to be the parent directory (project root)
COPY Enphase-API /Enphase-API

# Copy the application code
COPY enphase-dashboard/ .

# Expose the port Flask runs on
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]
