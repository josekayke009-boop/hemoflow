"""Testes das notificações do sistema e da revisão de cadastro de doadores.

Banco SIMULADO. Executar:  python -m unittest tests.test_notificacoes -v
"""
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import app_mysql


class FakeCursor:
    def __init__(self, db, dictionary):
        self.db, self.dictionary, self.rows, self.rowcount = db, dictionary, [], 0

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        self.db.executed.append((s, params))
        self.rows, self.rowcount = self.db.respond(s, params)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)

    def close(self):
        pass


class FakeDB:
    def __init__(self):
        self.executed, self.commits = [], 0
        self.config = {}            # configuracoes: chave -> valor_json
        self.stock = {"A+": 20, "A-": 0, "O+": 7, "O-": 12}
        self.expiry = {"vencendo": 2, "vencidas": 1}
        self.pending_donors = ["Doador Antigo"]
        self.donor_exists = True

    def cursor(self, dictionary=False):
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

    def respond(self, s, params):
        if s.startswith("SELECT valor_json FROM configuracoes"):
            return ([(self.config[params[0]],)] if params[0] in self.config else []), 0
        if s.startswith("INSERT INTO configuracoes"):
            self.config[params[0]] = params[1]
            return [], 1
        if s.startswith("SELECT ts.codigo AS tipo"):
            return [{"tipo": k, "n": v} for k, v in self.stock.items()], 0
        if s.startswith("SELECT SUM(data_validade BETWEEN"):
            return [self.expiry], 0
        if s.startswith("SELECT nome FROM doadores"):
            return [{"nome": n} for n in self.pending_donors], 0
        if s.startswith("UPDATE doadores SET atualizado_em=NOW()"):
            return [], (1 if self.donor_exists else 0)
        if s.startswith("INSERT INTO historico_auditoria"):
            return [], 1
        raise AssertionError(f"SQL inesperado: {s[:80]}")


class NotificationTests(unittest.TestCase):
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
        self.perms = {"estoque.consultar", "doadores.consultar", "doadores.editar"}
        app_mysql.SESSIONS.clear()
        app_mysql.SESSIONS["tok"] = {"id": 4, "nome": "T", "email": "t@exemplo.com", "is_admin": False, "expires": 10**12}
        for p in [
            mock.patch.object(app_mysql, "connect_db", lambda: self.db),
            mock.patch.object(app_mysql.Handler, "has_permission", lambda _h, _id, code: code in self.perms),
        ]:
            p.start()
            self.addCleanup(p.stop)

    def call(self, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = Request(self.base + path, data=data, method="POST" if data is not None else "GET",
                      headers={"Content-Type": "application/json", "Cookie": "hemoflow_session=tok"})
        try:
            with urlopen(req, timeout=5) as res:
                return res.status, json.loads(res.read())
        except HTTPError as err:
            with err:
                return err.code, json.loads(err.read())

    def test_alertas_de_estoque_validade_e_cadastro(self):
        status, data = self.call("/api/notifications")
        self.assertEqual(status, 200)
        self.assertTrue(data["ativas"])
        titles = [i["titulo"] for i in data["itens"]]
        self.assertIn("Estoque crítico de A-", titles)        # 0 bolsas
        self.assertIn("Estoque baixo de O+", titles)          # 7 bolsas
        self.assertNotIn("Estoque baixo de A+", titles)       # 20 bolsas: sem alerta
        self.assertNotIn("Estoque baixo de O-", titles)       # 12 bolsas: sem alerta
        self.assertIn("1 bolsa vencida", titles)
        self.assertIn("2 bolsas vencem em até 7 dias", titles)
        self.assertIn("1 cadastro de doador precisa de atualização", titles)
        self.assertEqual(data["total"], len(data["itens"]))      # nada lido ainda
        self.assertEqual(data["total_alertas"], len(data["itens"]))
        self.assertTrue(all(not i["lida"] and i["chave"] for i in data["itens"]))
        # críticos aparecem primeiro
        levels = [i["nivel"] for i in data["itens"]]
        self.assertEqual(levels, sorted(levels, key=lambda lv: 0 if lv == "critico" else 1))

    def test_sem_permissao_de_estoque_nao_mostra_alertas_de_estoque(self):
        self.perms = {"doadores.consultar"}
        _, data = self.call("/api/notifications")
        self.assertEqual([i["tipo"] for i in data["itens"]], ["cadastro"])

    def test_desativar_e_reativar(self):
        status, data = self.call("/api/notifications/preferences", {"ativas": False})
        self.assertEqual((status, data["mensagem"]), (200, "Notificações desativadas."))
        self.assertEqual(self.db.config["notificacoes.usuario.4"], "false")
        _, data = self.call("/api/notifications")
        self.assertEqual((data["ativas"], data["itens"]), (False, []))
        self.call("/api/notifications/preferences", {"ativas": True})
        _, data = self.call("/api/notifications")
        self.assertTrue(data["ativas"])
        self.assertTrue(data["itens"])

    def test_clicar_da_baixa_e_diminui_o_numero(self):
        _, data = self.call("/api/notifications")
        total, chave = data["total"], data["itens"][0]["chave"]
        status, r = self.call("/api/notifications/read", {"chaves": [chave]})
        self.assertEqual((status, r["total"]), (200, total - 1))
        _, data = self.call("/api/notifications")
        self.assertEqual(data["total"], total - 1)
        self.assertEqual(data["total_alertas"], total)          # o alerta continua na lista, como "vista"
        self.assertTrue(next(i for i in data["itens"] if i["chave"] == chave)["lida"])

    def test_marcar_todas(self):
        status, r = self.call("/api/notifications/read", {"todas": True})
        self.assertEqual((status, r["total"]), (200, 0))
        _, data = self.call("/api/notifications")
        self.assertEqual(data["total"], 0)

    def test_situacao_mudou_volta_a_contar(self):
        self.call("/api/notifications/read", {"todas": True})
        self.db.stock["A-"] = 3                                  # estoque mudou: 0 -> 3 bolsas
        _, data = self.call("/api/notifications")
        self.assertEqual(data["total"], 1)
        self.assertEqual([i["titulo"] for i in data["itens"] if not i["lida"]], ["Estoque crítico de A-"])

    def test_chave_inexistente_ou_invalida(self):
        status, r = self.call("/api/notifications/read", {"chaves": ["nao:existe"]})
        self.assertEqual(status, 200)
        _, data = self.call("/api/notifications")
        self.assertEqual(data["total"], data["total_alertas"])  # nada foi marcado
        status, _ = self.call("/api/notifications/read", {"chaves": "x"})
        self.assertEqual(status, 400)

    def test_vistas_sao_por_usuario(self):
        self.call("/api/notifications/read", {"todas": True})
        self.assertIn("notificacoes.vistas.usuario.4", self.db.config)

    def test_preferencia_invalida(self):
        status, _ = self.call("/api/notifications/preferences", {"ativas": "sim"})
        self.assertEqual(status, 400)

    def test_preferencia_gravada_por_usuario(self):
        self.call("/api/notifications/preferences", {"ativas": False})
        insert = [p for s, p in self.db.executed if s.startswith("INSERT INTO configuracoes")][0]
        self.assertEqual(insert[0], "notificacoes.usuario.4")

    def test_notificacoes_exigem_login(self):
        app_mysql.SESSIONS.clear()
        status, _ = self.call("/api/notifications")
        self.assertEqual(status, 401)

    def test_marcar_cadastro_como_revisado(self):
        status, data = self.call("/api/donors/7/review", {})
        self.assertEqual((status, data["mensagem"]), (200, "Cadastro marcado como revisado."))
        self.assertEqual(self.db.commits, 1)

    def test_revisar_doador_inexistente(self):
        self.db.donor_exists = False
        status, _ = self.call("/api/donors/999/review", {})
        self.assertEqual(status, 404)

    def test_revisar_sem_permissao(self):
        self.perms = {"doadores.consultar"}
        status, _ = self.call("/api/donors/7/review", {})
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
