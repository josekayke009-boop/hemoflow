"""Testes de ponta a ponta da versão 2.0 (doador, banco de sangue, parceiro e admin).

Rodam contra um servidor HemoFlow LOCAL com os dados fictícios de demonstração:
  1. em um terminal:  python scripts/dev.py
  2. recrie os dados: curl -X POST http://127.0.0.1:8000/api/dev/semear -d "{}"
  3. em outro:        set HEMOFLOW_TESTE_URL=http://127.0.0.1:8000
                      python -m unittest tests.test_v2_fluxos -v
Sem a variável HEMOFLOW_TESTE_URL os testes são pulados (não tocam em banco nenhum).
Nunca aponte para o servidor da nuvem: os testes criam doadores (@exemplo.com), agendamentos e cupons.
"""
import http.cookiejar
import json
import os
import random
import time
import unittest
import urllib.error
import urllib.request

from dados_demo import SENHA_DEMO

URL = os.environ.get("HEMOFLOW_TESTE_URL", "").rstrip("/")


class Cliente:
    """Navegador simplificado: guarda o cookie de sessão de uma conta."""

    def __init__(self):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def __call__(self, metodo, caminho, corpo=None):
        dados = json.dumps(corpo).encode() if corpo is not None else None
        req = urllib.request.Request(URL + caminho, data=dados, method=metodo, headers={"Content-Type": "application/json"})
        try:
            with self.op.open(req, timeout=15) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.loads(e.read())

    def entrar(self, email):
        status, _ = self("POST", "/api/login", {"email": email, "senha": SENHA_DEMO})
        assert status == 200, f"login {email} falhou"
        return self


def cpf_valido():
    """CPF fictício com dígitos verificadores corretos (para cadastrar doadores de teste)."""
    n = [random.randint(0, 9) for _ in range(9)]
    for tamanho in (9, 10):
        soma = sum(d * (tamanho + 1 - i) for i, d in enumerate(n[:tamanho]))
        n.append(0 if soma % 11 < 2 else 11 - soma % 11)
    return "".join(map(str, n))


def novo_doador():
    """Cadastra um doador de teste (sem doações, portanto apto) e devolve o cliente já logado."""
    c = Cliente()
    st, r = c("POST", "/api/cadastro", {
        "nome": "Doador Teste Automatico", "email": f"teste.{time.time_ns()}@exemplo.com", "senha": "abc12345",
        "cpf": cpf_valido(), "data_nascimento": "1995-03-10", "sexo": "M", "tipo_sanguineo": "O-",
        "cidade": "Recife", "uf": "PE", "aceite_termos": True, "consentimento_convocacao": True})
    assert st == 201, r
    return c


@unittest.skipUnless(URL.startswith(("http://127.0.0.1", "http://localhost")), "defina HEMOFLOW_TESTE_URL (servidor local)")
class FluxosV2(unittest.TestCase):
    def test_doador_agenda_banco_e_avisado_e_confirma(self):
        doador = novo_doador()
        banco = Cliente().entrar("captacao1@exemplo.com")
        st, inicio = doador("GET", "/api/doador/inicio")
        self.assertEqual(st, 200)
        self.assertTrue(inicio["aptidao"]["apto"])
        unidade = banco("GET", "/api/banco/painel")[1]["unidades"][0]["id"]
        vagas = doador("GET", f"/api/doador/vagas?unidade_id={unidade}")[1]["vagas"]
        vaga = next(v for v in vagas if v["livres"] > 0)
        avisos_antes = banco("GET", "/api/avisos")[1]["nao_lidos"]
        st, ag = doador("POST", "/api/doador/agendar", {"vaga_id": vaga["id"]})
        self.assertEqual(st, 201)
        self.assertEqual(doador("POST", "/api/doador/agendar", {"vaga_id": vaga["id"]})[0], 409)  # só um por vez
        self.assertGreater(banco("GET", "/api/avisos")[1]["nao_lidos"], avisos_antes)  # banco avisado
        st, conf = banco("POST", "/api/banco/confirmar", {"codigo": ag["agendamento"]["codigo"]})
        self.assertEqual(st, 200, conf)
        self.assertEqual(doador("GET", "/api/doador/historico")[1]["doacoes"][0]["status"], "VERIFICADA")
        self.assertFalse(doador("GET", "/api/doador/inicio")[1]["aptidao"]["apto"])  # intervalo de 60 dias começa
        self.assertEqual(doador("POST", "/api/doador/agendar", {"vaga_id": vaga["id"]})[0], 409)

    def test_cupom_de_uso_unico(self):
        doador = Cliente().entrar("doador@exemplo.com")
        padaria = Cliente().entrar("padaria@exemplo.com")
        ofertas = doador("GET", "/api/doador/vantagens")[1]["ofertas"]
        oferta = next(o for o in ofertas if o["parceiro"].startswith("Padaria"))
        st, cup = doador("POST", "/api/doador/cupons", {"oferta_id": oferta["id"]})
        self.assertEqual(st, 201)
        codigo = cup["cupom"]["codigo"]
        self.assertEqual(padaria("POST", "/api/parceiro/cupons/validar", {"codigo": codigo})[0], 200)
        self.assertEqual(padaria("POST", "/api/parceiro/cupons/validar", {"codigo": codigo})[0], 409)

    def test_convocacao_sugere_quantidade(self):
        banco = Cliente().entrar("captacao1@exemplo.com")
        unidade = banco("GET", "/api/banco/painel")[1]["unidades"][0]["id"]
        st, s = banco("GET", f"/api/banco/convocacao/sugestao?unidade_id={unidade}&tipo=O-")
        self.assertEqual(st, 200)
        for campo in ("faltam", "aptos", "vagas_livres", "convocar", "compativeis"):
            self.assertIn(campo, s)
        self.assertLessEqual(s["convocar"], min(s["aptos"], s["vagas_livres"]))

    def test_cada_perfil_so_ve_a_sua_area(self):
        doador = Cliente().entrar("doador@exemplo.com")
        padaria = Cliente().entrar("padaria@exemplo.com")
        self.assertEqual(doador("GET", "/api/banco/painel")[0], 403)
        self.assertEqual(doador("GET", "/api/admin/resumo")[0], 403)
        self.assertEqual(padaria("GET", "/api/doador/inicio")[0], 403)
        self.assertEqual(Cliente()("GET", "/api/doador/inicio")[0], 401)

    def test_admin_entra_como_banco_e_volta(self):
        admin = Cliente().entrar("admin@exemplo.com")
        banco_id = admin("GET", "/api/admin/bancos")[1]["bancos"][0]["id"]
        self.assertEqual(admin("POST", "/api/admin/entrar-como", {"papel": "BANCO", "id": banco_id})[0], 200)
        sessao = admin("GET", "/api/session")[1]["usuario"]
        self.assertEqual(sessao["papel"], "BANCO")
        self.assertTrue(sessao.get("entrou_como"))
        self.assertEqual(admin("GET", "/api/banco/painel")[0], 200)
        admin("POST", "/api/sair-como", {})
        self.assertEqual(admin("GET", "/api/session")[1]["usuario"]["papel"], "ADMINISTRADOR")

    def test_menor_de_idade_precisa_de_responsavel(self):
        st, r = Cliente()("POST", "/api/cadastro", {
            "nome": "Menor Teste", "email": "menor.teste@exemplo.com", "senha": "abc12345", "cpf": "11144477735",
            "data_nascimento": "2009-12-31", "sexo": "F", "tipo_sanguineo": "A+", "cidade": "Recife", "uf": "PE",
            "aceite_termos": True})
        self.assertEqual(st, 400)
        self.assertIn("respons", r["erro"])


if __name__ == "__main__":
    unittest.main()
