import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
import main


class HttpTests(unittest.TestCase):
    def test_health(self):
        self.assertEqual(TestClient(main.app).get("/health").json(), {"status": "ok"})

    def test_unconfigured_database(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(TestClient(main.app).get("/dbstatus").status_code, 503)

    def test_invalid_messages(self):
        client = TestClient(main.app)
        for payload in ({}, {"mensagem": "  "}, {"mensagem": "x" * 1001}):
            with self.subTest(payload=payload):
                self.assertEqual(client.post("/messages", json=payload).status_code, 422)


@unittest.skipUnless(os.getenv("RUN_PG_TESTS") == "1", "Requer PostgreSQL de teste")
class PostgresTests(unittest.TestCase):
    def test_persistence(self):
        self.assertEqual(os.environ["PGHOST"], "127.0.0.1")
        self.assertEqual(os.environ["PGDATABASE"], "lab_ci")
        conn = main.connect_db()
        self.addCleanup(conn.close)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS teste_iphone (id serial PRIMARY KEY, mensagem text NOT NULL)")
        conn.commit()
        client = TestClient(main.app)
        status = client.get("/dbstatus")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["database"], "lab_ci")
        message = "Teste de integração " + str(uuid4())
        response = client.post("/messages", json={"mensagem": message})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["mensagem"], message)
        self.assertIsInstance(response.json()["id"], int)
        listed = client.get("/messages")
        self.assertEqual(listed.status_code, 200)
        self.assertIn(response.json(), listed.json()["messages"])
