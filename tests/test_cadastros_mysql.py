"""Testes dos cadastros do app_mysql.py (doadores e profissionais).

Usam um banco SIMULADO (FakeDB) no lugar do MySQL: verificam as regras do backend
(validação, bloqueio de e-mail duplicado, tradução de erros do MySQL, permissão
de administrador e aviso de migração pendente) sem precisar de senha nem tocar
no banco real. O comportamento do MySQL em si (UNIQUE de verdade) é coberto
pelos testes de integração da Etapa 4, contra um banco de teste.

Executar:  python -m unittest tests.test_cadastros_mysql -v
"""
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import mysql.connector

import app_mysql


class FakeCursor:
    def __init__(self, db):
        self.db = db
        self.rows = []
        self.lastrowid = None
        self.rowcount = 0

    def execute(self, sql, params=None):
        self.db.executed.append((" ".join(sql.split()), params))
        self.rows, self.lastrowid = self.db.respond(sql, params)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)

    def close(self):
        pass


class FakeDB:
    """Conexão falsa compartilhada por todas as chamadas a connect_db()."""

    def __init__(self):
        self.executed = []
        self.commits = 0
        self.rollbacks = 0
        self.schema_applied = True
        self.donor_emails = set()
        self.professional_emails = set()
        self.insert_error = None
        self.donor_ids = {5}
        self.delete_error = None

    # API usada pelo app
    def cursor(self, dictionary=False):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def respond(self, sql, params):
        s = " ".join(sql.split())
        if "INFORMATION_SCHEMA" in s:
            return ([(1,)] if self.schema_applied else []), None
        if s.startswith("SELECT id FROM doadores WHERE email"):
            return ([(7,)] if params[0] in self.donor_emails else []), None
        if s.startswith("SELECT id FROM profissionais WHERE email"):
            return ([(8,)] if params[0] in self.professional_emails else []), None
        if s.startswith("SELECT id FROM profissionais WHERE registro_profissional"):
            return [], None
        if s.startswith("INSERT INTO doadores") or s.startswith("INSERT INTO profissionais"):
            if self.insert_error:
                raise self.insert_error
            return [], 42
        if s.startswith("INSERT INTO historico_auditoria"):
            return [], 1
        if s.startswith("SELECT id, codigo_ficticio FROM doadores WHERE id"):
            return ([{"id": params[0], "codigo_ficticio": "DOA-TESTE"}] if params[0] in self.donor_ids else []), None
        if s.startswith("DELETE FROM doadores"):
            if self.delete_error:
                raise self.delete_error
            return [], None
        raise AssertionError(f"SQL inesperado no teste: {s[:80]}")

    def inserts(self, table):
        return [(s, p) for s, p in self.executed if s.startswith(f"INSERT INTO {table}")]


DONOR = {
    "nome": "Doador Ficticio", "email": "Teste.Doador@Exemplo.com", "telefone": "(81) 90000-0000",
    "data_nascimento": "1995-05-10", "tipo_sanguineo": "O+", "peso_kg": "72", "observacoes": "",
}
PROFESSIONAL = {
    "nome": "Profissional Ficticio", "email": "Prof@Exemplo.com", "telefone": "(81) 90000-0001",
    "cargo": "Enfermagem", "registro_profissional": "COREN-TESTE-1", "observacoes": "",
}


class CadastrosMySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app_mysql.Handler)
        cls.server.daemon_threads = True
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.db = FakeDB()
        self.is_admin = True
        app_mysql._SCHEMA_OK.clear()
        app_mysql.SESSIONS.clear()
        app_mysql.SESSIONS["token-teste"] = {
            "id": 1, "nome": "Admin Teste", "email": "admin@exemplo.com",
            "is_admin": True, "expires": 10**12,
        }
        patches = [
            mock.patch.object(app_mysql, "connect_db", lambda: self.db),
            mock.patch.object(app_mysql.Handler, "is_admin_profile", lambda _h, _id: self.is_admin),
            mock.patch.object(app_mysql.Handler, "require_permission", lambda _h, _id, _code: None),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def delete(self, path):
        req = Request(self.base + path, method="DELETE", headers={"Cookie": "hemoflow_session=token-teste"})
        try:
            with urlopen(req, timeout=5) as res:
                return res.status, json.loads(res.read())
        except HTTPError as err:
            with err:
                return err.code, json.loads(err.read())

    def post(self, path, body):
        req = Request(self.base + path, data=json.dumps(body).encode("utf-8"), method="POST",
                      headers={"Content-Type": "application/json", "Cookie": "hemoflow_session=token-teste"})
        try:
            with urlopen(req, timeout=5) as res:
                return res.status, json.loads(res.read())
        except HTTPError as err:
            with err:
                return err.code, json.loads(err.read())

    # ---------- doadores ----------
    def test_doador_novo_e_gravado_com_email_minusculo(self):
        status, data = self.post("/api/donors", DONOR)
        self.assertEqual(status, 201, data)
        (_, params), = self.db.inserts("doadores")
        self.assertIn("teste.doador@exemplo.com", params)
        self.assertEqual(self.db.commits, 1)

    def test_doador_email_duplicado_bloqueado(self):
        self.db.donor_emails.add("teste.doador@exemplo.com")
        status, data = self.post("/api/donors", DONOR)
        self.assertEqual(status, 409)
        self.assertEqual(data["erro"], "Já existe um doador cadastrado com esse e-mail.")
        self.assertEqual(self.db.inserts("doadores"), [])

    def test_doador_duplicado_simultaneo_vira_409_pelo_unique(self):
        self.db.insert_error = mysql.connector.IntegrityError(
            msg="Duplicate entry 'x' for key 'doadores.uq_doadores_email'", errno=1062)
        status, data = self.post("/api/donors", DONOR)
        self.assertEqual(status, 409)
        self.assertEqual(data["erro"], "Já existe um doador cadastrado com esse e-mail.")
        self.assertEqual(self.db.commits, 0)
        self.assertEqual(self.db.rollbacks, 1)

    def test_doador_email_invalido(self):
        status, data = self.post("/api/donors", {**DONOR, "email": "sem-arroba"})
        self.assertEqual(status, 400)
        self.assertEqual(data["erro"], "Informe um e-mail válido.")

    def test_doador_campos_obrigatorios(self):
        status, data = self.post("/api/donors", {**DONOR, "telefone": ""})
        self.assertEqual(status, 400)
        self.assertEqual(data["erro"], "Informe o telefone.")

    # ---------- profissionais ----------
    def test_profissional_novo_grava_email(self):
        status, data = self.post("/api/professionals", PROFESSIONAL)
        self.assertEqual(status, 201, data)
        (sql, params), = self.db.inserts("profissionais")
        self.assertIn("email", sql)
        self.assertIn("prof@exemplo.com", params)

    def test_profissional_email_duplicado_bloqueado(self):
        self.db.professional_emails.add("prof@exemplo.com")
        status, data = self.post("/api/professionals", PROFESSIONAL)
        self.assertEqual(status, 409)
        self.assertEqual(data["erro"], "Já existe um profissional cadastrado com esse e-mail.")
        self.assertEqual(self.db.inserts("profissionais"), [])

    def test_profissional_duplicado_simultaneo_vira_409_pelo_unique(self):
        self.db.insert_error = mysql.connector.IntegrityError(
            msg="Duplicate entry 'x' for key 'profissionais.uq_profissionais_email'", errno=1062)
        status, data = self.post("/api/professionals", PROFESSIONAL)
        self.assertEqual(status, 409)
        self.assertEqual(data["erro"], "Já existe um profissional cadastrado com esse e-mail.")

    def test_profissional_sem_email(self):
        status, data = self.post("/api/professionals", {**PROFESSIONAL, "email": ""})
        self.assertEqual(status, 400)
        self.assertEqual(data["erro"], "Informe um e-mail válido.")

    def test_profissional_com_migracao_pendente_avisa_e_nao_grava(self):
        self.db.schema_applied = False
        status, data = self.post("/api/professionals", PROFESSIONAL)
        self.assertEqual(status, 503)
        self.assertIn("migracao_001_email_unico.py", data["erro"])
        self.assertEqual(self.db.inserts("profissionais"), [])

    def test_profissional_exige_administrador(self):
        self.is_admin = False
        status, data = self.post("/api/professionals", PROFESSIONAL)
        self.assertEqual(status, 403)
        self.assertEqual(self.db.inserts("profissionais"), [])

    def test_sem_sessao_retorna_401(self):
        app_mysql.SESSIONS.clear()
        status, _ = self.post("/api/professionals", PROFESSIONAL)
        self.assertEqual(status, 401)

    # ---------- exclusão de doadores ----------
    def test_excluir_doador(self):
        status, data = self.delete("/api/donors/5")
        self.assertEqual((status, data["mensagem"]), (200, "Doador excluído."))
        executed = [s for s, _ in self.db.executed]
        self.assertTrue(any(s.startswith("DELETE FROM doadores") for s in executed))
        self.assertTrue(any("'EXCLUIR'" in s for s in executed))
        self.assertEqual(self.db.commits, 1)

    def test_excluir_doador_inexistente(self):
        status, _ = self.delete("/api/donors/999")
        self.assertEqual(status, 404)

    def test_excluir_doador_com_doacoes_bloqueado(self):
        self.db.delete_error = mysql.connector.IntegrityError(
            msg="Cannot delete or update a parent row: a foreign key constraint fails", errno=1451)
        status, data = self.delete("/api/donors/5")
        self.assertEqual(status, 409)
        self.assertIn("não pode ser excluído", data["erro"])
        self.assertEqual((self.db.commits, self.db.rollbacks), (0, 1))

    def test_excluir_doador_sem_permissao(self):
        def deny(_h, _id, _code):
            raise app_mysql.ApiError("Você não tem permissão para realizar esta operação.", 403)
        with mock.patch.object(app_mysql.Handler, "require_permission", deny):
            status, _ = self.delete("/api/donors/5")
        self.assertEqual(status, 403)
        self.assertFalse(any(s.startswith("DELETE") for s, _ in self.db.executed))

    def test_excluir_doador_sem_login(self):
        app_mysql.SESSIONS.clear()
        status, _ = self.delete("/api/donors/5")
        self.assertEqual(status, 401)

    # ---------- verificação de migração ----------
    def test_migracao_pendente_listada(self):
        self.db.schema_applied = False
        self.assertEqual(app_mysql.pending_migration_001(), [
            "doadores.uq_doadores_email", "profissionais.email", "profissionais.uq_profissionais_email"])
        self.db.schema_applied = True
        self.assertEqual(app_mysql.pending_migration_001(), [])


if __name__ == "__main__":
    unittest.main()
