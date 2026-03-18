FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir Pillow PyYAML
COPY server.py /app/server.py
WORKDIR /app
EXPOSE 8099
CMD ["python3", "server.py"]
