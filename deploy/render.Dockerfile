FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY web/ web/
COPY main.py .
ENV PYTHONUNBUFFERED=1
USER 65532:65532
CMD ["sh", "-c", "exec python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
