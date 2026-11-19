#!/usr/bin/env python3
"""HemoFlow — migração 006 (versão 2.1): oferta de emergência e declarações para alunos.

Uso:
    python scripts/migracao_006_v21.py                    usuário administrativo do MySQL (pede a senha)
    python scripts/migracao_006_v21.py --usar-variaveis   usa as variáveis HEMOFLOW_DB_* (console do Railway)
    python scripts/migracao_006_v21.py --verificar        só mostra o que falta

- Faça o backup antes (na nuvem: python scripts/backup_interno.py --usar-variaveis).
- Só ACRESCENTA uma tabela e duas colunas. Pode rodar mais de uma vez.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import mysql.connector  # noqa: E402

import migracao_005_v2 as m5  # noqa: E402  (reaproveita conexão e verificações)

SQL = ROOT / "banco" / "migracoes" / "006_v21_diferenciais.sql"
COLUNAS = [("ofertas", "tipo_emergencia", "VARCHAR(3) NULL"), ("ofertas", "emergencia_ate", "DATE NULL")]


def estado(cur):
    faltam = [] if m5.existe_tabela(cur, "declaracoes") else ["declaracoes"]
    return faltam + [f"{t}.{c}" for t, c, _ in COLUNAS if not m5.existe_coluna(cur, t, c)]


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--verificar", action="store_true")
    p.add_argument("--usar-variaveis", action="store_true")
    a = p.parse_args()
    try:
        conn = m5.conectar(a.usar_variaveis)
    except mysql.connector.Error as exc:
        sys.exit(f"Não foi possível conectar: {exc}")
    cur = conn.cursor()
    if not m5.existe_tabela(cur, "ofertas"):
        sys.exit("A migração 005 (versão 2.0) precisa ser aplicada antes.")
    faltam = estado(cur)
    print(f"Migração 006 — pendências: {faltam or 'nenhuma'}")
    if a.verificar or not faltam:
        return
    for cmd in m5.comandos(SQL):
        cur.execute(cmd)
    for tabela, coluna, definicao in COLUNAS:
        if not m5.existe_coluna(cur, tabela, coluna):
            cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")
            print(f"  OK: coluna {tabela}.{coluna}")
    print("Estado final:", "tudo aplicado" if not estado(cur) else f"faltam {estado(cur)}")


if __name__ == "__main__":
    main()
