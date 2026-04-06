FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir Pillow PyYAML requests piexif
COPY server.py geotag_manager.py /app/
WORKDIR /app
ENV PYTHONUNBUFFERED=1
EXPOSE 8099
CMD ["python3", "server.py"]
