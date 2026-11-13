#!/usr/bin/env python3
"""HemoFlow — Migração 004: CPF do doador (somente números, sem repetir).

Uso (na pasta do projeto):
    python scripts/migracao_004_cpf_doador.py                   aplica (pede usuário administrativo do MySQL)
    python scripts/migracao_004_cpf_doador.py --verificar       só mostra o estado
    python scripts/migracao_004_cpf_doador.py --reverter        desfaz (pede confirmação)
    python scripts/migracao_004_cpf_doador.py --usar-variaveis  usa as variáveis HEMOFLOW_DB_* (console do Railway)

- Faça o backup antes (scripts/auditar_e_backup_banco.ps1 ou scripts/backup_nuvem.ps1).
- Aplicar só ACRESCENTA a coluna cpf vazia (NULL) e o índice único: nenhum dado é alterado ou apagado.
- Doadores já cadastrados ficam sem CPF; o índice único aceita vários vazios.
- Pode ser executado mais de uma vez: o que já existe é ignorado.
"""
import argparse
import getpass
import os
import sys
from pathlib import Path

import mysql.connector

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DB_NAME = os.environ.get("HEMOFLOW_DB_NAME", "hemoflow")


def state(cur):
    cur.execute("""SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                   WHERE TABLE_SCHEMA=%s AND TABLE_NAME='doadores' AND COLUMN_NAME='cpf'""", (DB_NAME,))
    has_column = cur.fetchone()[0] > 0
    cur.execute("""SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
                   WHERE TABLE_SCHEMA=%s AND TABLE_NAME='doadores' AND INDEX_NAME='uq_doadores_cpf'""", (DB_NAME,))
    has_index = cur.fetchone()[0] > 0
    return has_column, has_index


def print_state(cur):
    has_column, has_index = state(cur)
    print(f"  {'[aplicado]' if has_column else '[pendente]'} doadores.cpf")
    print(f"  {'[aplicado]' if has_index else '[pendente]'} índice único uq_doadores_cpf")


def apply(cur):
    has_column, has_index = state(cur)
    if not has_column:
        cur.execute("ALTER TABLE doadores ADD COLUMN cpf CHAR(11) NULL AFTER nome")
        print("  OK: coluna doadores.cpf")
    if not has_index:
        cur.execute("ALTER TABLE doadores ADD UNIQUE KEY uq_doadores_cpf (cpf)")
        print("  OK: índice único uq_doadores_cpf")
    if has_column and has_index:
        print("\nMigração 004 já estava aplicada. Nada a fazer.")
    return True


def revert(cur):
    print("\nATENÇÃO: reverter APAGA a coluna de CPF e os CPFs gravados nela.")
    if input("Digite REVERTER para confirmar: ").strip() != "REVERTER":
        print("Cancelado. Nada foi alterado.")
        return False
    has_column, has_index = state(cur)
    if has_index:
        cur.execute("ALTER TABLE doadores DROP INDEX uq_doadores_cpf")
    if has_column:
        cur.execute("ALTER TABLE doadores DROP COLUMN cpf")
    print("  OK: CPF removido da tabela doadores")
    return True


def connect(use_env: bool):
    if use_env:
        # Mesmas credenciais e TLS do servidor (no Railway, o usuário do banco é administrativo).
        import servidor
        return mysql.connector.connect(**{**servidor.db_config(), "autocommit": True})
    user = input("Usuário administrativo do MySQL [root]: ").strip() or "root"
    try:
        from criar_administrador import ask_secret  # mostra asteriscos ao digitar
    except Exception:
        ask_secret = getpass.getpass
    sys.path.insert(0, str(ROOT / "scripts"))
    password = ask_secret(f"Senha do MySQL para '{user}' (aparecem asteriscos): ")
    return mysql.connector.connect(
        host=os.environ.get("HEMOFLOW_DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("HEMOFLOW_DB_PORT", "3306")),
        user=user, password=password, database=DB_NAME, autocommit=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--verificar", action="store_true")
    group.add_argument("--reverter", action="store_true")
    parser.add_argument("--usar-variaveis", action="store_true",
                        help="conecta com HEMOFLOW_DB_* (console do Railway)")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        conn = connect(args.usar_variaveis)
    except mysql.connector.Error as exc:
        print(f"Não foi possível conectar: {exc}")
        sys.exit(1)
    cur = conn.cursor()
    try:
        print(f"\nBanco: {DB_NAME} — estado atual:")
        print_state(cur)
        if args.verificar:
            return
        ok = revert(cur) if args.reverter else apply(cur)
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
