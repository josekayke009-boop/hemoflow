#!/usr/bin/env python3
"""HemoFlow — servidor do sistema (API + páginas).

Roda com a biblioteca padrão do Python (http.server) e guarda os dados no MySQL.
Entrega as telas da pasta static/ e responde às chamadas /api/... feitas pelo
js/app.js. Configure as variáveis HEMOFLOW_* (ver .env.example) antes de iniciar.

ÍNDICE (procure pelo título com Ctrl+F)
   1. CONFIGURAÇÃO ................. variáveis de ambiente, limites e listas fixas
   2. BANCO DE DADOS ............... conexão (pool, TLS, fuso horário)
   3. SENHAS E DATAS ............... hash PBKDF2, validação e formatação
   4. E-MAIL ....................... envio do link de recuperação de senha
   5. ERROS E VALIDAÇÕES ........... mensagens de duplicidade, e-mail, migrações
   6. SERVIDOR HTTP (classe Handler)
        6.1 Respostas e segurança .. JSON, cabeçalhos, sessão, IP
        6.2 Rotas .................. GET, POST e DELETE (qual URL chama qual função)
        6.3 Login e senha .......... entrar, bloqueio, recuperação de senha
        6.4 Perfis e permissões .... administrador e matriz de permissões
        6.9 Arquivos das telas ..... HTML, CSS, JS e imagens da pasta static/
        6.10 Suporte ............... mensagem da aba Suporte enviada por e-mail
   7. INSTALAÇÃO AUTOMÁTICA ........ cria as tabelas num banco novo (nuvem)
   8. INÍCIO ....................... main()

As rotas da versão 2.0 (doador, banco de sangue, parceiro, admin) ficam em rotas_v2.py
e as regras de negócio em regras.py.

Projeto acadêmico: use somente dados fictícios.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import smtplib
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from email.message import EmailMessage
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import mysql.connector
from mysql.connector import Error as MySQLError
from mysql.connector import pooling
from mysql.connector.errors import PoolError


# ============================================================================
# 1. CONFIGURAÇÃO
# ============================================================================
BASE_DIR = Path(__file__).resolve().parent

# ---- Ambiente: "development" (padrão, computador local) ou "production" (nuvem) ----
ENV = os.environ.get("HEMOFLOW_ENV", "development").strip().lower()
PRODUCTION = ENV == "production"
# Na nuvem o servidor precisa escutar em 0.0.0.0 e na porta que a plataforma define em PORT.
HOST = os.environ.get("HEMOFLOW_HOST", "0.0.0.0" if PRODUCTION else "127.0.0.1")
PORT = int(os.environ.get("HEMOFLOW_PORT") or os.environ.get("PORT") or "8000")
# Endereço público (ex.: https://hemoflow.exemplo.com), usado no link de recuperação de senha.
PUBLIC_URL = os.environ.get("HEMOFLOW_PUBLIC_URL", "").strip().rstrip("/")
# Cookie com a flag Secure (só trafega por HTTPS). Obrigatório em produção.
COOKIE_SECURE = PRODUCTION or os.environ.get("HEMOFLOW_COOKIE_SECURE", "0") == "1"
# Atrás do proxy HTTPS da hospedagem, o IP real do usuário vem em X-Forwarded-For.
TRUST_PROXY = os.environ.get("HEMOFLOW_TRUST_PROXY", "1" if PRODUCTION else "0") == "1"
PROXY_HOPS = max(1, int(os.environ.get("HEMOFLOW_PROXY_HOPS", "1")))
# Fuso usado para "hoje" (vencimentos) e para NOW() nas sessões do MySQL.
TIMEZONE = os.environ.get("HEMOFLOW_TZ", "America/Recife")
try:
    TZ = ZoneInfo(TIMEZONE)
except Exception:  # sem base de fusos (instale tzdata): usa o relógio local
    TZ = None
DB_HOST = os.environ.get("HEMOFLOW_DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("HEMOFLOW_DB_PORT", "3306"))
DB_NAME = os.environ.get("HEMOFLOW_DB_NAME", "hemoflow")
DB_USER = os.environ.get("HEMOFLOW_DB_USER", "hemoflow_app")
DB_PASSWORD = os.environ.get("HEMOFLOW_DB_PASSWORD", "")
EMAIL_USER = os.environ.get("HEMOFLOW_EMAIL_USER", "")
EMAIL_PASSWORD = os.environ.get("HEMOFLOW_EMAIL_PASSWORD", "").replace(" ", "")
EMAIL_HOST = os.environ.get("HEMOFLOW_EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("HEMOFLOW_EMAIL_PORT", "587"))
# Brevo (brevo.com): envio de e-mail por HTTPS. Usado na nuvem, onde o Railway
# bloqueia as portas de e-mail (SMTP). Sem a chave, o envio é pelo Gmail (SMTP).
BREVO_API_KEY = os.environ.get("HEMOFLOW_BREVO_API_KEY", "").strip()
BREVO_URL = "https://api.brevo.com/v3/smtp/email"
# Remetente dos e-mails (no Brevo, precisa ser um remetente verificado na conta).
EMAIL_FROM = os.environ.get("HEMOFLOW_EMAIL_FROM", "").strip() or EMAIL_USER
# Caixa que recebe as mensagens da aba Suporte (padrão: o próprio remetente).
SUPPORT_EMAIL = os.environ.get("HEMOFLOW_SUPPORT_EMAIL", "").strip() or EMAIL_FROM
SUPPORT_REQUESTS: dict[int, list[float]] = {}
MAX_SUPPORT_REQUESTS = 5          # mensagens por usuário...
SUPPORT_WINDOW = 60 * 60          # ...a cada 1 hora
SUPPORT_CATEGORIES = ("Dúvida", "Problema no sistema", "Sugestão", "Acesso e senha", "Outro")
SESSION_COOKIE = "hemoflow_session"
SESSION_TTL = 8 * 60 * 60
SESSIONS: dict[str, dict] = {}
LOGIN_ATTEMPTS: dict[str, list[float]] = {}
# Limite de pedidos de recuperação por IP (evita usar o sistema para enviar e-mails em massa).
RESET_REQUESTS: dict[str, list[float]] = {}
MAX_RESET_REQUESTS = 5
MAX_LOGIN_ATTEMPTS = 10
LOGIN_WINDOW = 15 * 60
MAX_ACCOUNT_FAILURES = 5

BLOOD_TYPES = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}
UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB",
       "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}
# Endereço do doador (migração 002): coluna -> (rótulo, tamanho máximo, obrigatório)
ADDRESS_FIELDS = {
    "cep": ("CEP", 9, False),
    "logradouro": ("rua/avenida", 150, True),
    "numero": ("número", 10, True),
    "complemento": ("complemento", 80, False),
    "bairro": ("bairro", 80, True),
    "cidade": ("cidade", 80, True),
    "uf": ("estado (UF)", 2, True),
}


def only_digits(value) -> str:
    return re.sub(r"\D", "", str(value or ""))


def format_phone(value) -> str:
    """(81) 98765-4321 ou (81) 3456-7890. Levanta ValueError se não tiver 10 ou 11 dígitos."""
    d = only_digits(value)
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    raise ValueError("Informe o telefone com DDD: (00) 00000-0000.")
STATUSES = {"DISPONIVEL", "RESERVADA", "TRANSFUNDIDA", "DESCARTADA", "QUARENTENA"}
TRANSITIONS = {
    "DISPONIVEL": {"RESERVADA", "TRANSFUNDIDA", "DESCARTADA", "QUARENTENA"},
    "RESERVADA": {"DISPONIVEL", "TRANSFUNDIDA", "DESCARTADA"},
    "QUARENTENA": {"DISPONIVEL", "DESCARTADA"},
}
STATUS_LABELS = {
    "DISPONIVEL": "Disponível", "RESERVADA": "Reservada",
    "TRANSFUNDIDA": "Transfundida", "DESCARTADA": "Descartada",
    "QUARENTENA": "Quarentena",
}



# ============================================================================
# 2. BANCO DE DADOS
# ============================================================================
# TLS com o MySQL:
#   "preferred" (padrão local): usa TLS se o servidor oferecer — o MySQL 8 exige
#               conexão segura para autenticar com caching_sha2_password;
#   "required"  (padrão em produção): exige TLS;
#   "verify":   exige TLS e confere o certificado (HEMOFLOW_DB_SSL_CA ou _CA_PEM);
#   "disabled": sem TLS (só para redes privadas e contas que não usem caching_sha2_password).
DB_SSL = os.environ.get("HEMOFLOW_DB_SSL", "required" if PRODUCTION else "preferred").strip().lower()
DB_SSL_CA = os.environ.get("HEMOFLOW_DB_SSL_CA", "")
DB_POOL_SIZE = max(1, int(os.environ.get("HEMOFLOW_DB_POOL_SIZE", "5")))
_POOL = None
_POOL_LOCK = threading.Lock()


def hoje() -> date:
    """Data de hoje no fuso do HemoFlow (a nuvem costuma rodar em UTC)."""
    return datetime.now(TZ).date() if TZ else date.today()


def _utc_offset() -> str:
    offset = datetime.now(TZ).utcoffset() if TZ else datetime.now().astimezone().utcoffset()
    minutes = int(offset.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    return f"{sign}{abs(minutes) // 60:02d}:{abs(minutes) % 60:02d}"


def _ssl_ca_path() -> str:
    """Aceita o certificado como caminho de arquivo ou como texto (HEMOFLOW_DB_SSL_CA_PEM)."""
    if DB_SSL_CA:
        return DB_SSL_CA
    pem = os.environ.get("HEMOFLOW_DB_SSL_CA_PEM", "").strip()
    if not pem:
        return ""
    path = Path(tempfile.gettempdir()) / "hemoflow-mysql-ca.pem"
    path.write_text(pem.replace("\\n", "\n") + "\n", encoding="ascii")
    return str(path)


def db_config() -> dict:
    config = dict(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, autocommit=False, connection_timeout=10,
        charset="utf8mb4", collation="utf8mb4_0900_ai_ci",
        time_zone=_utc_offset(),
    )
    if DB_SSL == "preferred":
        pass  # comportamento padrão do conector: TLS quando disponível
    elif DB_SSL == "disabled":
        config["ssl_disabled"] = True
    else:
        config["ssl_disabled"] = False
        if DB_SSL == "verify":
            ca = _ssl_ca_path()
            if not ca:
                raise RuntimeError("HEMOFLOW_DB_SSL=verify exige HEMOFLOW_DB_SSL_CA ou HEMOFLOW_DB_SSL_CA_PEM.")
            config.update(ssl_ca=ca, ssl_verify_cert=True, ssl_verify_identity=True)
    return config


def connect_db():
    """Conexão vinda de um pool: evita abrir uma conexão TLS nova a cada consulta,
    o que deixaria o sistema lento com o banco na nuvem. close() devolve ao pool."""
    global _POOL
    if not DB_PASSWORD:
        raise RuntimeError("Defina HEMOFLOW_DB_PASSWORD antes de iniciar o HemoFlow.")
    if _POOL is None:
        with _POOL_LOCK:
            if _POOL is None:
                _POOL = pooling.MySQLConnectionPool(
                    pool_name="hemoflow", pool_size=DB_POOL_SIZE, pool_reset_session=True, **db_config())
    try:
        return _POOL.get_connection()
    except PoolError:
        # Pool cheio em pico de acessos: usa uma conexão avulsa em vez de falhar.
        return mysql.connector.connect(**db_config())



# ============================================================================
# 3. SENHAS E DATAS
# ============================================================================
def verify_password(password: str, stored: str) -> bool:
    """Valida o formato pbkdf2_sha256$iterações$salt$digest criado por scripts/criar_administrador.py."""
    try:
        algorithm, iterations_text, salt_text, digest_text = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        if not 100_000 <= iterations <= 2_000_000:
            return False
        salt = base64.urlsafe_b64decode(salt_text + "=" * (-len(salt_text) % 4))
        expected = base64.urlsafe_b64decode(digest_text + "=" * (-len(digest_text) % 4))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, UnicodeError):
        return False


def serialize_date(value):
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def parse_date(value, label):
    if not isinstance(value, str):
        raise ValueError(f"Informe {label}.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{label.capitalize()} inválida; use AAAA-MM-DD.")


def password_hash(password: str) -> str:
    """Mesmo formato de hash usado pela autenticação existente."""
    iterations = 600_000  # mesmo valor de scripts/criar_administrador.py (recomendação OWASP para PBKDF2-SHA256)
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    salt_text = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
    digest_text = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"pbkdf2_sha256${iterations}${salt_text}${digest_text}"



# ============================================================================
# 4. E-MAIL (recuperação de senha)
# ============================================================================
def ensure_password_reset_table():
    """Confere se a tabela de recuperação existe.

    O usuário da aplicação (hemoflow_app) não tem privilégio CREATE, então a
    tabela não pode ser criada aqui. Ela é criada uma única vez, por um usuário
    administrador do MySQL, com o script scripts/migracao_003_recuperacao_senha.py.
    """
    with connect_db() as db:
        cur = db.cursor()
        cur.execute("""
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA=%s AND TABLE_NAME='recuperacao_senhas' LIMIT 1
        """, (DB_NAME,))
        exists = cur.fetchone() is not None
        cur.close()
    if not exists:
        raise ApiError(
            "A recuperação de senha ainda não foi instalada no banco. "
            "Execute scripts/migracao_003_recuperacao_senha.py com um usuário administrador do MySQL.", 503)


def smtp_connection():
    server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT, timeout=20)
    server.starttls()
    server.login(EMAIL_USER, EMAIL_PASSWORD)
    return server


def email_configured() -> bool:
    """Há um jeito de enviar e-mail: Brevo (chave + remetente) ou Gmail (conta + senha de app)."""
    return bool(BREVO_API_KEY and EMAIL_FROM) or bool(EMAIL_USER and EMAIL_PASSWORD)


def send_via_brevo(message: EmailMessage):
    """Envia a mensagem pela API do Brevo (HTTPS). Erros viram OSError (urllib)."""
    text_part = message.get_body(("plain",))
    html_part = message.get_body(("html",))
    payload = {
        "sender": {"name": "HemoFlow", "email": EMAIL_FROM},
        "to": [{"email": message["To"]}],
        "subject": str(message["Subject"]),
        "textContent": text_part.get_content() if text_part else "",
    }
    if html_part:
        payload["htmlContent"] = html_part.get_content()
    if message["Reply-To"]:
        payload["replyTo"] = {"email": message["Reply-To"]}
    request = urllib.request.Request(
        BREVO_URL, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:300].decode("utf-8", "replace")
        raise OSError(f"Brevo recusou o envio (HTTP {exc.code}): {detail}") from None


def deliver_email(message: EmailMessage):
    """Envia pelo Brevo quando a chave existe; senão, pelo Gmail (SMTP)."""
    if BREVO_API_KEY:
        return send_via_brevo(message)
    with smtp_connection() as server:
        server.send_message(message)


def check_email_login():
    """Usado por iniciar_hemoflow.ps1: confere o Gmail e a senha de app antes de abrir o sistema."""
    if not EMAIL_USER or not EMAIL_PASSWORD:
        raise SystemExit("Informe o Gmail e a senha de app.")
    try:
        with smtp_connection():
            pass
    except (smtplib.SMTPAuthenticationError, smtplib.SMTPServerDisconnected):
        # O Gmail às vezes só fecha a conexão (em vez de responder 535) quando a senha não é aceita.
        raise SystemExit(f"  O Gmail recusou o login ({len(EMAIL_PASSWORD)} caracteres digitados). "
                         "Use a SENHA DE APP de 16 letras criada em myaccount.google.com/apppasswords "
                         "na MESMA conta do Gmail informado, não a senha normal.")
    except (OSError, smtplib.SMTPException) as exc:
        raise SystemExit(f"  Não foi possível conectar ao Gmail: {type(exc).__name__}: {exc}")


def send_recovery_email(to_email: str, reset_url: str, name: str = ""):
    if not email_configured():
        raise RuntimeError("Configure o envio de e-mail (Brevo ou Gmail).")
    first = (name or "").split(" ")[0]
    greeting = f"Olá, {first}!" if first else "Olá!"
    message = EmailMessage()
    message["Subject"] = "Redefinição de senha — HemoFlow"
    message["From"] = f"HemoFlow <{EMAIL_FROM}>"
    message["To"] = to_email
    message.set_content(
        f"{greeting}\n\n"
        "Recebemos uma solicitação para redefinir a senha da sua conta no HemoFlow.\n\n"
        f"Para criar uma nova senha, acesse o link abaixo (válido por 30 minutos e de uso único):\n{reset_url}\n\n"
        "Se você não fez essa solicitação, ignore este e-mail: sua senha continua a mesma.\n\n"
        "HemoFlow · Gestão de hemocentro"
    )
    safe_url = reset_url.replace("&", "&amp;").replace('"', "&quot;")
    safe_greeting = greeting.replace("<", "&lt;").replace(">", "&gt;")
    message.add_alternative(f"""<!doctype html><html lang="pt-BR"><body style="margin:0;background:#f4f6fa;font-family:Arial,Helvetica,sans-serif;color:#111a31">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:32px 12px"><tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#ffffff;border-radius:16px;border:1px solid #dce5f1">
<tr><td style="background:#8b0a1a;border-radius:16px 16px 0 0;padding:22px 28px;color:#ffffff;font-size:22px;font-weight:bold">HemoFlow</td></tr>
<tr><td style="padding:28px">
<p style="font-size:16px;margin:0 0 14px">{safe_greeting}</p>
<p style="font-size:15px;line-height:1.6;margin:0 0 22px">Recebemos uma solicitação para redefinir a senha da sua conta no HemoFlow. Clique no botão abaixo para criar uma nova senha.</p>
<p style="margin:0 0 24px"><a href="{safe_url}" style="display:inline-block;background:#c90012;color:#ffffff;text-decoration:none;font-weight:bold;padding:14px 26px;border-radius:10px">Criar nova senha</a></p>
<p style="font-size:13px;line-height:1.6;color:#617898;margin:0 0 8px">O link vale por <b>30 minutos</b> e só pode ser usado uma vez.</p>
<p style="font-size:13px;line-height:1.6;color:#617898;margin:0 0 8px">Se o botão não funcionar, copie e cole este endereço no navegador:<br><span style="word-break:break-all">{safe_url}</span></p>
<p style="font-size:13px;line-height:1.6;color:#617898;margin:16px 0 0">Se você não fez essa solicitação, ignore este e-mail: sua senha continua a mesma.</p>
</td></tr>
<tr><td style="padding:16px 28px;border-top:1px solid #edf1f7;font-size:12px;color:#8093b4">HemoFlow · Gestão de hemocentro</td></tr>
</table></td></tr></table></body></html>""", subtype="html")
    deliver_email(message)


def send_support_email(protocol: str, category: str, subject: str, text: str, name: str, email: str):
    """Aba Suporte: envia a mensagem do usuário para a caixa de suporte (SUPPORT_EMAIL).
    O "Responder" do Gmail vai direto para o e-mail de quem escreveu (Reply-To)."""
    message = EmailMessage()
    message["Subject"] = f"[Suporte HemoFlow] {protocol} · {category} · {subject}"
    message["From"] = f"HemoFlow <{EMAIL_FROM}>"
    message["To"] = SUPPORT_EMAIL
    message["Reply-To"] = email
    message.set_content(
        f"Protocolo: {protocol}\n"
        f"Enviado por: {name} <{email}>\n"
        f"Categoria: {category}\n"
        f"Assunto: {subject}\n\n"
        f"{text}\n\n"
        "Para responder, use o botão Responder: a resposta vai para o e-mail de quem enviou."
    )
    deliver_email(message)



# ============================================================================
# 5. ERROS E VALIDAÇÕES
# ============================================================================
class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


EMAIL_RE = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]{2,}")
DUPLICATE_KEY = 1062  # código MySQL ER_DUP_ENTRY
ROW_IS_REFERENCED = 1451  # código MySQL ER_ROW_IS_REFERENCED_2 (chave estrangeira)


def valid_email(email: str) -> bool:
    return 3 <= len(email) <= 254 and EMAIL_RE.fullmatch(email) is not None


def valid_cpf(cpf: str) -> bool:
    """Confere os dois dígitos verificadores do CPF (só números, 11 dígitos).
    Sequências repetidas (000.000.000-00, 111...) passam na conta, mas não existem."""
    if len(cpf) != 11 or not cpf.isdigit() or cpf == cpf[0] * 11:
        return False
    for size in (9, 10):
        total = sum(int(cpf[i]) * (size + 1 - i) for i in range(size))
        if (total * 10) % 11 % 10 != int(cpf[size]):
            return False
    return True


def mask_cpf(cpf) -> str:
    """LGPD: a lista mostra só o meio do CPF (***.456.789-**). O número completo não sai do servidor."""
    if not cpf or len(cpf) != 11:
        return ""
    return f"***.{cpf[3:6]}.{cpf[6:9]}-**"


def duplicate_message(exc: mysql.connector.IntegrityError) -> str:
    """Traduz violações de UNIQUE do MySQL para mensagens compreensíveis."""
    text = str(getattr(exc, "msg", exc))
    if "uq_usuarios_email" in text:
        return "Já existe uma conta cadastrada com esse e-mail."
    if "uq_doadores_email" in text:
        return "Já existe um doador cadastrado com esse e-mail."
    if "uq_doadores_cpf" in text:
        return "Já existe um doador cadastrado com esse CPF."
    if "uq_profissionais_email" in text:
        return "Já existe um profissional cadastrado com esse e-mail."
    if "uq_profissionais_registro" in text:
        return "Já existe um profissional cadastrado com esse registro profissional."
    if "uq_profissionais_usuario" in text:
        return "Essa conta já está vinculada a outro profissional."
    if "uq_reserva_ativa_por_bolsa" in text:
        return "Essa bolsa já possui uma reserva ativa."
    if "uq_descartes_bolsa" in text:
        return "Essa bolsa já possui descarte registrado."
    return "Registro duplicado: já existe um cadastro com esses dados."


def v2_instalado() -> bool:
    """A migração 005 (HemoFlow 2.0) já foi aplicada neste banco?"""
    with connect_db() as db:
        cur = db.cursor()
        cur.execute("""SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
                       WHERE TABLE_SCHEMA=%s AND TABLE_NAME IN ('agenda_doacoes','estoque_niveis','codigos_login')""", (DB_NAME,))
        n = cur.fetchone()[0]
        cur.close()
    return n == 3


# ============================================================================
# 6. SERVIDOR HTTP: cabeçalhos de segurança e cookie de sessão
# ============================================================================
CSP = (
    "default-src 'self'; script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; "
    "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)


def session_cookie(value: str, max_age: int) -> str:
    cookie = f"{SESSION_COOKIE}={value}; Path=/; Max-Age={max_age}; HttpOnly; SameSite=Strict"
    return cookie + "; Secure" if COOKIE_SECURE else cookie


import sys  # noqa: E402
import rotas_v2  # noqa: E402  (rotas da versão 2.0)

rotas_v2.S = sys.modules[__name__]


class Handler(rotas_v2.RotasV2, BaseHTTPRequestHandler):
    server_version = "HemoFlow/3.0"


    # ========================================================================
    # 6.1 Respostas e segurança
    # ========================================================================
    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def drain_body(self):
        """Lê (e descarta) o corpo que ainda não foi lido. Se o servidor responder sem
        ler o que o navegador enviou (ex.: 403 antes de read_json), o Windows pode
        cortar a conexão e o navegador recebe erro de rede em vez da mensagem."""
        if getattr(self, "_body_consumed", False):
            return
        self._body_consumed = True
        try:
            remaining = int(self.headers.get("Content-Length", "0") or 0)
        except ValueError:
            return
        remaining = min(remaining, 20_000)
        while remaining > 0:
            chunk = self.rfile.read(min(remaining, 4096))
            if not chunk:
                break
            remaining -= len(chunk)

    def send_json(self, data, status=200, extra_headers=None):
        self.drain_body()
        raw = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.security_headers()
        if extra_headers:
            for name, value in extra_headers:
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(raw)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 20_000:
                raise ApiError("Corpo da requisição ausente ou muito grande.", 413)
            self._body_consumed = True
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ApiError("O conteúdo enviado deve ser um objeto JSON.")
            return data
        except json.JSONDecodeError:
            raise ApiError("JSON inválido.")

    def security_headers(self):
        """Cabeçalhos enviados em todas as respostas (API e arquivos da interface)."""
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", CSP)
        if PRODUCTION:
            self.send_header("Strict-Transport-Security", "max-age=31536000")

    def client_ip(self):
        # Localmente não há proxy: usa o IP da conexão. Na nuvem, a conexão vem do
        # proxy HTTPS da hospedagem; o IP real é o que esse proxy acrescentou ao
        # X-Forwarded-For (PROXY_HOPS posições a partir do fim). Valores mais à
        # esquerda podem ter sido inventados pelo próprio cliente, então são ignorados.
        direct = self.client_address[0] if self.client_address else "unknown"
        if not TRUST_PROXY:
            return direct
        chain = [part.strip() for part in self.headers.get("X-Forwarded-For", "").split(",") if part.strip()]
        if len(chain) >= PROXY_HOPS:
            return chain[-PROXY_HOPS][:45]
        return direct

    def session(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
            morsel = cookie.get(SESSION_COOKIE)
            token = morsel.value if morsel else ""
        except Exception:
            token = ""
        record = SESSIONS.get(token)
        if not record:
            return None
        if record["expires"] <= time.time():
            SESSIONS.pop(token, None)
            return None
        record["expires"] = time.time() + SESSION_TTL
        return record

    def require_session(self):
        record = self.session()
        if not record:
            raise ApiError("Sua sessão expirou. Entre novamente.", 401)
        return record


    # ========================================================================
    # 6.2 Rotas: cada endereço /api/... chama uma função abaixo
    # ========================================================================
    def do_GET(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/healthz":
                return self.healthz()
            if parsed.path == "/api/session":
                record = self.session()
                if not record:
                    return self.send_json({"autenticado": False}, 200)
                ctx = self.contexto_efetivo(record)
                usuario = rotas_v2.usuario_json(record, ctx)
                if record.get("como"):
                    usuario["entrou_como"] = record["como"].get("nome_como")
                return self.send_json({"autenticado": True, "usuario": usuario})
            if parsed.path.startswith("/api/"):
                if self.rota_v2("GET", parsed.path, parse_qs(parsed.query)):
                    return None
                raise ApiError("Endpoint não encontrado.", 404)
            return self.static_file(parsed.path)
        except Exception as exc:  # noqa: BLE001 - toda falha vira resposta JSON
            self.handle_exception(exc)

    def healthz(self):
        """Verificação de saúde para a plataforma de hospedagem (sem login, sem dados)."""
        try:
            with connect_db() as db:
                cur = db.cursor()
                cur.execute("SELECT 1")
                cur.fetchone()
                cur.close()
            return self.send_json({"ok": True, "banco": "ok"})
        except Exception as exc:  # noqa: BLE001
            print("Healthcheck falhou:", type(exc).__name__)
            return self.send_json({"ok": False, "banco": "indisponivel"}, 503)

    def handle_exception(self, exc):
        """Converte exceções em respostas JSON; nunca deixa a conexão sem resposta."""
        if isinstance(exc, ApiError):
            return self.send_json({"erro": str(exc)}, exc.status)
        if isinstance(exc, mysql.connector.IntegrityError) and getattr(exc, "errno", None) == DUPLICATE_KEY:
            return self.send_json({"erro": duplicate_message(exc)}, 409)
        if isinstance(exc, mysql.connector.IntegrityError):
            print("Erro de integridade:", exc)
            return self.send_json({"erro": "Os dados violam uma regra de integridade do banco."}, 409)
        if isinstance(exc, (MySQLError, RuntimeError)):
            print("Erro de banco:", exc)
            return self.send_json({"erro": "Erro ao acessar o banco de dados. Confira a configuração."}, 500)
        print("Erro interno inesperado:", type(exc).__name__, exc)
        return self.send_json({"erro": "Erro interno no servidor."}, 500)

    def do_POST(self):
        try:
            path = urlparse(self.path).path
            if path == "/api/login":
                return self.login(self.read_json())
            if path == "/api/forgot-password":
                return self.forgot_password(self.read_json())
            if path == "/api/reset-password":
                return self.reset_password(self.read_json())
            if path == "/api/logout":
                record = self.session()
                if record:
                    # Revoga o token apresentado pelo navegador.
                    cookie = SimpleCookie()
                    cookie.load(self.headers.get("Cookie", ""))
                    morsel = cookie.get(SESSION_COOKIE)
                    if morsel:
                        SESSIONS.pop(morsel.value, None)
                return self.send_json({"ok": True}, 200, [
                    ("Set-Cookie", session_cookie("", 0))
                ])
            if path == "/api/support":
                # Aba Suporte: qualquer usuário logado pode escrever.
                return self.send_support(self.read_json(), self.require_session())
            if self.rota_v2("POST", path, {}):
                return None
            raise ApiError("Endpoint não encontrado.", 404)
        except Exception as exc:  # noqa: BLE001 - toda falha vira resposta JSON
            self.handle_exception(exc)

    def do_DELETE(self):
        try:
            raise ApiError("Endpoint não encontrado.", 404)
        except Exception as exc:  # noqa: BLE001
            self.handle_exception(exc)


    # ========================================================================
    # 6.3 Login, bloqueio de conta e recuperação de senha
    # ========================================================================
    def forgot_password(self, data):
        email = str(data.get("email", "")).strip().lower()[:254]
        # Same response whether the account exists or not, to avoid account enumeration.
        generic = {"ok": True, "mensagem": "Se o e-mail estiver cadastrado, você receberá instruções para recuperar a senha."}
        if not valid_email(email):
            raise ApiError("Informe um e-mail válido.")
        if not email_configured():
            raise ApiError("O envio de e-mail ainda não está configurado no servidor.", 503)
        ip, now = self.client_ip(), time.time()
        recent = [stamp for stamp in RESET_REQUESTS.get(ip, []) if now - stamp < LOGIN_WINDOW]
        if len(recent) >= MAX_RESET_REQUESTS:
            RESET_REQUESTS[ip] = recent
            raise ApiError("Muitas solicitações. Aguarde 15 minutos e tente novamente.", 429)
        RESET_REQUESTS[ip] = recent + [now]
        ensure_password_reset_table()
        with connect_db() as db:
            cur = db.cursor(dictionary=True)
            cur.execute("""
                SELECT u.id, u.email, u.nome,
                       EXISTS(SELECT 1 FROM recuperacao_senhas r WHERE r.usuario_id = u.id
                              AND r.criado_em > DATE_SUB(NOW(), INTERVAL 1 MINUTE)) AS pedido_recente
                FROM usuarios u WHERE u.email=%s AND u.status='ATIVO' LIMIT 1
            """, (email,))
            user = cur.fetchone()
            cur.close()
        # Conta inexistente, ou já recebeu um link no último minuto: mesma resposta, sem novo e-mail.
        if not user or user.get("pedido_recente"):
            return self.send_json(generic)
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        with connect_db() as db:
            cur = db.cursor()
            cur.execute("UPDATE recuperacao_senhas SET usado_em=NOW() WHERE usuario_id=%s AND usado_em IS NULL", (user["id"],))
            # Validade calculada pelo próprio MySQL: não depende do fuso do servidor Python.
            cur.execute(
                "INSERT INTO recuperacao_senhas (usuario_id,token_hash,expira_em) "
                "VALUES (%s,%s,DATE_ADD(NOW(), INTERVAL 30 MINUTE))",
                (user["id"], token_hash)
            )
            db.commit()
            cur.close()
        base_url = PUBLIC_URL or f"http://{'127.0.0.1' if HOST == '0.0.0.0' else HOST}:{PORT}"
        reset_url = f"{base_url}/?reset_token={raw_token}"
        try:
            send_recovery_email(user["email"], reset_url, user.get("nome") or "")
        except Exception as exc:
            # Resposta igual à de e-mail inexistente: um erro 502 só para contas que
            # existem revelaria quais e-mails estão cadastrados. A falha fica no log.
            print("Falha ao enviar e-mail de recuperação:", type(exc).__name__, exc)
            with connect_db() as db:
                cur = db.cursor()
                cur.execute("UPDATE recuperacao_senhas SET usado_em=NOW() WHERE token_hash=%s", (token_hash,))
                db.commit()
                cur.close()
        return self.send_json(generic)

    def reset_password(self, data):
        token = str(data.get("token", ""))
        password = data.get("senha", "")
        if not isinstance(password, str) or len(password) < 10 or len(password) > 128:
            raise ApiError("A nova senha deve ter entre 10 e 128 caracteres.")
        if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
            raise ApiError("A nova senha deve conter letras e números.")
        if not token or len(token) > 200:
            raise ApiError("Link de recuperação inválido ou expirado.", 400)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        ensure_password_reset_table()
        with connect_db() as db:
            cur = db.cursor(dictionary=True)
            cur.execute("""
                SELECT r.id, r.usuario_id FROM recuperacao_senhas r
                JOIN usuarios u ON u.id = r.usuario_id AND u.status = 'ATIVO'
                WHERE r.token_hash=%s AND r.usado_em IS NULL AND r.expira_em > NOW()
                LIMIT 1
            """, (token_hash,))
            reset = cur.fetchone()
            cur.close()
        if not reset:
            raise ApiError("Link de recuperação inválido ou expirado.", 400)
        new_hash = password_hash(password)
        with connect_db() as db:
            cur = db.cursor()
            # Marca o token como usado primeiro; se outro pedido já usou, não troca a senha.
            cur.execute("UPDATE recuperacao_senhas SET usado_em=NOW() WHERE id=%s AND usado_em IS NULL", (reset["id"],))
            if cur.rowcount != 1:
                db.rollback()
                cur.close()
                raise ApiError("Link de recuperação inválido ou expirado.", 400)
            cur.execute("""UPDATE usuarios SET senha_hash=%s, tentativas_falhas=0, bloqueado_ate=NULL
                           WHERE id=%s""", (new_hash, reset["usuario_id"]))
            db.commit()
            cur.close()
        # Encerra sessões abertas do usuário após a troca de senha.
        for key in [k for k, v in SESSIONS.items() if v["id"] == reset["usuario_id"]]:
            SESSIONS.pop(key, None)
        return self.send_json({"ok": True, "mensagem": "Senha alterada. Você já pode entrar com a nova senha."})

    def login(self, data):
        ip = self.client_ip()
        now = time.time()
        attempts = [t for t in LOGIN_ATTEMPTS.get(ip, []) if now - t < LOGIN_WINDOW]
        if len(attempts) >= MAX_LOGIN_ATTEMPTS:
            LOGIN_ATTEMPTS[ip] = attempts
            raise ApiError("Muitas tentativas. Aguarde 15 minutos e tente novamente.", 429)
        email = str(data.get("email", "")).strip().lower()[:254]
        password = data.get("senha", "")
        if not email or not isinstance(password, str) or not password:
            raise ApiError("Informe e-mail e senha.")
        with connect_db() as db:
            cur = db.cursor(dictionary=True)
            cur.execute("""
                SELECT u.id, u.nome, u.email, u.senha_hash, u.status,
                       (u.bloqueado_ate IS NOT NULL AND u.bloqueado_ate > NOW()) AS bloqueada
                FROM usuarios u WHERE u.email=%s LIMIT 1
            """, (email,))
            user = cur.fetchone()
            cur.close()
        # Bloqueio por conta: além do limite por IP, 5 senhas erradas seguidas na
        # mesma conta a bloqueiam por 15 minutos (protege contra tentativas
        # distribuídas e contra o IP compartilhado do proxy na nuvem).
        if user and user.get("bloqueada"):
            attempts.append(now)
            LOGIN_ATTEMPTS[ip] = attempts
            raise ApiError("Conta bloqueada temporariamente por excesso de tentativas. "
                           "Aguarde 15 minutos ou use “Esqueceu sua senha?”.", 429)
        if not user or user.get("status") != "ATIVO" or not verify_password(password, user.get("senha_hash") or ""):
            attempts.append(now)
            LOGIN_ATTEMPTS[ip] = attempts
            if user:
                self.register_failed_login(user["id"])
            raise ApiError("E-mail ou senha incorretos, ou usuário inativo.", 401)
        LOGIN_ATTEMPTS.pop(ip, None)
        with connect_db() as db:
            cur = db.cursor()
            cur.execute("""UPDATE usuarios SET tentativas_falhas=0, bloqueado_ate=NULL, ultimo_login=NOW()
                           WHERE id=%s""", (user["id"],))
            db.commit()
            cur.close()
        token, ctx = rotas_v2.criar_sessao(self, user)
        self.send_json({"ok": True, "usuario": rotas_v2.usuario_json(user, ctx)}, 200,
                       [("Set-Cookie", session_cookie(token, SESSION_TTL))])

    def register_failed_login(self, user_id):
        """Conta a senha errada; na 5ª seguida, bloqueia a conta por 15 minutos e zera o contador."""
        with connect_db() as db:
            cur = db.cursor()
            cur.execute("""
                UPDATE usuarios
                SET bloqueado_ate = IF(tentativas_falhas + 1 >= %s, DATE_ADD(NOW(), INTERVAL 15 MINUTE), bloqueado_ate),
                    tentativas_falhas = IF(tentativas_falhas + 1 >= %s, 0, tentativas_falhas + 1)
                WHERE id=%s
            """, (MAX_ACCOUNT_FAILURES, MAX_ACCOUNT_FAILURES, user_id))
            db.commit()
            cur.close()


    # ========================================================================
    # 6.10 Suporte (aba "Suporte": mensagem por e-mail para a equipe)
    # ========================================================================
    def send_support(self, data, record):
        category = str(data.get("categoria", "")).strip()
        subject = " ".join(str(data.get("assunto", "")).split())
        text = str(data.get("mensagem", "")).strip()
        if category not in SUPPORT_CATEGORIES:
            raise ApiError("Selecione o tipo da mensagem.")
        if not 3 <= len(subject) <= 120:
            raise ApiError("Escreva um assunto (de 3 a 120 caracteres).")
        if not 10 <= len(text) <= 3000:
            raise ApiError("Escreva a mensagem (de 10 a 3000 caracteres).")
        if not email_configured() or not SUPPORT_EMAIL:
            raise ApiError("O envio de mensagens ainda não foi configurado. Avise o administrador.", 503)
        # Limite por usuário: evita que o sistema seja usado para disparar e-mails em massa.
        now = time.time()
        recent = [t for t in SUPPORT_REQUESTS.get(record["id"], []) if now - t < SUPPORT_WINDOW]
        if len(recent) >= MAX_SUPPORT_REQUESTS:
            raise ApiError("Você já enviou várias mensagens na última hora. Aguarde um pouco e tente de novo.", 429)
        protocol = "SUP-" + datetime.now(TZ).strftime("%Y%m%d") + "-" + secrets.token_hex(2).upper()
        try:
            send_support_email(protocol, category, subject, text, record["nome"], record["email"])
        except (OSError, smtplib.SMTPException) as exc:
            print("Falha ao enviar mensagem de suporte:", type(exc).__name__, exc)
            raise ApiError("Não foi possível enviar a mensagem agora. Tente novamente em alguns minutos.", 502)
        recent.append(now)
        SUPPORT_REQUESTS[record["id"]] = recent
        with connect_db() as db:
            cur = db.cursor()
            cur.execute("""
                INSERT INTO historico_auditoria
                (usuario_id,acao,modulo,entidade,entidade_id,detalhes_json)
                VALUES (%s,'ENVIAR','suporte','mensagem',%s,%s)
            """, (record["id"], protocol, json.dumps({"categoria": category, "assunto": subject})))
            db.commit()
            cur.close()
        self.send_json({"ok": True, "protocolo": protocol,
                        "mensagem": f"Mensagem enviada! Protocolo {protocol}. A resposta chegará no seu e-mail."})

    # ========================================================================
    # 6.9 Arquivos das telas (pasta static/)
    # ========================================================================
    def static_file(self, path):
        relative = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (BASE_DIR / "static" / relative).resolve()
        static_root = (BASE_DIR / "static").resolve()
        if not target.is_relative_to(static_root) or not target.is_file():
            self.send_error(404, "Página não encontrada")
            return
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".png": "image/png",
            ".webmanifest": "application/manifest+json",
            ".webp": "image/webp",
            ".json": "application/json",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
        }.get(target.suffix.lower(), "application/octet-stream")
        raw = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        # Evita que o navegador continue usando um app.js/index.html antigo em cache.
        self.send_header("Cache-Control", "no-cache")
        self.security_headers()
        self.end_headers()
        self.wfile.write(raw)

    def send_error(self, code, message=None, explain=None):
        if self.path.startswith("/api/"):
            return self.send_json({"erro": message or "Erro na requisição."}, code)
        super().send_error(code, message, explain)



# ============================================================================
# Servidor com várias conexões ao mesmo tempo
# ============================================================================
class HemoFlowServer(ThreadingHTTPServer):
    # No Windows, SO_REUSEADDR permite que DOIS servidores escutem a mesma porta;
    # um servidor antigo esquecido continuaria respondendo com arquivos antigos.
    # Desligado no Windows, iniciar com a porta ocupada passa a dar erro claro.
    allow_reuse_address = os.name != "nt"
    daemon_threads = True



# ============================================================================
# 7. INSTALAÇÃO AUTOMÁTICA (banco novo na nuvem)
# ============================================================================
INSTALL_DIR = BASE_DIR / "banco" / "instalacao"


def sql_statements(sql_text: str):
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


def auto_install_schema() -> bool:
    """HEMOFLOW_AUTO_INSTALL=1: se o banco estiver VAZIO (sem a tabela usuarios), cria a
    estrutura e os dados de referência (perfis, permissões, tipos sanguíneos) a partir de
    banco/instalacao/. Nunca roda num banco que já tem o HemoFlow e não copia dados pessoais.
    Pensado para a nuvem, onde o banco não fica exposto à internet."""
    if os.environ.get("HEMOFLOW_AUTO_INSTALL", "0") != "1":
        return False
    conn = mysql.connector.connect(**{**db_config(), "autocommit": True})
    try:
        cur = conn.cursor()
        cur.execute("""SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
                       WHERE TABLE_SCHEMA=%s AND TABLE_NAME='usuarios'""", (DB_NAME,))
        if cur.fetchone()[0]:
            cur.close()
            return False
        files = sorted(INSTALL_DIR.glob("0*.sql"))
        if not files:
            raise RuntimeError(f"Arquivos de instalação não encontrados em {INSTALL_DIR}.")
        print("Banco vazio: instalando a estrutura do HemoFlow...")
        for path in files:
            commands = list(sql_statements(path.read_text(encoding="utf-8")))
            for command in commands:
                cur.execute(command)
            print(f"  OK: {path.name} ({len(commands)} comandos)")
        cur.close()
        print("Estrutura instalada. Crie o primeiro administrador com: python scripts/criar_administrador.py")
        return True
    finally:
        conn.close()



# ============================================================================
# 8. INÍCIO
# ============================================================================
def main():
    print(f"HemoFlow ({'produção' if PRODUCTION else 'desenvolvimento'}) escutando em http://{HOST}:{PORT}")
    print(f"MySQL: {DB_HOST}:{DB_PORT}/{DB_NAME} (usuário {DB_USER}, TLS: {DB_SSL})")
    print(f"Fuso: {TIMEZONE if TZ else 'relógio local'} · hoje = {hoje().isoformat()}")
    print("E-mail:", "Brevo (HTTPS)" if BREVO_API_KEY else ("Gmail (SMTP)" if EMAIL_USER else "não configurado"))
    print(f"Arquivos servidos de: {BASE_DIR / 'static'}")
    if PRODUCTION:
        if not PUBLIC_URL.startswith("https://"):
            print("AVISO: defina HEMOFLOW_PUBLIC_URL com o endereço https:// do sistema (link de recuperação de senha).")
        if DB_SSL == "disabled":
            print("AVISO: conexão com o MySQL sem TLS em produção. Use HEMOFLOW_DB_SSL=required ou verify.")
    try:
        conn = connect_db()
        conn.close()
        auto_install_schema()
        if not v2_instalado():
            print("AVISO: a migração 005 (HemoFlow 2.0) não foi aplicada neste banco.")
            print("  Execute: python scripts/migracao_005_v2.py  (com usuário administrativo)")
        server = HemoFlowServer((HOST, PORT), Handler)
    except OSError as exc:
        print(f"Não foi possível usar a porta {PORT}: {exc}")
        print("Provavelmente outro servidor HemoFlow já está aberto. Feche-o (Ctrl+C no terminal dele) e tente de novo.")
        return 1
    except (MySQLError, RuntimeError) as exc:
        print("Não foi possível iniciar o HemoFlow:", exc)
        return 1
    print("Servidor pronto.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
