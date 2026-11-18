"""HemoFlow — regras de negócio da captação e fidelização de doadores.

Funções puras (sem banco de dados), usadas pelo servidor e cobertas por
tests/test_regras.py. Datas sempre como datetime.date.

ÍNDICE
   1. Tipos sanguíneos e compatibilidade
   2. Aptidão do doador (intervalo, limite anual, idade)
   3. Termômetro (Normal / Atenção / Crítico)
   4. Metas e benefícios por estado
   5. Cupons e conquistas
"""
from __future__ import annotations

from datetime import date, timedelta

# ============================================================================
# 1. TIPOS SANGUÍNEOS E COMPATIBILIDADE
# ============================================================================
TIPOS = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")

# Quem pode doar hemácias para quem (doador -> receptores).
DOA_PARA = {
    "O-": {"O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"},
    "O+": {"O+", "A+", "B+", "AB+"},
    "A-": {"A-", "A+", "AB-", "AB+"},
    "A+": {"A+", "AB+"},
    "B-": {"B-", "B+", "AB-", "AB+"},
    "B+": {"B+", "AB+"},
    "AB-": {"AB-", "AB+"},
    "AB+": {"AB+"},
}


def doadores_compativeis(tipo_necessario: str) -> list[str]:
    """Tipos de doador que servem para repor o estoque de `tipo_necessario`."""
    return sorted(t for t, receptores in DOA_PARA.items() if tipo_necessario in receptores)


# ============================================================================
# 2. APTIDÃO DO DOADOR
# ============================================================================
INTERVALO_DIAS = {"M": 60, "F": 90}      # dias mínimos entre doações
LIMITE_ANUAL = {"M": 4, "F": 3}          # doações em 12 meses
IDADE_MIN, IDADE_MAX = 16, 69


def idade(nascimento: date, hoje: date) -> int:
    return hoje.year - nascimento.year - ((hoje.month, hoje.day) < (nascimento.month, nascimento.day))


def aptidao(sexo: str, nascimento: date | None, doacoes: list[date], hoje: date,
            responsavel_ok: bool = False) -> dict:
    """Pré-checagem das regras básicas. A aptidão final é a triagem do banco.

    `doacoes` são as datas das doações conhecidas (verificadas ou declaradas).
    Retorna {apto, a_partir_de, motivo, doacoes_12m, limite_anual}.
    """
    sexo = "F" if sexo == "F" else "M"
    resultado = {"apto": True, "a_partir_de": hoje, "motivo": "", "doacoes_12m": 0,
                 "limite_anual": LIMITE_ANUAL[sexo]}
    if nascimento:
        anos = idade(nascimento, hoje)
        if anos < IDADE_MIN:
            aniversario = date(nascimento.year + IDADE_MIN, nascimento.month, min(nascimento.day, 28))
            return {**resultado, "apto": False, "a_partir_de": aniversario,
                    "motivo": "A doação é permitida a partir dos 16 anos."}
        if anos > IDADE_MAX:
            return {**resultado, "apto": False, "a_partir_de": None,
                    "motivo": "A primeira doação é permitida até 69 anos; confirme com o banco de sangue."}
        if anos < 18 and not responsavel_ok:
            return {**resultado, "apto": False, "a_partir_de": None,
                    "motivo": "Para menores de 18 anos é preciso o consentimento do responsável."}
    passadas = sorted(d for d in doacoes if d and d <= hoje)
    um_ano = hoje - timedelta(days=365)
    no_ano = [d for d in passadas if d > um_ano]
    resultado["doacoes_12m"] = len(no_ano)
    datas_livres = [hoje]
    if passadas:
        datas_livres.append(passadas[-1] + timedelta(days=INTERVALO_DIAS[sexo]))
    if len(no_ano) >= LIMITE_ANUAL[sexo]:
        # libera quando a doação mais antiga dentro da janela completar 12 meses
        mais_antiga = no_ano[len(no_ano) - LIMITE_ANUAL[sexo]]
        datas_livres.append(mais_antiga + timedelta(days=366))
    liberado = max(datas_livres)
    if liberado > hoje:
        motivo = (f"Limite de {LIMITE_ANUAL[sexo]} doações em 12 meses atingido."
                  if len(no_ano) >= LIMITE_ANUAL[sexo] and liberado != passadas[-1] + timedelta(days=INTERVALO_DIAS[sexo])
                  else f"Intervalo mínimo de {INTERVALO_DIAS[sexo]} dias desde a última doação.")
        return {**resultado, "apto": False, "a_partir_de": liberado, "motivo": motivo}
    return resultado


# ============================================================================
# 3. TERMÔMETRO
# ============================================================================
def nivel(quantidade: int, limite_critico: int, limite_atencao: int) -> str:
    if quantidade <= limite_critico:
        return "CRITICO"
    if quantidade <= limite_atencao:
        return "ATENCAO"
    return "NORMAL"


def bolsas_faltando(quantidade: int, limite_atencao: int) -> int:
    """Quantas bolsas faltam para o tipo voltar ao Normal."""
    return max(0, limite_atencao + 1 - quantidade)


def quantos_convocar(faltando: int, vagas_livres: int, aptos: int, comparecimento: float = 0.5) -> int:
    """Convoca o suficiente para cobrir o que falta, considerando que nem todos comparecem,
    sem passar das vagas livres nem do número de aptos."""
    if faltando <= 0:
        return 0
    desejado = int(-(-faltando // comparecimento))  # arredonda para cima
    return max(0, min(desejado, vagas_livres, aptos))


# ============================================================================
# 4. METAS E BENEFÍCIOS POR ESTADO
# ============================================================================
def meta_regular(sexo: str, minimo_homens: int, minimo_mulheres: int, verificadas_12m: int) -> dict:
    alvo = minimo_mulheres if sexo == "F" else minimo_homens
    return {"alvo": alvo, "feitas": min(verificadas_12m, alvo), "cumprida": verificadas_12m >= alvo}


# ============================================================================
# 5. CUPONS E CONQUISTAS
# ============================================================================
CUPOM_JANELA_DIAS = 183  # doação verificada nos últimos 6 meses
VIDAS_POR_DOACAO = 4


def pode_gerar_cupom(ultima_verificada: date | None, hoje: date) -> bool:
    return bool(ultima_verificada) and (hoje - ultima_verificada).days <= CUPOM_JANELA_DIAS


def conquistas(total_doacoes: int, regular: bool) -> list[dict]:
    lista = [
        {"codigo": "primeira", "titulo": "1ª doação", "ganhou": total_doacoes >= 1},
        {"codigo": "regular", "titulo": "Doador regular", "ganhou": regular},
        {"codigo": "cinco", "titulo": "5 doações", "ganhou": total_doacoes >= 5},
        {"codigo": "dez", "titulo": "10 doações", "ganhou": total_doacoes >= 10},
    ]
    return lista


def vidas_impactadas(total_doacoes: int) -> int:
    return total_doacoes * VIDAS_POR_DOACAO
