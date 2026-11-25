"""HemoFlow 2.0 — rotas da captação e fidelização de doadores.

Este módulo é "misturado" à classe Handler do servidor.py (class Handler(RotasV2, ...)).
Cada rota da tabela ROTAS chama um método desta classe. As regras puras ficam em regras.py.

ÍNDICE (procure pelo título com Ctrl+F)
   A. Infraestrutura ............ acesso ao banco, auditoria, avisos, contexto do usuário
   B. Tabela de rotas ........... endereço -> função -> perfil exigido
   C. Cadastro e login por código
   D. App do doador ............. início, termômetro, agenda, histórico, direitos, vantagens, grupos, perfil
   E. Painel do banco de sangue . termômetro, estoque, convocação, agenda, confirmação, métricas
   F. Painel do parceiro ........ ofertas, validação de cupom, relatório agregado
   G. Painel admin .............. resumo, aprovações, cadastros, contas, "entrar como"
   H. Avisos (sino)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import string
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from email.message import EmailMessage

import regras

S = None  # módulo servidor (definido por servidor.py ao importar este arquivo)


# ============================================================================
# A. INFRAESTRUTURA
# ============================================================================
def consulta(sql, params=(), um=False):
    with S.connect_db() as db:
        cur = db.cursor(dictionary=True)
        cur.execute(sql, params)
        linhas = cur.fetchall()
        cur.close()
    return (linhas[0] if linhas else None) if um else linhas


def transacao(funcao):
    """Executa funcao(cur) numa transação: grava tudo ou nada."""
    conn = S.connect_db()
    try:
        cur = conn.cursor(dictionary=True)
        resultado = funcao(cur)
        conn.commit()
        cur.close()
        return resultado
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def auditar(cur, usuario_id, acao, modulo, entidade, entidade_id=None, detalhes=None):
    cur.execute("""INSERT INTO historico_auditoria (usuario_id, acao, modulo, entidade, entidade_id, detalhes_json)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (usuario_id, acao, modulo, entidade, None if entidade_id is None else str(entidade_id),
                 json.dumps(detalhes or {}, ensure_ascii=False, default=str)))


def avisar(cur, usuario_id, titulo, mensagem, link=None):
    if usuario_id:
        cur.execute("INSERT INTO avisos (usuario_id, titulo, mensagem, link) VALUES (%s,%s,%s,%s)",
                    (usuario_id, titulo[:160], mensagem[:500], link))


def avisar_equipe_banco(cur, banco_id, titulo, mensagem, link=None):
    cur.execute("SELECT id FROM usuarios WHERE banco_id=%s AND status='ATIVO'", (banco_id,))
    for linha in cur.fetchall():
        avisar(cur, linha["id"], titulo, mensagem, link)


def texto(data, campo, maximo, obrigatorio=True, rotulo=None):
    valor = " ".join(str(data.get(campo, "") or "").split())
    if obrigatorio and not valor:
        raise S.ApiError(f"Informe {rotulo or campo}.")
    if len(valor) > maximo:
        raise S.ApiError(f"O campo {rotulo or campo} aceita até {maximo} caracteres.")
    return valor or None


def inteiro(valor, rotulo, minimo=0, maximo=100000):
    try:
        n = int(valor)
    except (TypeError, ValueError):
        raise S.ApiError(f"Informe {rotulo} com um número inteiro.")
    if not minimo <= n <= maximo:
        raise S.ApiError(f"{rotulo.capitalize()} deve estar entre {minimo} e {maximo}.")
    return n


def data_iso(valor):
    return valor.isoformat() if isinstance(valor, (date, datetime)) else valor


def codigo_aleatorio(tamanho, alfabeto=string.digits):
    return "".join(secrets.choice(alfabeto) for _ in range(tamanho))


def primeiro_nome(nome):
    partes = (nome or "").split()
    return f"{partes[0]} {partes[-1][0]}." if len(partes) > 1 else (partes[0] if partes else "")


PAPEIS = ("ADMINISTRADOR", "BANCO", "PARCEIRO", "DOADOR")


def contexto_do_usuario(usuario_id):
    """Perfil principal e vínculos (banco, parceiro ou doador) do usuário."""
    linhas = consulta("""SELECT pf.nome FROM usuario_perfis up JOIN perfis pf ON pf.id=up.perfil_id
                         WHERE up.usuario_id=%s""", (usuario_id,))
    perfis = [l["nome"] for l in linhas]
    papel = next((p for p in PAPEIS if p in perfis), None)
    u = consulta("SELECT banco_id, parceiro_id FROM usuarios WHERE id=%s", (usuario_id,), um=True) or {}
    d = consulta("SELECT id FROM doadores WHERE usuario_id=%s", (usuario_id,), um=True)
    return {"papel": papel, "perfis": perfis, "banco_id": u.get("banco_id"),
            "parceiro_id": u.get("parceiro_id"), "doador_id": d["id"] if d else None}


def criar_sessao(handler, usuario):
    """Cria a sessão (cookie) e devolve o JSON do usuário com o contexto."""
    ctx = contexto_do_usuario(usuario["id"])
    if not ctx["papel"]:
        raise S.ApiError("Esta conta não possui perfil de acesso. Procure a equipe HemoFlow.", 403)
    agora = time.time()
    for token_antigo in [k for k, v in S.SESSIONS.items() if v["expires"] <= agora]:
        S.SESSIONS.pop(token_antigo, None)
    token = secrets.token_urlsafe(32)
    S.SESSIONS[token] = {"id": usuario["id"], "nome": usuario["nome"], "email": usuario["email"],
                         "is_admin": ctx["papel"] == "ADMINISTRADOR", "expires": agora + S.SESSION_TTL}
    return token, ctx


def usuario_json(record, ctx):
    return {"id": record["id"], "nome": record["nome"], "email": record["email"], "papel": ctx["papel"],
            "is_admin": ctx["papel"] == "ADMINISTRADOR", "banco_id": ctx["banco_id"],
            "parceiro_id": ctx["parceiro_id"], "doador_id": ctx["doador_id"]}


# ============================================================================
# B. TABELA DE ROTAS  (método, padrão, função, perfil exigido; None = público)
# ============================================================================
# Versão vigente dos Termos de Uso e da Política de Privacidade (static/termos.html e static/privacidade.html).
# Mudou o texto de forma relevante? Atualize aqui e no topo dos documentos.
VERSAO_TERMOS = "1.2 de 20/11/2026"

ROTAS = [
    ("POST", r"/api/cadastro", "cadastrar_doador", None),
    ("POST", r"/api/login/codigo/enviar", "enviar_codigo_login", None),
    ("POST", r"/api/login/codigo/entrar", "entrar_com_codigo", None),
    ("GET", r"/api/publico/locais", "locais_publicos", None),
    # app do doador
    ("GET", r"/api/doador/inicio", "doador_inicio", "DOADOR"),
    ("GET", r"/api/doador/locais", "doador_locais", "DOADOR"),
    ("GET", r"/api/doador/vagas", "doador_vagas", "DOADOR"),
    ("POST", r"/api/doador/agendar", "doador_agendar", "DOADOR"),
    ("POST", r"/api/doador/agendamentos/(\d+)/cancelar", "doador_cancelar", "DOADOR"),
    ("GET", r"/api/doador/historico", "doador_historico", "DOADOR"),
    ("POST", r"/api/doador/doacao-declarada", "doador_declarar", "DOADOR"),
    ("GET", r"/api/doador/direitos", "doador_direitos", "DOADOR"),
    ("GET", r"/api/doador/vantagens", "doador_vantagens", "DOADOR"),
    ("POST", r"/api/doador/cupons", "doador_gerar_cupom", "DOADOR"),
    ("POST", r"/api/doador/codigo-parceiro", "doador_codigo_parceiro", "DOADOR"),
    ("POST", r"/api/doador/declaracoes", "doador_declaracao", "DOADOR"),
    ("GET", r"/api/publico/declaracoes/([A-Za-z0-9-]{4,12})", "verificar_declaracao", None),
    ("GET", r"/api/doador/grupos", "doador_grupos", "DOADOR"),
    ("POST", r"/api/doador/grupos", "doador_criar_grupo", "DOADOR"),
    ("POST", r"/api/doador/grupos/entrar", "doador_entrar_grupo", "DOADOR"),
    ("GET", r"/api/doador/perfil", "doador_perfil", "DOADOR"),
    ("POST", r"/api/doador/perfil", "doador_salvar_perfil", "DOADOR"),
    ("GET", r"/api/doador/excluir-conta/resumo", "doador_resumo_exclusao", "DOADOR"),
    ("POST", r"/api/doador/excluir-conta", "doador_excluir_conta", "DOADOR"),
    # painel do banco
    ("GET", r"/api/banco/painel", "banco_painel", "BANCO"),
    ("POST", r"/api/banco/estoque/movimento", "banco_movimento", "BANCO"),
    ("POST", r"/api/banco/estoque/limites", "banco_limites", "BANCO"),
    ("GET", r"/api/banco/convocacao/sugestao", "banco_sugestao", "BANCO"),
    ("POST", r"/api/banco/convocacoes", "banco_convocar", "BANCO"),
    ("GET", r"/api/banco/convocacoes", "banco_convocacoes", "BANCO"),
    ("GET", r"/api/banco/agenda", "banco_agenda", "BANCO"),
    ("POST", r"/api/banco/vagas", "banco_criar_vagas", "BANCO"),
    ("POST", r"/api/banco/confirmar", "banco_confirmar", "BANCO"),
    ("POST", r"/api/banco/agendamentos/(\d+)/faltou", "banco_faltou", "BANCO"),
    ("GET", r"/api/banco/metricas", "banco_metricas", "BANCO"),
    # painel do parceiro
    ("GET", r"/api/parceiro/painel", "parceiro_painel", "PARCEIRO"),
    ("POST", r"/api/parceiro/ofertas", "parceiro_oferta", "PARCEIRO"),
    ("POST", r"/api/parceiro/cupons/validar", "parceiro_validar", "PARCEIRO"),
    ("POST", r"/api/parceiro/ofertas/(\d+)/emergencia", "parceiro_emergencia", "PARCEIRO"),
    # admin
    ("GET", r"/api/admin/resumo", "admin_resumo", "ADMINISTRADOR"),
    ("GET", r"/api/admin/bancos", "admin_bancos", "ADMINISTRADOR"),
    ("POST", r"/api/admin/bancos", "admin_salvar_banco", "ADMINISTRADOR"),
    ("POST", r"/api/admin/unidades", "admin_salvar_unidade", "ADMINISTRADOR"),
    ("GET", r"/api/admin/parceiros", "admin_parceiros", "ADMINISTRADOR"),
    ("POST", r"/api/admin/parceiros", "admin_salvar_parceiro", "ADMINISTRADOR"),
    ("POST", r"/api/admin/ofertas/(\d+)/status", "admin_status_oferta", "ADMINISTRADOR"),
    ("GET", r"/api/admin/doadores", "admin_doadores", "ADMINISTRADOR"),
    ("POST", r"/api/admin/doadores/(\d+)", "admin_salvar_doador", "ADMINISTRADOR"),
    ("GET", r"/api/admin/contas", "admin_contas", "ADMINISTRADOR"),
    ("POST", r"/api/admin/contas", "admin_criar_conta", "ADMINISTRADOR"),
    ("POST", r"/api/admin/contas/(\d+)/status", "admin_status_conta", "ADMINISTRADOR"),
    ("POST", r"/api/admin/entrar-como", "admin_entrar_como", "ADMINISTRADOR"),
    ("POST", r"/api/sair-como", "sair_como", "QUALQUER"),
    ("POST", r"/api/dev/semear", "dev_semear", None),
    # avisos
    ("GET", r"/api/avisos", "avisos_listar", "QUALQUER"),
    # Assistente HemoFlow (IA com RAG, pasta assistente/): roda como serviço local no computador
    ("GET", r"/api/assistente/status", "assistente_status", "QUALQUER"),
    ("POST", r"/api/doador/assistente", "doador_assistente", "DOADOR"),
    ("POST", r"/api/parceiro/assistente", "parceiro_assistente", "PARCEIRO"),
    ("POST", r"/api/avisos/lidos", "avisos_marcar_lidos", "QUALQUER"),
]
_ROTAS = [(m, re.compile(p + r"$"), f, papel) for m, p, f, papel in ROTAS]


class RotasV2:
    """Métodos das rotas da versão 2.0 (misturados ao Handler do servidor.py)."""

    def rota_v2(self, metodo, caminho, query):
        """Procura a rota; devolve False se o endereço não é da versão 2.0."""
        for m, padrao, funcao, papel in _ROTAS:
            if m != metodo:
                continue
            achou = padrao.match(caminho)
            if not achou:
                continue
            args = [int(g) if g.isdigit() else g for g in achou.groups()]  # ids viram número; códigos ficam texto
            dados = self.read_json() if metodo == "POST" else {}
            if papel is None:
                getattr(self, funcao)(dados, query, *args)
                return True
            record = self.require_session()
            ctx = self.contexto_efetivo(record)
            if papel != "QUALQUER" and ctx["papel"] != papel:
                raise S.ApiError("Você não tem acesso a esta área.", 403)
            self.ctx, self.record = ctx, record
            getattr(self, funcao)(dados, query, *args)
            return True
        return False

    def contexto_efetivo(self, record):
        """Contexto do usuário; se o admin usou "Entrar como", age como aquele usuário."""
        ctx = contexto_do_usuario(record["id"])
        como = record.get("como")
        if como and ctx["papel"] == "ADMINISTRADOR":
            return {**ctx, **como, "admin_real": True}
        return ctx

    def uid(self):
        return self.record["id"]

    # ========================================================================
    # C. CADASTRO E LOGIN POR CÓDIGO
    # ========================================================================
    def cadastrar_doador(self, data, query):
        """Cadastro do doador pelo app (cria a conta de login e a ficha de doador)."""
        nome = texto(data, "nome", 120, rotulo="o nome completo")
        email = str(data.get("email", "")).strip().lower()
        senha = data.get("senha", "")
        cpf = S.only_digits(str(data.get("cpf", "")))
        tipo = str(data.get("tipo_sanguineo", "")).upper()
        sexo = str(data.get("sexo", "")).upper()
        cidade = texto(data, "cidade", 80, rotulo="a cidade")
        uf = str(data.get("uf", "")).upper()
        if not S.valid_email(email):
            raise S.ApiError("Informe um e-mail válido.")
        if not isinstance(senha, str) or len(senha) < 8 or not re.search(r"[A-Za-z]", senha) or not re.search(r"\d", senha):
            raise S.ApiError("A senha deve ter pelo menos 8 caracteres, com letras e números.")
        if not S.valid_cpf(cpf):
            raise S.ApiError("CPF inválido: confira os números digitados.")
        if tipo not in regras.TIPOS:
            raise S.ApiError("Selecione o seu tipo sanguíneo.")
        if sexo not in ("M", "F"):
            raise S.ApiError("Selecione o sexo informado no documento (usado nas regras de doação).")
        if uf not in S.UFS:
            raise S.ApiError("Selecione o estado (UF).")
        try:
            nascimento = S.parse_date(data.get("data_nascimento"), "data de nascimento")
        except ValueError as exc:
            raise S.ApiError(str(exc))
        anos = regras.idade(nascimento, S.hoje())
        if anos < 16:
            raise S.ApiError("O cadastro de doador é permitido a partir dos 16 anos.")
        responsavel = texto(data, "responsavel_nome", 120, obrigatorio=anos < 18, rotulo="o nome do responsável")
        responsavel_ok = bool(data.get("responsavel_consentiu")) if anos < 18 else False
        if anos < 18 and not responsavel_ok:
            raise S.ApiError("Menores de 18 anos precisam do consentimento do responsável.")
        if not data.get("aceite_termos"):
            raise S.ApiError("É preciso ler e aceitar os Termos de Uso e a Política de Privacidade.")
        if not data.get("aceite_dados_saude"):
            raise S.ApiError("É preciso autorizar o tratamento dos dados de saúde (tipo sanguíneo e doações) para usar o HemoFlow.")
        ultima = None
        if data.get("ultima_doacao"):
            try:
                ultima = S.parse_date(data.get("ultima_doacao"), "data da última doação")
            except ValueError as exc:
                raise S.ApiError(str(exc))
            if ultima > S.hoje():
                raise S.ApiError("A data da última doação não pode ser futura.")
        telefone = None
        if data.get("telefone"):
            try:
                telefone = S.format_phone(str(data.get("telefone")))
            except ValueError as exc:
                raise S.ApiError(str(exc))
        consentiu = bool(data.get("consentimento_convocacao"))

        def gravar(cur):
            cur.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
            if cur.fetchone():
                raise S.ApiError("Já existe uma conta com esse e-mail. Use “Entrar”.", 409)
            cur.execute("SELECT id FROM doadores WHERE cpf=%s", (cpf,))
            if cur.fetchone():
                raise S.ApiError("Já existe um doador com esse CPF.", 409)
            cur.execute("INSERT INTO usuarios (nome, email, senha_hash, status) VALUES (%s,%s,%s,'ATIVO')",
                        (nome, email, S.password_hash(senha)))
            usuario_id = cur.lastrowid
            cur.execute("""INSERT INTO usuario_perfis (usuario_id, perfil_id)
                           SELECT %s, id FROM perfis WHERE nome='DOADOR'""", (usuario_id,))
            cur.execute("""INSERT INTO doadores (nome, cpf, data_nascimento, email, telefone, codigo_ficticio, status,
                               tipo_sanguineo, cidade, uf, usuario_id, sexo, ultima_doacao_informada,
                               consentimento_convocacao, consentimento_em, responsavel_nome, responsavel_consentiu)
                           VALUES (%s,%s,%s,%s,%s,%s,'ATIVO',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (nome, cpf, nascimento, email, telefone, "DOA-" + secrets.token_hex(5).upper(), tipo, cidade, uf,
                         usuario_id, sexo, ultima, int(consentiu), datetime.now() if consentiu else None,
                         responsavel, int(responsavel_ok)))
            auditar(cur, usuario_id, "CADASTRO", "doador", "doadores", cur.lastrowid, {"origem": "app"})
            # Prova do consentimento (LGPD, art. 8º, §2º): versão dos documentos, o que foi autorizado, quando e de onde
            auditar(cur, usuario_id, "ACEITE_TERMOS", "lgpd", "usuarios", usuario_id,
                    {"termos": VERSAO_TERMOS, "privacidade": VERSAO_TERMOS, "dados_saude": True,
                     "convocacao": consentiu, "responsavel": responsavel if anos < 18 else None, "ip": self.client_ip()})
            avisar(cur, usuario_id, "Bem-vindo ao HemoFlow!", "Seu cadastro está pronto. Veja onde o seu tipo sanguíneo está em falta.")
            return usuario_id

        usuario_id = transacao(gravar)
        token, ctx = criar_sessao(self, {"id": usuario_id, "nome": nome, "email": email})
        self.send_json({"ok": True, "usuario": usuario_json({"id": usuario_id, "nome": nome, "email": email}, ctx)},
                       201, [("Set-Cookie", S.session_cookie(token, S.SESSION_TTL))])

    def enviar_codigo_login(self, data, query):
        """Envia um código de 6 dígitos para o e-mail (entrar sem senha). Resposta sempre igual."""
        email = str(data.get("email", "")).strip().lower()[:254]
        if not S.valid_email(email):
            raise S.ApiError("Informe um e-mail válido.")
        ip, agora = self.client_ip(), time.time()
        recentes = [t for t in S.RESET_REQUESTS.get(ip, []) if agora - t < S.LOGIN_WINDOW]
        if len(recentes) >= S.MAX_RESET_REQUESTS:
            raise S.ApiError("Muitos pedidos. Aguarde alguns minutos e tente de novo.", 429)
        S.RESET_REQUESTS[ip] = recentes + [agora]
        generico = {"ok": True, "mensagem": "Se o e-mail estiver cadastrado, enviamos um código de 6 dígitos. Ele vale por 10 minutos."}
        u = consulta("SELECT id, nome, email FROM usuarios WHERE email=%s AND status='ATIVO'", (email,), um=True)
        if not u:
            return self.send_json(generico)
        codigo = codigo_aleatorio(6)

        def gravar(cur):
            cur.execute("UPDATE codigos_login SET usado_em=NOW() WHERE usuario_id=%s AND usado_em IS NULL", (u["id"],))
            cur.execute("INSERT INTO codigos_login (usuario_id, codigo_hash, expira_em) VALUES (%s,%s,DATE_ADD(NOW(), INTERVAL 10 MINUTE))",
                        (u["id"], hashlib.sha256(codigo.encode()).hexdigest()))
        transacao(gravar)
        msg = EmailMessage()
        msg["Subject"] = f"Seu código de acesso HemoFlow: {codigo}"
        msg["From"] = f"HemoFlow <{S.EMAIL_FROM}>"
        msg["To"] = u["email"]
        msg.set_content(f"Olá, {u['nome'].split()[0]}!\n\nSeu código para entrar no HemoFlow é: {codigo}\n\n"
                        "Ele vale por 10 minutos e só pode ser usado uma vez. Se não foi você, ignore este e-mail.\n\nHemoFlow · Doe. Volte. Salve vidas.")
        try:
            S.deliver_email(msg)
        except Exception as exc:  # noqa: BLE001 - resposta igual para não revelar contas
            print("Falha ao enviar código de login:", type(exc).__name__, exc)
        return self.send_json(generico)

    def entrar_com_codigo(self, data, query):
        email = str(data.get("email", "")).strip().lower()[:254]
        codigo = S.only_digits(str(data.get("codigo", "")))
        if len(codigo) != 6:
            raise S.ApiError("Digite os 6 números do código.")
        u = consulta("SELECT id, nome, email FROM usuarios WHERE email=%s AND status='ATIVO'", (email,), um=True)
        erro = S.ApiError("Código inválido ou vencido. Peça um novo código.", 401)
        if not u:
            raise erro

        def validar(cur):
            cur.execute("""SELECT id, codigo_hash, tentativas FROM codigos_login
                           WHERE usuario_id=%s AND usado_em IS NULL AND expira_em > NOW()
                           ORDER BY id DESC LIMIT 1 FOR UPDATE""", (u["id"],))
            linha = cur.fetchone()
            if not linha or linha["tentativas"] >= 5:
                return False
            if not secrets.compare_digest(linha["codigo_hash"], hashlib.sha256(codigo.encode()).hexdigest()):
                cur.execute("UPDATE codigos_login SET tentativas=tentativas+1 WHERE id=%s", (linha["id"],))
                return False
            cur.execute("UPDATE codigos_login SET usado_em=NOW() WHERE id=%s", (linha["id"],))
            cur.execute("UPDATE usuarios SET ultimo_login=NOW(), tentativas_falhas=0, bloqueado_ate=NULL WHERE id=%s", (u["id"],))
            return True
        if not transacao(validar):
            raise erro
        token, ctx = criar_sessao(self, u)
        self.send_json({"ok": True, "usuario": usuario_json(u, ctx)}, 200,
                       [("Set-Cookie", S.session_cookie(token, S.SESSION_TTL))])

    def locais_publicos(self, data, query):
        uf = (query.get("uf", [""])[0] or "").upper()
        sql = "SELECT id, nome, tipo, endereco, bairro, cidade, uf, horario FROM unidades u WHERE ativo=1"
        params = []
        if uf:
            sql += " AND uf=%s"
            params.append(uf)
        sql += " AND (tipo='PUBLICO' OR banco_id IN (SELECT id FROM bancos_sangue WHERE status='ATIVO')) ORDER BY uf, cidade, nome"
        self.send_json(consulta(sql, params))

    # ========================================================================
    # D. APP DO DOADOR
    # ========================================================================
    def doador(self):
        d = consulta("""SELECT id, nome, email, telefone, cpf, data_nascimento, tipo_sanguineo, sexo, cidade, uf,
                               ultima_doacao_informada, consentimento_convocacao, responsavel_nome, responsavel_consentiu
                        FROM doadores WHERE id=%s""", (self.ctx["doador_id"],), um=True)
        if not d:
            raise S.ApiError("Ficha de doador não encontrada.", 404)
        return d

    def datas_doacao(self, doador):
        linhas = consulta("SELECT data, status FROM historico_doacoes WHERE doador_id=%s ORDER BY data", (doador["id"],))
        datas = [l["data"] for l in linhas]
        if doador.get("ultima_doacao_informada"):
            datas.append(doador["ultima_doacao_informada"])
        verificadas = [l["data"] for l in linhas if l["status"] == "VERIFICADA"]
        return sorted(set(datas)), verificadas

    def aptidao_do(self, doador):
        datas, _ = self.datas_doacao(doador)
        return regras.aptidao(doador.get("sexo") or "M", doador.get("data_nascimento"), datas, S.hoje(),
                              responsavel_ok=bool(doador.get("responsavel_consentiu")))

    def termometro_publico(self, uf, cidade, tipo_do_doador):
        """Níveis (só as cores) de cada banco parceiro ativo no estado; o tipo do doador em destaque."""
        linhas = consulta("""
            SELECT u.id AS unidade_id, u.nome AS unidade, u.cidade, b.nome AS banco, e.tipo_sanguineo, e.quantidade,
                   e.limite_critico, e.limite_atencao, e.atualizado_em, e.editado_admin
            FROM unidades u JOIN bancos_sangue b ON b.id=u.banco_id AND b.status='ATIVO'
            JOIN estoque_niveis e ON e.unidade_id=u.id
            WHERE u.ativo=1 AND u.tipo='BANCO' AND u.uf=%s
            ORDER BY (u.cidade=%s) DESC, b.nome, u.nome""", (uf, cidade))
        unidades = {}
        for l in linhas:
            un = unidades.setdefault(l["unidade_id"], {"unidade_id": l["unidade_id"], "banco": l["banco"], "unidade": l["unidade"],
                                                        "cidade": l["cidade"], "atualizado_em": None, "fonte": "", "niveis": {}})
            un["niveis"][l["tipo_sanguineo"]] = regras.nivel(l["quantidade"], l["limite_critico"], l["limite_atencao"])
            if not un["atualizado_em"] or l["atualizado_em"] > un["atualizado_em"]:
                un["atualizado_em"] = l["atualizado_em"]
                un["fonte"] = "equipe HemoFlow" if l["editado_admin"] else l["banco"]
        lista = []
        for un in unidades.values():
            un["atualizado_em"] = data_iso(un["atualizado_em"])
            lista.append(un)
        ordem = {"CRITICO": 0, "ATENCAO": 1, "NORMAL": 2}
        destaque = None
        for un in lista:
            n = un["niveis"].get(tipo_do_doador)
            if n and (destaque is None or ordem[n] < ordem[destaque["nivel"]]):
                destaque = {"nivel": n, "banco": un["banco"], "unidade": un["unidade"], "unidade_id": un["unidade_id"],
                            "fonte": un["fonte"], "atualizado_em": un["atualizado_em"]}
        return lista, destaque

    def doador_inicio(self, data, query):
        d = self.doador()
        apt = self.aptidao_do(d)
        bancos, destaque = self.termometro_publico(d["uf"], d["cidade"], d["tipo_sanguineo"])
        convocacoes = consulta("""
            SELECT c.id, c.tipo_sanguineo, c.mensagem, c.unidade_id, u.nome AS unidade, b.nome AS banco, cd.enviada_em
            FROM convocacao_doadores cd JOIN convocacoes c ON c.id=cd.convocacao_id
            JOIN unidades u ON u.id=c.unidade_id JOIN bancos_sangue b ON b.id=c.banco_id
            WHERE cd.doador_id=%s AND cd.status='ENVIADA' AND cd.enviada_em > DATE_SUB(NOW(), INTERVAL 14 DAY)
            ORDER BY cd.enviada_em DESC""", (d["id"],))
        proximo = consulta("""
            SELECT a.id, a.codigo, a.status, v.inicio, u.nome AS unidade, u.endereco, u.cidade, b.nome AS banco
            FROM agenda_doacoes a JOIN vagas v ON v.id=a.vaga_id JOIN unidades u ON u.id=a.unidade_id
            LEFT JOIN bancos_sangue b ON b.id=u.banco_id
            WHERE a.doador_id=%s AND a.status='AGENDADO' AND v.inicio >= DATE_SUB(NOW(), INTERVAL 3 HOUR)
            ORDER BY v.inicio LIMIT 1""", (d["id"],), um=True)
        datas, verificadas = self.datas_doacao(d)
        for c in convocacoes:
            c["enviada_em"] = data_iso(c["enviada_em"])
        if proximo:
            proximo["inicio"] = data_iso(proximo["inicio"])
        nao_lidos = consulta("SELECT COUNT(*) AS n FROM avisos WHERE usuario_id=%s AND lido_em IS NULL", (self.uid(),), um=True)["n"]
        self.send_json({
            "doador": {"nome": d["nome"], "primeiro_nome": d["nome"].split()[0], "tipo_sanguineo": d["tipo_sanguineo"],
                       "cidade": d["cidade"], "uf": d["uf"], "sexo": d["sexo"]},
            "aptidao": {**apt, "a_partir_de": data_iso(apt["a_partir_de"])},
            "destaque": destaque, "bancos": bancos, "convocacoes": convocacoes, "proximo_agendamento": proximo,
            "doacoes": len(datas), "vidas": regras.vidas_impactadas(len(datas)), "avisos_nao_lidos": nao_lidos,
            "impacto": self.ultimo_impacto(),
            "nivel": regras.nivel_doador(len(datas)), "ultima_doacao": data_iso(max(datas)) if datas else None,
            "intervalo_dias": regras.INTERVALO_DIAS.get(d["sexo"] or "M", 60),
        })

    def ultimo_impacto(self):
        """Último aviso "Doações como a sua salvam vidas" dos últimos 7 dias (cartão de destaque na tela Início)."""
        a = consulta("""SELECT mensagem, criado_em FROM avisos WHERE usuario_id=%s AND titulo=%s
                        AND criado_em > DATE_SUB(NOW(), INTERVAL 7 DAY) ORDER BY id DESC LIMIT 1""",
                     (self.uid(), self.TITULO_IMPACTO), um=True)
        return {"mensagem": a["mensagem"], "em": data_iso(a["criado_em"])} if a else None

    def doador_locais(self, data, query):
        d = self.doador()
        linhas = consulta("""
            SELECT u.id, u.nome, u.tipo, u.endereco, u.bairro, u.cidade, u.uf, u.horario, b.nome AS banco
            FROM unidades u LEFT JOIN bancos_sangue b ON b.id=u.banco_id
            WHERE u.ativo=1 AND u.uf=%s AND (u.tipo='PUBLICO' OR b.status='ATIVO')
            ORDER BY (u.cidade=%s) DESC, u.tipo, u.nome""", (d["uf"], d["cidade"]))
        self.send_json(linhas)

    def vagas_livres(self, unidade_id, dias=10):
        linhas = consulta("""
            SELECT v.id, v.inicio, v.capacidade,
                   (SELECT COUNT(*) FROM agenda_doacoes a WHERE a.vaga_id=v.id AND a.status IN ('AGENDADO','COMPARECEU')) AS ocupadas
            FROM vagas v WHERE v.unidade_id=%s AND v.inicio > NOW() AND v.inicio < DATE_ADD(NOW(), INTERVAL %s DAY)
            ORDER BY v.inicio""", (unidade_id, dias))
        for l in linhas:
            l["livres"] = max(0, l["capacidade"] - l["ocupadas"])
            l["inicio"] = data_iso(l["inicio"])
        return linhas

    def doador_vagas(self, data, query):
        unidade_id = inteiro(query.get("unidade_id", ["0"])[0], "a unidade", 1, 10**12)
        un = consulta("""SELECT u.id, u.nome, u.endereco, u.cidade, b.nome AS banco FROM unidades u
                         JOIN bancos_sangue b ON b.id=u.banco_id AND b.status='ATIVO' WHERE u.id=%s AND u.ativo=1""",
                      (unidade_id,), um=True)
        if not un:
            raise S.ApiError("Esse local não recebe agendamentos pelo HemoFlow.", 404)
        self.send_json({"unidade": un, "vagas": self.vagas_livres(unidade_id)})

    def doador_agendar(self, data, query):
        d = self.doador()
        apt = self.aptidao_do(d)
        if not apt["apto"]:
            quando = apt["a_partir_de"].strftime("%d/%m/%Y") if apt["a_partir_de"] else ""
            raise S.ApiError(f"{apt['motivo']} " + (f"Você poderá doar a partir de {quando}." if quando else ""), 409)
        vaga_id = inteiro(data.get("vaga_id"), "o horário", 1, 10**12)
        convocacao_id = data.get("convocacao_id")

        def gravar(cur):
            cur.execute("""SELECT v.id, v.inicio, v.capacidade, v.unidade_id, u.banco_id, u.nome AS unidade
                           FROM vagas v JOIN unidades u ON u.id=v.unidade_id WHERE v.id=%s FOR UPDATE""", (vaga_id,))
            vaga = cur.fetchone()
            if not vaga or vaga["inicio"] <= datetime.now() or not vaga["banco_id"]:
                raise S.ApiError("Esse horário não está mais disponível.", 409)
            cur.execute("SELECT COUNT(*) AS n FROM agenda_doacoes WHERE vaga_id=%s AND status IN ('AGENDADO','COMPARECEU')", (vaga_id,))
            if cur.fetchone()["n"] >= vaga["capacidade"]:
                raise S.ApiError("Esse horário acabou de lotar. Escolha outro.", 409)
            cur.execute("""SELECT a.id FROM agenda_doacoes a JOIN vagas v ON v.id=a.vaga_id
                           WHERE a.doador_id=%s AND a.status='AGENDADO' AND v.inicio > NOW()""", (d["id"],))
            if cur.fetchone():
                raise S.ApiError("Você já tem uma doação agendada. Cancele a atual para marcar outra.", 409)
            origem, conv = "ESPONTANEO", None
            if convocacao_id:
                cur.execute("""SELECT c.id FROM convocacoes c JOIN convocacao_doadores cd ON cd.convocacao_id=c.id
                               WHERE c.id=%s AND cd.doador_id=%s""", (int(convocacao_id), d["id"]))
                if cur.fetchone():
                    origem, conv = "CONVOCACAO", int(convocacao_id)
                    cur.execute("UPDATE convocacao_doadores SET status='AGENDOU' WHERE convocacao_id=%s AND doador_id=%s", (conv, d["id"]))
            codigo = codigo_aleatorio(6)
            cur.execute("""INSERT INTO agenda_doacoes (doador_id, unidade_id, vaga_id, convocacao_id, origem, codigo)
                           VALUES (%s,%s,%s,%s,%s,%s)""", (d["id"], vaga["unidade_id"], vaga_id, conv, origem, codigo))
            agenda_id = cur.lastrowid
            quando = vaga["inicio"].strftime("%d/%m às %H:%M")
            avisar_equipe_banco(cur, vaga["banco_id"], "Novo agendamento",
                                f"{primeiro_nome(d['nome'])} ({d['tipo_sanguineo']}) agendou para {quando} · "
                                f"{'resposta a convocação' if conv else 'agendamento espontâneo'}. Pré-checagem: apto.", "agenda")
            avisar(cur, self.uid(), "Doação agendada", f"{vaga['unidade']} · {quando}. Mostre o código {codigo} no balcão.", "inicio")
            auditar(cur, self.uid(), "AGENDAR", "agenda", "agenda_doacoes", agenda_id, {"vaga": vaga_id, "origem": origem})
            return {"id": agenda_id, "codigo": codigo, "inicio": data_iso(vaga["inicio"]), "unidade": vaga["unidade"]}
        self.send_json({"ok": True, "agendamento": transacao(gravar),
                        "mensagem": "Doação agendada! A aptidão final é confirmada na triagem do banco de sangue."}, 201)

    def doador_cancelar(self, data, query, agenda_id):
        d = self.doador()

        def gravar(cur):
            cur.execute("""SELECT a.id, a.status, a.unidade_id, v.inicio, u.banco_id, u.nome AS unidade
                           FROM agenda_doacoes a JOIN vagas v ON v.id=a.vaga_id
                           JOIN unidades u ON u.id=a.unidade_id WHERE a.id=%s AND a.doador_id=%s FOR UPDATE""", (agenda_id, d["id"]))
            a = cur.fetchone()
            if not a or a["status"] != "AGENDADO":
                raise S.ApiError("Agendamento não encontrado.", 404)
            cur.execute("UPDATE agenda_doacoes SET status='CANCELADO' WHERE id=%s", (agenda_id,))
            avisar_equipe_banco(cur, a["banco_id"], "Agendamento cancelado",
                                f"{primeiro_nome(d['nome'])} cancelou a doação de {a['inicio'].strftime('%d/%m às %H:%M')}. A vaga foi liberada.", "agenda")
            auditar(cur, self.uid(), "CANCELAR", "agenda", "agenda_doacoes", agenda_id)
            if a["inicio"] > datetime.now():
                self.encaixar(cur, a, d["id"])
        transacao(gravar)
        self.send_json({"ok": True, "mensagem": "Agendamento cancelado. A vaga foi liberada."})

    def encaixar(self, cur, agendamento, quem_cancelou):
        """Encaixe automático: a vaga liberada é oferecida a até 3 convocados (últimos 14 dias, mesma unidade)
        que ainda não agendaram. Quem tocar primeiro em Agendar fica com ela."""
        cur.execute("""SELECT DISTINCT d.usuario_id FROM convocacao_doadores cd JOIN convocacoes c ON c.id=cd.convocacao_id
                       JOIN doadores d ON d.id=cd.doador_id
                       WHERE c.unidade_id=%s AND cd.status='ENVIADA' AND cd.enviada_em > DATE_SUB(NOW(), INTERVAL 14 DAY)
                         AND d.id<>%s AND d.usuario_id IS NOT NULL
                         AND NOT EXISTS (SELECT 1 FROM agenda_doacoes x WHERE x.doador_id=d.id AND x.status='AGENDADO')
                       LIMIT 3""", (agendamento["unidade_id"], quem_cancelou))
        quando = agendamento["inicio"].strftime("%d/%m às %H:%M")
        for r in cur.fetchall():
            avisar(cur, r["usuario_id"], "Abriu uma vaga para você",
                   f"{agendamento['unidade']} tem um horário livre em {quando}. Toque em Agendar para garantir.", "agendar")

    def doador_historico(self, data, query):
        d = self.doador()
        linhas = consulta("""SELECT h.id, h.data, h.status, COALESCE(u.nome, h.local_texto) AS local
                             FROM historico_doacoes h LEFT JOIN unidades u ON u.id=h.unidade_id
                             WHERE h.doador_id=%s ORDER BY h.data DESC""", (d["id"],))
        for l in linhas:
            l["data"] = data_iso(l["data"])
        datas, verificadas = self.datas_doacao(d)
        self.send_json({"doacoes": linhas, "total": len(datas), "verificadas": len(verificadas),
                        "vidas": regras.vidas_impactadas(len(datas)),
                        "ultima_informada": data_iso(d["ultima_doacao_informada"])})

    def doador_declarar(self, data, query):
        d = self.doador()
        try:
            quando = S.parse_date(data.get("data"), "data da doação")
        except ValueError as exc:
            raise S.ApiError(str(exc))
        if quando > S.hoje():
            raise S.ApiError("A data não pode ser futura.")
        local = texto(data, "local", 150, rotulo="o local da doação")

        def gravar(cur):
            cur.execute("INSERT INTO historico_doacoes (doador_id, local_texto, data, status) VALUES (%s,%s,%s,'DECLARADA')",
                        (d["id"], local, quando))
            auditar(cur, self.uid(), "DECLARAR", "doacoes", "historico_doacoes", cur.lastrowid, {"local": local})
        transacao(gravar)
        self.send_json({"ok": True, "mensagem": "Doação registrada como declarada. Ela conta para o intervalo entre doações."}, 201)

    def doador_direitos(self, data, query):
        d = self.doador()
        _, verificadas = self.datas_doacao(d)
        beneficios = consulta("""SELECT id, uf, titulo, descricao, minimo_homens, minimo_mulheres, janela_meses
                                 FROM beneficios_estado WHERE ativo=1 AND (uf IS NULL OR uf=%s)
                                 ORDER BY uf IS NULL, id""", (d["uf"],))
        for b in beneficios:
            if b["minimo_homens"]:
                janela = S.hoje() - timedelta(days=30 * (b["janela_meses"] or 12))
                feitas = len([v for v in verificadas if v > janela])
                b["meta"] = regras.meta_regular(d["sexo"] or "M", b["minimo_homens"], b["minimo_mulheres"], feitas)
        regular = any(b.get("meta", {}).get("cumprida") for b in beneficios)
        self.send_json({"uf": d["uf"], "beneficios": beneficios,
                        "conquistas": regras.conquistas(len(self.datas_doacao(d)[0]), regular),
                        "aviso": "O HemoFlow não emite documento oficial. A comprovação é a declaração do banco de sangue."})

    def doador_vantagens(self, data, query):
        d = self.doador()
        _, verificadas = self.datas_doacao(d)
        pode = regras.pode_gerar_cupom(max(verificadas) if verificadas else None, S.hoje())
        ofertas = consulta("""
            SELECT o.id, o.titulo, o.descricao, o.validade, o.destaque, p.nome AS parceiro, p.tipo, p.cidade, p.endereco,
                   (o.tipo_emergencia=%s AND o.emergencia_ate >= CURDATE()) AS emergencia
            FROM ofertas o JOIN parceiros p ON p.id=o.parceiro_id AND p.status='ATIVO'
            WHERE o.status='APROVADA' AND (o.validade IS NULL OR o.validade >= CURDATE()) AND p.uf=%s
            ORDER BY emergencia DESC, o.destaque DESC, (p.cidade=%s) DESC, o.id DESC""", (d["tipo_sanguineo"], d["uf"], d["cidade"]))
        cupons = consulta("""SELECT c.codigo, c.expira_em, c.usado_em, o.titulo, p.nome AS parceiro, o.id AS oferta_id
                             FROM cupons c JOIN ofertas o ON o.id=c.oferta_id JOIN parceiros p ON p.id=o.parceiro_id
                             WHERE c.doador_id=%s ORDER BY c.id DESC LIMIT 20""", (d["id"],))
        for o in ofertas:
            o["validade"] = data_iso(o["validade"])
            o["emergencia"] = bool(o["emergencia"])
        for c in cupons:
            c["expira_em"], c["usado_em"] = data_iso(c["expira_em"]), data_iso(c["usado_em"])
        self.send_json({"pode_gerar": pode, "ofertas": ofertas, "cupons": cupons,
                        "regra": "Cupons liberados para quem tem doação verificada nos últimos 6 meses."})

    def doador_gerar_cupom(self, data, query):
        d = self.doador()
        _, verificadas = self.datas_doacao(d)
        if not regras.pode_gerar_cupom(max(verificadas) if verificadas else None, S.hoje()):
            raise S.ApiError("Doe e tenha a doação confirmada pelo banco de sangue para liberar os cupons.", 403)
        oferta_id = inteiro(data.get("oferta_id"), "a oferta", 1, 10**12)

        def gravar(cur):
            cur.execute("""SELECT o.id, o.validade FROM ofertas o JOIN parceiros p ON p.id=o.parceiro_id
                           WHERE o.id=%s AND o.status='APROVADA' AND p.status='ATIVO'""", (oferta_id,))
            oferta = cur.fetchone()
            if not oferta:
                raise S.ApiError("Oferta indisponível.", 404)
            cur.execute("""SELECT codigo, expira_em FROM cupons WHERE oferta_id=%s AND doador_id=%s
                           AND usado_em IS NULL AND expira_em >= CURDATE()""", (oferta_id, d["id"]))
            existente = cur.fetchone()
            if existente:
                return {"codigo": existente["codigo"], "expira_em": data_iso(existente["expira_em"])}
            expira = S.hoje() + timedelta(days=30)
            if oferta["validade"] and oferta["validade"] < expira:
                expira = oferta["validade"]
            codigo = "DOA-" + codigo_aleatorio(4, string.ascii_uppercase + string.digits)
            cur.execute("INSERT INTO cupons (oferta_id, doador_id, codigo, expira_em) VALUES (%s,%s,%s,%s)",
                        (oferta_id, d["id"], codigo, expira))
            auditar(cur, self.uid(), "GERAR", "cupons", "cupons", cur.lastrowid, {"oferta": oferta_id})
            return {"codigo": codigo, "expira_em": data_iso(expira)}
        self.send_json({"ok": True, "cupom": transacao(gravar)}, 201)

    def doador_codigo_parceiro(self, data, query):
        d = self.doador()
        codigo = texto(data, "codigo", 20, rotulo="o código").upper()
        p = consulta("SELECT id, nome FROM parceiros WHERE codigo_alunos=%s AND status='ATIVO'", (codigo,), um=True)
        if not p:
            raise S.ApiError("Código não encontrado. Confira com a sua instituição.", 404)

        def gravar(cur):
            cur.execute("INSERT IGNORE INTO doador_parceiros (doador_id, parceiro_id) VALUES (%s,%s)", (d["id"], p["id"]))
            auditar(cur, self.uid(), "VINCULAR", "parceiros", "doador_parceiros", p["id"])
        transacao(gravar)
        self.send_json({"ok": True, "mensagem": f"Pronto! Você agora faz parte de {p['nome']}."})

    def doador_declaracao(self, data, query):
        """Declaração de doação para um cursinho ou faculdade parceira em que o doador está vinculado."""
        d = self.doador()
        parceiro_id = inteiro(data.get("parceiro_id"), "a instituição", 1, 10**12)
        p = consulta("""SELECT p.id, p.nome, p.tipo FROM doador_parceiros dp JOIN parceiros p ON p.id=dp.parceiro_id
                        WHERE dp.doador_id=%s AND p.id=%s AND p.tipo<>'COMERCIO'""", (d["id"], parceiro_id), um=True)
        if not p:
            raise S.ApiError("Você não está vinculado a essa instituição.", 404)
        doacoes = consulta("""SELECT h.data, COALESCE(u.nome, h.local_texto) AS local FROM historico_doacoes h
                              LEFT JOIN unidades u ON u.id=h.unidade_id WHERE h.doador_id=%s AND h.status='VERIFICADA'
                              ORDER BY h.data DESC""", (d["id"],))
        if not doacoes:
            raise S.ApiError("A declaração lista doações verificadas pelo banco de sangue. Você ainda não tem nenhuma.", 409)
        codigo = "DEC-" + codigo_aleatorio(6, string.ascii_uppercase + string.digits)

        def gravar(cur):
            cur.execute("""INSERT INTO declaracoes (codigo, doador_id, parceiro_id, total_doacoes, ultima_doacao)
                           VALUES (%s,%s,%s,%s,%s)""", (codigo, d["id"], p["id"], len(doacoes), doacoes[0]["data"]))
            auditar(cur, self.uid(), "DECLARACAO", "doador", "declaracoes", cur.lastrowid, {"parceiro": p["id"]})
        transacao(gravar)
        self.send_json({"ok": True, "codigo": codigo, "nome": d["nome"], "cpf_mascarado": S.mask_cpf(d["cpf"]),
                        "instituicao": p["nome"], "emitida_em": S.hoje().isoformat(),
                        "doacoes": [{"data": data_iso(x["data"]), "local": x["local"]} for x in doacoes]}, 201)

    def verificar_declaracao(self, data, query, codigo):
        """Público: confere se uma declaração existe (mostra só o nome abreviado, por privacidade)."""
        r = consulta("""SELECT dc.codigo, dc.total_doacoes, dc.ultima_doacao, dc.criado_em, d.nome, p.nome AS instituicao
                        FROM declaracoes dc JOIN doadores d ON d.id=dc.doador_id JOIN parceiros p ON p.id=dc.parceiro_id
                        WHERE dc.codigo=%s""", (codigo.upper()[:10],), um=True)
        if not r:
            return self.send_json({"valida": False, "erro": "Declaração não encontrada. Confira o código."}, 404)
        partes = r["nome"].split()
        self.send_json({"valida": True, "codigo": r["codigo"], "nome": partes[0] + (f" {partes[-1][0]}." if len(partes) > 1 else ""),
                        "instituicao": r["instituicao"], "total_doacoes": r["total_doacoes"],
                        "ultima_doacao": data_iso(r["ultima_doacao"]), "emitida_em": data_iso(r["criado_em"])})

    def doador_grupos(self, data, query):
        d = self.doador()
        grupos = consulta("""SELECT g.id, g.nome, g.codigo, g.meta FROM grupos g
                             JOIN grupo_membros m ON m.grupo_id=g.id WHERE m.doador_id=%s ORDER BY g.id DESC""", (d["id"],))
        for g in grupos:
            membros = consulta("""SELECT dd.nome, (SELECT COUNT(*) FROM historico_doacoes h WHERE h.doador_id=dd.id
                                     AND h.status='VERIFICADA' AND h.data > DATE_SUB(CURDATE(), INTERVAL 6 MONTH)) AS doacoes
                                  FROM grupo_membros m JOIN doadores dd ON dd.id=m.doador_id WHERE m.grupo_id=%s
                                  ORDER BY doacoes DESC, dd.nome""", (g["id"],))
            g["membros"] = [{"nome": primeiro_nome(m["nome"]), "doacoes": m["doacoes"]} for m in membros]
            g["total"] = sum(m["doacoes"] for m in membros)
        self.send_json(grupos)

    def doador_criar_grupo(self, data, query):
        d = self.doador()
        nome = texto(data, "nome", 120, rotulo="o nome do grupo")
        meta = inteiro(data.get("meta", 10), "a meta", 1, 1000)

        def gravar(cur):
            codigo = "GRP-" + codigo_aleatorio(5, string.ascii_uppercase + string.digits)
            cur.execute("INSERT INTO grupos (nome, codigo, meta, criado_por) VALUES (%s,%s,%s,%s)", (nome, codigo, meta, d["id"]))
            gid = cur.lastrowid
            cur.execute("INSERT INTO grupo_membros (grupo_id, doador_id) VALUES (%s,%s)", (gid, d["id"]))
            return codigo
        codigo = transacao(gravar)
        self.send_json({"ok": True, "codigo": codigo, "mensagem": f"Grupo criado! Convide pelo código {codigo}."}, 201)

    def doador_entrar_grupo(self, data, query):
        d = self.doador()
        codigo = texto(data, "codigo", 12, rotulo="o código do grupo").upper()
        g = consulta("SELECT id, nome FROM grupos WHERE codigo=%s", (codigo,), um=True)
        if not g:
            raise S.ApiError("Grupo não encontrado.", 404)
        transacao(lambda cur: cur.execute("INSERT IGNORE INTO grupo_membros (grupo_id, doador_id) VALUES (%s,%s)", (g["id"], d["id"])))
        self.send_json({"ok": True, "mensagem": f"Você entrou no grupo {g['nome']}."})

    def doador_perfil(self, data, query):
        d = self.doador()
        parceiros = consulta("""SELECT p.id, p.nome, p.tipo FROM doador_parceiros dp JOIN parceiros p ON p.id=dp.parceiro_id
                                WHERE dp.doador_id=%s""", (d["id"],))
        self.send_json({**{k: data_iso(v) for k, v in d.items() if k != "cpf"}, "cpf_mascarado": S.mask_cpf(d["cpf"]),
                        "parceiros": parceiros})

    def doador_salvar_perfil(self, data, query):
        d = self.doador()
        campos, valores = [], []
        if "consentimento_convocacao" in data:
            consentiu = bool(data["consentimento_convocacao"])
            campos += ["consentimento_convocacao=%s", "consentimento_em=%s"]
            valores += [int(consentiu), datetime.now() if consentiu else None]
        if "telefone" in data:
            try:
                valores.append(S.format_phone(str(data["telefone"])) if data["telefone"] else None)
            except ValueError as exc:
                raise S.ApiError(str(exc))
            campos.append("telefone=%s")
        if "cidade" in data:
            campos.append("cidade=%s")
            valores.append(texto(data, "cidade", 80, rotulo="a cidade"))
        if "uf" in data:
            uf = str(data["uf"]).upper()
            if uf not in S.UFS:
                raise S.ApiError("Selecione o estado (UF).")
            campos.append("uf=%s")
            valores.append(uf)
        if not campos:
            raise S.ApiError("Nada para salvar.")

        def gravar(cur):
            cur.execute(f"UPDATE doadores SET {', '.join(campos)} WHERE id=%s", (*valores, d["id"]))
            auditar(cur, self.uid(), "EDITAR", "doador", "doadores", d["id"], {"campos": list(data)})
        transacao(gravar)
        self.send_json({"ok": True, "mensagem": "Perfil atualizado."})

    # ------------------------------------------------------------------------
    # Excluir a própria conta (LGPD, art. 18, VI): apaga os dados pessoais e
    # mantém só o histórico ANONIMIZADO (tipo, data e local), que não identifica
    # ninguém e preserva os números dos bancos de sangue (LGPD, art. 16).
    # ------------------------------------------------------------------------
    def doador_resumo_exclusao(self, data, query):
        """O que será afetado (mostrado na janela de confirmação)."""
        d = self.doador()
        ag = consulta("""SELECT v.inicio, u.nome AS unidade FROM agenda_doacoes a JOIN vagas v ON v.id=a.vaga_id
                         JOIN unidades u ON u.id=a.unidade_id WHERE a.doador_id=%s AND a.status='AGENDADO' AND v.inicio > NOW()
                         ORDER BY v.inicio""", (d["id"],))
        cupons = consulta("SELECT COUNT(*) AS n FROM cupons WHERE doador_id=%s AND usado_em IS NULL AND expira_em >= CURDATE()",
                          (d["id"],), um=True)["n"]
        self.send_json({"agendamentos": [{"inicio": data_iso(a["inicio"]), "unidade": a["unidade"]} for a in ag],
                        "cupons_ativos": cupons, "pode_confirmar_com_senha": True})

    def doador_excluir_conta(self, data, query):
        d = self.doador()
        if str(data.get("confirmacao", "")).strip().upper() != "EXCLUIR":
            raise S.ApiError("Para confirmar, escreva EXCLUIR no campo indicado.")
        u = consulta("SELECT id, email, senha_hash FROM usuarios WHERE id=%s", (self.uid(),), um=True)
        if self.ctx.get("admin_real"):
            raise S.ApiError("No modo “Entrar como”, o admin não pode excluir a conta do doador por aqui.", 403)
        if not u or not S.verify_password(str(data.get("senha", "")), u["senha_hash"]):
            raise S.ApiError("Senha incorreta. A conta não foi excluída.", 403)
        email_original, nome_original = u["email"], d["nome"]

        def gravar(cur):
            # 1) agendamentos futuros: cancela e avisa o banco de sangue
            cur.execute("""SELECT a.id, v.inicio, u.banco_id FROM agenda_doacoes a JOIN vagas v ON v.id=a.vaga_id
                           JOIN unidades u ON u.id=a.unidade_id WHERE a.doador_id=%s AND a.status='AGENDADO' AND v.inicio > NOW()""",
                        (d["id"],))
            for a in cur.fetchall():
                cur.execute("UPDATE agenda_doacoes SET status='CANCELADO' WHERE id=%s", (a["id"],))
                avisar_equipe_banco(cur, a["banco_id"], "Agendamento cancelado",
                                    f"Um doador excluiu a conta e o agendamento de {a['inicio'].strftime('%d/%m às %H:%M')} foi cancelado. A vaga foi liberada.",
                                    "agenda")
            # 2) vínculos e itens pessoais
            cur.execute("DELETE FROM cupons WHERE doador_id=%s AND usado_em IS NULL", (d["id"],))
            cur.execute("DELETE FROM grupo_membros WHERE doador_id=%s", (d["id"],))
            cur.execute("DELETE FROM doador_parceiros WHERE doador_id=%s", (d["id"],))
            cur.execute("DELETE FROM convocacao_doadores WHERE doador_id=%s AND status='ENVIADA'", (d["id"],))
            cur.execute("DELETE FROM declaracoes WHERE doador_id=%s", (d["id"],))
            cur.execute("UPDATE historico_doacoes SET local_texto=NULL WHERE doador_id=%s AND unidade_id IS NOT NULL", (d["id"],))
            # 3) cadastro do doador: apaga tudo o que identifica; ficam tipo sanguíneo e estado (estatística)
            cur.execute("""UPDATE doadores SET nome='Doador removido', cpf=NULL, email=NULL, telefone=NULL, data_nascimento=NULL,
                               cep=NULL, logradouro=NULL, numero=NULL, complemento=NULL, bairro=NULL, cidade=NULL,
                               codigo_ficticio=NULL, observacoes=NULL, peso_kg=NULL, sexo=NULL, ultima_doacao_informada=NULL,
                               consentimento_convocacao=0, consentimento_em=NULL, responsavel_nome=NULL, responsavel_consentiu=0,
                               usuario_id=NULL, status='INATIVO' WHERE id=%s""", (d["id"],))
            # 4) login: perfil, avisos e códigos apagados; e-mail, nome e senha viram valores que ninguém conhece
            uid = self.uid()
            for tabela in ("usuario_perfis", "avisos", "codigos_login", "recuperacao_senhas"):
                cur.execute(f"DELETE FROM {tabela} WHERE usuario_id=%s", (uid,))
            # o registro do aceite tinha IP e nome do responsável: fica só a marca de que existiu
            cur.execute("""UPDATE historico_auditoria SET detalhes_json=%s WHERE usuario_id=%s AND acao IN ('ACEITE_TERMOS','CADASTRO','EDITAR')""",
                        ('{"anonimizado": true}', uid))
            cur.execute("""UPDATE usuarios SET nome='Conta removida', email=%s, senha_hash=%s, status='INATIVO',
                               tentativas_falhas=0, bloqueado_ate=NULL, banco_id=NULL, parceiro_id=NULL WHERE id=%s""",
                        (f"removido.{uid}.{secrets.token_hex(4)}@hemoflow.invalid", S.password_hash(secrets.token_urlsafe(32)), uid))
            # registro sem dados pessoais (prova de que o pedido foi atendido)
            auditar(cur, None, "EXCLUSAO_CONTA", "lgpd", "doadores", d["id"], {"anonimizado": True})
        transacao(gravar)
        for token, sessao in list(S.SESSIONS.items()):  # encerra todas as sessões abertas dessa conta
            if sessao["id"] == self.uid():
                S.SESSIONS.pop(token, None)
        self.enviar_confirmacao_exclusao(email_original, nome_original)
        self.send_json({"ok": True, "mensagem": "Sua conta foi excluída e seus dados pessoais foram apagados. Obrigado por ter doado com o HemoFlow."},
                       200, [("Set-Cookie", S.session_cookie("", 0))])

    def enviar_confirmacao_exclusao(self, email, nome):
        """E-mail de confirmação (nunca para endereços de demonstração @exemplo.com)."""
        if not email or email.endswith("@exemplo.com") or not S.email_configured():
            return
        try:
            msg = S.EmailMessage()
            msg["Subject"] = "HemoFlow · sua conta foi excluída"
            msg["From"] = f"HemoFlow <{S.EMAIL_FROM}>"
            msg["To"] = email
            msg.set_content(
                f"Olá, {primeiro_nome(nome)}.\n\nConfirmamos a exclusão da sua conta no HemoFlow em {S.hoje().strftime('%d/%m/%Y')}.\n"
                "Seus dados pessoais foram apagados. Guardamos apenas o histórico de doações sem nada que identifique você "
                "e os registros de acesso pelo prazo exigido pelo Marco Civil da Internet (6 meses).\n\n"
                "Se não foi você quem pediu, responda este e-mail.\n\nObrigado por doar sangue. HemoFlow · Doe. Volte. Salve vidas.")
            S.deliver_email(msg)
        except Exception as exc:  # noqa: BLE001 - o e-mail é cortesia: a exclusão já foi feita
            print("Aviso: e-mail de confirmação de exclusão não enviado:", type(exc).__name__)

    # ========================================================================
    # E. PAINEL DO BANCO DE SANGUE
    # ========================================================================
    def banco_id(self):
        if not self.ctx.get("banco_id"):
            raise S.ApiError("Conta sem banco de sangue vinculado.", 403)
        return self.ctx["banco_id"]

    def unidade_do_banco(self, unidade_id):
        un = consulta("SELECT id, nome, cidade, uf, banco_id FROM unidades WHERE id=%s AND banco_id=%s",
                      (unidade_id, self.banco_id()), um=True)
        if not un:
            raise S.ApiError("Unidade não encontrada neste banco de sangue.", 404)
        return un

    def banco_painel(self, data, query):
        b = consulta("SELECT id, nome, cidade, uf, status FROM bancos_sangue WHERE id=%s", (self.banco_id(),), um=True)
        unidades = consulta("SELECT id, nome, endereco, bairro, cidade, uf, horario FROM unidades WHERE banco_id=%s AND ativo=1 ORDER BY id",
                            (self.banco_id(),))
        for un in unidades:
            niveis = {l["tipo_sanguineo"]: l for l in consulta("SELECT * FROM estoque_niveis WHERE unidade_id=%s", (un["id"],))}
            saidas = {l["tipo_sanguineo"]: int(l["n"]) for l in consulta(
                """SELECT tipo_sanguineo, SUM(quantidade) AS n FROM estoque_movimentos WHERE unidade_id=%s AND movimento='SAIDA'
                   AND criado_em > DATE_SUB(NOW(), INTERVAL %s DAY) GROUP BY tipo_sanguineo""", (un["id"], regras.JANELA_PREVISAO_DIAS))}
            un["termometro"] = []
            for tipo in regras.TIPOS:
                l = niveis.get(tipo) or {"quantidade": 0, "limite_critico": 5, "limite_atencao": 10, "atualizado_em": None, "editado_admin": 0}
                un["termometro"].append({"tipo": tipo, "quantidade": l["quantidade"], "limite_critico": l["limite_critico"],
                                         "limite_atencao": l["limite_atencao"], "nivel": regras.nivel(l["quantidade"], l["limite_critico"], l["limite_atencao"]),
                                         "faltam": regras.bolsas_faltando(l["quantidade"], l["limite_atencao"]),
                                         "previsao_dias": regras.previsao_dias(l["quantidade"], saidas.get(tipo, 0)),
                                         "atualizado_em": data_iso(l["atualizado_em"]), "editado_admin": bool(l["editado_admin"])})
            un["movimentos"] = consulta("""SELECT tipo_sanguineo, movimento, quantidade, motivo, criado_em FROM estoque_movimentos
                                           WHERE unidade_id=%s ORDER BY id DESC LIMIT 12""", (un["id"],))
            for m in un["movimentos"]:
                m["criado_em"] = data_iso(m["criado_em"])
        self.send_json({"banco": b, "unidades": unidades, "admin_como": bool(self.ctx.get("admin_real"))})

    def banco_movimento(self, data, query):
        un = self.unidade_do_banco(inteiro(data.get("unidade_id"), "a unidade", 1, 10**12))
        tipo = str(data.get("tipo_sanguineo", "")).upper()
        mov = str(data.get("movimento", "")).upper()
        qtd = inteiro(data.get("quantidade"), "a quantidade", 0 if mov == "AJUSTE" else 1, 10000)
        if tipo not in regras.TIPOS or mov not in ("ENTRADA", "SAIDA", "AJUSTE"):
            raise S.ApiError("Informe o tipo sanguíneo e o movimento (entrada, saída ou ajuste).")
        motivo = texto(data, "motivo", 200, obrigatorio=False)
        para_paciente = mov == "SAIDA" and bool(data.get("para_paciente"))
        admin = bool(self.ctx.get("admin_real"))

        def gravar(cur):
            cur.execute("INSERT IGNORE INTO estoque_niveis (unidade_id, tipo_sanguineo) VALUES (%s,%s)", (un["id"], tipo))
            cur.execute("""SELECT quantidade, limite_critico, limite_atencao FROM estoque_niveis
                           WHERE unidade_id=%s AND tipo_sanguineo=%s FOR UPDATE""", (un["id"], tipo))
            linha = cur.fetchone()
            atual = linha["quantidade"]
            novo = atual + qtd if mov == "ENTRADA" else atual - qtd if mov == "SAIDA" else qtd
            if novo < 0:
                raise S.ApiError(f"Saída maior que o estoque atual ({atual} bolsas).", 409)
            cur.execute("""UPDATE estoque_niveis SET quantidade=%s, atualizado_em=NOW(), atualizado_por=%s, editado_admin=%s
                           WHERE unidade_id=%s AND tipo_sanguineo=%s""", (novo, self.uid(), int(admin), un["id"], tipo))
            cur.execute("""INSERT INTO estoque_movimentos (unidade_id, tipo_sanguineo, movimento, quantidade, motivo, usuario_id)
                           VALUES (%s,%s,%s,%s,%s,%s)""", (un["id"], tipo, mov, qtd, motivo, self.uid()))
            auditar(cur, self.uid(), mov, "estoque", "estoque_niveis", un["id"], {"tipo": tipo, "de": atual, "para": novo, "admin": admin})
            # Alerta automático: o tipo acabou de entrar no crítico -> a equipe recebe o atalho para convocar
            if regras.entrou_no_critico(atual, novo, linha["limite_critico"], linha["limite_atencao"]):
                avisar_equipe_banco(cur, un["banco_id"], f"{tipo} entrou no nível crítico",
                                    f"{un['nome']}: {novo} bolsas de {tipo}. Convoque doadores compatíveis agora.", f"convocar:{tipo}")
            if para_paciente:
                self.avisar_impacto(cur, un, tipo)
            return novo
        novo = transacao(gravar)
        self.send_json({"ok": True, "quantidade": novo, "mensagem": f"Estoque de {tipo} atualizado: {novo} bolsas."})

    TITULO_IMPACTO = "Doações como a sua salvam vidas 💛"

    def avisar_impacto(self, cur, un, tipo):
        """Saída de bolsa para paciente: avisa quem doou esse tipo nesse banco nos últimos 42 dias (validade das
        hemácias). Mensagem honesta: o sistema conta bolsas por tipo, não sabe qual bolsa foi de quem.
        No máximo um aviso desses por doador a cada 7 dias."""
        cur.execute("""SELECT DISTINCT d.usuario_id FROM historico_doacoes h JOIN doadores d ON d.id=h.doador_id
                       JOIN unidades u ON u.id=h.unidade_id
                       WHERE u.banco_id=%s AND d.tipo_sanguineo=%s AND h.status='VERIFICADA' AND d.usuario_id IS NOT NULL
                         AND h.data >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                         AND NOT EXISTS (SELECT 1 FROM avisos a WHERE a.usuario_id=d.usuario_id AND a.titulo=%s
                                         AND a.criado_em > DATE_SUB(NOW(), INTERVAL 7 DAY))""",
                    (un["banco_id"], tipo, regras.VALIDADE_HEMACIAS_DIAS, self.TITULO_IMPACTO))
        for r in cur.fetchall():
            avisar(cur, r["usuario_id"], self.TITULO_IMPACTO,
                   f"Uma bolsa {tipo} saiu do {un['nome']} para atender um paciente. "
                   "Doações como a sua tornam isso possível. Obrigado!", "inicio")

    def banco_limites(self, data, query):
        un = self.unidade_do_banco(inteiro(data.get("unidade_id"), "a unidade", 1, 10**12))
        tipo = str(data.get("tipo_sanguineo", "")).upper()
        if tipo not in regras.TIPOS:
            raise S.ApiError("Selecione o tipo sanguíneo.")
        critico = inteiro(data.get("limite_critico"), "o limite crítico", 0, 10000)
        atencao = inteiro(data.get("limite_atencao"), "o limite de atenção", 0, 10000)
        if atencao < critico:
            raise S.ApiError("O limite de atenção deve ser maior ou igual ao limite crítico.")

        def gravar(cur):
            cur.execute("""INSERT INTO estoque_niveis (unidade_id, tipo_sanguineo, limite_critico, limite_atencao)
                           VALUES (%s,%s,%s,%s) ON DUPLICATE KEY UPDATE limite_critico=VALUES(limite_critico),
                           limite_atencao=VALUES(limite_atencao)""", (un["id"], tipo, critico, atencao))
            auditar(cur, self.uid(), "LIMITES", "estoque", "estoque_niveis", un["id"], {"tipo": tipo, "critico": critico, "atencao": atencao})
        transacao(gravar)
        self.send_json({"ok": True, "mensagem": f"Limites de {tipo} salvos."})

    def candidatos(self, un, tipo):
        """Doadores compatíveis, que consentiram, da mesma cidade/UF e aptos agora."""
        compat = regras.doadores_compativeis(tipo)
        marcadores = ",".join(["%s"] * len(compat))
        linhas = consulta(f"""
            SELECT d.id, d.nome, d.tipo_sanguineo, d.sexo, d.data_nascimento, d.ultima_doacao_informada,
                   d.responsavel_consentiu, d.usuario_id, d.email,
                   (SELECT MAX(h.data) FROM historico_doacoes h WHERE h.doador_id=d.id) AS ultima
            FROM doadores d
            WHERE d.status='ATIVO' AND d.consentimento_convocacao=1 AND d.usuario_id IS NOT NULL
              AND d.tipo_sanguineo IN ({marcadores}) AND d.uf=%s AND d.cidade=%s
              AND d.id NOT IN (SELECT cd.doador_id FROM convocacao_doadores cd WHERE cd.enviada_em > DATE_SUB(NOW(), INTERVAL 7 DAY))
              AND d.id NOT IN (SELECT a.doador_id FROM agenda_doacoes a JOIN vagas v ON v.id=a.vaga_id
                               WHERE a.status='AGENDADO' AND v.inicio > NOW())""",
                          (*compat, un["uf"], un["cidade"]))
        total = len(linhas)
        aptos = []
        for d in linhas:
            datas = [r["data"] for r in consulta("SELECT data FROM historico_doacoes WHERE doador_id=%s", (d["id"],))]
            if d["ultima_doacao_informada"]:
                datas.append(d["ultima_doacao_informada"])
            if regras.aptidao(d["sexo"] or "M", d["data_nascimento"], datas, S.hoje(), bool(d["responsavel_consentiu"]))["apto"]:
                aptos.append(d)
        aptos.sort(key=lambda d: d["ultima"] or d["ultima_doacao_informada"] or date(1900, 1, 1))
        return total, aptos

    def resumo_sugestao(self, un, tipo):
        n = consulta("SELECT quantidade, limite_critico, limite_atencao FROM estoque_niveis WHERE unidade_id=%s AND tipo_sanguineo=%s",
                     (un["id"], tipo), um=True) or {"quantidade": 0, "limite_critico": 5, "limite_atencao": 10}
        faltam = regras.bolsas_faltando(n["quantidade"], n["limite_atencao"])
        vagas = sum(v["livres"] for v in self.vagas_livres(un["id"], dias=7))
        total, aptos = self.candidatos(un, tipo)
        return {"unidade": un["nome"], "tipo": tipo, "quantidade": n["quantidade"], "faltam": faltam,
                "nivel": regras.nivel(n["quantidade"], n["limite_critico"], n["limite_atencao"]),
                "compativeis": regras.doadores_compativeis(tipo), "cadastrados_regiao": total, "aptos": len(aptos),
                "vagas_livres": vagas, "convocar": regras.quantos_convocar(faltam, vagas, len(aptos)),
                "regiao": f"{un['cidade']}/{un['uf']}"}, aptos

    def banco_sugestao(self, data, query):
        un = self.unidade_do_banco(inteiro(query.get("unidade_id", ["0"])[0], "a unidade", 1, 10**12))
        tipo = (query.get("tipo", [""])[0] or "").upper()
        if tipo not in regras.TIPOS:
            raise S.ApiError("Selecione o tipo sanguíneo.")
        resumo, _ = self.resumo_sugestao(un, tipo)
        resumo["mensagem_sugerida"] = f"Nosso estoque de {tipo} está baixo. Sua doação pode salvar até 4 vidas. Escolha um horário no app."
        self.send_json(resumo)

    def banco_convocar(self, data, query):
        un = self.unidade_do_banco(inteiro(data.get("unidade_id"), "a unidade", 1, 10**12))
        tipo = str(data.get("tipo_sanguineo", "")).upper()
        if tipo not in regras.TIPOS:
            raise S.ApiError("Selecione o tipo sanguíneo.")
        mensagem = texto(data, "mensagem", 500, rotulo="a mensagem")
        resumo, aptos = self.resumo_sugestao(un, tipo)
        if resumo["vagas_livres"] <= 0:
            raise S.ApiError("Não há vagas livres na agenda dos próximos 7 dias. Abra vagas antes de convocar.", 409)
        quantidade = resumo["convocar"] if data.get("quantidade") in (None, "") else min(
            inteiro(data.get("quantidade"), "a quantidade", 1, 500), resumo["vagas_livres"], len(aptos))
        escolhidos = aptos[:quantidade]
        if not escolhidos:
            raise S.ApiError("Nenhum doador compatível e apto na região neste momento.", 409)

        def gravar(cur):
            cur.execute("""INSERT INTO convocacoes (banco_id, unidade_id, tipo_sanguineo, bolsas_faltando, mensagem, cidade, uf, criado_por)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (self.banco_id(), un["id"], tipo, resumo["faltam"], mensagem, un["cidade"], un["uf"], self.uid()))
            cid = cur.lastrowid
            for d in escolhidos:
                cur.execute("INSERT INTO convocacao_doadores (convocacao_id, doador_id) VALUES (%s,%s)", (cid, d["id"]))
                avisar(cur, d["usuario_id"], f"{un['nome']} precisa de você", mensagem, f"convocacao:{cid}")
            auditar(cur, self.uid(), "CONVOCAR", "convocacoes", "convocacoes", cid, {"tipo": tipo, "doadores": len(escolhidos)})
            return cid
        cid = transacao(gravar)
        if S.os.environ.get("HEMOFLOW_EMAIL_CONVOCACAO") == "1":
            for d in escolhidos:
                if d.get("email") and not d["email"].endswith("@exemplo.com"):
                    msg = EmailMessage()
                    msg["Subject"] = f"{un['nome']} precisa de você · HemoFlow"
                    msg["From"] = f"HemoFlow <{S.EMAIL_FROM}>"
                    msg["To"] = d["email"]
                    msg.set_content(f"Olá, {d['nome'].split()[0]}!\n\n{mensagem}\n\nAbra o app HemoFlow para escolher um horário:\n{S.PUBLIC_URL or ''}\n\nHemoFlow · Doe. Volte. Salve vidas.")
                    try:
                        S.deliver_email(msg)
                    except Exception as exc:  # noqa: BLE001
                        print("Falha ao enviar convocação:", type(exc).__name__)
        self.send_json({"ok": True, "convocacao_id": cid, "convocados": len(escolhidos),
                        "mensagem": f"Convocação enviada para {len(escolhidos)} doadores."}, 201)

    def banco_convocacoes(self, data, query):
        linhas = consulta("""
            SELECT c.id, c.tipo_sanguineo, c.bolsas_faltando, c.mensagem, c.criado_em, u.nome AS unidade,
                   COUNT(cd.doador_id) AS convocados, SUM(cd.status='AGENDOU') AS agendaram,
                   (SELECT COUNT(*) FROM agenda_doacoes a WHERE a.convocacao_id=c.id AND a.status='COMPARECEU') AS doaram
            FROM convocacoes c JOIN unidades u ON u.id=c.unidade_id
            LEFT JOIN convocacao_doadores cd ON cd.convocacao_id=c.id
            WHERE c.banco_id=%s GROUP BY c.id ORDER BY c.id DESC LIMIT 30""", (self.banco_id(),))
        for l in linhas:
            l["criado_em"] = data_iso(l["criado_em"])
            l["agendaram"] = int(l["agendaram"] or 0)
        self.send_json(linhas)

    def banco_agenda(self, data, query):
        un = self.unidade_do_banco(inteiro(query.get("unidade_id", ["0"])[0], "a unidade", 1, 10**12))
        dia = query.get("dia", [""])[0] or S.hoje().isoformat()
        try:
            dia_d = S.parse_date(dia, "dia")
        except ValueError as exc:
            raise S.ApiError(str(exc))
        vagas = consulta("""SELECT v.id, v.inicio, v.capacidade FROM vagas v
                            WHERE v.unidade_id=%s AND DATE(v.inicio)=%s ORDER BY v.inicio""", (un["id"], dia_d))
        for v in vagas:
            ags = consulta("""SELECT a.id, a.status, a.origem, a.codigo, d.nome, d.tipo_sanguineo FROM agenda_doacoes a
                              JOIN doadores d ON d.id=a.doador_id WHERE a.vaga_id=%s AND a.status <> 'CANCELADO' ORDER BY a.id""", (v["id"],))
            v["agendados"] = [{**a, "nome": primeiro_nome(a["nome"])} for a in ags]
            v["livres"] = max(0, v["capacidade"] - len([a for a in ags if a["status"] in ("AGENDADO", "COMPARECEU")]))
            v["inicio"] = data_iso(v["inicio"])
        self.send_json({"unidade": un, "dia": dia_d.isoformat(), "vagas": vagas})

    def banco_criar_vagas(self, data, query):
        un = self.unidade_do_banco(inteiro(data.get("unidade_id"), "a unidade", 1, 10**12))
        try:
            dia = S.parse_date(data.get("dia"), "dia")
        except ValueError as exc:
            raise S.ApiError(str(exc))
        if dia < S.hoje():
            raise S.ApiError("Escolha hoje ou uma data futura.")
        horarios = data.get("horarios") or []
        if not isinstance(horarios, list) or not horarios or len(horarios) > 24:
            raise S.ApiError("Informe os horários (ex.: 08:00, 09:00).")
        capacidade = inteiro(data.get("capacidade", 4), "a capacidade", 1, 100)

        def gravar(cur):
            criadas = 0
            for h in horarios:
                if not re.fullmatch(r"\d{2}:\d{2}", str(h)):
                    raise S.ApiError(f"Horário inválido: {h}. Use HH:MM.")
                inicio = datetime.combine(dia, datetime.strptime(h, "%H:%M").time())
                cur.execute("""INSERT INTO vagas (unidade_id, inicio, capacidade) VALUES (%s,%s,%s)
                               ON DUPLICATE KEY UPDATE capacidade=VALUES(capacidade)""", (un["id"], inicio, capacidade))
                criadas += 1
            auditar(cur, self.uid(), "VAGAS", "agenda", "vagas", un["id"], {"dia": dia, "horarios": horarios, "capacidade": capacidade})
            return criadas
        n = transacao(gravar)
        self.send_json({"ok": True, "mensagem": f"{n} horários abertos em {dia.strftime('%d/%m')}."}, 201)

    def banco_confirmar(self, data, query):
        codigo = S.only_digits(str(data.get("codigo", "")))
        if len(codigo) != 6:
            raise S.ApiError("Digite os 6 números do código do doador.")

        def gravar(cur):
            cur.execute("""SELECT a.id, a.doador_id, a.unidade_id, a.status, v.inicio, d.nome, d.tipo_sanguineo, d.usuario_id, u.nome AS unidade
                           FROM agenda_doacoes a JOIN vagas v ON v.id=a.vaga_id JOIN unidades u ON u.id=a.unidade_id
                           JOIN doadores d ON d.id=a.doador_id
                           WHERE a.codigo=%s AND u.banco_id=%s AND a.status='AGENDADO'
                             AND DATE(v.inicio) BETWEEN DATE_SUB(CURDATE(), INTERVAL 1 DAY) AND DATE_ADD(CURDATE(), INTERVAL 1 DAY)
                           ORDER BY v.inicio LIMIT 1 FOR UPDATE""", (codigo, self.banco_id()))
            a = cur.fetchone()
            if not a:
                raise S.ApiError("Código não encontrado entre os agendamentos de hoje deste banco.", 404)
            cur.execute("UPDATE agenda_doacoes SET status='COMPARECEU' WHERE id=%s", (a["id"],))
            cur.execute("""INSERT INTO historico_doacoes (doador_id, unidade_id, data, status, agenda_id, confirmado_por)
                           VALUES (%s,%s,CURDATE(),'VERIFICADA',%s,%s)""", (a["doador_id"], a["unidade_id"], a["id"], self.uid()))
            avisar(cur, a["usuario_id"], "Doação verificada! Obrigado ❤", f"Sua doação em {a['unidade']} foi confirmada. Você pode ter salvo até 4 vidas.", "historico")
            auditar(cur, self.uid(), "CONFIRMAR", "doacoes", "agenda_doacoes", a["id"], {"doador": a["doador_id"]})
            return {"nome": a["nome"], "tipo_sanguineo": a["tipo_sanguineo"], "horario": a["inicio"].strftime("%H:%M")}
        r = transacao(gravar)
        self.send_json({"ok": True, "doador": r, "mensagem": f"Doação de {r['nome']} ({r['tipo_sanguineo']}) registrada como verificada."})

    def banco_faltou(self, data, query, agenda_id):
        def gravar(cur):
            cur.execute("""SELECT a.id FROM agenda_doacoes a JOIN unidades u ON u.id=a.unidade_id
                           WHERE a.id=%s AND u.banco_id=%s AND a.status='AGENDADO'""", (agenda_id, self.banco_id()))
            if not cur.fetchone():
                raise S.ApiError("Agendamento não encontrado.", 404)
            cur.execute("UPDATE agenda_doacoes SET status='FALTOU' WHERE id=%s", (agenda_id,))
            auditar(cur, self.uid(), "FALTOU", "agenda", "agenda_doacoes", agenda_id)
        transacao(gravar)
        self.send_json({"ok": True, "mensagem": "Marcado como não compareceu."})

    def banco_metricas(self, data, query):
        b = self.banco_id()
        dias = inteiro(query.get("dias", ["90"])[0], "o período", 7, 730)
        conv = consulta("""SELECT COUNT(*) AS convocados, SUM(cd.status='AGENDOU') AS agendaram
                           FROM convocacao_doadores cd JOIN convocacoes c ON c.id=cd.convocacao_id
                           WHERE c.banco_id=%s AND cd.enviada_em > DATE_SUB(NOW(), INTERVAL %s DAY)""", (b, dias), um=True)
        ag = consulta("""SELECT SUM(a.status='COMPARECEU') AS compareceram, SUM(a.status='FALTOU') AS faltaram,
                                SUM(a.origem='ESPONTANEO') AS espontaneos, COUNT(*) AS agendamentos
                         FROM agenda_doacoes a JOIN unidades u ON u.id=a.unidade_id
                         WHERE u.banco_id=%s AND a.criado_em > DATE_SUB(NOW(), INTERVAL %s DAY)""", (b, dias), um=True)
        por_doador = consulta("""SELECT h.doador_id, COUNT(*) AS n FROM historico_doacoes h JOIN unidades u ON u.id=h.unidade_id
                                 WHERE u.banco_id=%s AND h.status='VERIFICADA' GROUP BY h.doador_id""", (b,))
        doadores = len(por_doador)
        voltaram = len([p for p in por_doador if p["n"] >= 2])
        por_tipo = consulta("""SELECT d.tipo_sanguineo AS tipo, COUNT(*) AS doacoes FROM historico_doacoes h
                               JOIN unidades u ON u.id=h.unidade_id JOIN doadores d ON d.id=h.doador_id
                               WHERE u.banco_id=%s AND h.status='VERIFICADA' AND h.data > DATE_SUB(CURDATE(), INTERVAL %s DAY)
                               GROUP BY d.tipo_sanguineo ORDER BY doacoes DESC""", (b, dias))
        convocados = int(conv["convocados"] or 0)
        self.send_json({
            "periodo_dias": dias, "convocados": convocados, "agendaram": int(conv["agendaram"] or 0),
            "agendamentos": int(ag["agendamentos"] or 0), "compareceram": int(ag["compareceram"] or 0),
            "faltaram": int(ag["faltaram"] or 0), "espontaneos": int(ag["espontaneos"] or 0),
            "doadores_unicos": doadores, "voltaram": voltaram,
            "taxa_retorno": round(100 * voltaram / doadores) if doadores else 0, "por_tipo": por_tipo,
        })

    # ========================================================================
    # F. PAINEL DO PARCEIRO
    # ========================================================================
    def parceiro_id(self):
        if not self.ctx.get("parceiro_id"):
            raise S.ApiError("Conta sem parceiro vinculado.", 403)
        return self.ctx["parceiro_id"]

    def parceiro_painel(self, data, query):
        p = consulta("SELECT id, nome, tipo, cidade, uf, codigo_alunos, status FROM parceiros WHERE id=%s", (self.parceiro_id(),), um=True)
        ofertas = consulta("""SELECT o.id, o.titulo, o.descricao, o.validade, o.status, o.destaque, o.tipo_emergencia, o.emergencia_ate,
                                     (SELECT COUNT(*) FROM cupons c WHERE c.oferta_id=o.id AND c.usado_em IS NOT NULL) AS usados
                              FROM ofertas o WHERE o.parceiro_id=%s ORDER BY o.id DESC""", (p["id"],))
        for o in ofertas:
            o["validade"] = data_iso(o["validade"])
            ativa = o["emergencia_ate"] and o["emergencia_ate"] >= S.hoje()
            o["emergencia"] = o["tipo_emergencia"] if ativa else None
            o["emergencia_ate"] = data_iso(o["emergencia_ate"]) if ativa else None
            o.pop("tipo_emergencia")
        mes = consulta("""SELECT COUNT(*) AS n, COUNT(DISTINCT c.doador_id) AS doadores FROM cupons c JOIN ofertas o ON o.id=c.oferta_id
                          WHERE o.parceiro_id=%s AND c.usado_em >= DATE_FORMAT(CURDATE(), '%%Y-%%m-01')""", (p["id"],), um=True)
        usados_mes = mes["n"]
        total = consulta("""SELECT COUNT(DISTINCT c.doador_id) AS n FROM cupons c JOIN ofertas o ON o.id=c.oferta_id
                            WHERE o.parceiro_id=%s AND c.usado_em IS NOT NULL""", (p["id"],), um=True)["n"]
        criticos = sorted({l["tipo_sanguineo"] for l in consulta(
            """SELECT e.tipo_sanguineo, e.quantidade, e.limite_critico, e.limite_atencao FROM estoque_niveis e
               JOIN unidades u ON u.id=e.unidade_id JOIN bancos_sangue b ON b.id=u.banco_id AND b.status='ATIVO'
               WHERE u.ativo=1 AND u.uf=%s AND u.cidade=%s""", (p["uf"], p["cidade"]))
            if regras.nivel(l["quantidade"], l["limite_critico"], l["limite_atencao"]) == "CRITICO"})
        relatorio = None
        if p["codigo_alunos"]:
            alunos = consulta("""SELECT d.id, d.sexo FROM doador_parceiros dp JOIN doadores d ON d.id=dp.doador_id
                                 WHERE dp.parceiro_id=%s""", (p["id"],))
            relatorio = {"alunos": len(alunos), "minimo_para_mostrar": 5}
            if len(alunos) >= 5:
                em_dia = 0
                for a in alunos:
                    n = consulta("""SELECT COUNT(*) AS n FROM historico_doacoes WHERE doador_id=%s AND status='VERIFICADA'
                                    AND data > DATE_SUB(CURDATE(), INTERVAL 12 MONTH)""", (a["id"],), um=True)["n"]
                    em_dia += n >= (2 if a["sexo"] == "F" else 3)
                relatorio.update({"em_dia_meta": em_dia, "doaram_12m": None})
        self.send_json({"parceiro": p, "ofertas": ofertas, "cupons_usados_mes": usados_mes, "relatorio": relatorio,
                        "impacto": {"doadores_mes": mes["doadores"], "doadores_total": total}, "criticos_cidade": criticos})

    def parceiro_emergencia(self, data, query, oferta_id):
        """Oferta de emergência: destaca uma oferta aprovada para um tipo em falta, por 7 dias (ou desliga)."""
        tipo = str(data.get("tipo") or "").upper() or None
        if tipo and tipo not in regras.TIPOS:
            raise S.ApiError("Tipo sanguíneo inválido.")
        o = consulta("SELECT id, status FROM ofertas WHERE id=%s AND parceiro_id=%s", (oferta_id, self.parceiro_id()), um=True)
        if not o:
            raise S.ApiError("Oferta não encontrada.", 404)
        if o["status"] != "APROVADA":
            raise S.ApiError("Só ofertas já aprovadas podem virar oferta de emergência.", 409)
        ate = S.hoje() + timedelta(days=7) if tipo else None

        def gravar(cur):
            cur.execute("UPDATE ofertas SET tipo_emergencia=%s, emergencia_ate=%s WHERE id=%s", (tipo, ate, oferta_id))
            auditar(cur, self.uid(), "EMERGENCIA", "parceiro", "ofertas", oferta_id, {"tipo": tipo})
        transacao(gravar)
        self.send_json({"ok": True, "mensagem": f"Oferta de emergência para {tipo} ativa até {ate.strftime('%d/%m')}." if tipo
                        else "Oferta de emergência desligada."})

    def parceiro_oferta(self, data, query):
        titulo = texto(data, "titulo", 120, rotulo="o título da oferta")
        descricao = texto(data, "descricao", 400, obrigatorio=False)
        validade = None
        if data.get("validade"):
            try:
                validade = S.parse_date(data.get("validade"), "validade")
            except ValueError as exc:
                raise S.ApiError(str(exc))

        def gravar(cur):
            cur.execute("INSERT INTO ofertas (parceiro_id, titulo, descricao, validade) VALUES (%s,%s,%s,%s)",
                        (self.parceiro_id(), titulo, descricao, validade))
            auditar(cur, self.uid(), "CRIAR", "ofertas", "ofertas", cur.lastrowid)
            cur.execute("""SELECT u.id FROM usuarios u JOIN usuario_perfis up ON up.usuario_id=u.id JOIN perfis pf ON pf.id=up.perfil_id
                           WHERE pf.nome='ADMINISTRADOR' AND u.status='ATIVO'""")
            for adm in cur.fetchall():
                avisar(cur, adm["id"], "Nova oferta para aprovar", titulo, "admin")
        transacao(gravar)
        self.send_json({"ok": True, "mensagem": "Oferta enviada. Ela aparece no app depois da aprovação da equipe HemoFlow."}, 201)

    def parceiro_validar(self, data, query):
        codigo = texto(data, "codigo", 12, rotulo="o código do cupom").upper()

        def gravar(cur):
            cur.execute("""SELECT c.id, c.usado_em, c.expira_em, o.titulo FROM cupons c JOIN ofertas o ON o.id=c.oferta_id
                           WHERE c.codigo=%s AND o.parceiro_id=%s FOR UPDATE""", (codigo, self.parceiro_id()))
            c = cur.fetchone()
            if not c:
                raise S.ApiError("Cupom não encontrado para este parceiro.", 404)
            if c["usado_em"]:
                raise S.ApiError(f"Este cupom já foi usado em {c['usado_em'].strftime('%d/%m/%Y')}.", 409)
            if c["expira_em"] < S.hoje():
                raise S.ApiError("Este cupom está vencido.", 409)
            cur.execute("UPDATE cupons SET usado_em=NOW(), validado_por=%s WHERE id=%s", (self.uid(), c["id"]))
            auditar(cur, self.uid(), "VALIDAR", "cupons", "cupons", c["id"])
            return c["titulo"]
        titulo = transacao(gravar)
        self.send_json({"ok": True, "mensagem": f"Cupom válido · {titulo}. Uso registrado."})

    # ========================================================================
    # G. PAINEL ADMIN
    # ========================================================================
    def admin_resumo(self, data, query):
        n = lambda sql: consulta(sql, um=True)["n"]  # noqa: E731
        self.send_json({
            "doadores": n("SELECT COUNT(*) AS n FROM doadores WHERE usuario_id IS NOT NULL"),
            "bancos": n("SELECT COUNT(*) AS n FROM bancos_sangue WHERE status='ATIVO'"),
            "parceiros": n("SELECT COUNT(*) AS n FROM parceiros WHERE status='ATIVO'"),
            "doacoes_verificadas": n("SELECT COUNT(*) AS n FROM historico_doacoes WHERE status='VERIFICADA'"),
            "cupons_usados": n("SELECT COUNT(*) AS n FROM cupons WHERE usado_em IS NOT NULL"),
            "convocacoes": n("SELECT COUNT(*) AS n FROM convocacoes"),
            "pendentes": {
                "bancos": consulta("SELECT id, nome, cidade, uf, criado_em FROM bancos_sangue WHERE status='PENDENTE'"),
                "parceiros": consulta("SELECT id, nome, tipo, cidade, uf, criado_em FROM parceiros WHERE status='PENDENTE'"),
                "ofertas": consulta("""SELECT o.id, o.titulo, o.descricao, p.nome AS parceiro, o.criado_em FROM ofertas o
                                       JOIN parceiros p ON p.id=o.parceiro_id WHERE o.status='PENDENTE'"""),
            },
        })

    def admin_bancos(self, data, query):
        bancos = consulta("""SELECT b.*, (SELECT COUNT(*) FROM usuarios u JOIN usuario_perfis up ON up.usuario_id=u.id
                                         JOIN perfis pf ON pf.id=up.perfil_id AND pf.nome='BANCO'
                                         WHERE u.banco_id=b.id AND u.status='ATIVO') AS logins
                             FROM bancos_sangue b ORDER BY b.id DESC""")
        for b in bancos:
            b["unidades"] = consulta("SELECT * FROM unidades WHERE banco_id=%s ORDER BY id", (b["id"],))
        self.send_json({"bancos": bancos, "publicos": consulta("SELECT * FROM unidades WHERE tipo='PUBLICO' ORDER BY uf, nome")})

    def admin_salvar_banco(self, data, query):
        nome = texto(data, "nome", 150, rotulo="o nome do banco de sangue")
        cidade = texto(data, "cidade", 80, rotulo="a cidade")
        uf = str(data.get("uf", "")).upper()
        status = str(data.get("status", "ATIVO")).upper()
        if uf not in S.UFS or status not in ("PENDENTE", "ATIVO", "SUSPENSO"):
            raise S.ApiError("Confira o estado (UF) e a situação.")
        cnpj = S.only_digits(str(data.get("cnpj", ""))) or None
        if cnpj and len(cnpj) != 14:
            raise S.ApiError("CNPJ deve ter 14 números.")
        telefone, email = texto(data, "telefone", 30, False), (str(data.get("email", "")).strip().lower() or None)
        bid = data.get("id")

        def gravar(cur):
            if bid:
                cur.execute("""UPDATE bancos_sangue SET nome=%s, cnpj=%s, cidade=%s, uf=%s, telefone=%s, email=%s, status=%s WHERE id=%s""",
                            (nome, cnpj, cidade, uf, telefone, email, status, int(bid)))
                novo = int(bid)
            else:
                cur.execute("""INSERT INTO bancos_sangue (nome, cnpj, cidade, uf, telefone, email, status) VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                            (nome, cnpj, cidade, uf, telefone, email, status))
                novo = cur.lastrowid
                cur.execute("""INSERT INTO unidades (banco_id, nome, tipo, endereco, bairro, cidade, uf, horario)
                               VALUES (%s,%s,'BANCO',%s,%s,%s,%s,%s)""",
                            (novo, texto(data, "unidade", 150, False) or f"{nome} · {cidade}", texto(data, "endereco", 200, False),
                             texto(data, "bairro", 80, False), cidade, uf, texto(data, "horario", 150, False)))
            auditar(cur, self.uid(), "SALVAR", "admin", "bancos_sangue", novo, {"status": status})
            return novo
        self.send_json({"ok": True, "id": transacao(gravar), "mensagem": "Banco de sangue salvo."}, 201)

    def admin_salvar_unidade(self, data, query):
        nome = texto(data, "nome", 150, rotulo="o nome da unidade")
        cidade = texto(data, "cidade", 80, rotulo="a cidade")
        uf = str(data.get("uf", "")).upper()
        if uf not in S.UFS:
            raise S.ApiError("Selecione o estado (UF).")
        banco_id = int(data["banco_id"]) if data.get("banco_id") else None
        tipo = "BANCO" if banco_id else "PUBLICO"
        valores = (banco_id, nome, tipo, texto(data, "endereco", 200, False), texto(data, "bairro", 80, False), cidade, uf,
                   texto(data, "horario", 150, False), int(bool(data.get("ativo", True))))

        def gravar(cur):
            if data.get("id"):
                cur.execute("""UPDATE unidades SET banco_id=%s, nome=%s, tipo=%s, endereco=%s, bairro=%s, cidade=%s, uf=%s, horario=%s, ativo=%s
                               WHERE id=%s""", (*valores, int(data["id"])))
                uid = int(data["id"])
            else:
                cur.execute("""INSERT INTO unidades (banco_id, nome, tipo, endereco, bairro, cidade, uf, horario, ativo)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""", valores)
                uid = cur.lastrowid
            auditar(cur, self.uid(), "SALVAR", "admin", "unidades", uid)
            return uid
        self.send_json({"ok": True, "id": transacao(gravar), "mensagem": "Unidade salva."}, 201)

    def admin_parceiros(self, data, query):
        parceiros = consulta("""SELECT p.*, (SELECT COUNT(*) FROM usuarios u JOIN usuario_perfis up ON up.usuario_id=u.id
                                            JOIN perfis pf ON pf.id=up.perfil_id AND pf.nome='PARCEIRO'
                                            WHERE u.parceiro_id=p.id AND u.status='ATIVO') AS logins
                                FROM parceiros p ORDER BY p.id DESC""")
        ofertas = consulta("""SELECT o.*, p.nome AS parceiro FROM ofertas o JOIN parceiros p ON p.id=o.parceiro_id ORDER BY o.id DESC""")
        self.send_json({"parceiros": parceiros, "ofertas": ofertas})

    def admin_salvar_parceiro(self, data, query):
        nome = texto(data, "nome", 150, rotulo="o nome do parceiro")
        tipo = str(data.get("tipo", "")).upper()
        cidade = texto(data, "cidade", 80, rotulo="a cidade")
        uf = str(data.get("uf", "")).upper()
        status = str(data.get("status", "ATIVO")).upper()
        if tipo not in ("COMERCIO", "CURSINHO_CONCURSO", "PRE_ENEM", "FACULDADE", "OUTRO"):
            raise S.ApiError("Selecione o tipo de parceiro.")
        if uf not in S.UFS or status not in ("PENDENTE", "ATIVO", "SUSPENSO"):
            raise S.ApiError("Confira o estado (UF) e a situação.")
        cnpj = S.only_digits(str(data.get("cnpj", ""))) or None
        codigo = (str(data.get("codigo_alunos", "")).strip().upper() or None)
        if tipo != "COMERCIO" and not codigo:
            codigo = re.sub(r"[^A-Z]", "", nome.upper())[:8] + "-" + codigo_aleatorio(2)
        valores = (nome, tipo, cnpj, cidade, uf, texto(data, "endereco", 200, False), codigo, status)

        def gravar(cur):
            if data.get("id"):
                cur.execute("""UPDATE parceiros SET nome=%s, tipo=%s, cnpj=%s, cidade=%s, uf=%s, endereco=%s, codigo_alunos=%s, status=%s
                               WHERE id=%s""", (*valores, int(data["id"])))
                pid = int(data["id"])
            else:
                cur.execute("""INSERT INTO parceiros (nome, tipo, cnpj, cidade, uf, endereco, codigo_alunos, status)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""", valores)
                pid = cur.lastrowid
            auditar(cur, self.uid(), "SALVAR", "admin", "parceiros", pid, {"status": status})
            return pid
        self.send_json({"ok": True, "id": transacao(gravar), "codigo_alunos": codigo, "mensagem": "Parceiro salvo."}, 201)

    def admin_status_oferta(self, data, query, oferta_id):
        status = str(data.get("status", "")).upper()
        if status not in ("APROVADA", "RECUSADA", "PENDENTE"):
            raise S.ApiError("Situação inválida.")
        destaque = int(bool(data.get("destaque", False)))

        def gravar(cur):
            cur.execute("UPDATE ofertas SET status=%s, destaque=%s WHERE id=%s", (status, destaque, oferta_id))
            if cur.rowcount == 0:
                cur.execute("SELECT id FROM ofertas WHERE id=%s", (oferta_id,))
                if not cur.fetchone():
                    raise S.ApiError("Oferta não encontrada.", 404)
            cur.execute("SELECT u.id FROM usuarios u JOIN ofertas o ON o.parceiro_id=u.parceiro_id WHERE o.id=%s", (oferta_id,))
            for u in cur.fetchall():
                avisar(cur, u["id"], f"Oferta {status.lower()}", f"A oferta #{oferta_id} foi {status.lower()} pela equipe HemoFlow.", "ofertas")
            auditar(cur, self.uid(), status, "admin", "ofertas", oferta_id)
        transacao(gravar)
        self.send_json({"ok": True, "mensagem": f"Oferta {status.lower()}."})

    def admin_doadores(self, data, query):
        busca = (query.get("q", [""])[0] or "").strip()[:100]
        sql = """SELECT d.id, d.nome, d.email, d.telefone, d.tipo_sanguineo, d.sexo, d.cidade, d.uf, d.status, d.cpf,
                        d.consentimento_convocacao, d.data_nascimento, d.ultima_doacao_informada, d.usuario_id,
                        (SELECT COUNT(*) FROM historico_doacoes h WHERE h.doador_id=d.id AND h.status='VERIFICADA') AS verificadas
                 FROM doadores d"""
        params = []
        if busca:
            sql += " WHERE d.nome LIKE %s OR d.email LIKE %s OR d.cidade LIKE %s OR d.cpf=%s"
            params = [f"%{busca}%"] * 3 + [S.only_digits(busca)]
        linhas = consulta(sql + " ORDER BY d.id DESC LIMIT 300", params)
        for l in linhas:
            l["cpf_mascarado"] = S.mask_cpf(l.pop("cpf"))
            l["data_nascimento"], l["ultima_doacao_informada"] = data_iso(l["data_nascimento"]), data_iso(l["ultima_doacao_informada"])
        self.send_json(linhas)

    def admin_salvar_doador(self, data, query, doador_id):
        campos, valores = [], []
        for campo, maximo in (("nome", 120), ("cidade", 80), ("telefone", 30)):
            if campo in data:
                campos.append(f"{campo}=%s")
                valores.append(texto(data, campo, maximo, obrigatorio=campo != "telefone"))
        if "uf" in data:
            if str(data["uf"]).upper() not in S.UFS:
                raise S.ApiError("UF inválida.")
            campos.append("uf=%s")
            valores.append(str(data["uf"]).upper())
        if "tipo_sanguineo" in data:
            if str(data["tipo_sanguineo"]).upper() not in regras.TIPOS:
                raise S.ApiError("Tipo sanguíneo inválido.")
            campos.append("tipo_sanguineo=%s")
            valores.append(str(data["tipo_sanguineo"]).upper())
        if "status" in data:
            if data["status"] not in ("ATIVO", "INATIVO", "BLOQUEADO"):
                raise S.ApiError("Situação inválida.")
            campos.append("status=%s")
            valores.append(data["status"])
        if not campos:
            raise S.ApiError("Nada para salvar.")

        def gravar(cur):
            cur.execute(f"UPDATE doadores SET {', '.join(campos)} WHERE id=%s", (*valores, doador_id))
            if cur.rowcount == 0:
                cur.execute("SELECT id FROM doadores WHERE id=%s", (doador_id,))
                if not cur.fetchone():
                    raise S.ApiError("Doador não encontrado.", 404)
            auditar(cur, self.uid(), "EDITAR", "admin", "doadores", doador_id, {"campos": list(data)})
        transacao(gravar)
        self.send_json({"ok": True, "mensagem": "Doador atualizado."})

    def admin_contas(self, data, query):
        contas = consulta("""SELECT u.id, u.nome, u.email, u.status, u.ultimo_login, pf.nome AS papel,
                                    b.nome AS banco, p.nome AS parceiro
                             FROM usuarios u LEFT JOIN usuario_perfis up ON up.usuario_id=u.id LEFT JOIN perfis pf ON pf.id=up.perfil_id
                             LEFT JOIN bancos_sangue b ON b.id=u.banco_id LEFT JOIN parceiros p ON p.id=u.parceiro_id
                             WHERE pf.nome IN ('ADMINISTRADOR','BANCO','PARCEIRO') ORDER BY u.id DESC""")
        for c in contas:
            c["ultimo_login"] = data_iso(c["ultimo_login"])
        self.send_json(contas)

    def admin_criar_conta(self, data, query):
        nome = texto(data, "nome", 120, rotulo="o nome")
        email = str(data.get("email", "")).strip().lower()
        senha = data.get("senha", "")
        papel = str(data.get("papel", "")).upper()
        if not S.valid_email(email):
            raise S.ApiError("Informe um e-mail válido.")
        if papel not in ("ADMINISTRADOR", "BANCO", "PARCEIRO"):
            raise S.ApiError("Escolha o tipo de conta: administrador, banco de sangue ou parceiro.")
        if not isinstance(senha, str) or len(senha) < 10 or not re.search(r"[A-Za-z]", senha) or not re.search(r"\d", senha):
            raise S.ApiError("A senha inicial deve ter pelo menos 10 caracteres, com letras e números.")
        banco_id = int(data["banco_id"]) if papel == "BANCO" and data.get("banco_id") else None
        parceiro_id = int(data["parceiro_id"]) if papel == "PARCEIRO" and data.get("parceiro_id") else None
        if papel == "BANCO" and not banco_id:
            raise S.ApiError("Escolha o banco de sangue da conta.")
        if papel == "PARCEIRO" and not parceiro_id:
            raise S.ApiError("Escolha o parceiro da conta.")

        def gravar(cur):
            cur.execute("SELECT id FROM usuarios WHERE email=%s", (email,))
            if cur.fetchone():
                raise S.ApiError("Já existe uma conta com esse e-mail.", 409)
            cur.execute("INSERT INTO usuarios (nome, email, senha_hash, status, banco_id, parceiro_id) VALUES (%s,%s,%s,'ATIVO',%s,%s)",
                        (nome, email, S.password_hash(senha), banco_id, parceiro_id))
            novo = cur.lastrowid
            cur.execute("INSERT INTO usuario_perfis (usuario_id, perfil_id, atribuido_por) SELECT %s, id, %s FROM perfis WHERE nome=%s",
                        (novo, self.uid(), papel))
            auditar(cur, self.uid(), "CRIAR", "admin", "usuarios", novo, {"papel": papel})
            return novo
        self.send_json({"ok": True, "id": transacao(gravar), "mensagem": "Conta criada."}, 201)

    def admin_status_conta(self, data, query, usuario_id):
        status = str(data.get("status", "")).upper()
        if status not in ("ATIVO", "INATIVO", "BLOQUEADO"):
            raise S.ApiError("Situação inválida.")
        if usuario_id == self.uid() and status != "ATIVO":
            raise S.ApiError("Você não pode desativar a sua própria conta.")

        def gravar(cur):
            cur.execute("UPDATE usuarios SET status=%s WHERE id=%s", (status, usuario_id))
            auditar(cur, self.uid(), status, "admin", "usuarios", usuario_id)
        transacao(gravar)
        for token, sessao in list(S.SESSIONS.items()):
            if sessao["id"] == usuario_id and status != "ATIVO":
                S.SESSIONS.pop(token, None)
        self.send_json({"ok": True, "mensagem": "Situação da conta atualizada."})

    def admin_entrar_como(self, data, query):
        """O admin vê o sistema exatamente como um banco, parceiro ou doador (fica registrado)."""
        papel = str(data.get("papel", "")).upper()
        alvo = inteiro(data.get("id"), "o cadastro", 1, 10**12)
        if papel == "BANCO":
            nome = consulta("SELECT nome FROM bancos_sangue WHERE id=%s", (alvo,), um=True)
            como = {"papel": "BANCO", "banco_id": alvo, "parceiro_id": None, "doador_id": None}
        elif papel == "PARCEIRO":
            nome = consulta("SELECT nome FROM parceiros WHERE id=%s", (alvo,), um=True)
            como = {"papel": "PARCEIRO", "banco_id": None, "parceiro_id": alvo, "doador_id": None}
        elif papel == "DOADOR":
            nome = consulta("SELECT nome FROM doadores WHERE id=%s", (alvo,), um=True)
            como = {"papel": "DOADOR", "banco_id": None, "parceiro_id": None, "doador_id": alvo}
        else:
            raise S.ApiError("Escolha banco, parceiro ou doador.")
        if not nome:
            raise S.ApiError("Cadastro não encontrado.", 404)
        self.record["como"] = {**como, "nome_como": nome["nome"]}
        transacao(lambda cur: auditar(cur, self.uid(), "ENTRAR_COMO", "admin", papel.lower(), alvo))
        self.send_json({"ok": True, "mensagem": f"Você está vendo o HemoFlow como {nome['nome']}."})

    def sair_como(self, data, query):
        self.record.pop("como", None)
        self.send_json({"ok": True})

    def dev_semear(self, data, query):
        """Só no computador de desenvolvimento: recria os dados FICTÍCIOS de demonstração."""
        if S.PRODUCTION or self.client_address[0] not in ("127.0.0.1", "::1"):
            raise S.ApiError("Endpoint não encontrado.", 404)
        import dados_demo
        self.send_json({"ok": True, **dados_demo.semear()})

    # ========================================================================
    # G2. ASSISTENTE HEMOFLOW (IA com RAG) — repassa a pergunta ao serviço local
    # ========================================================================
    # Dois modos:
    #  - COMPUTADOR: o serviço assistente/servico.py (embeddings locais com sentence-transformers) roda à parte.
    #    A configuração vem de HEMOFLOW_ASSISTENTE_URL / HEMOFLOW_ASSISTENTE_SEGREDO ou do assistente/.env.
    #  - NUVEM: com ASSISTENTE_EMBEDDINGS=openai e OPENAI_API_KEY nas variáveis do Railway, o mesmo agente
    #    roda DENTRO deste servidor, com embeddings pela API da OpenAI (sem PyTorch na imagem).
    # Sem nenhum dos dois, a aba some e nada mais é afetado.
    LIMITE_PERGUNTAS, JANELA_PERGUNTAS = 15, 600  # por usuário: controla o gasto com a IA
    LIMITE_DIA = int(os.environ.get("HEMOFLOW_ASSISTENTE_LIMITE_DIA", "100"))  # todas as pessoas, por dia
    _perguntas_recentes: dict = {}

    @staticmethod
    def assistente_na_nuvem():
        return (os.environ.get("ASSISTENTE_EMBEDDINGS", "").strip().lower() == "openai"
                and bool(os.environ.get("OPENAI_API_KEY", "").strip()))

    @staticmethod
    def assistente_interno(pergunta, doador_id):
        """Modo nuvem: importa o agente da pasta assistente/ e usa as conexões do próprio HemoFlow."""
        pasta = str(S.BASE_DIR / "assistente")
        if pasta not in sys.path:
            sys.path.insert(0, pasta)
        import agente
        import ferramentas
        ferramentas.Ferramentas.conectar = S.connect_db
        return agente.Assistente(doador_id).responder(pergunta)

    @staticmethod
    def config_assistente():
        url = os.environ.get("HEMOFLOW_ASSISTENTE_URL", "").strip()
        segredo = os.environ.get("HEMOFLOW_ASSISTENTE_SEGREDO", "").strip()
        env = S.BASE_DIR / "assistente" / ".env"
        if (not segredo or not url) and env.exists():
            valores = dict(l.split("=", 1) for l in env.read_text(encoding="utf-8").splitlines() if "=" in l and not l.startswith("#"))
            segredo = segredo or valores.get("ASSISTENTE_SEGREDO", "").strip()
            url = url or f"http://127.0.0.1:{valores.get('ASSISTENTE_PORTA', '8765').strip() or '8765'}"
        return (url.rstrip("/"), segredo) if url and segredo else None

    def assistente_status(self, data, query):
        if self.assistente_na_nuvem():
            return self.send_json({"disponivel": True})
        cfg = self.config_assistente()
        disponivel = False
        if cfg:
            try:
                with urllib.request.urlopen(cfg[0] + "/saude", timeout=2) as r:
                    disponivel = r.status == 200
            except (OSError, ValueError):
                disponivel = False
        self.send_json({"disponivel": disponivel})

    def perguntar_assistente(self, data, doador_id):
        pergunta = texto(data, "pergunta", 500, rotulo="a sua pergunta")
        nuvem = self.assistente_na_nuvem()
        cfg = None if nuvem else self.config_assistente()
        if not nuvem and not cfg:
            raise S.ApiError("O Assistente HemoFlow não está disponível neste servidor.", 503)
        agora = time.time()
        recentes = [t for t in self._perguntas_recentes.get(self.uid(), []) if agora - t < self.JANELA_PERGUNTAS]
        if len(recentes) >= self.LIMITE_PERGUNTAS:
            raise S.ApiError("Você fez muitas perguntas em pouco tempo. Aguarde alguns minutos e tente de novo.", 429)
        # Limite do dia para todas as pessoas, contado na auditoria (vale mesmo depois de o servidor reiniciar).
        # A auditoria guarda só que houve uma pergunta, nunca o texto dela.
        hoje = consulta("""SELECT COUNT(*) AS n FROM historico_auditoria WHERE acao='PERGUNTA_IA' AND criado_em >= CURDATE()""",
                        um=True)["n"]
        if hoje >= self.LIMITE_DIA:
            raise S.ApiError("O Assistente atingiu o limite de perguntas de hoje. Tente amanhã ou veja a aba Ajuda.", 429)
        self._perguntas_recentes[self.uid()] = recentes + [agora]
        transacao(lambda cur: auditar(cur, self.uid(), "PERGUNTA_IA", "assistente", "assistente", None,
                                      {"modo": "nuvem" if nuvem else "computador"}))
        if nuvem:
            try:
                r = self.assistente_interno(pergunta, doador_id)
            except Exception as exc:  # noqa: BLE001 - erro da IA ou do banco vira mensagem amigável
                print("Assistente (nuvem) falhou:", type(exc).__name__)
                raise S.ApiError("O assistente não conseguiu responder agora. Tente de novo em instantes.", 502)
            return self.send_json({"resposta": r["resposta"], "fontes": r.get("fontes", []), "ferramentas": r.get("ferramentas", [])})
        corpo = json.dumps({"pergunta": pergunta, "doador_id": doador_id}).encode("utf-8")
        req = urllib.request.Request(cfg[0] + "/perguntar", data=corpo, method="POST",
                                     headers={"Content-Type": "application/json", "X-Assistente-Segredo": cfg[1]})
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                resposta = json.loads(r.read())
        except urllib.error.HTTPError as exc:
            with exc:
                erro = json.loads(exc.read() or b"{}").get("erro")
            raise S.ApiError(erro or "O assistente não conseguiu responder agora.", 502)
        except (OSError, ValueError):
            raise S.ApiError("O Assistente HemoFlow está desligado neste computador. Inicie com: python servico.py", 503)
        self.send_json({"resposta": resposta.get("resposta", ""), "fontes": resposta.get("fontes", []),
                        "ferramentas": resposta.get("ferramentas", [])})

    def doador_assistente(self, data, query):
        self.perguntar_assistente(data, self.doador()["id"])  # só o doador logado (ou o do "Entrar como")

    def parceiro_assistente(self, data, query):
        self.parceiro_id()
        self.perguntar_assistente(data, None)  # parceiro: só o FAQ, sem dados de doador

    # ========================================================================
    # H. AVISOS (SINO)
    # ========================================================================
    def avisos_listar(self, data, query):
        linhas = consulta("""SELECT id, titulo, mensagem, link, lido_em, criado_em FROM avisos WHERE usuario_id=%s
                             ORDER BY id DESC LIMIT 40""", (self.uid(),))
        for l in linhas:
            l["lido_em"], l["criado_em"] = data_iso(l["lido_em"]), data_iso(l["criado_em"])
        self.send_json({"nao_lidos": len([l for l in linhas if not l["lido_em"]]), "avisos": linhas})

    def avisos_marcar_lidos(self, data, query):
        transacao(lambda cur: cur.execute("UPDATE avisos SET lido_em=NOW() WHERE usuario_id=%s AND lido_em IS NULL", (self.uid(),)))
        self.send_json({"ok": True})
