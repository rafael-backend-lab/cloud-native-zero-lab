"""Cloud Native Zero Lab - FastAPI + Neon, compatible with a-Shell."""
from pathlib import Path
from fastapi.responses import FileResponse, StreamingResponse
import os
import ssl
import json
import logging
import secrets
import base64
import time
import socket
import threading
import queue
import re
import unicodedata
from collections import OrderedDict
from fastapi.responses import Response
from urllib import request, error
import pg8000
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("uvicorn.error")

app = FastAPI(title="Cloud Native Zero Lab", version="0.4.0")

@app.middleware("http")
async def acesso_pessoal(req, call_next):
    password = os.getenv("LAB_ACCESS_PASSWORD")
    if password and req.url.path != "/health":
        expected = b"Basic " + base64.b64encode(("rafael:" + password).encode())
        provided = req.headers.get("authorization", "").encode()
        if not secrets.compare_digest(provided, expected):
            return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="Zero Lab", charset="UTF-8"'})
    return await call_next(req)


HOST = "ep-muddy-sun-bfxcceif-pooler.c-5.us-west-2.aws.neon.tech"
DATABASE = "cloud_native_zero_lab"
USER = "cloud_native_zero_lab_owner"


def connect_db():
    password = os.getenv("NEON_DB_PASSWORD")
    if not password:
        raise HTTPException(status_code=503, detail="NEON_DB_PASSWORD nao configurada")
    try:
        host = os.getenv("PGHOST", HOST)
        local_db = host == "postgres" and os.getenv("LAB_LOCAL_POSTGRES") == "1"
        tls = False if local_db or host in {"127.0.0.1", "::1"} else ssl.create_default_context()
        return pg8000.connect(user=os.getenv("PGUSER", USER), password=password, host=host,
                              database=os.getenv("PGDATABASE", DATABASE), port=int(os.getenv("PGPORT", "5432")),
                              ssl_context=tls, timeout=15)
    except Exception:
        raise HTTPException(status_code=503, detail="Banco indisponivel") from None


@app.get("/")
def inicio():
    return {"projeto": "Cloud Native Zero Lab", "status": "online"}


@app.get("/chat", include_in_schema=False)
def conversa():
    return FileResponse(Path(__file__).parent / "web" / "chat.html", media_type="text/html", headers={"Cache-Control": "no-store, max-age=0"})


@app.get("/health")
def health():
    return {"status": "ok", "release": "external-ai-v1"}


@app.get("/dbstatus")
def dbstatus():
    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT current_database(), current_user")
        database, user = cursor.fetchone()
        return {"status": "connected", "database": database, "user": user}
    except Exception:
        raise HTTPException(status_code=503, detail="Consulta ao banco falhou") from None
    finally:
        conn.close()


class MessageIn(BaseModel):
    mensagem: str


@app.get("/messages")
def messages():
    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, mensagem FROM teste_iphone ORDER BY id DESC LIMIT 100")
        return {"messages": [{"id": r[0], "mensagem": r[1]} for r in cursor.fetchall()]}
    except Exception:
        raise HTTPException(status_code=503, detail="Consulta de mensagens falhou") from None
    finally:
        conn.close()


@app.post("/messages", status_code=201)
def create_message(payload: MessageIn):
    if not payload.mensagem.strip() or len(payload.mensagem) > 1000:
        raise HTTPException(status_code=422, detail="Mensagem deve ter entre 1 e 1000 caracteres")
    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO teste_iphone (mensagem) VALUES (%s) RETURNING id", (payload.mensagem,))
        new_id = cursor.fetchone()[0]
        conn.commit()
        return {"id": new_id, "mensagem": payload.mensagem}
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=503, detail="Gravacao falhou") from None
    finally:
        conn.close()


# Inference happens outside Render; no local Ollama process is required.
SYSTEM_PROMPT = ("Você é o assistente do Cloud Native Zero Lab. Responda em português "
                 "brasileiro com precisão e clareza. Não invente informações; "
                 "quando não souber, diga isso. Seja objetivo, mas completo.")
class Prompt(BaseModel):
    pergunta: str

def inference_config():
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        raise HTTPException(503, "IA ainda não configurada: falta GROQ_API_KEY no servidor.")
    return key, os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

def ask_provider(question, streaming=False):
    key, model = inference_config()
    body = {"model": model, "messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question}
    ], "temperature": 0.2, "max_tokens": 450, "stream": streaming}
    return request.Request("https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"), headers={
            "Content-Type": "application/json", "Authorization": "Bearer " + key})

@app.get("/ia/status")
def ia_status():
    return {"provider": "groq", "configured": bool(os.getenv("GROQ_API_KEY")),
            "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")}

@app.post("/ia")
def gerar(payload: Prompt):
    question = payload.pergunta.strip()
    if not 1 <= len(question) <= 2000:
        raise HTTPException(422, "Pergunta deve ter entre 1 e 2000 caracteres")
    try:
        with request.urlopen(ask_provider(question), timeout=25) as resp:
            result = json.load(resp)
        answer = result["choices"][0]["message"]["content"]
        if not answer:
            raise ValueError("Empty answer")
        return {"resposta": answer}
    except error.HTTPError as exc:
        logger.warning("Groq HTTP error: %s", exc.code)
        raise HTTPException(503, "Provedor de IA indisponível ou limite de uso atingido.") from None
    except (OSError, ValueError, KeyError, IndexError):
        logger.exception("Groq request failed")
        raise HTTPException(503, "Não foi possível obter resposta do provedor de IA.") from None

@app.post("/ia/stream")
def gerar_stream(payload: Prompt):
    question = payload.pergunta.strip()
    if not 1 <= len(question) <= 2000:
        raise HTTPException(422, "Pergunta deve ter entre 1 e 2000 caracteres")
    req = ask_provider(question, streaming=True)
    def events():
        started = time.monotonic()
        try:
            with request.urlopen(req, timeout=25) as resp:
                for raw in resp:
                    line = raw.decode("utf-8").strip()
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        yield json.dumps({"done": True, "duration_ms": round((time.monotonic()-started)*1000)}) + "\\n"
                        return
                    event = json.loads(data)
                    token = event.get("choices", [{}])[0].get("delta", {}).get("content")
                    if token:
                        yield json.dumps({"token": token}, ensure_ascii=False) + "\\n"
            yield json.dumps({"error": "Resposta interrompida pelo provedor"}) + "\\n"
        except error.HTTPError as exc:
            logger.warning("Groq stream HTTP %s", exc.code)
            yield json.dumps({"error": "IA indisponível ou limite gratuito atingido"}) + "\\n"
        except Exception:
            logger.exception("Groq streaming failed")
            yield json.dumps({"error": "Falha de comunicação com a IA"}) + "\\n"
    return StreamingResponse(events(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
