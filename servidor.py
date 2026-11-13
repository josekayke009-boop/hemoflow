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
        6.5 Estoque e bolsas ....... painel, bolsas, movimentações
        6.6 Doadores ............... listar, cadastrar, revisar, excluir
        6.7 Notificações ........... alertas do sino, baixa e preferência
        6.8 Contas e profissionais . contas de acesso e cadastro de profissionais
        6.9 Arquivos das telas ..... HTML, CSS, JS e imagens da pasta static/
   7. INSTALAÇÃO AUTOMÁTICA ........ cria as tabelas num banco novo (nuvem)
   8. INÍCIO ....................... main()

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
import uuid
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


def expired(row):
    value = row["data_validade"]
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value < hoje()
    return str(value) < hoje().isoformat()


def serialize_date(value):
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def bag_json(row):
    item = dict(row)
    item["data_coleta"] = serialize_date(item.get("data_coleta"))
    item["data_validade"] = serialize_date(item.get("data_validade"))
    item["criado_em"] = serialize_date(item.get("criado_em"))
    item["vencida"] = expired(item)
    item["status_label"] = STATUS_LABELS.get(item.get("status"), item.get("status"))
    item["tipo_sanguineo"] = item.get("tipo_sanguineo")
    item["localizacao"] = item.get("localizacao")
    return item


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
    if not EMAIL_USER or not EMAIL_PASSWORD:
        raise RuntimeError("Configure HEMOFLOW_EMAIL_USER e HEMOFLOW_EMAIL_PASSWORD.")
    first = (name or "").split(" ")[0]
    greeting = f"Olá, {first}!" if first else "Olá!"
    message = EmailMessage()
    message["Subject"] = "Redefinição de senha — HemoFlow"
    message["From"] = f"HemoFlow <{EMAIL_USER}>"
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
    with smtp_connection() as server:
        server.send_message(message)



# ============================================================================
# 5. ERROS E VALIDAÇÕES
# ============================================================================
class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


EMAIL_RE = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]{2,}")
# Notificações: limites de estoque disponível por tipo sanguíneo e prazo de revisão de cadastro.
STOCK_CRITICAL = 5
STOCK_LOW = 10
DONOR_REVIEW_MONTHS = 12


def notification_pref_key(user_id) -> str:
    return f"notificacoes.usuario.{int(user_id)}"


def notification_seen_key(user_id) -> str:
    return f"notificacoes.vistas.usuario.{int(user_id)}"


DUPLICATE_KEY = 1062  # código MySQL ER_DUP_ENTRY
ROW_IS_REFERENCED = 1451  # código MySQL ER_ROW_IS_REFERENCED_2 (chave estrangeira)


def valid_email(email: str) -> bool:
    return 3 <= len(email) <= 254 and EMAIL_RE.fullmatch(email) is not None


def duplicate_message(exc: mysql.connector.IntegrityError) -> str:
    """Traduz violações de UNIQUE do MySQL para mensagens compreensíveis."""
    text = str(getattr(exc, "msg", exc))
    if "uq_usuarios_email" in text:
        return "Já existe uma conta cadastrada com esse e-mail."
    if "uq_doadores_email" in text:
        return "Já existe um doador cadastrado com esse e-mail."
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


# Itens da migração 001 (scripts/migracao_001_email_unico.py).
# Só resultados positivos ficam em cache: aplicar a migração com o servidor
# aberto passa a valer na próxima requisição, sem reiniciar.
MIGRATION_001 = {
    ("doadores", "uq_doadores_email"): "index",
    ("profissionais", "email"): "column",
    ("profissionais", "uq_profissionais_email"): "index",
}
MIGRATION_002 = {("doadores", column): "column" for column in ADDRESS_FIELDS}
SCHEMA_KINDS = {**MIGRATION_001, **MIGRATION_002}
_SCHEMA_OK: set = set()


def schema_has(table: str, name: str) -> bool:
    key = (table, name)
    if key in _SCHEMA_OK:
        return True
    if SCHEMA_KINDS.get(key) == "column":
        sql = """SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                 WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s LIMIT 1"""
    else:
        sql = """SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
                 WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND INDEX_NAME=%s LIMIT 1"""
    with connect_db() as db:
        cur = db.cursor()
        cur.execute(sql, (DB_NAME, table, name))
        found = cur.fetchone() is not None
        cur.close()
    if found:
        _SCHEMA_OK.add(key)
    return found


def pending_migration_002() -> list[str]:
    return [f"{table}.{name}" for table, name in MIGRATION_002 if not schema_has(table, name)]


def donor_address_ready() -> bool:
    return not pending_migration_002()


def pending_migration_001() -> list[str]:
    return [f"{table}.{name}" for table, name in MIGRATION_001 if not schema_has(table, name)]



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


class Handler(BaseHTTPRequestHandler):
    server_version = "HemoFlow/2.2"


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
                is_admin = self.is_admin_profile(record["id"])
                profiles, permissions = self.access_profile(record["id"])
                return self.send_json({
                    "autenticado": True,
                    "usuario": {
                        "id": record["id"],
                        "nome": record["nome"],
                        "email": record["email"],
                        "is_admin": is_admin,
                        "perfis": profiles,
                        "permissoes": permissions,
                    }
                })
            if parsed.path.startswith("/api/"):
                record = self.require_session()
                actor_id = record["id"]
                if parsed.path == "/api/access-accounts":
                    self.require_admin_profile(actor_id, "consultar contas de acesso")
                    return self.list_access_accounts()
                if parsed.path == "/api/summary":
                    self.require_permission(actor_id, "painel.consultar")
                    return self.summary()
                if parsed.path == "/api/bags":
                    self.require_permission(actor_id, "estoque.consultar")
                    return self.list_bags(parse_qs(parsed.query))
                if parsed.path == "/api/movements":
                    self.require_permission(actor_id, "estoque.consultar")
                    return self.list_movements()
                if parsed.path == "/api/donors":
                    self.require_permission(actor_id, "doadores.consultar")
                    return self.list_donors(parse_qs(parsed.query))
                if parsed.path == "/api/notifications":
                    return self.list_notifications(actor_id)
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
            record = self.require_session()
            actor_id = record["id"]
            if path == "/api/access-accounts":
                self.require_admin_profile(actor_id, "criar contas de acesso")
                return self.create_access_account(self.read_json(), actor_id)
            if path == "/api/bags":
                self.require_permission(actor_id, "estoque.bolsa.criar")
                return self.create_bag(self.read_json(), actor_id)
            if path == "/api/donors":
                self.require_permission(actor_id, "doadores.criar")
                return self.create_donor(self.read_json(), actor_id)
            if path == "/api/notifications/read":
                return self.mark_notifications_read(self.read_json(), actor_id)
            if path == "/api/notifications/preferences":
                # Cada usuário liga/desliga as próprias notificações.
                return self.save_notification_preference(self.read_json(), actor_id)
            review = re.fullmatch(r"/api/donors/(\d+)/review", path)
            if review:
                self.require_permission(actor_id, "doadores.editar")
                return self.review_donor(int(review.group(1)), actor_id)
            if path == "/api/professionals":
                # Restrição explícita: só ADMINISTRADOR pode cadastrar profissionais,
                # mesmo que outro perfil tenha profissionais.gerenciar no banco.
                self.require_admin_profile(actor_id, "cadastrar profissionais")
                return self.create_professional(self.read_json(), actor_id)
            match = re.fullmatch(r"/api/bags/(\d+)/transition", path)
            if match:
                data = self.read_json()
                status = str(data.get("status", "")).upper()
                required = {
                    "RESERVADA": "estoque.bolsa.reservar",
                    "TRANSFUNDIDA": "estoque.bolsa.transfundir",
                    "DESCARTADA": "estoque.bolsa.descartar",
                    "DISPONIVEL": "estoque.bolsa.liberar",
                    "QUARENTENA": "estoque.bolsa.editar",
                }.get(status)
                if not required:
                    raise ApiError("Status inválido.")
                self.require_permission(actor_id, required)
                return self.transition(int(match.group(1)), data, actor_id)
            raise ApiError("Endpoint não encontrado.", 404)
        except Exception as exc:  # noqa: BLE001 - toda falha vira resposta JSON
            self.handle_exception(exc)

    def do_DELETE(self):
        try:
            path = urlparse(self.path).path
            record = self.require_session()
            match = re.fullmatch(r"/api/donors/(\d+)", path)
            if match:
                # "Editar e inativar doadores": ADMINISTRADOR e RESPONSAVEL_TECNICO.
                self.require_permission(record["id"], "doadores.editar")
                return self.delete_donor(int(match.group(1)), record["id"])
            raise ApiError("Endpoint não encontrado.", 404)
        except Exception as exc:  # noqa: BLE001 - toda falha vira resposta JSON
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
        if not EMAIL_USER or not EMAIL_PASSWORD:
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
        is_admin = self.is_admin_profile(user["id"])
        profiles, permissions = self.access_profile(user["id"])
        if not profiles:
            raise ApiError("Esta conta não possui perfil de acesso. Procure o administrador.", 403)
        token = secrets.token_urlsafe(32)
        # Remove sessões expiradas para limitar crescimento em memória.
        for old_token in [key for key, value in SESSIONS.items() if value["expires"] <= now]:
            SESSIONS.pop(old_token, None)
        SESSIONS[token] = {
            "id": user["id"], "nome": user["nome"], "email": user["email"],
            "is_admin": is_admin,
            "expires": now + SESSION_TTL,
        }
        cookie = session_cookie(token, SESSION_TTL)  # inclui Secure em produção (HTTPS)
        self.send_json({
            "ok": True,
            "usuario": {
                "id": user["id"],
                "nome": user["nome"],
                "email": user["email"],
                "is_admin": is_admin,
                "perfis": profiles,
                "permissoes": permissions,
            }
        }, 200, [("Set-Cookie", cookie)])

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
    # 6.4 Perfis e permissões
    # ========================================================================
    def require_operator(self, actor_id):
        if not isinstance(actor_id, int) or actor_id <= 0:
            raise ApiError("Usuário autenticado inválido.", 401)
        return actor_id

    def is_admin_profile(self, actor_id):
        """Consulta no MySQL se o usuário possui o perfil ADMINISTRADOR."""
        with connect_db() as db:
            cur = db.cursor()
            cur.execute("""
                SELECT 1
                FROM usuario_perfis up
                JOIN perfis pf ON pf.id = up.perfil_id
                WHERE up.usuario_id = %s AND pf.nome = 'ADMINISTRADOR'
                LIMIT 1
            """, (actor_id,))
            allowed = cur.fetchone() is not None
            cur.close()
        return allowed

    def require_admin_profile(self, actor_id, action="realizar esta operação"):
        """Bloqueia no servidor qualquer gerenciamento por não administradores."""
        if not self.is_admin_profile(actor_id):
            raise ApiError(f"Somente o perfil ADMINISTRADOR pode {action}.", 403)

    def access_profile(self, actor_id):
        """Perfis e códigos de permissão do usuário (usados só para ajustar a interface;
        a autorização real continua sendo verificada em cada rota)."""
        with connect_db() as db:
            cur = db.cursor()
            cur.execute("""
                SELECT pf.nome FROM usuario_perfis up JOIN perfis pf ON pf.id=up.perfil_id
                WHERE up.usuario_id=%s ORDER BY pf.id
            """, (actor_id,))
            profiles = [row[0] for row in cur.fetchall()]
            cur.execute("""
                SELECT DISTINCT p.codigo
                FROM usuario_perfis up
                JOIN perfil_permissoes pp ON pp.perfil_id = up.perfil_id
                JOIN permissoes p ON p.id = pp.permissao_id
                WHERE up.usuario_id=%s ORDER BY p.codigo
            """, (actor_id,))
            permissions = [row[0] for row in cur.fetchall()]
            cur.close()
        return profiles, permissions

    def require_permission(self, actor_id, permission_code):
        """Administrador é superusuário; os demais seguem a matriz de permissões."""
        if not self.has_permission(actor_id, permission_code):
            raise ApiError("Você não tem permissão para realizar esta operação.", 403)

    def has_permission(self, actor_id, permission_code):
        if self.is_admin_profile(actor_id):
            return True
        with connect_db() as db:
            cur = db.cursor()
            cur.execute("""
                SELECT 1
                FROM usuario_perfis up
                JOIN perfil_permissoes pp ON pp.perfil_id = up.perfil_id
                JOIN permissoes p ON p.id = pp.permissao_id
                WHERE up.usuario_id = %s AND p.codigo = %s
                LIMIT 1
            """, (actor_id, permission_code))
            allowed = cur.fetchone() is not None
            cur.close()
        return allowed


    # ========================================================================
    # 6.5 Estoque: painel, bolsas e movimentações
    # ========================================================================
    def summary(self):
        today = hoje()
        with connect_db() as db:
            cur = db.cursor(dictionary=True)
            cur.execute("SELECT COUNT(*) AS n FROM bolsas")
            total = cur.fetchone()["n"]
            cur.execute("""
                SELECT ts.codigo AS tipo_sanguineo, COUNT(*) AS n
                FROM bolsas b JOIN tipos_sanguineos ts ON ts.id=b.tipo_sanguineo_id
                WHERE b.status='DISPONIVEL' AND b.data_validade >= %s
                GROUP BY ts.codigo
            """, (today,))
            grouped = {r["tipo_sanguineo"]: r["n"] for r in cur.fetchall()}
            cur.execute("SELECT COUNT(*) AS n FROM bolsas WHERE status='DISPONIVEL' AND data_validade >= %s", (today,))
            available = cur.fetchone()["n"]
            cur.execute("""
                SELECT COUNT(*) AS n FROM bolsas
                WHERE data_validade < %s AND status NOT IN ('TRANSFUNDIDA','DESCARTADA')
            """, (today,))
            attention = cur.fetchone()["n"]
            cur.execute("""
                SELECT COUNT(*) AS n FROM bolsas
                WHERE data_validade BETWEEN %s AND DATE_ADD(%s, INTERVAL 7 DAY)
                  AND status NOT IN ('TRANSFUNDIDA','DESCARTADA')
            """, (today, today))
            near = cur.fetchone()["n"]
            cur.close()
        self.send_json({
            "total": total, "disponiveis": available, "vencidas": attention,
            "vencem_em_7_dias": near,
            "por_tipo": {t: grouped.get(t, 0) for t in sorted(BLOOD_TYPES)},
            "hoje": today.isoformat(),
        })

    def list_bags(self, query):
        clauses, params = [], []
        blood = query.get("tipo", [""])[0].upper()
        status = query.get("status", [""])[0].upper()
        search = query.get("q", [""])[0].strip()[:100]
        if blood:
            if blood not in BLOOD_TYPES:
                raise ApiError("Tipo sanguíneo inválido.")
            clauses.append("ts.codigo=%s")
            params.append(blood)
        if status:
            if status not in STATUSES:
                raise ApiError("Status inválido.")
            clauses.append("b.status=%s")
            params.append(status)
        if search:
            clauses.append("(b.codigo LIKE %s OR la.nome LIKE %s OR ts.codigo LIKE %s)")
            params.extend([f"%{search}%"] * 3)
        sql = """
            SELECT b.id,b.codigo,ts.codigo AS tipo_sanguineo,b.volume_ml,
                   b.data_coleta,b.data_validade,la.nome AS localizacao,b.status,
                   NULL AS identificador_doador,COALESCE(b.observacoes,'') AS observacoes,
                   b.criado_em
            FROM bolsas b
            JOIN tipos_sanguineos ts ON ts.id=b.tipo_sanguineo_id
            JOIN locais_armazenamento la ON la.id=b.local_id
        """
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY b.data_validade ASC, b.id DESC LIMIT 500"
        with connect_db() as db:
            cur = db.cursor(dictionary=True)
            cur.execute(sql, params)
            rows = cur.fetchall()
            cur.close()
        self.send_json([bag_json(r) for r in rows])

    def create_bag(self, data, actor_id):
        actor = self.require_operator(actor_id)
        blood = str(data.get("tipo_sanguineo", "")).upper()
        if blood not in BLOOD_TYPES:
            raise ApiError("Selecione um tipo sanguíneo válido.")
        try:
            volume = int(data.get("volume_ml", 0))
        except (TypeError, ValueError):
            raise ApiError("Volume deve ser um número inteiro.")
        if not 1 <= volume <= 1000:
            raise ApiError("Volume deve estar entre 1 e 1000 ml.")
        try:
            collected = parse_date(data.get("data_coleta"), "data de coleta")
            expiry = parse_date(data.get("data_validade"), "data de validade")
        except ValueError as exc:
            raise ApiError(str(exc))
        if expiry < collected:
            raise ApiError("A validade não pode ser anterior à coleta.")
        if expiry < hoje():
            raise ApiError("Não é possível cadastrar uma bolsa já vencida como nova entrada.")
        location = str(data.get("localizacao", "")).strip()[:100]
        if not location:
            raise ApiError("Informe a localização da bolsa.")
        status = str(data.get("status", "DISPONIVEL")).upper()
        if status not in {"DISPONIVEL", "QUARENTENA"}:
            raise ApiError("Uma nova bolsa deve iniciar disponível ou em quarentena.")
        note = str(data.get("observacoes", "")).strip()[:2000]
        code = "HF-" + uuid.uuid4().hex[:10].upper()
        conn = connect_db()
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT id FROM tipos_sanguineos WHERE codigo=%s AND ativo=TRUE", (blood,))
            type_row = cur.fetchone()
            if not type_row:
                raise ApiError("Tipo sanguíneo não cadastrado no banco.", 500)
            cur.execute("SELECT id FROM hemocomponentes WHERE codigo='CONCENTRADO_HEMACIAS' AND ativo=TRUE")
            component = cur.fetchone()
            if not component:
                raise ApiError("Hemocomponente padrão não cadastrado.", 500)
            cur.execute("SELECT id FROM locais_armazenamento WHERE nome=%s AND ativo=TRUE", (location,))
            loc = cur.fetchone()
            if not loc:
                cur.execute("INSERT INTO locais_armazenamento (nome,descricao,ativo) VALUES (%s,%s,TRUE)",
                            (location, "Local criado pelo protótipo acadêmico"))
                loc_id = cur.lastrowid
            else:
                loc_id = loc["id"]
            cur.execute("""
                INSERT INTO bolsas
                (codigo,tipo_sanguineo_id,hemocomponente_id,local_id,volume_ml,
                 data_coleta,data_validade,status,observacoes,criado_por)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (code, type_row["id"], component["id"], loc_id, volume,
                  collected, expiry, status, note, actor))
            bag_id = cur.lastrowid
            cur.execute("""
                INSERT INTO movimentacoes_estoque
                (bolsa_id,tipo_movimentacao,status_anterior,status_novo,
                 local_destino_id,responsavel_id,motivo)
                VALUES (%s,'ENTRADA',NULL,%s,%s,%s,'Cadastro inicial')
            """, (bag_id, status, loc_id, actor))
            cur.execute("""
                INSERT INTO historico_auditoria
                (usuario_id,acao,modulo,entidade,entidade_id,detalhes_json)
                VALUES (%s,'CRIAR','estoque','bolsas',%s,%s)
            """, (actor, str(bag_id), json.dumps({"codigo": code, "status": status}))
            )
            conn.commit()
            cur.execute("""
                SELECT b.id,b.codigo,ts.codigo AS tipo_sanguineo,b.volume_ml,
                       b.data_coleta,b.data_validade,la.nome AS localizacao,b.status,
                       NULL AS identificador_doador,COALESCE(b.observacoes,'') AS observacoes,
                       b.criado_em
                FROM bolsas b
                JOIN tipos_sanguineos ts ON ts.id=b.tipo_sanguineo_id
                JOIN locais_armazenamento la ON la.id=b.local_id
                WHERE b.id=%s
            """, (bag_id,))
            result = bag_json(cur.fetchone())
            cur.close()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        self.send_json(result, 201)

    def transition(self, bag_id, data, actor_id):
        actor = self.require_operator(actor_id)
        new_status = str(data.get("status", "")).upper()
        if new_status not in STATUSES:
            raise ApiError("Status inválido.")
        note = str(data.get("observacao", "")).strip()[:2000]
        conn = connect_db()
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT b.*,ts.codigo AS tipo_sanguineo,la.nome AS localizacao
                FROM bolsas b
                JOIN tipos_sanguineos ts ON ts.id=b.tipo_sanguineo_id
                JOIN locais_armazenamento la ON la.id=b.local_id
                WHERE b.id=%s FOR UPDATE
            """, (bag_id,))
            row = cur.fetchone()
            if row is None:
                raise ApiError("Bolsa não encontrada.", 404)
            if new_status not in TRANSITIONS.get(row["status"], set()):
                raise ApiError(f"Não é permitido alterar de {row['status']} para {new_status}.", 409)
            if new_status == "TRANSFUNDIDA" and expired(row):
                raise ApiError("Bolsa vencida não pode ser registrada como transfundida.", 409)
            cur.execute("UPDATE bolsas SET status=%s WHERE id=%s", (new_status, bag_id))
            cur.execute("""
                INSERT INTO movimentacoes_estoque
                (bolsa_id,tipo_movimentacao,status_anterior,status_novo,
                 local_origem_id,local_destino_id,responsavel_id,motivo)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (bag_id, {
                "RESERVADA":"RESERVA", "DISPONIVEL":"LIBERACAO",
                "TRANSFUNDIDA":"TRANSFUSAO", "DESCARTADA":"DESCARTE",
                "QUARENTENA":"QUARENTENA"
            }[new_status], row["status"], new_status, row["local_id"], row["local_id"], actor, note))
            # Mantém a tabela reservas coerente com o status da bolsa.
            if new_status == "RESERVADA":
                cur.execute("""
                    INSERT INTO reservas (bolsa_id, status, reservada_por, motivo)
                    VALUES (%s,'ATIVA',%s,%s)
                """, (bag_id, actor, note or None))
            elif row["status"] == "RESERVADA":
                closing = {"TRANSFUNDIDA": "CONCLUIDA", "DISPONIVEL": "LIBERADA"}.get(new_status, "CANCELADA")
                cur.execute("""
                    UPDATE reservas SET status=%s, liberada_em=NOW()
                    WHERE bolsa_id=%s AND status='ATIVA'
                """, (closing, bag_id))
            if new_status == "DESCARTADA":
                cur.execute("""
                    INSERT INTO descartes (bolsa_id,motivo_codigo,justificativa,descartada_por)
                    VALUES (%s,%s,%s,%s)
                """, (bag_id, "OUTRO", note or "Descarte registrado no protótipo", actor))
            cur.execute("""
                INSERT INTO historico_auditoria
                (usuario_id,acao,modulo,entidade,entidade_id,detalhes_json)
                VALUES (%s,'ALTERAR_STATUS','estoque','bolsas',%s,%s)
            """, (actor, str(bag_id), json.dumps({"de": row["status"], "para": new_status, "observacao": note})))
            conn.commit()
            cur.execute("""
                SELECT b.id,b.codigo,ts.codigo AS tipo_sanguineo,b.volume_ml,
                       b.data_coleta,b.data_validade,la.nome AS localizacao,b.status,
                       NULL AS identificador_doador,COALESCE(b.observacoes,'') AS observacoes,
                       b.criado_em
                FROM bolsas b JOIN tipos_sanguineos ts ON ts.id=b.tipo_sanguineo_id
                JOIN locais_armazenamento la ON la.id=b.local_id WHERE b.id=%s
            """, (bag_id,))
            result = bag_json(cur.fetchone())
            cur.close()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        self.send_json(result)



    # ========================================================================
    # 6.6 Doadores
    # ========================================================================
    def list_donors(self, query):
        search = query.get("q", [""])[0].strip()[:100]
        address = (", " + ", ".join(ADDRESS_FIELDS)) if donor_address_ready() else ""
        sql = f"""
            SELECT id, nome, data_nascimento, email, telefone, codigo_ficticio,
                   status, observacoes, tipo_sanguineo, peso_kg, criado_em, atualizado_em{address},
                   (status = 'ATIVO' AND atualizado_em < DATE_SUB(NOW(), INTERVAL %s MONTH)) AS revisao_pendente
            FROM doadores
        """
        params = [DONOR_REVIEW_MONTHS]
        if search:
            sql += " WHERE nome LIKE %s OR codigo_ficticio LIKE %s OR email LIKE %s"
            params.extend([f"%{search}%"] * 3)
        sql += " ORDER BY id DESC LIMIT 500"
        with connect_db() as db:
            cur = db.cursor(dictionary=True)
            cur.execute(sql, params)
            rows = cur.fetchall()
            cur.close()
        for row in rows:
            row["data_nascimento"] = serialize_date(row.get("data_nascimento"))
            row["criado_em"] = serialize_date(row.get("criado_em"))
            row["atualizado_em"] = serialize_date(row.get("atualizado_em"))
            row["revisao_pendente"] = bool(row.get("revisao_pendente"))
        self.send_json(rows)

    def review_donor(self, donor_id, actor_id):
        """Registra que os dados do doador foram conferidos/atualizados hoje."""
        conn = connect_db()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE doadores SET atualizado_em=NOW() WHERE id=%s", (donor_id,))
            if cur.rowcount != 1:
                raise ApiError("Doador não encontrado.", 404)
            cur.execute("""
                INSERT INTO historico_auditoria
                (usuario_id,acao,modulo,entidade,entidade_id,detalhes_json)
                VALUES (%s,'REVISAR','doadores','doadores',%s,%s)
            """, (actor_id, str(donor_id), json.dumps({"cadastro_revisado": True})))
            conn.commit()
            cur.close()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        self.send_json({"ok": True, "mensagem": "Cadastro marcado como revisado."})

    # ---------------- Notificações do sistema ----------------

    # ========================================================================
    # 6.7 Notificações (sino)
    # ========================================================================
    def notifications_enabled(self, actor_id) -> bool:
        with connect_db() as db:
            cur = db.cursor()
            cur.execute("SELECT valor_json FROM configuracoes WHERE chave=%s LIMIT 1",
                        (notification_pref_key(actor_id),))
            row = cur.fetchone()
            cur.close()
        if not row:
            return True  # padrão: ativadas
        value = row[0]
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8")
        try:
            return bool(json.loads(value)) if isinstance(value, str) else bool(value)
        except ValueError:
            return True

    def save_notification_preference(self, data, actor_id):
        enabled = data.get("ativas")
        if not isinstance(enabled, bool):
            raise ApiError("Informe se as notificações devem ficar ativas (true ou false).")
        with connect_db() as db:
            cur = db.cursor()
            cur.execute("""
                INSERT INTO configuracoes (chave, valor_json, descricao, atualizado_por)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE valor_json=VALUES(valor_json), atualizado_por=VALUES(atualizado_por)
            """, (notification_pref_key(actor_id), json.dumps(enabled),
                  "Notificações do sistema ativas para o usuário", actor_id))
            db.commit()
            cur.close()
        self.send_json({"ok": True, "ativas": enabled,
                        "mensagem": "Notificações ativadas." if enabled else "Notificações desativadas."})

    def load_seen_notifications(self, actor_id) -> set:
        with connect_db() as db:
            cur = db.cursor()
            cur.execute("SELECT valor_json FROM configuracoes WHERE chave=%s LIMIT 1",
                        (notification_seen_key(actor_id),))
            row = cur.fetchone()
            cur.close()
        if not row:
            return set()
        value = row[0]
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8")
        try:
            data = json.loads(value) if isinstance(value, str) else value
        except ValueError:
            return set()
        return {str(k) for k in data} if isinstance(data, list) else set()

    def save_seen_notifications(self, actor_id, keys):
        with connect_db() as db:
            cur = db.cursor()
            cur.execute("""
                INSERT INTO configuracoes (chave, valor_json, descricao, atualizado_por)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE valor_json=VALUES(valor_json), atualizado_por=VALUES(atualizado_por)
            """, (notification_seen_key(actor_id), json.dumps(sorted(keys)),
                  "Notificações já vistas pelo usuário", actor_id))
            db.commit()
            cur.close()

    def list_notifications(self, actor_id):
        """Alertas calculados na hora a partir do banco. "total" conta só os não lidos:
        um alerta visto deixa de contar até a situação mudar (a chave muda)."""
        if not self.notifications_enabled(actor_id):
            return self.send_json({"ativas": False, "total": 0, "total_alertas": 0, "itens": []})
        items = self.build_notifications(actor_id)
        seen = self.load_seen_notifications(actor_id)
        for item in items:
            item["lida"] = item["chave"] in seen
        unread = sum(1 for item in items if not item["lida"])
        self.send_json({"ativas": True, "total": unread, "total_alertas": len(items), "itens": items})

    def mark_notifications_read(self, data, actor_id):
        """Dá baixa (marca como vista) em uma ou mais notificações, ou em todas."""
        current = {item["chave"] for item in self.build_notifications(actor_id)}
        if data.get("todas") is True:
            chosen = set(current)
        else:
            keys = data.get("chaves")
            if not isinstance(keys, list) or not keys or len(keys) > 200 \
                    or not all(isinstance(k, str) and len(k) <= 120 for k in keys):
                raise ApiError("Informe as notificações a marcar como lidas.")
            chosen = set(keys) & current
        # Guarda só o que ainda está ativo: a lista não cresce sem limite.
        seen = (self.load_seen_notifications(actor_id) & current) | chosen
        self.save_seen_notifications(actor_id, seen)
        self.send_json({"ok": True, "total": len(current - seen)})

    def build_notifications(self, actor_id):
        """Estoque baixo/crítico por tipo, bolsas perto do vencimento ou vencidas
        e cadastros de doadores sem atualização há mais de 1 ano."""
        items = []
        today = hoje()
        if self.has_permission(actor_id, "estoque.consultar"):
            with connect_db() as db:
                cur = db.cursor(dictionary=True)
                cur.execute("""
                    SELECT ts.codigo AS tipo, COUNT(b.id) AS n
                    FROM tipos_sanguineos ts
                    LEFT JOIN bolsas b ON b.tipo_sanguineo_id = ts.id
                         AND b.status = 'DISPONIVEL' AND b.data_validade >= %s
                    WHERE ts.ativo = TRUE
                    GROUP BY ts.codigo
                """, (today,))
                stock = cur.fetchall()
                cur.execute("""
                    SELECT
                      SUM(data_validade BETWEEN %s AND DATE_ADD(%s, INTERVAL 7 DAY)) AS vencendo,
                      SUM(data_validade < %s) AS vencidas
                    FROM bolsas
                    WHERE status IN ('DISPONIVEL','RESERVADA','QUARENTENA')
                """, (today, today, today))
                expiry = cur.fetchone() or {}
                cur.close()
            for row in sorted(stock, key=lambda r: (int(r["n"]), r["tipo"])):
                n = int(row["n"])
                if n <= STOCK_LOW:
                    critical = n <= STOCK_CRITICAL
                    items.append({
                        "chave": f"estoque:{row['tipo']}:{n}",
                        "tipo": "estoque", "nivel": "critico" if critical else "atencao",
                        "titulo": f"Estoque {'crítico' if critical else 'baixo'} de {row['tipo']}",
                        "mensagem": f"{n} {'bolsa disponível' if n == 1 else 'bolsas disponíveis'}.",
                        "pagina": "stock",
                    })
            expired = int(expiry.get("vencidas") or 0)
            expiring = int(expiry.get("vencendo") or 0)
            if expired:
                items.append({
                    "chave": f"vencidas:{expired}",
                    "tipo": "validade", "nivel": "critico",
                    "titulo": f"{expired} {'bolsa vencida' if expired == 1 else 'bolsas vencidas'}",
                    "mensagem": "Registre o descarte das bolsas fora da validade.", "pagina": "bags",
                })
            if expiring:
                items.append({
                    "chave": f"vencendo:{expiring}",
                    "tipo": "validade", "nivel": "atencao",
                    "titulo": f"{expiring} {'bolsa vence' if expiring == 1 else 'bolsas vencem'} em até 7 dias",
                    "mensagem": "Priorize o uso dessas bolsas.", "pagina": "bags",
                })
        if self.has_permission(actor_id, "doadores.consultar"):
            with connect_db() as db:
                cur = db.cursor(dictionary=True)
                cur.execute("""
                    SELECT nome FROM doadores
                    WHERE status = 'ATIVO' AND atualizado_em < DATE_SUB(NOW(), INTERVAL %s MONTH)
                    ORDER BY atualizado_em ASC LIMIT 100
                """, (DONOR_REVIEW_MONTHS,))
                pending = [r["nome"] for r in cur.fetchall()]
                cur.close()
            if pending:
                names = ", ".join(pending[:3]) + ("…" if len(pending) > 3 else "")
                one = len(pending) == 1
                items.append({
                    "chave": f"cadastro:{len(pending)}",
                    "tipo": "cadastro", "nivel": "atencao",
                    "titulo": f"{len(pending)} {'cadastro de doador precisa' if one else 'cadastros de doadores precisam'} de atualização",
                    "mensagem": f"Sem atualização há mais de 1 ano: {names}", "pagina": "donors",
                })
        order = {"critico": 0, "atencao": 1}
        items.sort(key=lambda item: order.get(item["nivel"], 2))
        return items


    # ========================================================================
    # 6.6 Doadores (cadastro e exclusão)
    # ========================================================================
    def create_donor(self, data, actor_id):
        name = str(data.get("nome", "")).strip()
        email = str(data.get("email", "")).strip().lower()
        phone = str(data.get("telefone", "")).strip()
        birth_text = data.get("data_nascimento", "")
        blood = str(data.get("tipo_sanguineo", "")).strip().upper()
        weight_text = data.get("peso_kg", "")
        note = str(data.get("observacoes", "")).strip()[:2000]
        if not name or len(name) > 120:
            raise ApiError("Informe o nome completo (até 120 caracteres).")
        if not valid_email(email):
            raise ApiError("Informe um e-mail válido.")
        if not phone:
            raise ApiError("Informe o telefone.")
        try:
            phone = format_phone(phone)
        except ValueError as exc:
            raise ApiError(str(exc))
        address = {}
        for column, (label, size, required) in ADDRESS_FIELDS.items():
            value = " ".join(str(data.get(column, "") or "").split())
            if required and not value:
                raise ApiError(f"Informe {'o' if label in ('número', 'bairro', 'CEP', 'complemento', 'estado (UF)') else 'a'} {label}.")
            if len(value) > size:
                raise ApiError(f"O campo {label} aceita até {size} caracteres.")
            address[column] = value or None
        if address["cep"]:
            cep = only_digits(address["cep"])
            if len(cep) != 8:
                raise ApiError("CEP inválido: use 00000-000.")
            address["cep"] = f"{cep[:5]}-{cep[5:]}"
        address["uf"] = (address["uf"] or "").upper()
        if address["uf"] not in UFS:
            raise ApiError("Selecione um estado (UF) válido.")
        try:
            birth = parse_date(birth_text, "data de nascimento")
        except ValueError as exc:
            raise ApiError(str(exc))
        if birth > hoje():
            raise ApiError("A data de nascimento não pode ser futura.")
        if blood not in BLOOD_TYPES:
            raise ApiError("Selecione um tipo sanguíneo válido.")
        try:
            weight = float(weight_text)
        except (TypeError, ValueError):
            raise ApiError("Informe o peso em kg.")
        if not 1 <= weight <= 500:
            raise ApiError("O peso deve estar entre 1 e 500 kg.")
        # Código fictício gerado pelo sistema; o CPF digitado no protótipo não é armazenado.
        code = "DOA-" + uuid.uuid4().hex[:10].upper()
        if not donor_address_ready():
            raise ApiError(
                "O banco ainda não guarda o endereço dos doadores. Um administrador do MySQL "
                "precisa executar scripts/migracao_002_endereco_doador.py.", 503)
        conn = connect_db()
        try:
            cur = conn.cursor()
            # Consulta prévia: mensagem clara no caso comum. A garantia definitiva é o
            # UNIQUE uq_doadores_email (migração 001): se dois cadastros chegarem juntos,
            # o segundo recebe IntegrityError 1062 -> 409 e nada é gravado.
            # O e-mail é salvo sempre em minúsculas, então a comparação direta usa o índice.
            cur.execute("SELECT id FROM doadores WHERE email=%s LIMIT 1", (email,))
            if cur.fetchone():
                raise ApiError("Já existe um doador cadastrado com esse e-mail.", 409)
            cur.execute("""
                INSERT INTO doadores
                (nome, data_nascimento, email, telefone, codigo_ficticio, status,
                 observacoes, tipo_sanguineo, peso_kg,
                 cep, logradouro, numero, complemento, bairro, cidade, uf)
                VALUES (%s,%s,%s,%s,%s,'ATIVO',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (name, birth, email, phone, code, note, blood, weight,
                  *[address[column] for column in ADDRESS_FIELDS]))
            donor_id = cur.lastrowid
            cur.execute("""
                INSERT INTO historico_auditoria
                (usuario_id,acao,modulo,entidade,entidade_id,detalhes_json)
                VALUES (%s,'CRIAR','doadores','doadores',%s,%s)
            """, (actor_id, str(donor_id), json.dumps({"codigo_ficticio": code})))
            conn.commit()
            cur.close()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        self.send_json({"ok": True, "id": donor_id, "codigo_ficticio": code,
                        "mensagem": "Doador cadastrado com sucesso."}, 201)

    def delete_donor(self, donor_id, actor_id):
        """Exclui o cadastro do doador. Se ele já tiver doações ou agendamentos
        registrados, o MySQL bloqueia (chave estrangeira) e nada é apagado."""
        conn = connect_db()
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT id, codigo_ficticio FROM doadores WHERE id=%s FOR UPDATE", (donor_id,))
            donor = cur.fetchone()
            if not donor:
                raise ApiError("Doador não encontrado.", 404)
            cur.execute("DELETE FROM doadores WHERE id=%s", (donor_id,))
            # A auditoria guarda só o código interno, não nome nem contato.
            cur.execute("""
                INSERT INTO historico_auditoria
                (usuario_id,acao,modulo,entidade,entidade_id,detalhes_json)
                VALUES (%s,'EXCLUIR','doadores','doadores',%s,%s)
            """, (actor_id, str(donor_id), json.dumps({"codigo_ficticio": donor["codigo_ficticio"]})))
            conn.commit()
            cur.close()
        except mysql.connector.IntegrityError as exc:
            conn.rollback()
            if getattr(exc, "errno", None) == ROW_IS_REFERENCED:
                raise ApiError("Este doador tem doações ou agendamentos registrados e não pode ser excluído.", 409)
            raise
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        self.send_json({"ok": True, "mensagem": "Doador excluído."})


    # ========================================================================
    # 6.8 Contas de acesso e profissionais
    # ========================================================================
    def list_access_accounts(self):
        """Lista contas e perfis disponíveis; o endpoint já exige ADMINISTRADOR."""
        with connect_db() as db:
            cur = db.cursor(dictionary=True)
            cur.execute("""
                SELECT u.id, u.nome, u.email, u.status, p.nome AS perfil
                FROM usuarios u
                LEFT JOIN usuario_perfis up ON up.usuario_id = u.id
                LEFT JOIN perfis p ON p.id = up.perfil_id
                ORDER BY u.id
            """)
            accounts = cur.fetchall()
            cur.execute("SELECT id, nome FROM perfis ORDER BY id")
            profiles = cur.fetchall()
            cur.close()
        return self.send_json({"usuarios": accounts, "perfis": profiles})

    def create_access_account(self, data, actor_id):
        """Cria usuário de login e associa exatamente um dos quatro perfis do sistema."""
        name = str(data.get("nome", "")).strip()
        email = str(data.get("email", "")).strip().lower()
        password = data.get("senha", "")
        profile_name = str(data.get("perfil", "")).strip().upper()
        allowed_profiles = {
            "ADMINISTRADOR", "RESPONSAVEL_TECNICO", "OPERADOR_ESTOQUE", "CONSULTA"
        }
        if not name or len(name) > 120:
            raise ApiError("Informe o nome completo (até 120 caracteres).")
        if not valid_email(email):
            raise ApiError("Informe um e-mail válido.")
        if not isinstance(password, str) or len(password) < 10 or len(password) > 128:
            raise ApiError("A senha deve ter entre 10 e 128 caracteres.")
        if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
            raise ApiError("A senha deve conter letras e números.")
        if profile_name not in allowed_profiles:
            raise ApiError("Selecione um dos quatro perfis válidos.")

        conn = connect_db()
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT id FROM usuarios WHERE LOWER(email)=%s LIMIT 1", (email,))
            if cur.fetchone():
                raise ApiError("Já existe uma conta cadastrada com esse e-mail.", 409)
            cur.execute("SELECT id FROM perfis WHERE nome=%s LIMIT 1", (profile_name,))
            profile = cur.fetchone()
            if not profile:
                raise ApiError("O perfil selecionado não existe no banco de dados.", 400)
            # Se dois pedidos chegarem juntos, o UNIQUE uq_usuarios_email bloqueia o
            # segundo (IntegrityError 1062 -> 409) e nada é gravado (rollback).
            cur.execute("""
                INSERT INTO usuarios
                    (nome, email, senha_hash, status, tentativas_falhas, criado_em, atualizado_em)
                VALUES (%s, %s, %s, 'ATIVO', 0, NOW(), NOW())
            """, (name, email, password_hash(password)))
            user_id = cur.lastrowid
            cur.execute("""
                INSERT INTO usuario_perfis (usuario_id, perfil_id, atribuido_por, atribuido_em)
                VALUES (%s, %s, %s, NOW())
            """, (user_id, profile["id"], actor_id))
            cur.execute("""
                INSERT INTO historico_auditoria
                (usuario_id,acao,modulo,entidade,entidade_id,detalhes_json)
                VALUES (%s,'CRIAR','usuarios','usuarios',%s,%s)
            """, (actor_id, str(user_id), json.dumps({"perfil": profile_name})))
            conn.commit()
            cur.close()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.send_json({
            "ok": True,
            "mensagem": "Conta de acesso criada com sucesso.",
            "id": user_id
        }, 201)

    def create_professional(self, data, actor_id):
        name = str(data.get("nome", "")).strip()
        email = str(data.get("email", "")).strip().lower()
        role = str(data.get("cargo", "")).strip()
        council = str(data.get("registro_profissional", "")).strip()
        phone = str(data.get("telefone", "")).strip()
        if not name or len(name) > 120:
            raise ApiError("Informe o nome completo (até 120 caracteres).")
        if not valid_email(email):
            raise ApiError("Informe um e-mail válido.")
        if not role or len(role) > 100:
            raise ApiError("Selecione a função profissional.")
        if len(council) > 80:
            raise ApiError("O conselho profissional aceita até 80 caracteres.")
        if phone:
            try:
                phone = format_phone(phone)
            except ValueError as exc:
                raise ApiError(str(exc))
        if not (schema_has("profissionais", "email") and schema_has("profissionais", "uq_profissionais_email")):
            raise ApiError(
                "O banco ainda não guarda o e-mail dos profissionais. Um administrador do MySQL "
                "precisa executar scripts/migracao_001_email_unico.py.", 503)
        conn = connect_db()
        try:
            cur = conn.cursor()
            # Consulta prévia para mensagem clara; o UNIQUE uq_profissionais_email
            # garante a regra mesmo com cadastros simultâneos (1062 -> 409).
            cur.execute("SELECT id FROM profissionais WHERE email=%s LIMIT 1", (email,))
            if cur.fetchone():
                raise ApiError("Já existe um profissional cadastrado com esse e-mail.", 409)
            if council:
                cur.execute("SELECT id FROM profissionais WHERE registro_profissional=%s LIMIT 1", (council,))
                if cur.fetchone():
                    raise ApiError("Já existe um profissional cadastrado com esse registro profissional.", 409)
            # O formulário cadastra os dados profissionais, mas não cria uma conta de
            # acesso. Por isso usuario_id fica NULL (não associar à conta do administrador).
            cur.execute("""
                INSERT INTO profissionais
                (usuario_id, nome, email, registro_profissional, cargo, telefone, status)
                VALUES (NULL,%s,%s,%s,%s,%s,'ATIVO')
            """, (name, email, council or None, role, phone or None))
            professional_id = cur.lastrowid
            cur.execute("""
                INSERT INTO historico_auditoria
                (usuario_id,acao,modulo,entidade,entidade_id,detalhes_json)
                VALUES (%s,'CRIAR','profissionais','profissionais',%s,%s)
            """, (actor_id, str(professional_id), json.dumps({"cargo": role})))
            conn.commit()
            cur.close()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        self.send_json({"ok": True, "id": professional_id,
                        "mensagem": "Profissional cadastrado com sucesso."}, 201)


    # ========================================================================
    # 6.5 Estoque: histórico de movimentações
    # ========================================================================
    def list_movements(self):
        with connect_db() as db:
            cur = db.cursor(dictionary=True)
            cur.execute("""
                SELECT m.id,m.bolsa_id,b.codigo,m.status_anterior,m.status_novo,
                       u.nome AS responsavel,COALESCE(m.motivo,'') AS observacao,
                       m.criado_em
                FROM movimentacoes_estoque m
                JOIN bolsas b ON b.id=m.bolsa_id
                JOIN usuarios u ON u.id=m.responsavel_id
                ORDER BY m.id DESC LIMIT 200
            """)
            rows = cur.fetchall()
            cur.close()
        for row in rows:
            row["criado_em"] = serialize_date(row.get("criado_em"))
            row["responsavel"] = row.get("responsavel") or "Operador"
            row["observacao"] = row.get("observacao") or ""
        self.send_json(rows)


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
        _SCHEMA_OK.clear()
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
        pending = pending_migration_001()
        if pending:
            print("AVISO: migração 001 (e-mail único) pendente:", ", ".join(pending))
            print("  Execute: python scripts/migracao_001_email_unico.py  (com usuário administrativo)")
        pending = pending_migration_002()
        if pending:
            print("AVISO: migração 002 (endereço do doador) pendente:", ", ".join(pending))
            print("  Execute: python scripts/migracao_002_endereco_doador.py  (com usuário administrativo)")
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
