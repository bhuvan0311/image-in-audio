FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py advanced.py lab.py start_server.py ./
COPY watermark_lab ./watermark_lab
COPY docs ./docs
COPY .streamlit ./.streamlit
EXPOSE 8501
HEALTHCHECK CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8501')+'/_stcore/health',timeout=5)"
CMD ["python", "start_server.py"]
