#!/usr/bin/env python3
"""HemoFlow — Migração 000: tipo sanguíneo e peso do doador (só acrescenta colunas).

Uso: python scripts/migracao_000_tipo_sanguineo_peso.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import servidor  # noqa: E402

def main():
    with servidor.connect_db() as db:
        cur = db.cursor()
        cur.execute("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA=%s AND TABLE_NAME='doadores'
        """, (servidor.DB_NAME,))
        existing = {row[0] for row in cur.fetchall()}
        additions = {
            "tipo_sanguineo": "VARCHAR(3) NULL",
            "peso_kg": "DECIMAL(5,2) NULL",
        }
        for name, definition in additions.items():
            if name not in existing:
                cur.execute(f"ALTER TABLE doadores ADD COLUMN {name} {definition}")
                print(f"Coluna adicionada: doadores.{name}")
            else:
                print(f"Já existe: doadores.{name}")
        db.commit()
        cur.close()
    print("Migração concluída. Nenhum dado existente foi apagado.")

if __name__ == "__main__":
    main()
