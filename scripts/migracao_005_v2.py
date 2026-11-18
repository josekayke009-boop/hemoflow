#!/usr/bin/env python3
"""HemoFlow — Migração 005: HemoFlow 2.0 (captação e fidelização de doadores).

Uso (na pasta do projeto):
    python scripts/migracao_005_v2.py                   aplica (pede usuário administrativo do MySQL)
    python scripts/migracao_005_v2.py --verificar       só mostra o estado
    python scripts/migracao_005_v2.py --usar-variaveis  usa as variáveis HEMOFLOW_DB_* (console do Railway)

- Faça o backup antes (scripts/auditar_e_backup_banco.ps1 ou scripts/backup_nuvem.ps1).
- Só ACRESCENTA tabelas, colunas e dados de referência: nada existente é alterado ou apagado.
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
sys.path.insert(0, str(ROOT / "scripts"))
DB_NAME = os.environ.get("HEMOFLOW_DB_NAME", "hemoflow")
SQL = ROOT / "banco" / "migracoes" / "005_v2_captacao.sql"
DADOS = ROOT / "banco" / "migracoes" / "005_v2_dados.sql"

TABELAS = ["bancos_sangue", "unidades", "estoque_niveis", "estoque_movimentos", "vagas", "convocacoes",
           "convocacao_doadores", "agenda_doacoes", "historico_doacoes", "parceiros", "doador_parceiros", "ofertas",
           "cupons", "grupos", "grupo_membros", "beneficios_estado", "avisos", "codigos_login"]
COLUNAS = {
    "usuarios": [("banco_id", "BIGINT UNSIGNED NULL"), ("parceiro_id", "BIGINT UNSIGNED NULL")],
    "doadores": [("usuario_id", "BIGINT UNSIGNED NULL"), ("sexo", "CHAR(1) NULL"),
                 ("ultima_doacao_informada", "DATE NULL"),
                 ("consentimento_convocacao", "TINYINT(1) NOT NULL DEFAULT 0"),
                 ("consentimento_em", "DATETIME NULL"), ("responsavel_nome", "VARCHAR(120) NULL"),
                 ("responsavel_consentiu", "TINYINT(1) NOT NULL DEFAULT 0")],
}
CHAVES = [  # (tabela, nome, comando)
    ("usuarios", "fk_usuarios_banco", "ALTER TABLE usuarios ADD CONSTRAINT fk_usuarios_banco FOREIGN KEY (banco_id) REFERENCES bancos_sangue (id) ON DELETE SET NULL"),
    ("usuarios", "fk_usuarios_parceiro", "ALTER TABLE usuarios ADD CONSTRAINT fk_usuarios_parceiro FOREIGN KEY (parceiro_id) REFERENCES parceiros (id) ON DELETE SET NULL"),
    ("doadores", "uq_doadores_usuario", "ALTER TABLE doadores ADD UNIQUE KEY uq_doadores_usuario (usuario_id)"),
    ("doadores", "fk_doadores_usuario", "ALTER TABLE doadores ADD CONSTRAINT fk_doadores_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE SET NULL"),
]


def comandos(caminho):
    import servidor
    return list(servidor.sql_statements(caminho.read_text(encoding="utf-8")))


def existe_tabela(cur, nome):
    cur.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s", (DB_NAME, nome))
    return cur.fetchone()[0] > 0


def existe_coluna(cur, tabela, coluna):
    cur.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s",
                (DB_NAME, tabela, coluna))
    return cur.fetchone()[0] > 0


def existe_chave(cur, tabela, nome):
    cur.execute("""SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND CONSTRAINT_NAME=%s""",
                (DB_NAME, tabela, nome))
    if cur.fetchone()[0]:
        return True
    cur.execute("""SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND INDEX_NAME=%s""",
                (DB_NAME, tabela, nome))
    return cur.fetchone()[0] > 0


def estado(cur):
    faltam = [t for t in TABELAS if not existe_tabela(cur, t)]
    faltam += [f"{t}.{c}" for t, cols in COLUNAS.items() for c, _ in cols if not existe_coluna(cur, t, c)]
    faltam += [n for t, n, _ in CHAVES if existe_tabela(cur, t) and not existe_chave(cur, t, n)]
    cur.execute("SELECT COUNT(*) FROM perfis WHERE nome IN ('BANCO','PARCEIRO','DOADOR')")
    if cur.fetchone()[0] < 3:
        faltam.append("perfis BANCO/PARCEIRO/DOADOR")
    return faltam


def aplicar(cur):
    for cmd in comandos(SQL):
        inicio = cmd.lstrip().upper()
        if inicio.startswith("CREATE TABLE") or inicio.startswith("INSERT"):
            cur.execute(cmd)
    for tabela, cols in COLUNAS.items():
        for coluna, definicao in cols:
            if not existe_coluna(cur, tabela, coluna):
                cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")
                print(f"  OK: coluna {tabela}.{coluna}")
    for tabela, nome, cmd in CHAVES:
        if not existe_chave(cur, tabela, nome):
            cur.execute(cmd)
            print(f"  OK: {nome}")
    for cmd in comandos(DADOS):
        cur.execute(cmd)
    print("  OK: tabelas e dados de referência da versão 2.0")


def conectar(usar_variaveis):
    if usar_variaveis:
        import servidor
        return mysql.connector.connect(**{**servidor.db_config(), "autocommit": True})
    usuario = input("Usuário administrativo do MySQL [root]: ").strip() or "root"
    senha = os.environ.get("HEMOFLOW_ADMIN_PASSWORD")
    if not senha:
        try:
            from criar_administrador import ask_secret
        except Exception:
            ask_secret = getpass.getpass
        senha = ask_secret(f"Senha do MySQL para '{usuario}' (aparecem asteriscos): ")
    return mysql.connector.connect(host=os.environ.get("HEMOFLOW_DB_HOST", "127.0.0.1"),
                                   port=int(os.environ.get("HEMOFLOW_DB_PORT", "3306")),
                                   user=usuario, password=senha, database=DB_NAME, autocommit=True)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--verificar", action="store_true")
    p.add_argument("--usar-variaveis", action="store_true")
    a = p.parse_args()
    try:
        conn = conectar(a.usar_variaveis)
    except mysql.connector.Error as exc:
        sys.exit(f"Não foi possível conectar: {exc}")
    cur = conn.cursor()
    try:
        faltam = estado(cur)
        print(f"\nBanco: {DB_NAME} — pendências: {len(faltam)}")
        for f in faltam:
            print("  [pendente]", f)
        if a.verificar or not faltam:
            if not faltam:
                print("Migração 005 já aplicada. Nada a fazer.")
            return
        aplicar(cur)
        restantes = estado(cur)
        print("\nEstado final:", "tudo aplicado" if not restantes else f"faltam {restantes}")
    except mysql.connector.Error as exc:
        sys.exit(f"\nErro MySQL: {exc}\nRode com --verificar para ver o que já foi aplicado.")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
