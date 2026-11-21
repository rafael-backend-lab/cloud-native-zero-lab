"""Cloud Native Zero Lab - FastAPI + Neon, compatible with a-Shell."""
import os
import ssl
import pg8000
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Cloud Native Zero Lab", version="0.2.0")

HOST = "ep-muddy-sun-bfxcceif-pooler.c-5.us-west-2.aws.neon.tech"
DATABASE = "cloud_native_zero_lab"
USER = "cloud_native_zero_lab_owner"


def connect_db():
    password = os.getenv("NEON_DB_PASSWORD")
    if not password:
        raise HTTPException(status_code=503, detail="NEON_DB_PASSWORD nao configurada")
    try:
        host = os.getenv("PGHOST", HOST)
        tls = False if host in {"127.0.0.1", "::1"} else ssl.create_default_context()
        return pg8000.connect(user=os.getenv("PGUSER", USER), password=password, host=host,
                              database=os.getenv("PGDATABASE", DATABASE), port=int(os.getenv("PGPORT", "5432")),
                              ssl_context=tls, timeout=15)
    except Exception:
        raise HTTPException(status_code=503, detail="Banco indisponivel") from None


@app.get("/")
def inicio():
    return {"projeto": "Cloud Native Zero Lab", "status": "online"}


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
