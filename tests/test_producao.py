"""Testes da configuração de produção do app_mysql.py.

Banco SIMULADO (sem senha, sem tocar no MySQL real). Cobrem: cabeçalhos de
segurança, cookie Secure, IP real atrás de proxy, verificação de saúde (/healthz),
fuso horário, opções de TLS do MySQL e bloqueio de conta por senha errada.

Executar:  python -m unittest tests.test_producao -v
"""
import json
import threading
import unittest
from datetime import datetime
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import app_mysql


class FakeCursor:
    def __init__(self, db, dictionary):
        self.db, self.dictionary, self.rows = db, dictionary, []

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        self.db.executed.append((s, params))
        self.rows = self.db.respond(s, params, self.dictionary)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)

    def close(self):
        pass


class FakeDB:
    def __init__(self):
        self.executed, self.commits = [], 0
        self.user = None
        self.fail = False

    def cursor(self, dictionary=False):
        if self.fail:
            raise app_mysql.MySQLError("banco fora do ar")
        return FakeCursor(self, dictionary)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def respond(self, s, params, dictionary):
        if s == "SELECT 1":
            return [(1,)]
        if s.startswith("SELECT u.id, u.nome, u.email, u.senha_hash, u.status"):
            return [self.user] if self.user else []
        if s.startswith("UPDATE usuarios"):
            return []
        raise AssertionError(f"SQL inesperado: {s[:80]}")

    def updates(self):
        return [s for s, _ in self.executed if s.startswith("UPDATE usuarios")]


class ServerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app_mysql.Handler)
        cls.server.daemon_threads = True
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.db = FakeDB()
        app_mysql.LOGIN_ATTEMPTS.clear()
        for p in [
            mock.patch.object(app_mysql, "connect_db", lambda: self.db),
            mock.patch.object(app_mysql.Handler, "is_admin_profile", lambda _h, _id: False),
            mock.patch.object(app_mysql.Handler, "access_profile", lambda _h, _id: (["CONSULTA"], ["painel.consultar"])),
        ]:
            p.start()
            self.addCleanup(p.stop)

    def request(self, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = Request(self.base + path, data=data, method="POST" if data else "GET",
                      headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=5) as res:
                return res.status, res.headers, res.read()
        except HTTPError as err:
            with err:
                return err.code, err.headers, err.read()


class HeadersAndHealthTests(ServerTestCase):
    def test_cabecalhos_de_seguranca_na_api_e_na_interface(self):
        for path in ("/api/session", "/", "/app.js"):
            status, headers, _ = self.request(path)
            self.assertEqual(status, 200, path)
            self.assertEqual(headers["X-Frame-Options"], "DENY", path)
            self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"], path)
            self.assertIn("script-src 'self'", headers["Content-Security-Policy"], path)
            self.assertEqual(headers["X-Content-Type-Options"], "nosniff", path)

    def test_arquivos_do_app_instalavel(self):
        status, headers, body = self.request("/manifest.webmanifest")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/manifest+json")
        manifest = json.loads(body)
        self.assertEqual((manifest["short_name"], manifest["display"], manifest["start_url"]), ("HemoFlow", "standalone", "/"))
        for icon in manifest["icons"]:
            self.assertEqual(self.request(icon["src"])[0], 200, icon["src"])
        status, headers, body = self.request("/sw.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", headers["Content-Type"])
        self.assertIn('url.pathname.startsWith("/api/")', body.decode())   # API nunca vai para o cache
        status, _, body = self.request("/")
        self.assertIn(b'rel="manifest"', body)

    def test_healthz_ok_e_banco_fora(self):
        status, _, body = self.request("/healthz")
        self.assertEqual((status, json.loads(body)["banco"]), (200, "ok"))
        self.db.fail = True
        status, _, body = self.request("/healthz")
        self.assertEqual((status, json.loads(body)["banco"]), (503, "indisponivel"))
        self.assertNotIn("fora do ar", body.decode())  # não vaza detalhes internos


class LoginLockoutTests(ServerTestCase):
    def user(self, bloqueada=0):
        return {"id": 9, "nome": "Teste", "email": "t@exemplo.com", "status": "ATIVO",
                "senha_hash": app_mysql.password_hash("SenhaCorreta123"), "bloqueada": bloqueada}

    def test_senha_errada_conta_tentativa_na_conta(self):
        self.db.user = self.user()
        status, _, _ = self.request("/api/login", {"email": "t@exemplo.com", "senha": "errada"})
        self.assertEqual(status, 401)
        (sql,) = self.db.updates()
        self.assertIn("tentativas_falhas + 1", sql)
        self.assertIn("INTERVAL 15 MINUTE", sql)

    def test_conta_bloqueada_recusa_ate_senha_certa(self):
        self.db.user = self.user(bloqueada=1)
        status, _, body = self.request("/api/login", {"email": "t@exemplo.com", "senha": "SenhaCorreta123"})
        self.assertEqual(status, 429)
        self.assertIn("bloqueada", json.loads(body)["erro"])
        self.assertEqual(self.db.updates(), [])

    def test_login_certo_zera_contador_e_registra_ultimo_login(self):
        self.db.user = self.user()
        status, headers, _ = self.request("/api/login", {"email": "t@exemplo.com", "senha": "SenhaCorreta123"})
        self.assertEqual(status, 200)
        (sql,) = self.db.updates()
        self.assertIn("tentativas_falhas=0", sql)
        self.assertIn("ultimo_login=NOW()", sql)
        self.assertIn("HttpOnly", headers["Set-Cookie"])

    def test_email_inexistente_nao_atualiza_nada(self):
        status, _, _ = self.request("/api/login", {"email": "nao@exemplo.com", "senha": "x"})
        self.assertEqual(status, 401)
        self.assertEqual(self.db.updates(), [])


class ConfigTests(unittest.TestCase):
    def handler(self, xff=None, ip="10.0.0.5"):
        headers = {"X-Forwarded-For": xff} if xff else {}
        return SimpleNamespace(headers=headers, client_address=(ip, 1234))

    def test_ip_local_ignora_x_forwarded_for(self):
        with mock.patch.object(app_mysql, "TRUST_PROXY", False):
            self.assertEqual(app_mysql.Handler.client_ip(self.handler("1.2.3.4")), "10.0.0.5")

    def test_ip_atras_do_proxy_usa_o_valor_do_proxy(self):
        with mock.patch.object(app_mysql, "TRUST_PROXY", True), mock.patch.object(app_mysql, "PROXY_HOPS", 1):
            # "6.6.6.6" foi inventado pelo cliente; "1.2.3.4" foi acrescentado pelo proxy.
            self.assertEqual(app_mysql.Handler.client_ip(self.handler("6.6.6.6, 1.2.3.4")), "1.2.3.4")
            self.assertEqual(app_mysql.Handler.client_ip(self.handler()), "10.0.0.5")

    def test_cookie_secure_em_producao(self):
        with mock.patch.object(app_mysql, "COOKIE_SECURE", True):
            self.assertTrue(app_mysql.session_cookie("abc", 10).endswith("; Secure"))
        with mock.patch.object(app_mysql, "COOKIE_SECURE", False):
            self.assertNotIn("Secure", app_mysql.session_cookie("abc", 10))

    def test_hoje_no_fuso_de_recife(self):
        self.assertEqual(app_mysql.hoje(), datetime.now(ZoneInfo("America/Recife")).date())
        self.assertEqual(app_mysql._utc_offset(), "-03:00")

    def test_opcoes_tls_do_mysql(self):
        with mock.patch.object(app_mysql, "DB_SSL", "disabled"):
            self.assertTrue(app_mysql.db_config()["ssl_disabled"])
        with mock.patch.object(app_mysql, "DB_SSL", "required"):
            cfg = app_mysql.db_config()
            self.assertFalse(cfg["ssl_disabled"])
            self.assertNotIn("ssl_verify_cert", cfg)
        with mock.patch.object(app_mysql, "DB_SSL", "verify"), mock.patch.object(app_mysql, "DB_SSL_CA", ""), \
                mock.patch.dict("os.environ", {"HEMOFLOW_DB_SSL_CA_PEM": ""}):
            with self.assertRaises(RuntimeError):
                app_mysql.db_config()
        with mock.patch.object(app_mysql, "DB_SSL", "verify"), mock.patch.object(app_mysql, "DB_SSL_CA", "ca.pem"):
            cfg = app_mysql.db_config()
            self.assertTrue(cfg["ssl_verify_cert"] and cfg["ssl_verify_identity"])


if __name__ == "__main__":
    unittest.main()
