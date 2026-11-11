"""Testes do "Esqueceu sua senha?" (pedido do link e troca da senha).

Banco SIMULADO e envio de e-mail SIMULADO (nenhum e-mail real é enviado).
Executar:  python -m unittest tests.test_recuperacao -v
"""
import hashlib
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

import app_mysql


class FakeCursor:
    def __init__(self, db):
        self.db, self.rows, self.rowcount = db, [], 0

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        self.db.executed.append((s, params))
        self.rows, self.rowcount = self.db.respond(s, params)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def close(self):
        pass


class FakeDB:
    def __init__(self):
        self.executed, self.commits = [], 0
        self.users = {"ana@exemplo.com": {"id": 3, "email": "ana@exemplo.com", "nome": "Ana Souza"}}
        self.recent = False
        self.tokens = {}     # token_hash -> {"id", "usuario_id", "usado"}
        self.password_hash = None

    def cursor(self, dictionary=False):
        return FakeCursor(self)

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

    def respond(self, s, params):
        if "INFORMATION_SCHEMA.TABLES" in s:
            return [(1,)], 0
        if s.startswith("SELECT u.id, u.email, u.nome"):
            user = self.users.get(params[0])
            return ([{**user, "pedido_recente": int(self.recent)}] if user else []), 0
        if s.startswith("UPDATE recuperacao_senhas SET usado_em=NOW() WHERE usuario_id"):
            return [], 0
        if s.startswith("INSERT INTO recuperacao_senhas"):
            self.tokens[params[1]] = {"id": len(self.tokens) + 1, "usuario_id": params[0], "usado": False}
            return [], 1
        if s.startswith("SELECT r.id, r.usuario_id FROM recuperacao_senhas"):
            tok = self.tokens.get(params[0])
            return ([{"id": tok["id"], "usuario_id": tok["usuario_id"]}] if tok and not tok["usado"] else []), 0
        if s.startswith("UPDATE recuperacao_senhas SET usado_em=NOW() WHERE id"):
            for tok in self.tokens.values():
                if tok["id"] == params[0] and not tok["usado"]:
                    tok["usado"] = True
                    return [], 1
            return [], 0
        if s.startswith("UPDATE recuperacao_senhas SET usado_em=NOW() WHERE token_hash"):
            return [], 1
        if s.startswith("UPDATE usuarios SET senha_hash"):
            self.password_hash = params[0]
            return [], 1
        raise AssertionError(f"SQL inesperado: {s[:80]}")


class RecoveryTests(unittest.TestCase):
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
        self.sent = []
        app_mysql.RESET_REQUESTS.clear()
        for p in [
            mock.patch.object(app_mysql, "connect_db", lambda: self.db),
            mock.patch.object(app_mysql, "EMAIL_USER", "hemoflow.envio@gmail.com"),
            mock.patch.object(app_mysql, "EMAIL_PASSWORD", "senhadeapp"),
            mock.patch.object(app_mysql, "PUBLIC_URL", "https://hemoflow.exemplo.com"),
            mock.patch.object(app_mysql, "send_recovery_email",
                              lambda to, url, name="": self.sent.append((to, url, name))),
        ]:
            p.start()
            self.addCleanup(p.stop)

    def post(self, path, body):
        req = Request(self.base + path, data=json.dumps(body).encode(), method="POST",
                      headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=5) as res:
                return res.status, json.loads(res.read())
        except HTTPError as err:
            with err:
                return err.code, json.loads(err.read())

    def request_link(self, email="ana@exemplo.com"):
        return self.post("/api/forgot-password", {"email": email})

    def test_email_cadastrado_recebe_link(self):
        status, data = self.request_link("ANA@exemplo.com ")
        self.assertEqual(status, 200)
        self.assertIn("Se o e-mail estiver cadastrado", data["mensagem"])
        (to, url, name), = self.sent
        self.assertEqual((to, name), ("ana@exemplo.com", "Ana Souza"))
        self.assertTrue(url.startswith("https://hemoflow.exemplo.com/?reset_token="))
        token = parse_qs(urlparse(url).query)["reset_token"][0]
        # O banco guarda só o hash do token, nunca o token em si.
        self.assertIn(hashlib.sha256(token.encode()).hexdigest(), self.db.tokens)
        self.assertNotIn(token, self.db.tokens)

    def test_email_nao_cadastrado_mesma_resposta_sem_envio(self):
        status, data = self.request_link("ninguem@exemplo.com")
        self.assertEqual(status, 200)
        self.assertIn("Se o e-mail estiver cadastrado", data["mensagem"])
        self.assertEqual(self.sent, [])

    def test_pedido_repetido_em_menos_de_1_minuto_nao_envia_de_novo(self):
        self.db.recent = True
        status, _ = self.request_link()
        self.assertEqual(status, 200)
        self.assertEqual(self.sent, [])

    def test_limite_de_pedidos_por_ip(self):
        for _ in range(app_mysql.MAX_RESET_REQUESTS):
            self.assertEqual(self.request_link("ninguem@exemplo.com")[0], 200)
        status, data = self.request_link("ninguem@exemplo.com")
        self.assertEqual(status, 429)

    def test_sem_gmail_configurado(self):
        with mock.patch.object(app_mysql, "EMAIL_PASSWORD", ""):
            status, data = self.request_link()
        self.assertEqual(status, 503)

    def test_falha_no_gmail_mesma_resposta_e_link_invalidado(self):
        def broken(*_a, **_k):
            raise OSError("sem internet")
        with mock.patch.object(app_mysql, "send_recovery_email", broken):
            status, data = self.request_link()
        self.assertEqual(status, 200)
        self.assertTrue(any(s.startswith("UPDATE recuperacao_senhas SET usado_em=NOW() WHERE token_hash")
                            for s, _ in self.db.executed))

    def test_trocar_senha_com_link_valido_e_uso_unico(self):
        self.request_link()
        token = parse_qs(urlparse(self.sent[0][1]).query)["reset_token"][0]
        status, data = self.post("/api/reset-password", {"token": token, "senha": "NovaSenha2026"})
        self.assertEqual((status, data["mensagem"]), (200, "Senha alterada. Você já pode entrar com a nova senha."))
        self.assertTrue(app_mysql.verify_password("NovaSenha2026", self.db.password_hash))
        status, data = self.post("/api/reset-password", {"token": token, "senha": "OutraSenha2026"})
        self.assertEqual((status, data["erro"]), (400, "Link de recuperação inválido ou expirado."))

    def test_senha_nova_fraca_ou_link_falso(self):
        status, data = self.post("/api/reset-password", {"token": "x", "senha": "curta1"})
        self.assertEqual(status, 400)
        self.assertIn("entre 10 e 128", data["erro"])
        status, data = self.post("/api/reset-password", {"token": "x", "senha": "somenteletras"})
        self.assertIn("letras e números", data["erro"])
        status, data = self.post("/api/reset-password", {"token": "falso", "senha": "NovaSenha2026"})
        self.assertEqual((status, data["erro"]), (400, "Link de recuperação inválido ou expirado."))

    def test_email_tem_botao_e_link(self):
        """Monta o e-mail de verdade (sem enviar) e confere o conteúdo."""
        captured = {}

        class FakeSMTP:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def send_message(self, message):
                captured["msg"] = message

        with mock.patch.object(app_mysql, "smtp_connection", lambda: FakeSMTP()):
            mock.patch.stopall()  # usa o send_recovery_email real
            with mock.patch.object(app_mysql, "EMAIL_USER", "hemoflow.envio@gmail.com"), \
                    mock.patch.object(app_mysql, "EMAIL_PASSWORD", "senhadeapp"):
                app_mysql.send_recovery_email("ana@exemplo.com", "https://h.exemplo.com/?reset_token=abc", "Ana Souza")
        msg = captured["msg"]
        self.assertEqual(msg["To"], "ana@exemplo.com")
        self.assertIn("HemoFlow", msg["From"])
        html = msg.get_body(("html",)).get_content()
        text = msg.get_body(("plain",)).get_content()
        self.assertIn("Criar nova senha", html)
        self.assertIn("https://h.exemplo.com/?reset_token=abc", html)
        self.assertIn("Olá, Ana!", text)
        self.assertIn("30 minutos", text)


if __name__ == "__main__":
    unittest.main()
