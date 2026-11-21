import unittest
from unittest.mock import patch
from fastapi import HTTPException
import main

class Tests(unittest.TestCase):
    def test_root(self):
        self.assertEqual(main.inicio()["status"], "online")

    def test_health(self):
        self.assertEqual(main.health(), {"status": "ok"})

    def test_missing_secret(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(HTTPException) as exc:
                main.dbstatus()
            self.assertEqual(exc.exception.status_code, 503)

    def test_dbstatus(self):
        class Cursor:
            def execute(self, sql):
                assert sql.startswith("SELECT")
            def fetchone(self):
                return ("cloud_native_zero_lab", "cloud_native_zero_lab_owner")
        class Conn:
            def cursor(self): return Cursor()
            def close(self): pass
        with patch.object(main, "connect_db", return_value=Conn()):
            self.assertEqual(main.dbstatus()["status"], "connected")

if __name__ == "__main__":
    unittest.main()
