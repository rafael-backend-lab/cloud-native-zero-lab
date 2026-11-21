"""Cloud Native Zero Lab - FastAPI + Neon, compatible with a-Shell."""
from pathlib import Path
from fastapi.responses import FileResponse
import os
import ssl
import json
import secrets
import base64
from fastapi.responses import Response
from urllib import request, error
import pg8000
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Cloud Native Zero Lab", version="0.2.0")

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
    return FileResponse(Path(__file__).parent / "web" / "chat.html", media_type="text/html")


@app.get("/health")
def health():
    return {"status": "ok"}


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

class Prompt(BaseModel):
    pergunta: str


@app.post("/ia")
def gerar(payload: Prompt):
    if not 1 <= len(payload.pergunta.strip()) <= 2000 or len(payload.pergunta) > 2000:
        raise HTTPException(422, "Pergunta deve ter entre 1 e 2000 caracteres")
    url = os.getenv("OLLAMA_URL")
    if not url:
        raise HTTPException(503, "IA local desativada")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
    options = {"num_predict": 96, "num_ctx": 2048}
    if model == "smollm2:135m":
        options.update(num_thread=1, num_predict=48, num_ctx=1024, num_batch=32)
    body = {"model": model, "prompt": payload.pergunta, "stream": True, "options": options}
    req = request.Request(url + "/api/generate", data=json.dumps(body).encode(),
                          headers={"Content-Type": "application/json"})
    parts = []
    try:
        # O tempo limite vale para inatividade na leitura, inclusive ao carregar o modelo.
        with request.urlopen(req, timeout=180) as response:
            for line in response:
                event = json.loads(line)
                if "error" in event:
                    raise ValueError("Falha durante a geração")
                parts.append(event.get("response", ""))
                if event.get("done"):
                    answer = "".join(parts).strip()
                    if answer:
                        return {"resposta": answer}
                    break
    except TimeoutError:
        raise HTTPException(504, "O modelo demorou demais para responder.") from None
    except error.HTTPError as exc:
        raise HTTPException(503, f"O serviço de IA retornou HTTP {exc.code}.") from None
    except (OSError, ValueError):
        raise HTTPException(503, "Falha de comunicação com o serviço de IA.") from None
    raise HTTPException(503, "O modelo encerrou a geração sem completar a resposta.")
