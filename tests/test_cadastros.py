"""Testes dos cadastros do servidor.py (doadores e profissionais).

Usam um banco SIMULADO (FakeDB) no lugar do MySQL: verificam as regras do backend
(validação, bloqueio de e-mail duplicado, tradução de erros do MySQL, permissão
de administrador e aviso de migração pendente) sem precisar de senha nem tocar
no banco real. O comportamento do MySQL em si (UNIQUE de verdade) é coberto
pelos testes de integração da Etapa 4, contra um banco de teste.

Executar:  python -m unittest tests.test_cadastros -v
"""
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import mysql.connector

import servidor


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
        self.donor_cpfs = set()
        self.missing_schema = set()   # nomes de coluna/índice "ainda não migrados"
        self.donor_rows = []

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
            missing = params and params[-1] in self.missing_schema
            return ([(1,)] if self.schema_applied and not missing else []), None
        if s.startswith("SELECT id FROM doadores WHERE email"):
            return ([(7,)] if params[0] in self.donor_emails else []), None
        if s.startswith("SELECT id FROM doadores WHERE cpf"):
            return ([(9,)] if params[0] in self.donor_cpfs else []), None
        if s.startswith("SELECT id, nome, data_nascimento"):
            return [dict(row) for row in self.donor_rows], None
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
    "nome": "Doador Ficticio", "cpf": "123.456.789-09", "email": "Teste.Doador@Exemplo.com",
    "telefone": "(81) 90000-0000",
    "data_nascimento": "1995-05-10", "tipo_sanguineo": "O+", "peso_kg": "72", "observacoes": "",
    "cep": "50030230", "logradouro": "Rua da Aurora", "numero": "100", "complemento": "",
    "bairro": "Boa Vista", "cidade": "Recife", "uf": "pe",
}
PROFESSIONAL = {
    "nome": "Profissional Ficticio", "email": "Prof@Exemplo.com", "telefone": "(81) 90000-0001",
    "cargo": "Enfermagem", "registro_profissional": "COREN-TESTE-1", "observacoes": "",
}


class CadastrosMySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), servidor.Handler)
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
        servidor._SCHEMA_OK.clear()
        servidor.SESSIONS.clear()
        servidor.SESSIONS["token-teste"] = {
            "id": 1, "nome": "Admin Teste", "email": "admin@exemplo.com",
            "is_admin": True, "expires": 10**12,
        }
        patches = [
            mock.patch.object(servidor, "connect_db", lambda: self.db),
            mock.patch.object(servidor.Handler, "is_admin_profile", lambda _h, _id: self.is_admin),
            mock.patch.object(servidor.Handler, "require_permission", lambda _h, _id, _code: None),
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

    def get(self, path):
        req = Request(self.base + path, headers={"Cookie": "hemoflow_session=token-teste"})
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

    def test_doador_grava_endereco_e_formata_telefone_e_cep(self):
        status, data = self.post("/api/donors", {**DONOR, "telefone": "81900000000"})
        self.assertEqual(status, 201, data)
        (sql, params), = self.db.inserts("doadores")
        for column in ("cep", "logradouro", "numero", "complemento", "bairro", "cidade", "uf"):
            self.assertIn(column, sql)
        self.assertIn("(81) 90000-0000", params)
        self.assertIn("50030-230", params)
        self.assertIn("PE", params)
        self.assertIn(None, params)            # complemento vazio vira NULL

    def test_doador_endereco_obrigatorio(self):
        for field, message in [("logradouro", "Informe a rua/avenida."), ("numero", "Informe o número."),
                               ("bairro", "Informe o bairro."), ("cidade", "Informe a cidade."),
                               ("uf", "Informe o estado (UF).")]:
            status, data = self.post("/api/donors", {**DONOR, field: ""})
            self.assertEqual((status, data["erro"]), (400, message), field)
        self.assertEqual(self.db.inserts("doadores"), [])

    def test_doador_uf_cep_e_telefone_invalidos(self):
        status, data = self.post("/api/donors", {**DONOR, "uf": "XX"})
        self.assertEqual((status, data["erro"]), (400, "Selecione um estado (UF) válido."))
        status, data = self.post("/api/donors", {**DONOR, "cep": "123"})
        self.assertEqual((status, data["erro"]), (400, "CEP inválido: use 00000-000."))
        status, data = self.post("/api/donors", {**DONOR, "telefone": "12345"})
        self.assertEqual((status, data["erro"]), (400, "Informe o telefone com DDD: (00) 00000-0000."))

    def test_doador_com_migracao_002_pendente_avisa_e_nao_grava(self):
        self.db.schema_applied = False
        status, data = self.post("/api/donors", DONOR)
        self.assertEqual(status, 503)
        self.assertIn("migracao_002_endereco_doador.py", data["erro"])
        self.assertEqual(self.db.inserts("doadores"), [])

    # ---------- CPF do doador ----------
    def test_cpf_valido_e_invalido(self):
        self.assertTrue(servidor.valid_cpf("12345678909"))
        self.assertFalse(servidor.valid_cpf("12345678900"))   # dígito verificador errado
        self.assertFalse(servidor.valid_cpf("11111111111"))   # sequência repetida
        self.assertFalse(servidor.valid_cpf("1234567890"))    # 10 dígitos
        self.assertEqual(servidor.mask_cpf("12345678909"), "***.456.789-**")
        self.assertEqual(servidor.mask_cpf(None), "")

    def test_doador_grava_cpf_so_com_numeros(self):
        status, data = self.post("/api/donors", DONOR)
        self.assertEqual(status, 201, data)
        (sql, params), = self.db.inserts("doadores")
        self.assertIn("cpf", sql)
        self.assertIn("12345678909", params)

    def test_doador_cpf_obrigatorio_e_invalido(self):
        status, data = self.post("/api/donors", {**DONOR, "cpf": ""})
        self.assertEqual((status, data["erro"]), (400, "Informe o CPF."))
        for cpf in ("123.456.789-00", "111.111.111-11", "123.456"):
            status, data = self.post("/api/donors", {**DONOR, "cpf": cpf})
            self.assertEqual((status, data["erro"]), (400, "CPF inválido: confira os números digitados."), cpf)
        self.assertEqual(self.db.inserts("doadores"), [])

    def test_doador_cpf_duplicado_bloqueado(self):
        self.db.donor_cpfs.add("12345678909")
        status, data = self.post("/api/donors", DONOR)
        self.assertEqual((status, data["erro"]), (409, "Já existe um doador cadastrado com esse CPF."))
        self.assertEqual(self.db.inserts("doadores"), [])

    def test_doador_cpf_duplicado_simultaneo_vira_409_pelo_unique(self):
        self.db.insert_error = mysql.connector.IntegrityError(
            msg="Duplicate entry '12345678909' for key 'doadores.uq_doadores_cpf'", errno=1062)
        status, data = self.post("/api/donors", DONOR)
        self.assertEqual((status, data["erro"]), (409, "Já existe um doador cadastrado com esse CPF."))
        self.assertEqual(self.db.rollbacks, 1)

    def test_doador_com_migracao_004_pendente_avisa_e_nao_grava(self):
        self.db.missing_schema = {"cpf", "uq_doadores_cpf"}
        status, data = self.post("/api/donors", DONOR)
        self.assertEqual(status, 503)
        self.assertIn("migracao_004_cpf_doador.py", data["erro"])
        self.assertEqual(self.db.inserts("doadores"), [])

    def test_lista_de_doadores_mostra_cpf_mascarado(self):
        self.db.donor_rows = [{"id": 1, "nome": "Doador Ficticio", "cpf": "12345678909",
                               "data_nascimento": None, "criado_em": None, "atualizado_em": None,
                               "revisao_pendente": 0}]
        status, data = self.get("/api/donors")
        self.assertEqual(status, 200, data)
        self.assertEqual(data[0]["cpf_mascarado"], "***.456.789-**")
        self.assertNotIn("cpf", data[0])
        self.assertNotIn("12345678909", json.dumps(data))

    def test_busca_de_doador_pelo_cpf_completo(self):
        status, _ = self.get("/api/donors?q=123.456.789-09")
        self.assertEqual(status, 200)
        sql, params = [e for e in self.db.executed if e[0].startswith("SELECT id, nome")][-1]
        self.assertIn("OR cpf = %s", sql)
        self.assertEqual(params[-1], "12345678909")

    # ---------- suporte ----------
    def support_config(self, configured=True):
        values = ("hemoflow@exemplo.com", "senhadeapp", "suporte@exemplo.com") if configured else ("", "", "")
        for name, value in zip(("EMAIL_USER", "EMAIL_PASSWORD", "SUPPORT_EMAIL"), values):
            patcher = mock.patch.object(servidor, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        sent = mock.patch.object(servidor, "send_support_email")
        self.addCleanup(sent.stop)
        servidor.SUPPORT_REQUESTS.clear()
        return sent.start()

    SUPPORT = {"categoria": "Dúvida", "assunto": "Como registrar bolsa", "mensagem": "Não encontrei o botão de registrar bolsa."}

    def test_suporte_envia_email_e_registra_protocolo(self):
        sent = self.support_config()
        status, data = self.post("/api/support", self.SUPPORT)
        self.assertEqual(status, 200, data)
        self.assertTrue(data["protocolo"].startswith("SUP-"))
        protocol, category, subject, text, name, email = sent.call_args.args
        self.assertEqual((category, name, email), ("Dúvida", "Admin Teste", "admin@exemplo.com"))
        self.assertEqual(len(self.db.inserts("historico_auditoria")), 1)

    def test_suporte_valida_campos(self):
        sent = self.support_config()
        for body, message in [({**self.SUPPORT, "categoria": "Spam"}, "Selecione o tipo da mensagem."),
                              ({**self.SUPPORT, "assunto": "a"}, "Escreva um assunto (de 3 a 120 caracteres)."),
                              ({**self.SUPPORT, "mensagem": "curta"}, "Escreva a mensagem (de 10 a 3000 caracteres).")]:
            status, data = self.post("/api/support", body)
            self.assertEqual((status, data["erro"]), (400, message))
        sent.assert_not_called()

    def test_suporte_limite_de_mensagens_por_hora(self):
        self.support_config()
        for _ in range(servidor.MAX_SUPPORT_REQUESTS):
            self.assertEqual(self.post("/api/support", self.SUPPORT)[0], 200)
        status, _ = self.post("/api/support", self.SUPPORT)
        self.assertEqual(status, 429)

    def test_suporte_sem_email_configurado(self):
        sent = self.support_config(configured=False)
        status, data = self.post("/api/support", self.SUPPORT)
        self.assertEqual(status, 503)
        sent.assert_not_called()

    def test_suporte_exige_login(self):
        servidor.SESSIONS.clear()
        status, _ = self.post("/api/support", self.SUPPORT)
        self.assertEqual(status, 401)

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
        servidor.SESSIONS.clear()
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
            raise servidor.ApiError("Você não tem permissão para realizar esta operação.", 403)
        with mock.patch.object(servidor.Handler, "require_permission", deny):
            status, _ = self.delete("/api/donors/5")
        self.assertEqual(status, 403)
        self.assertFalse(any(s.startswith("DELETE") for s, _ in self.db.executed))

    def test_excluir_doador_sem_login(self):
        servidor.SESSIONS.clear()
        status, _ = self.delete("/api/donors/5")
        self.assertEqual(status, 401)

    # ---------- verificação de migração ----------
    def test_migracao_pendente_listada(self):
        self.db.schema_applied = False
        self.assertEqual(servidor.pending_migration_001(), [
            "doadores.uq_doadores_email", "profissionais.email", "profissionais.uq_profissionais_email"])
        self.db.schema_applied = True
        self.assertEqual(servidor.pending_migration_001(), [])


if __name__ == "__main__":
    unittest.main()
