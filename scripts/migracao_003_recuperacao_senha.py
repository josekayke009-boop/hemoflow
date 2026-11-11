#!/usr/bin/env python3
"""HemoFlow — Migração 003: cria a tabela recuperacao_senhas ("Esqueceu sua senha?").

Uso (na pasta do projeto, com usuário administrativo do MySQL, ex.: root):
    python scripts/migracao_003_recuperacao_senha.py

Só CRIA a tabela se ela ainda não existir (CREATE TABLE IF NOT EXISTS):
não altera nem apaga nenhum dado. Pode ser executado mais de uma vez.
Mesmo conteúdo de sql/criar_recuperacao_senhas.sql.
"""
import os
import sys
from pathlib import Path

import mysql.connector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from redefinir_senha_app import ask_secret  # noqa: E402  (senha com asteriscos)
from instalar_banco_nuvem import statements  # noqa: E402

DB_NAME = os.environ.get("HEMOFLOW_DB_NAME", "hemoflow")
SQL_FILE = HERE.parent / "sql" / "instalacao" / "03_recuperacao_senhas.sql"


def table_exists(cur):
    cur.execute("""SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                   WHERE TABLE_SCHEMA=%s AND TABLE_NAME='recuperacao_senhas'""", (DB_NAME,))
    return cur.fetchone() is not None


def main():
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
        if table_exists(cur):
            print("\n[aplicado] recuperacao_senhas já existe. Nada a fazer.")
            return
        for command in statements(SQL_FILE.read_text(encoding="utf-8")):
            cur.execute(command)
        print("\n  OK: tabela recuperacao_senhas criada" if table_exists(cur) else "\nA tabela não foi criada.")
    except mysql.connector.Error as exc:
        print(f"\nErro MySQL: {exc}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
