#!/usr/bin/env python3
"""HemoFlow — backup DENTRO do próprio banco (para a nuvem, onde o MySQL não tem acesso público).

Copia cada tabela para uma tabela "bkp_<data>_<nome>" no mesmo banco (estrutura + dados).
Não altera nem apaga nada das tabelas originais.

Uso (Console do serviço hemoflow no Railway):
    python scripts/backup_interno.py --usar-variaveis            cria o backup
    python scripts/backup_interno.py --usar-variaveis --listar   mostra os backups existentes

Restaurar uma tabela (no MySQL, com cuidado e só se necessário):
    DELETE FROM doadores;  INSERT INTO doadores SELECT * FROM bkp_20261118_1500_doadores;
Apagar um backup antigo:  DROP TABLE bkp_..._nome;  (um por tabela)
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import mysql.connector  # noqa: E402

import servidor  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--usar-variaveis", action="store_true", help="usa as variáveis HEMOFLOW_DB_* (console do Railway)")
    p.add_argument("--listar", action="store_true", help="só lista os backups existentes")
    a = p.parse_args()
    if not a.usar_variaveis:
        sys.exit("Use --usar-variaveis (este script foi feito para o console da nuvem).")
    conn = mysql.connector.connect(**{**servidor.db_config(), "autocommit": True})
    cur = conn.cursor()
    cur.execute("""SELECT TABLE_NAME, TABLE_ROWS FROM INFORMATION_SCHEMA.TABLES
                   WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME""")
    tabelas = cur.fetchall()
    if a.listar:
        for nome, _ in tabelas:
            if nome.startswith("bkp_"):
                print(nome)
        return
    prefixo = "bkp_" + datetime.now(servidor.TZ).strftime("%Y%m%d_%H%M") + "_"
    originais = [n for n, _ in tabelas if not n.startswith("bkp_")]
    print(f"Copiando {len(originais)} tabelas com o prefixo {prefixo} …")
    total = 0
    for nome in originais:
        copia = (prefixo + nome)[:64]
        cur.execute(f"CREATE TABLE `{copia}` LIKE `{nome}`")
        # Colunas calculadas (GENERATED) não podem receber valor: o MySQL recalcula sozinho.
        cur.execute("""SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=DATABASE()
                       AND TABLE_NAME=%s AND EXTRA NOT LIKE %s ORDER BY ORDINAL_POSITION""", (nome, "%GENERATED%"))
        colunas = ", ".join(f"`{c}`" for (c,) in cur.fetchall())
        cur.execute(f"INSERT INTO `{copia}` ({colunas}) SELECT {colunas} FROM `{nome}`")
        cur.execute(f"SELECT COUNT(*) FROM `{nome}`")
        n_orig = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM `{copia}`")
        n_copia = cur.fetchone()[0]
        if n_orig != n_copia:
            sys.exit(f"ERRO: {nome} tem {n_orig} linhas e a cópia {n_copia}. Pare e verifique.")
        total += n_copia
        print(f"  {nome:<32} {n_copia:>6} linhas")
    print(f"Backup concluído: {len(originais)} tabelas, {total} linhas, prefixo {prefixo}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
