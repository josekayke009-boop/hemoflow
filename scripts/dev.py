#!/usr/bin/env python3
"""HemoFlow — modo de desenvolvimento (só no computador): usa o usuário root do MySQL local,
pede a senha UMA vez e reinicia o servidor
sozinho sempre que um arquivo .py do projeto muda.

Uso (na pasta do projeto):  python scripts/dev.py
Pare com Ctrl+C. A senha fica só na memória deste processo.
"""
import getpass
import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def assinatura():
    return {p: p.stat().st_mtime for p in RAIZ.glob("*.py")}


def main():
    env = dict(os.environ)
    if not env.get("HEMOFLOW_DB_PASSWORD"):
        import mysql.connector
        for tentativa in range(1, 6):
            senha = getpass.getpass(f"({tentativa} de 5) Senha do ROOT do MySQL (a mesma do backup; não aparece): ")
            try:
                mysql.connector.connect(host=env.get("HEMOFLOW_DB_HOST", "127.0.0.1"), user=env.setdefault("HEMOFLOW_DB_USER", "root"),
                                        password=senha, database=env.get("HEMOFLOW_DB_NAME", "hemoflow")).close()
                print("Senha correta.")
                env["HEMOFLOW_DB_PASSWORD"] = senha
                break
            except mysql.connector.Error as exc:
                print("Senha recusada pelo MySQL. Tente de novo." if getattr(exc, "errno", 0) == 1045 else f"Erro: {exc}")
        else:
            sys.exit("Não foi possível conectar. Se esqueceu a senha, use scripts/redefinir_senha_app.py.")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    while True:
        print("\n=== iniciando o HemoFlow (modo desenvolvimento) ===", flush=True)
        processo = subprocess.Popen([sys.executable, str(RAIZ / "servidor.py")], cwd=RAIZ, env=env)
        antes = assinatura()
        try:
            while processo.poll() is None:
                time.sleep(1)
                if assinatura() != antes:
                    print("\n=== arquivo alterado: reiniciando ===", flush=True)
                    processo.terminate()
                    processo.wait(10)
                    break
            else:
                print("O servidor parou. Corrija o erro acima; ele reinicia quando um arquivo .py mudar.", flush=True)
                while assinatura() == antes:
                    time.sleep(1)
        except KeyboardInterrupt:
            processo.terminate()
            print("\nModo desenvolvimento encerrado.")
            return


if __name__ == "__main__":
    main()
