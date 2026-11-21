FROM ollama/ollama:0.11.10 AS engine
FROM python:3.13-slim
WORKDIR /app
COPY --from=engine /usr/bin/ollama /usr/bin/ollama
COPY --from=engine /usr/lib/ollama/*.so* /usr/lib/ollama/
ENV OLLAMA_MODELS=/opt/models OLLAMA_HOST=127.0.0.1:11434 OLLAMA_URL=http://127.0.0.1:11434 OLLAMA_MODEL=qwen2.5:0.5b-instruct-q3_K_S OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 HOME=/tmp
RUN mkdir -p "$OLLAMA_MODELS" && ollama serve >/tmp/build-model.log 2>&1 & \
    server=$!; for i in $(seq 1 60); do ollama list >/dev/null 2>&1 && break; sleep 1; done; \
    ollama pull "$OLLAMA_MODEL" && chown -R 65532:65532 "$OLLAMA_MODELS"; result=$?; kill "$server" || true; exit "$result"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY web/ web/
COPY main.py .
COPY deploy/start.sh /app/start.sh
USER 65532:65532
CMD ["bash","/app/start.sh"]
