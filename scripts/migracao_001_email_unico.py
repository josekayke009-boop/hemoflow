#!/usr/bin/env python3
"""HemoFlow — Migração 001: e-mail único em doadores e profissionais.

Uso (na pasta do projeto, com usuário administrativo do MySQL, ex.: root):
    python scripts/migracao_001_email_unico.py              aplica
    python scripts/migracao_001_email_unico.py --verificar  só mostra o estado, não altera nada
    python scripts/migracao_001_email_unico.py --reverter   desfaz (pede confirmação)

- Faça o backup antes (scripts/auditar_e_backup_banco.ps1).
- Aplicar não apaga dados. Se já houver doadores com e-mail repetido, o script
  PARA sem alterar nada e lista os IDs envolvidos (os e-mails não são exibidos).
- Pode ser executado mais de uma vez: passos já aplicados são ignorados.
- A senha é pedida sem aparecer na tela e não é gravada.
"""
import argparse
import getpass
import os
import sys

import mysql.connector

DB_NAME = os.environ.get("HEMOFLOW_DB_NAME", "hemoflow")


def column_exists(cur, table, column):
    cur.execute("""SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                   WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s""",
                (DB_NAME, table, column))
    return cur.fetchone() is not None


def index_exists(cur, table, index):
    cur.execute("""SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
                   WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND INDEX_NAME=%s LIMIT 1""",
                (DB_NAME, table, index))
    return cur.fetchone() is not None


def donor_duplicates(cur):
    cur.execute("""SELECT COUNT(*) AS qtd, GROUP_CONCAT(id ORDER BY id) AS ids
                   FROM doadores WHERE email IS NOT NULL
                   GROUP BY LOWER(TRIM(email)) HAVING COUNT(*) > 1""")
    return cur.fetchall()


def state(cur):
    return {
        "doadores.uq_doadores_email": index_exists(cur, "doadores", "uq_doadores_email"),
        "profissionais.email": column_exists(cur, "profissionais", "email"),
        "profissionais.uq_profissionais_email": index_exists(cur, "profissionais", "uq_profissionais_email"),
    }


def print_state(cur):
    for name, ok in state(cur).items():
        print(f"  {'[aplicado]' if ok else '[pendente]'} {name}")


def apply(cur):
    dups = donor_duplicates(cur)
    if dups and not index_exists(cur, "doadores", "uq_doadores_email"):
        print("\nExistem doadores com e-mail repetido. Nada foi alterado.")
        for qtd, ids in dups:
            print(f"  {qtd} doadores com o mesmo e-mail — IDs: {ids}")
        print("Corrija ou inative os registros duplicados e execute novamente.")
        return False
    steps = []
    if not index_exists(cur, "doadores", "uq_doadores_email"):
        steps.append(("UNIQUE em doadores.email",
                      "ALTER TABLE doadores ADD CONSTRAINT uq_doadores_email UNIQUE (email)"))
    if not column_exists(cur, "profissionais", "email"):
        steps.append(("coluna profissionais.email",
                      "ALTER TABLE profissionais ADD COLUMN email VARCHAR(254) NULL AFTER nome"))
    if not index_exists(cur, "profissionais", "uq_profissionais_email"):
        steps.append(("UNIQUE em profissionais.email",
                      "ALTER TABLE profissionais ADD CONSTRAINT uq_profissionais_email UNIQUE (email)"))
    if not steps:
        print("\nMigração 001 já estava aplicada. Nada a fazer.")
        return True
    for label, sql in steps:
        # DDL no MySQL é confirmado automaticamente, passo a passo.
        cur.execute(sql)
        print(f"  OK: {label}")
    return True


def revert(cur):
    print("\nATENÇÃO: reverter APAGA a coluna profissionais.email e os e-mails gravados nela.")
    if input("Digite REVERTER para confirmar: ").strip() != "REVERTER":
        print("Cancelado. Nada foi alterado.")
        return False
    if index_exists(cur, "profissionais", "uq_profissionais_email"):
        cur.execute("ALTER TABLE profissionais DROP INDEX uq_profissionais_email")
        print("  OK: removido UNIQUE de profissionais.email")
    if column_exists(cur, "profissionais", "email"):
        cur.execute("ALTER TABLE profissionais DROP COLUMN email")
        print("  OK: removida coluna profissionais.email")
    if index_exists(cur, "doadores", "uq_doadores_email"):
        cur.execute("ALTER TABLE doadores DROP INDEX uq_doadores_email")
        print("  OK: removido UNIQUE de doadores.email")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--verificar", action="store_true")
    group.add_argument("--reverter", action="store_true")
    args = parser.parse_args()

    user = input("Usuário administrativo do MySQL [root]: ").strip() or "root"
    password = getpass.getpass(f"Senha do MySQL para '{user}': ")
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
            dups = donor_duplicates(cur)
            print(f"  Grupos de doadores com e-mail repetido: {len(dups)}")
            return
        ok = revert(cur) if args.reverter else apply(cur)
        print("\nEstado final:")
        print_state(cur)
        if not ok:
            sys.exit(1)
    except mysql.connector.Error as exc:
        print(f"\nErro MySQL: {exc}")
        print("Passos anteriores a este erro podem ter sido aplicados; rode com --verificar.")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
