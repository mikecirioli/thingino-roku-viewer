FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir Pillow PyYAML
WORKDIR /app
EXPOSE 8099
# server.py is the only layer that changes frequently — keep it last
COPY server.py /app/server.py
CMD ["python3", "server.py"]
