"""Assistente HemoFlow — cria no MySQL do computador um usuário SÓ DE LEITURA para o agente.

- Pede a senha do root (não aparece na tela e não é guardada).
- Cria 'hemoflow_leitura'@'localhost' com permissão apenas de SELECT nas tabelas que o agente usa.
- Gera uma senha aleatória para esse usuário e grava direto no assistente/.env
  (cria o .env a partir do .env.example se ainda não existir). Ninguém precisa ver essa senha.

Uso (pasta assistente):  python scripts/criar_usuario_leitura.py
"""
import getpass
import secrets
import sys
from pathlib import Path

import mysql.connector

PASTA = Path(__file__).resolve().parent.parent
ENV, EXEMPLO = PASTA / ".env", PASTA / ".env.example"
USUARIO = "hemoflow_leitura"
TABELAS = ["doadores", "usuarios", "historico_doacoes", "beneficios_estado", "estoque_niveis", "unidades",
           "bancos_sangue", "cupons", "ofertas", "parceiros", "convocacoes", "convocacao_doadores", "agenda_doacoes", "vagas"]


def gravar_env(chave, valor):
    linhas = (ENV if ENV.exists() else EXEMPLO).read_text(encoding="utf-8").splitlines()
    achou = False
    for i, l in enumerate(linhas):
        if l.startswith(f"{chave}="):
            linhas[i], achou = f"{chave}={valor}", True
    if not achou:
        linhas.append(f"{chave}={valor}")
    ENV.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def main():
    banco = "hemoflow"
    for tentativa in range(1, 4):
        senha_root = getpass.getpass(f"({tentativa} de 3) Senha do ROOT do MySQL (não aparece): ")
        try:
            conn = mysql.connector.connect(host="127.0.0.1", user="root", password=senha_root, database=banco)
            break
        except mysql.connector.Error as exc:
            print("Senha recusada." if getattr(exc, "errno", 0) == 1045 else f"Erro: {exc}")
    else:
        sys.exit("Não foi possível conectar como root.")
    nova = secrets.token_urlsafe(24)
    cur = conn.cursor()
    cur.execute(f"CREATE USER IF NOT EXISTS '{USUARIO}'@'localhost' IDENTIFIED BY %s", (nova,))
    cur.execute(f"ALTER USER '{USUARIO}'@'localhost' IDENTIFIED BY %s", (nova,))
    for t in TABELAS:
        cur.execute(f"GRANT SELECT ON `{banco}`.`{t}` TO '{USUARIO}'@'localhost'")
    conn.commit()
    cur.close()
    conn.close()
    gravar_env("HEMOFLOW_DB_USER", USUARIO)
    gravar_env("HEMOFLOW_DB_PASSWORD", nova)
    segredo_atual = next((l.split("=", 1)[1] for l in ENV.read_text(encoding="utf-8").splitlines()
                          if l.startswith("ASSISTENTE_SEGREDO=")), "")
    if not segredo_atual.strip():  # segredo do serviço local (a aba Assistente do app usa o mesmo)
        gravar_env("ASSISTENTE_SEGREDO", secrets.token_urlsafe(24))
    print(f"Pronto: usuário '{USUARIO}' criado só com SELECT em {len(TABELAS)} tabelas. A senha dele foi gravada em assistente/.env.")


if __name__ == "__main__":
    main()
