#!/usr/bin/env python3
"""Cria o primeiro usuário administrador do HemoFlow no MySQL.

Execute com: python scripts/criar_administrador.py
Não grava senhas no arquivo. O hash usa PBKDF2-HMAC-SHA256.
"""
import base64
import getpass
import hashlib
import os
import secrets
import sys
from pathlib import Path

# Pasta principal do projeto (onde fica servidor.py)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mysql.connector


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    iterations = 600_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.urlsafe_b64encode(salt).decode("ascii").rstrip("="),
        base64.urlsafe_b64encode(digest).decode("ascii").rstrip("="),
    )


def ask_secret(prompt: str) -> str:
    """Lê uma senha mostrando * a cada tecla (Windows e Linux/console da nuvem).
    Se o terminal não permitir, usa o getpass comum (sem mostrar nada)."""
    print(prompt, end="", flush=True)
    chars = []
    try:
        if os.name == "nt":
            import msvcrt
            read = msvcrt.getwch
            restore = None
        else:
            import termios
            import tty
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            tty.setraw(fd)
            read = lambda: sys.stdin.read(1)  # noqa: E731
            restore = lambda: termios.tcsetattr(fd, termios.TCSADRAIN, old)  # noqa: E731
    except Exception:
        print()
        return getpass.getpass("(digite e aperte Enter; nada aparece na tela) ")
    try:
        while True:
            ch = read()
            if ch in ("\r", "\n"):
                break
            if ch == "\x03":
                raise KeyboardInterrupt
            if ch in ("\x08", "\x7f"):
                if chars:
                    chars.pop()
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
                continue
            if ch in ("\x00", "\xe0", "\x1b"):  # teclas especiais: ignora
                continue
            chars.append(ch)
            sys.stdout.write("*")
            sys.stdout.flush()
    finally:
        if restore:
            restore()
        sys.stdout.write("\r\n")
        sys.stdout.flush()
    return "".join(chars)


def main():
    print("Configuração inicial do administrador HemoFlow")
    print("Ao digitar as senhas aparecem asteriscos (*).\n")

    db_user = os.environ.get("HEMOFLOW_DB_USER", "hemoflow_app")
    db_host = os.environ.get("HEMOFLOW_DB_HOST", "127.0.0.1")
    print(f"Banco: {db_host} (usuário {db_user})")
    # Na nuvem (console do Railway) a senha do banco já está em HEMOFLOW_DB_PASSWORD.
    db_password = os.environ.get("HEMOFLOW_DB_PASSWORD") or getpass.getpass(f"Senha do MySQL para {db_user}: ")
    if not db_password:
        print("A senha do MySQL não pode ficar vazia.")
        sys.exit(1)

    nome = input("Nome do administrador: ").strip()
    email = input("E-mail do administrador: ").strip().lower()
    if not nome or not email or "@" not in email:
        print("Informe um nome e um e-mail válido.")
        sys.exit(1)

    for attempt in range(1, 4):
        admin_password = ask_secret("Crie uma senha para o administrador (mínimo 12 caracteres): ")
        if len(admin_password) < 12:
            print(f"A senha tem {len(admin_password)} caracteres; use pelo menos 12. Tente de novo.\n")
            continue
        if ask_secret("Repita a senha do administrador: ") == admin_password:
            break
        print("As senhas não conferem. Tente de novo.\n")
    else:
        print("Não foi possível confirmar a senha. Nada foi gravado.")
        sys.exit(1)

    try:
        # Mesmas configurações do app (HEMOFLOW_DB_HOST, _PORT, _USER, _NAME, _SSL...),
        # então funciona tanto no MySQL local quanto no MySQL da nuvem com TLS.
        import servidor
        servidor.DB_PASSWORD = db_password
        conn = mysql.connector.connect(**servidor.db_config())
        conn.start_transaction()
        cur = conn.cursor(dictionary=True)

        cur.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
        existing = cur.fetchone()
        if existing:
            conn.rollback()
            print("Já existe um usuário com esse e-mail. Nenhuma alteração foi feita.")
            sys.exit(1)

        cur.execute(
            "INSERT INTO usuarios (nome,email,senha_hash,status) VALUES (%s,%s,%s,'ATIVO')",
            (nome, email, password_hash(admin_password)),
        )
        user_id = cur.lastrowid

        cur.execute("SELECT id FROM perfis WHERE nome='ADMINISTRADOR' LIMIT 1")
        profile = cur.fetchone()
        if not profile:
            conn.rollback()
            print("Perfil ADMINISTRADOR não encontrado. Nenhuma alteração foi confirmada.")
            sys.exit(1)

        cur.execute(
            "INSERT INTO usuario_perfis (usuario_id,perfil_id,atribuido_por) VALUES (%s,%s,%s)",
            (user_id, profile["id"], user_id),
        )
        conn.commit()
        print("\nAdministrador criado com sucesso.")
        print(f"ID do usuário: {user_id}")
        print("Guarde esse ID; ele será usado para configurar HEMOFLOW_OPERATOR_ID.")
        print("A senha do administrador não foi exibida nem salva em arquivo.")
        cur.close()
        conn.close()
    except mysql.connector.Error as exc:
        print(f"Erro MySQL: {exc}")
        print("Confira a senha do usuário MySQL e se o banco hemoflow está disponível.")
        sys.exit(1)


if __name__ == "__main__":
    main()
