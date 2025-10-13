# Use a slim Python image for a smaller footprint
# Updated base image to drop the older 'buster' tag for better security and stability.
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /usr/src/app

# Set environment variables for non-interactive commands
# Corrected to use the recommended 'key=value' format to suppress the legacy format warning.
ENV PYTHONUNBUFFERED=1 \
    SERVER_PORT=8001

# Copy requirements file and install dependencies
COPY requirements.txt .
# Gunicorn is needed for production, so we ensure it's installed alongside other dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

# Copy the entire application source code (including src/)
# This copies src/bottle_app.py, src/server.py, etc.
COPY . .

# Expose the Gunicorn port
EXPOSE 8001

# Final Production CMD:
# 1. '-w 4' (4 workers) is good for production performance.
# 2. '-b 0.0.0.0:8001' binds to all interfaces, making it accessible from the outside.
# 3. '--chdir src' fixes ModuleNotFoundErrors for sibling files (like 'tester' or 'storage').
# 4. 'bottle_app:application' points to the correct module and the correct WSGI callable name.
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8001", "--chdir", "src", "bottle_app:application"]
