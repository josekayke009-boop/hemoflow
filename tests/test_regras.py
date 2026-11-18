"""Testes das regras de negócio do HemoFlow 2.0 (regras.py)."""
import unittest
from datetime import date

import regras as r

HOJE = date(2026, 11, 20)


class CompatibilidadeTests(unittest.TestCase):
    def test_o_negativo_so_recebe_de_o_negativo(self):
        self.assertEqual(r.doadores_compativeis("O-"), ["O-"])

    def test_ab_positivo_recebe_de_todos(self):
        self.assertEqual(sorted(r.doadores_compativeis("AB+")), sorted(r.TIPOS))

    def test_a_positivo(self):
        self.assertEqual(set(r.doadores_compativeis("A+")), {"A+", "A-", "O+", "O-"})

    def test_tabela_completa(self):
        self.assertEqual(r.DOA_PARA["O+"], {"O+", "A+", "B+", "AB+"})
        self.assertEqual(r.DOA_PARA["B-"], {"B-", "B+", "AB-", "AB+"})


class AptidaoTests(unittest.TestCase):
    def test_sem_doacao_esta_apto(self):
        a = r.aptidao("F", date(1990, 1, 1), [], HOJE)
        self.assertTrue(a["apto"])

    def test_intervalo_mulher_90_dias(self):
        a = r.aptidao("F", date(1990, 1, 1), [date(2026, 9, 1)], HOJE)
        self.assertFalse(a["apto"])
        self.assertEqual(a["a_partir_de"], date(2026, 11, 30))

    def test_intervalo_homem_60_dias(self):
        a = r.aptidao("M", date(1990, 1, 1), [date(2026, 9, 1)], HOJE)
        self.assertTrue(a["apto"])  # 1/9 + 60 dias = 31/10

    def test_limite_anual_mulher(self):
        doacoes = [date(2026, 1, 5), date(2026, 4, 10), date(2026, 7, 20)]
        a = r.aptidao("F", date(1990, 1, 1), doacoes, HOJE)
        self.assertFalse(a["apto"])
        self.assertEqual(a["doacoes_12m"], 3)
        self.assertGreater(a["a_partir_de"], HOJE)

    def test_menor_sem_responsavel(self):
        a = r.aptidao("M", date(2009, 6, 1), [], HOJE)
        self.assertFalse(a["apto"])
        self.assertIn("responsável", a["motivo"])

    def test_menor_com_responsavel(self):
        self.assertTrue(r.aptidao("M", date(2009, 6, 1), [], HOJE, responsavel_ok=True)["apto"])

    def test_menor_de_16(self):
        a = r.aptidao("F", date(2012, 3, 1), [], HOJE)
        self.assertFalse(a["apto"])
        self.assertEqual(a["a_partir_de"].year, 2028)

    def test_acima_de_69(self):
        self.assertFalse(r.aptidao("M", date(1950, 1, 1), [], HOJE)["apto"])


class TermometroTests(unittest.TestCase):
    def test_niveis(self):
        self.assertEqual(r.nivel(4, 5, 12), "CRITICO")
        self.assertEqual(r.nivel(5, 5, 12), "CRITICO")
        self.assertEqual(r.nivel(9, 5, 12), "ATENCAO")
        self.assertEqual(r.nivel(13, 5, 12), "NORMAL")

    def test_bolsas_faltando(self):
        self.assertEqual(r.bolsas_faltando(4, 12), 9)
        self.assertEqual(r.bolsas_faltando(20, 12), 0)

    def test_quantos_convocar(self):
        self.assertEqual(r.quantos_convocar(9, 30, 40), 18)   # 9 / 50% = 18
        self.assertEqual(r.quantos_convocar(9, 10, 40), 10)   # limitado às vagas
        self.assertEqual(r.quantos_convocar(9, 30, 5), 5)     # limitado aos aptos
        self.assertEqual(r.quantos_convocar(0, 30, 40), 0)


class MetaECuponsTests(unittest.TestCase):
    def test_meta_pe(self):
        self.assertTrue(r.meta_regular("F", 3, 2, 2)["cumprida"])
        self.assertFalse(r.meta_regular("M", 3, 2, 2)["cumprida"])

    def test_cupom_janela_6_meses(self):
        self.assertTrue(r.pode_gerar_cupom(date(2026, 8, 1), HOJE))
        self.assertFalse(r.pode_gerar_cupom(date(2026, 1, 1), HOJE))
        self.assertFalse(r.pode_gerar_cupom(None, HOJE))

    def test_vidas_e_conquistas(self):
        self.assertEqual(r.vidas_impactadas(3), 12)
        ganhou = {c["codigo"] for c in r.conquistas(5, True) if c["ganhou"]}
        self.assertEqual(ganhou, {"primeira", "regular", "cinco"})


if __name__ == "__main__":
    unittest.main()
