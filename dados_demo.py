"""HemoFlow 2.0 — dados FICTÍCIOS de demonstração (bancos, parceiros, doadores, agenda e histórico).

Nada aqui é real: nomes, e-mails (@exemplo.com) e CPFs gerados são inventados.
Uso: no modo de desenvolvimento, POST /api/dev/semear (só funciona fora de produção e a partir
do próprio computador). Na nuvem (console do Railway):  python dados_demo.py
Pode rodar mais de uma vez: apaga e recria só os dados de demonstração.

Senha das contas de demonstração:
  - no computador: SENHA_DEMO abaixo;
  - na NUVEM: a variável HEMOFLOW_DEMO_SENHA (definida no Railway, fora do GitHub) ou, sem ela,
    uma senha aleatória que ninguém conhece (o admin mostra cada perfil pelo "Entrar como").
    Na nuvem NÃO é criada a conta admin de demonstração: este código é público, então uma senha
    escrita aqui nunca pode abrir contas no servidor da internet.
"""
import os
import random
import secrets
from datetime import date, datetime, timedelta

import regras
import rotas_v2 as R

SENHA_DEMO = "HemoFlow2026"  # só para o computador local


_SENHA_NUVEM = None


def senha_das_contas():
    """Senha das contas demo. Computador: SENHA_DEMO. Nuvem: HEMOFLOW_DEMO_SENHA (se definida no Railway)
    ou, sem ela, uma senha aleatória que ninguém conhece — o admin mostra cada perfil pelo "Entrar como"."""
    global _SENHA_NUVEM
    if not R.S.PRODUCTION:
        return SENHA_DEMO
    if _SENHA_NUVEM is None:
        senha = os.environ.get("HEMOFLOW_DEMO_SENHA", "")
        if senha and (len(senha) < 12 or senha == SENHA_DEMO):
            raise SystemExit("HEMOFLOW_DEMO_SENHA precisa ter 12+ caracteres e ser diferente da senha local.")
        _SENHA_NUVEM = senha or secrets.token_urlsafe(24)
    return _SENHA_NUVEM


MARCA = "(demo)"

BANCOS = [
    {"nome": "Banco de Sangue Vida", "cidade": "Recife", "uf": "PE", "unidade": "Banco Vida · Boa Vista",
     "endereco": "Rua Fictícia, 100", "bairro": "Boa Vista", "horario": "Seg a sáb, 7h às 17h"},
    {"nome": "Banco de Sangue Esperança", "cidade": "Caruaru", "uf": "PE", "unidade": "Banco Esperança · Centro",
     "endereco": "Avenida Exemplo, 250", "bairro": "Centro", "horario": "Seg a sex, 7h às 16h"},
]
ESTOQUE = {  # tipo: (quantidade Vida, quantidade Esperança)
    "O-": (4, 9), "O+": (38, 22), "A-": (9, 14), "A+": (31, 18), "B-": (3, 6), "B+": (17, 12), "AB-": (5, 4), "AB+": (12, 9),
}
LIMITES = {"O-": (5, 12), "O+": (10, 20), "A-": (5, 10), "A+": (10, 20), "B-": (4, 8), "B+": (6, 12), "AB-": (3, 6), "AB+": (4, 8)}
PARCEIROS = [
    ("Padaria Pão Quente", "COMERCIO", "Caruaru", None, "Café da manhã grátis no dia da doação", "Mostre o cupom no caixa."),
    ("Cursinho Aprova PE", "CURSINHO_CONCURSO", "Caruaru", "APROVA-25", "20% na mensalidade para doadores", "Válido para novas matrículas."),
    ("Pré-Enem Futuro", "PRE_ENEM", "Recife", "FUTURO-26", "Bolsa de 30% no intensivo", "Para alunos com doação verificada."),
    ("Faculdade Exemplo", "FACULDADE", "Recife", "FACEX-01", "Horas complementares por doação", "Conforme o regulamento da faculdade."),
]
NOMES = ["Mariana Alves", "Rafael Costa", "Juliana Mendes", "Carlos Eduardo Lima", "Patrícia Souza", "Thiago Ribeiro",
         "Fernanda Rocha", "Lucas Ferreira", "Ana Beatriz Santos", "Bruno Tavares", "Camila Duarte", "Diego Nogueira",
         "Elisa Ramos", "Felipe Araújo", "Gabriela Pinto", "Henrique Barros", "Isabela Moura", "João Pedro Vieira",
         "Larissa Freitas", "Mateus Cardoso", "Natália Gomes", "Otávio Pires", "Paula Teixeira", "Renato Lopes"]


def cpf_ficticio(semente):
    rnd = random.Random(semente)
    while True:
        n = [rnd.randint(0, 9) for _ in range(9)]
        if len(set(n)) == 1:
            continue
        for tamanho in (9, 10):
            n.append((sum(n[i] * (tamanho + 1 - i) for i in range(tamanho)) * 10) % 11 % 10)
        return "".join(map(str, n))


def limpar(cur):
    """Remove só os dados de demonstração (marcados por e-mail @exemplo.com e nomes com (demo))."""
    cur.execute("SELECT id FROM doadores WHERE email LIKE %s", ("%@exemplo.com",))
    doadores = [r["id"] for r in cur.fetchall()]
    if doadores:
        marc = ",".join(["%s"] * len(doadores))
        for tabela in ("cupons", "grupo_membros", "doador_parceiros", "historico_doacoes", "agenda_doacoes", "convocacao_doadores"):
            cur.execute(f"DELETE FROM {tabela} WHERE doador_id IN ({marc})", doadores)
    cur.execute("DELETE FROM grupos WHERE nome LIKE %s", (f"%{MARCA}%",))
    cur.execute("SELECT id FROM bancos_sangue WHERE nome LIKE %s", (f"%{MARCA}%",))
    for b in [r["id"] for r in cur.fetchall()]:
        cur.execute("DELETE FROM convocacoes WHERE banco_id=%s", (b,))
        cur.execute("UPDATE usuarios SET banco_id=NULL WHERE banco_id=%s", (b,))
        cur.execute("DELETE FROM unidades WHERE banco_id=%s", (b,))
        cur.execute("DELETE FROM bancos_sangue WHERE id=%s", (b,))
    cur.execute("SELECT id FROM parceiros WHERE nome LIKE %s", (f"%{MARCA}%",))
    for p in [r["id"] for r in cur.fetchall()]:
        cur.execute("UPDATE usuarios SET parceiro_id=NULL WHERE parceiro_id=%s", (p,))
        cur.execute("DELETE FROM parceiros WHERE id=%s", (p,))
    # Contas de demonstração: @exemplo.com, NUNCA uma conta de administrador (protege o admin real da nuvem).
    cur.execute("""SELECT u.id FROM usuarios u WHERE u.email LIKE %s AND NOT EXISTS (
                       SELECT 1 FROM usuario_perfis up JOIN perfis pf ON pf.id=up.perfil_id
                       WHERE up.usuario_id=u.id AND pf.nome='ADMINISTRADOR')""", ("%@exemplo.com",))
    usuarios = [r["id"] for r in cur.fetchall()]
    if not R.S.PRODUCTION:  # no computador, o admin de demonstração também é recriado
        cur.execute("SELECT id FROM usuarios WHERE email='admin@exemplo.com'")
        usuarios += [r["id"] for r in cur.fetchall()]
    if usuarios:
        marc = ",".join(["%s"] * len(usuarios))
        cur.execute(f"DELETE FROM avisos WHERE usuario_id IN ({marc})", usuarios)
        cur.execute(f"DELETE FROM codigos_login WHERE usuario_id IN ({marc})", usuarios)
        cur.execute(f"UPDATE doadores SET usuario_id=NULL WHERE usuario_id IN ({marc})", usuarios)
        cur.execute(f"DELETE FROM usuario_perfis WHERE usuario_id IN ({marc})", usuarios)
        cur.execute(f"DELETE FROM recuperacao_senhas WHERE usuario_id IN ({marc})", usuarios)
        cur.execute(f"UPDATE historico_auditoria SET usuario_id=NULL WHERE usuario_id IN ({marc})", usuarios)
        cur.execute(f"DELETE FROM usuarios WHERE id IN ({marc})", usuarios)
    if doadores:
        cur.execute(f"DELETE FROM doadores WHERE id IN ({','.join(['%s'] * len(doadores))})", doadores)


def conta(cur, nome, email, papel, banco_id=None, parceiro_id=None):
    cur.execute("INSERT INTO usuarios (nome, email, senha_hash, status, banco_id, parceiro_id) VALUES (%s,%s,%s,'ATIVO',%s,%s)",
                (nome, email, R.S.password_hash(senha_das_contas()), banco_id, parceiro_id))
    uid = cur.lastrowid
    cur.execute("INSERT INTO usuario_perfis (usuario_id, perfil_id) SELECT %s, id FROM perfis WHERE nome=%s", (uid, papel))
    return uid


def semear():
    hoje = R.S.hoje()

    def gravar(cur):
        limpar(cur)
        if not R.S.PRODUCTION:  # na nuvem o admin é a conta real da equipe, nunca uma conta de demonstração
            conta(cur, "Admin Demonstração", "admin@exemplo.com", "ADMINISTRADOR")
        unidades = []
        for i, b in enumerate(BANCOS):
            cur.execute("INSERT INTO bancos_sangue (nome, cidade, uf, telefone, email, status) VALUES (%s,%s,%s,%s,%s,'ATIVO')",
                        (f"{b['nome']} {MARCA}", b["cidade"], b["uf"], "(81) 3000-000" + str(i), f"contato{i}@exemplo.com"))
            bid = cur.lastrowid
            cur.execute("""INSERT INTO unidades (banco_id, nome, tipo, endereco, bairro, cidade, uf, horario)
                           VALUES (%s,%s,'BANCO',%s,%s,%s,%s,%s)""",
                        (bid, b["unidade"], b["endereco"], b["bairro"], b["cidade"], b["uf"], b["horario"]))
            uid = cur.lastrowid
            unidades.append((bid, uid, b))
            conta(cur, f"Captação {b['nome'].split()[-1]}", f"captacao{i + 1}@exemplo.com", "BANCO", banco_id=bid)
            for tipo, qtds in ESTOQUE.items():
                crit, aten = LIMITES[tipo]
                cur.execute("""INSERT INTO estoque_niveis (unidade_id, tipo_sanguineo, quantidade, limite_critico, limite_atencao)
                               VALUES (%s,%s,%s,%s,%s)""", (uid, tipo, qtds[i], crit, aten))
                cur.execute("""INSERT INTO estoque_movimentos (unidade_id, tipo_sanguineo, movimento, quantidade, motivo)
                               VALUES (%s,%s,'AJUSTE',%s,'Contagem inicial (demonstração)')""", (uid, tipo, qtds[i]))
            for d in range(-20, 8):
                dia = hoje + timedelta(days=d)
                if dia.weekday() == 6:
                    continue
                for h in ("08:00", "09:00", "10:00", "11:00", "14:00", "15:00"):
                    cur.execute("INSERT INTO vagas (unidade_id, inicio, capacidade) VALUES (%s,%s,4)",
                                (uid, datetime.combine(dia, datetime.strptime(h, "%H:%M").time())))
        parceiros = []
        for nome, tipo, cidade, codigo, titulo, desc in PARCEIROS:
            cur.execute("""INSERT INTO parceiros (nome, tipo, cidade, uf, endereco, codigo_alunos, status)
                           VALUES (%s,%s,%s,'PE','Endereço fictício',%s,'ATIVO')""", (f"{nome} {MARCA}", tipo, cidade, codigo))
            pid = cur.lastrowid
            parceiros.append(pid)
            cur.execute("""INSERT INTO ofertas (parceiro_id, titulo, descricao, validade, status, destaque)
                           VALUES (%s,%s,%s,%s,'APROVADA',%s)""", (pid, titulo, desc, hoje + timedelta(days=90), int(tipo == "COMERCIO")))
        cur.execute("""INSERT INTO ofertas (parceiro_id, titulo, descricao, status) VALUES (%s,'10% em bolos','Oferta aguardando aprovação','PENDENTE')""",
                    (parceiros[0],))
        conta(cur, "Padaria Pão Quente", "padaria@exemplo.com", "PARCEIRO", parceiro_id=parceiros[0])
        conta(cur, "Cursinho Aprova PE", "cursinho@exemplo.com", "PARCEIRO", parceiro_id=parceiros[1])
        cur.execute("INSERT INTO parceiros (nome, tipo, cidade, uf, status) VALUES (%s,'COMERCIO','Recife','PE','PENDENTE')",
                    (f"Farmácia Saúde {MARCA}",))
        # doadores
        doadores = []
        for i, nome in enumerate(NOMES):
            tipo = regras.TIPOS[i % 8] if i % 3 else ("O-" if i % 2 else "O+")
            sexo = "F" if nome.split()[0].endswith("a") or nome.split()[0] in ("Isabela", "Elisa") else "M"
            cidade = "Recife" if i % 2 == 0 else "Caruaru"
            email = "doador@exemplo.com" if i == 0 else f"{nome.split()[0].lower()}.{i}@exemplo.com".replace("ã", "a").replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").replace("â", "a")
            uid = conta(cur, nome, email, "DOADOR")
            nasc = date(1985 + i % 18, 1 + i % 12, 1 + i % 27)
            cur.execute("""INSERT INTO doadores (nome, cpf, data_nascimento, email, telefone, codigo_ficticio, status, tipo_sanguineo,
                                                 cidade, uf, usuario_id, sexo, consentimento_convocacao, consentimento_em)
                           VALUES (%s,%s,%s,%s,%s,%s,'ATIVO',%s,%s,'PE',%s,%s,1,NOW())""",
                        (nome, cpf_ficticio(i + 100), nasc, email, f"(81) 98{i:03d}-{1000 + i:04d}", f"DOA-DEMO{i:03d}",
                         "O-" if i == 0 else tipo, cidade, uid, "F" if i == 0 else sexo))
            doadores.append((cur.lastrowid, uid, cidade, "O-" if i == 0 else tipo))
        # histórico: doações verificadas e declaradas para dar vida às métricas
        for k, (did, uid, cidade, tipo) in enumerate(doadores):
            bid, unid, _ = unidades[0] if cidade == "Recife" else unidades[1]
            n = k % 4
            for j in range(n):
                quando = hoje - timedelta(days=100 + 120 * j + k)
                cur.execute("INSERT INTO historico_doacoes (doador_id, unidade_id, data, status) VALUES (%s,%s,%s,'VERIFICADA')",
                            (did, unid, quando))
            if k % 5 == 0:
                cur.execute("INSERT INTO historico_doacoes (doador_id, local_texto, data, status) VALUES (%s,'HEMOPE',%s,'DECLARADA')",
                            (did, hoje - timedelta(days=300)))
        # a doadora principal (Mariana) com 2 verificadas no ano: cumpre a meta de PE
        did0, uid0, _, _ = doadores[0]
        cur.execute("DELETE FROM historico_doacoes WHERE doador_id=%s", (did0,))
        for dias in (106, 230):
            cur.execute("INSERT INTO historico_doacoes (doador_id, unidade_id, data, status) VALUES (%s,%s,%s,'VERIFICADA')",
                        (did0, unidades[0][1], hoje - timedelta(days=dias)))
        cur.execute("INSERT IGNORE INTO doador_parceiros (doador_id, parceiro_id) VALUES (%s,%s)", (did0, parceiros[1]))
        # convocação passada com agendamentos (compareceu / faltou) para as métricas
        bid, unid, _ = unidades[0]
        cur.execute("""INSERT INTO convocacoes (banco_id, unidade_id, tipo_sanguineo, bolsas_faltando, mensagem, cidade, uf, criado_em)
                       VALUES (%s,%s,'O-',8,'Nosso estoque de O− está crítico. Sua doação pode salvar até 4 vidas.','Recife','PE',%s)""",
                    (bid, unid, datetime.combine(hoje - timedelta(days=15), datetime.min.time())))
        cid = cur.lastrowid
        cur.execute("SELECT id FROM vagas WHERE unidade_id=%s AND DATE(inicio)=%s ORDER BY inicio LIMIT 1",
                    (unid, hoje - timedelta(days=12)))
        vaga = cur.fetchone()
        for k, (did, uid, cidade, tipo) in enumerate(doadores[1:12]):
            cur.execute("INSERT INTO convocacao_doadores (convocacao_id, doador_id, status, enviada_em) VALUES (%s,%s,%s,%s)",
                        (cid, did, "AGENDOU" if k < 6 else "ENVIADA", hoje - timedelta(days=15)))
            if k < 6 and vaga:
                status = "COMPARECEU" if k < 4 else "FALTOU"
                cur.execute("""INSERT INTO agenda_doacoes (doador_id, unidade_id, vaga_id, convocacao_id, origem, codigo, status)
                               VALUES (%s,%s,%s,%s,'CONVOCACAO',%s,%s)""", (did, unid, vaga["id"], cid, f"{100000 + k}", status))
        # grupo com meta coletiva
        cur.execute("INSERT INTO grupos (nome, codigo, meta) VALUES (%s,'GRP-TURMC',20)", (f"Turma C · ADS {MARCA}",))
        gid = cur.lastrowid
        for did, *_ in doadores[:9]:
            cur.execute("INSERT INTO grupo_membros (grupo_id, doador_id) VALUES (%s,%s)", (gid, did))
        R.avisar(cur, uid0, "Bem-vinda ao HemoFlow!", "Seu tipo O− está em falta no Banco Vida. Veja os horários livres.", "inicio")
        return {"bancos": len(unidades), "parceiros": len(parceiros) + 1, "doadores": len(doadores)}

    senha_das_contas()  # na nuvem, para antes de apagar qualquer coisa se a senha não estiver definida
    resumo = R.transacao(gravar)
    resumo["contas"] = ([] if R.S.PRODUCTION else ["admin@exemplo.com"]) + ["captacao1@exemplo.com", "captacao2@exemplo.com", "padaria@exemplo.com",
                        "cursinho@exemplo.com", "doador@exemplo.com"]
    if not R.S.PRODUCTION:
        resumo["senha"] = "veja SENHA_DEMO em dados_demo.py"
    elif os.environ.get("HEMOFLOW_DEMO_SENHA"):
        resumo["senha"] = "a da variável HEMOFLOW_DEMO_SENHA"
    else:
        resumo["senha"] = "aleatória (ninguém conhece): use 'Entrar como' no painel do admin"
    return resumo


if __name__ == "__main__":
    import sys
    import servidor  # noqa: F401  (liga rotas_v2 ao servidor: conexão, senhas, data de hoje)
    sys.modules["rotas_v2"].S = servidor
    print("Recriando os dados FICTÍCIOS de demonstração (só os marcados com (demo) e @exemplo.com)…")
    print(semear())
