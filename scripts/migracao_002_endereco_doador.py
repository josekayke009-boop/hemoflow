#!/usr/bin/env python3
"""HemoFlow — Migração 002: endereço do doador (CEP, rua, número, complemento, bairro, cidade, UF).

Uso (na pasta do projeto, com usuário administrativo do MySQL, ex.: root):
    python scripts/migracao_002_endereco_doador.py              aplica
    python scripts/migracao_002_endereco_doador.py --verificar  só mostra o estado
    python scripts/migracao_002_endereco_doador.py --reverter   desfaz (pede confirmação)

- Faça o backup antes (scripts/auditar_e_backup_banco.ps1).
- Aplicar só ACRESCENTA colunas vazias (NULL) em doadores: nenhum dado é alterado ou apagado.
- Pode ser executado mais de uma vez: colunas já existentes são ignoradas.
"""
import argparse
import os
import sys
from pathlib import Path

import mysql.connector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from redefinir_senha_app import ask_secret  # noqa: E402  (senha com asteriscos)

DB_NAME = os.environ.get("HEMOFLOW_DB_NAME", "hemoflow")
COLUMNS = [  # (coluna, definição) — na ordem em que ficam na tabela, depois de telefone
    ("cep", "VARCHAR(9) NULL"),
    ("logradouro", "VARCHAR(150) NULL"),
    ("numero", "VARCHAR(10) NULL"),
    ("complemento", "VARCHAR(80) NULL"),
    ("bairro", "VARCHAR(80) NULL"),
    ("cidade", "VARCHAR(80) NULL"),
    ("uf", "CHAR(2) NULL"),
]


def existing_columns(cur):
    cur.execute("""SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
                   WHERE TABLE_SCHEMA=%s AND TABLE_NAME='doadores'""", (DB_NAME,))
    return {row[0] for row in cur.fetchall()}


def print_state(cur):
    have = existing_columns(cur)
    for name, _ in COLUMNS:
        print(f"  {'[aplicado]' if name in have else '[pendente]'} doadores.{name}")


def apply(cur):
    have = existing_columns(cur)
    previous = "telefone"
    for name, definition in COLUMNS:
        if name not in have:
            cur.execute(f"ALTER TABLE doadores ADD COLUMN {name} {definition} AFTER {previous}")
            print(f"  OK: coluna doadores.{name}")
        previous = name
    if not any(name not in have for name, _ in COLUMNS):
        print("\nMigração 002 já estava aplicada. Nada a fazer.")
    if "idx_doadores_cidade" not in index_names(cur):
        cur.execute("ALTER TABLE doadores ADD INDEX idx_doadores_cidade (cidade)")
        print("  OK: índice idx_doadores_cidade")


def index_names(cur):
    cur.execute("""SELECT DISTINCT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS
                   WHERE TABLE_SCHEMA=%s AND TABLE_NAME='doadores'""", (DB_NAME,))
    return {row[0] for row in cur.fetchall()}


def revert(cur):
    print("\nATENÇÃO: reverter APAGA as colunas de endereço e os endereços gravados nelas.")
    if input("Digite REVERTER para confirmar: ").strip() != "REVERTER":
        print("Cancelado. Nada foi alterado.")
        return False
    if "idx_doadores_cidade" in index_names(cur):
        cur.execute("ALTER TABLE doadores DROP INDEX idx_doadores_cidade")
    have = existing_columns(cur)
    for name, _ in reversed(COLUMNS):
        if name in have:
            cur.execute(f"ALTER TABLE doadores DROP COLUMN {name}")
            print(f"  OK: removida doadores.{name}")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--verificar", action="store_true")
    group.add_argument("--reverter", action="store_true")
    args = parser.parse_args()

    user = input("Usuário administrativo do MySQL [root]: ").strip() or "root"
    password = ask_secret(f"Senha do MySQL para '{user}' (aparecem asteriscos): ")
    try:
        conn = mysql.connector.connect(
            host=os.environ.get("HEMOFLOW_DB_HOST", "127.0.0.1"),
            port=int(os.environ.get("HEMOFLOW_DB_PORT", "3306")),
            user=user, password=password, database=DB_NAME,
        )
    except mysql.connector.Error as exc:
        print(f"Não foi possível conectar: {exc}")
        sys.exit(1)
    cur = conn.cursor()
    try:
        print(f"\nBanco: {DB_NAME} — estado atual:")
        print_state(cur)
        if args.verificar:
            return
        ok = revert(cur) if args.reverter else (apply(cur) is None)
        print("\nEstado final:")
        print_state(cur)
        if not ok:
            sys.exit(1)
    except mysql.connector.Error as exc:
        print(f"\nErro MySQL: {exc}")
        print("Rode com --verificar para ver o que já foi aplicado.")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
