#!/usr/bin/env python3
"""HemoFlow — redefine a senha do usuário MySQL da aplicação (hemoflow_app).

Use quando esquecer a senha do hemoflow_app. Precisa da senha do root.
Só troca a senha: não altera tabelas, dados nem permissões.
As senhas são pedidas sem aparecer na tela e não são gravadas.

    python scripts/redefinir_senha_app.py
"""
import getpass
import os
import sys

import mysql.connector

APP_USER = os.environ.get("HEMOFLOW_DB_USER", "hemoflow_app")


def ask_secret(prompt: str) -> str:
    """Lê uma senha mostrando * a cada tecla (no Windows); nos demais sistemas usa getpass."""
    if os.name != "nt":
        return getpass.getpass(prompt)
    import msvcrt
    print(prompt, end="", flush=True)
    chars = []
    while True:
        ch = msvcrt.getwch()
        if ch in ("\r", "\n"):
            print()
            return "".join(chars)
        if ch == "\x03":
            raise KeyboardInterrupt
        if ch == "\x08":
            if chars:
                chars.pop()
                print("\b \b", end="", flush=True)
            continue
        if ch in ("\x00", "\xe0"):  # teclas especiais (setas etc.): ignora
            msvcrt.getwch()
            continue
        chars.append(ch)
        print("*", end="", flush=True)


def main():
    print(f"Redefinir a senha do usuário MySQL '{APP_USER}'@'localhost'.\n")
    root_password = ask_secret("Senha do ROOT do MySQL (aparecem asteriscos): ")
    try:
        conn = mysql.connector.connect(
            host=os.environ.get("HEMOFLOW_DB_HOST", "127.0.0.1"),
            port=int(os.environ.get("HEMOFLOW_DB_PORT", "3306")),
            user="root", password=root_password,
        )
    except mysql.connector.Error as exc:
        print(f"Não foi possível entrar como root: {exc}")
        sys.exit(1)

    new_password = ask_secret(f"Nova senha para {APP_USER} (mínimo 12 caracteres): ")
    if len(new_password) < 12:
        print("Use pelo menos 12 caracteres. Nada foi alterado.")
        sys.exit(1)
    if ask_secret("Repita a nova senha: ") != new_password:
        print("As senhas não conferem. Nada foi alterado.")
        sys.exit(1)
    if new_password == root_password:
        print("Use uma senha diferente da do root. Nada foi alterado.")
        sys.exit(1)

    cur = conn.cursor()
    try:
        cur.execute("ALTER USER %s@'localhost' IDENTIFIED BY %s", (APP_USER, new_password))
    except mysql.connector.Error as exc:
        print(f"Erro ao trocar a senha: {exc}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()
    print(f"\nSenha do {APP_USER} alterada. Use a NOVA senha ao iniciar o HemoFlow.")
    print("Guarde-a num gerenciador de senhas; ela não foi salva em nenhum arquivo.")


if __name__ == "__main__":
    main()
