#!/usr/bin/env python3
"""HemoFlow — instala a estrutura do banco num MySQL NOVO (ex.: MySQL na nuvem).

Executa, em ordem, os arquivos de sql/instalacao/:
  01_estrutura.sql         26 tabelas, chaves, índices e regras (sem dados)
  02_dados_referencia.sql  tipos sanguíneos, hemocomponentes, perfis e permissões
  03_recuperacao_senhas.sql
  04_email_unico.sql

Não copia doadores, usuários nem nenhum outro dado pessoal. Se o banco de destino
já tiver as tabelas do HemoFlow, o script PARA sem alterar nada.

Uso (os dados de conexão vêm do painel da hospedagem; a senha é pedida sem aparecer):
    python scripts/instalar_banco_nuvem.py
Depois, crie o primeiro administrador no banco novo com setup_admin.py
(usando as mesmas variáveis HEMOFLOW_DB_*).
"""
import getpass
import sys
from pathlib import Path

import mysql.connector

ROOT = Path(__file__).resolve().parent.parent
FILES = sorted((ROOT / "sql" / "instalacao").glob("0*.sql"))


def statements(sql_text: str):
    """Divide um arquivo .sql em comandos (terminam com ';' no fim da linha)."""
    buffer = []
    for line in sql_text.splitlines():
        if not buffer and (not line.strip() or line.lstrip().startswith("--")):
            continue
        buffer.append(line)
        if line.rstrip().endswith(";"):
            command = "\n".join(buffer).strip().rstrip(";").strip()
            buffer = []
            if command:
                yield command
    if "".join(buffer).strip():
        raise ValueError("Comando final sem ';'.")


def ask(label, default=""):
    value = input(f"{label}{f' [{default}]' if default else ''}: ").strip()
    return value or default


def main():
    print("Instalação do banco HemoFlow num servidor MySQL novo.\n")
    host = ask("Servidor (host) do MySQL")
    port = int(ask("Porta", "3306"))
    user = ask("Usuário")
    database = ask("Nome do banco")
    ssl = ask("TLS: required (criptografado) ou disabled", "required").lower()
    password = getpass.getpass(f"Senha do MySQL para '{user}': ")
    if not all([host, user, database, password]):
        print("Informe servidor, usuário, banco e senha.")
        sys.exit(1)
    try:
        conn = mysql.connector.connect(
            host=host, port=port, user=user, password=password, database=database,
            ssl_disabled=(ssl == "disabled"), connection_timeout=15, autocommit=True,
            charset="utf8mb4", collation="utf8mb4_0900_ai_ci",
        )
    except mysql.connector.Error as exc:
        print(f"Não foi possível conectar: {exc}")
        sys.exit(1)
    cur = conn.cursor()
    cur.execute("SELECT VERSION()")
    print(f"Conectado: MySQL {cur.fetchone()[0]}")
    cur.execute("""SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
                   WHERE TABLE_SCHEMA=%s AND TABLE_NAME IN ('usuarios','bolsas','doadores','perfis')""",
                (database,))
    if cur.fetchone()[0]:
        print("\nEste banco já tem tabelas do HemoFlow. Nada foi alterado.")
        print("Para atualizar um banco existente, use os scripts de migração em scripts/.")
        sys.exit(1)
    try:
        for path in FILES:
            commands = list(statements(path.read_text(encoding="utf-8")))
            for command in commands:
                cur.execute(command)
            print(f"  OK: {path.name} ({len(commands)} comandos)")
    except mysql.connector.Error as exc:
        print(f"\nErro MySQL em {path.name}: {exc}")
        print("A instalação ficou incompleta. Como o banco era novo, é seguro apagá-lo no painel e repetir.")
        sys.exit(1)
    cur.execute("""SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=%s""", (database,))
    tables = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM perfis")
    profiles = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM permissoes")
    permissions = cur.fetchone()[0]
    print(f"\nConcluído: {tables} tabelas, {profiles} perfis, {permissions} permissões.")
    print("Próximo passo: criar o primeiro administrador com setup_admin.py apontando para este banco.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
