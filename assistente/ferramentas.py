"""Assistente HemoFlow — ferramentas (tools) SOMENTE LEITURA no banco do projeto (padrão da Aula 7).

Segurança:
- O id do doador NUNCA é um parâmetro que a IA escolhe: ele vem da sessão do HemoFlow e fica
  "preso" ao objeto Ferramentas. Mesmo que alguém peça "mostre os cupons do João", a ferramenta
  só enxerga o doador logado.
- A conexão é aberta em modo READ ONLY e o recomendado é um usuário do MySQL só com SELECT.
- As respostas trazem o mínimo: nada de CPF, e-mail, telefone ou quantidade de bolsas.
As regras (intervalos, metas) vêm do regras.py do próprio HemoFlow: o agente calcula igual ao app.
"""
import sys
from datetime import date, datetime, timedelta

import mysql.connector

import config

sys.path.insert(0, str(config.PASTA.parent))  # pasta do HemoFlow: reutiliza regras.py
import regras  # noqa: E402

NIVEL_TEXTO = {"CRITICO": "Crítico", "ATENCAO": "Atenção", "NORMAL": "Normal"}


def _data(v):
    return v.strftime("%d/%m/%Y") if isinstance(v, (date, datetime)) else v


class Ferramentas:
    def __init__(self, doador_id: int | None = None):
        self.doador_id = doador_id

    # ---- banco ------------------------------------------------------------------
    def _consulta(self, sql, params=(), um=False):
        conn = mysql.connector.connect(**config.DB, connection_timeout=8)
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SET SESSION TRANSACTION READ ONLY")
            cur.execute("START TRANSACTION READ ONLY")
            cur.execute(sql, params)
            linhas = cur.fetchall()
            conn.rollback()
            return (linhas[0] if linhas else None) if um else linhas
        finally:
            conn.close()

    def _doador(self):
        if not self.doador_id:
            return None
        return self._consulta("""SELECT id, sexo, data_nascimento, uf, cidade, tipo_sanguineo, responsavel_consentiu,
                                        ultima_doacao_informada FROM doadores WHERE id=%s AND status='ATIVO'""",
                              (self.doador_id,), um=True)

    def tipo_do_usuario(self):
        """Só o tipo sanguíneo do doador logado (contexto mínimo para a IA responder sobre compatibilidade)."""
        d = self._doador()
        return d["tipo_sanguineo"] if d else None

    # ---- ferramentas ---------------------------------------------------------------
    def quando_posso_doar(self):
        d = self._doador()
        if not d:
            return {"erro": "Entre no app com a sua conta de doador para eu consultar seu histórico."}
        datas = [r["data"] for r in self._consulta("SELECT data FROM historico_doacoes WHERE doador_id=%s", (d["id"],))]
        if d["ultima_doacao_informada"]:
            datas.append(d["ultima_doacao_informada"])
        apt = regras.aptidao(d["sexo"] or "M", d["data_nascimento"], datas, date.today(), bool(d["responsavel_consentiu"]))
        return {"pode_doar_agora": apt["apto"], "a_partir_de": None if apt["apto"] else _data(apt["a_partir_de"]), "motivo": apt["motivo"],
                "doacoes_ultimos_12_meses": apt["doacoes_12m"], "limite_anual": apt["limite_anual"],
                "ultima_doacao": _data(max(datas)) if datas else None,
                "observacao": "Pré-checagem do app. A decisão final é da triagem do banco de sangue."}

    def minha_meta_isencao(self):
        d = self._doador()
        if not d:
            return {"erro": "Entre no app com a sua conta de doador para eu consultar sua meta."}
        b = self._consulta("""SELECT titulo, minimo_homens, minimo_mulheres, janela_meses FROM beneficios_estado
                              WHERE ativo=1 AND uf=%s AND minimo_homens IS NOT NULL LIMIT 1""", (d["uf"],), um=True)
        if not b:
            return {"erro": f"Não há meta de isenção cadastrada para o estado {d['uf']}."}
        janela = date.today() - timedelta(days=30 * (b["janela_meses"] or 12))
        n = self._consulta("""SELECT COUNT(*) AS n FROM historico_doacoes WHERE doador_id=%s AND status='VERIFICADA'
                              AND data > %s""", (d["id"], janela), um=True)["n"]
        meta = regras.meta_regular(d["sexo"] or "M", b["minimo_homens"], b["minimo_mulheres"], n)
        return {"beneficio": b["titulo"], "estado": d["uf"], "doacoes_verificadas_na_janela": n, "meta": meta["alvo"],
                "cumprida": meta["cumprida"], "faltam": max(0, meta["alvo"] - n), "janela_meses": b["janela_meses"],
                "observacao": "Conta só doações verificadas. A comprovação oficial é a declaração da entidade coletora."}

    def nivel_do_estoque(self, tipo_sanguineo: str = "", banco: str = ""):
        tipo = (tipo_sanguineo or "").upper().replace("−", "-").replace(" ", "")
        if not tipo:
            d = self._doador()
            tipo = d["tipo_sanguineo"] if d else ""
        if tipo not in regras.TIPOS:
            return {"erro": "Informe o tipo sanguíneo (A+, A-, B+, B-, AB+, AB-, O+ ou O-)."}
        sql = """SELECT b.nome AS banco, u.nome AS unidade, u.cidade, e.quantidade, e.limite_critico, e.limite_atencao,
                        e.atualizado_em FROM estoque_niveis e JOIN unidades u ON u.id=e.unidade_id AND u.ativo=1
                 JOIN bancos_sangue b ON b.id=u.banco_id AND b.status='ATIVO' WHERE e.tipo_sanguineo=%s"""
        params = [tipo]
        if banco:
            sql += " AND (b.nome LIKE %s OR u.nome LIKE %s OR u.cidade LIKE %s)"
            params += [f"%{banco}%"] * 3
        linhas = self._consulta(sql + " ORDER BY b.nome", params)
        if not linhas:
            return {"erro": "Não encontrei esse banco de sangue entre os parceiros do HemoFlow."}
        return {"tipo": tipo, "aviso": "Nível informado por cada banco parceiro; não é o estoque oficial do HEMOPE. "
                                       "Na resposta, informe o nível e a data de atualização de cada banco.",
                "bancos": [{"banco": l["banco"], "unidade": l["unidade"], "cidade": l["cidade"],
                            "nivel": NIVEL_TEXTO[regras.nivel(l["quantidade"], l["limite_critico"], l["limite_atencao"])],
                            "atualizado_em": _data(l["atualizado_em"])} for l in linhas]}

    def meus_cupons_e_convocacoes(self):
        if not self._doador():
            return {"erro": "Entre no app com a sua conta de doador para eu consultar seus cupons e convocações."}
        cupons = self._consulta("""SELECT c.codigo, o.titulo, p.nome AS parceiro, c.expira_em, c.usado_em FROM cupons c
                                   JOIN ofertas o ON o.id=c.oferta_id JOIN parceiros p ON p.id=o.parceiro_id
                                   WHERE c.doador_id=%s ORDER BY c.id DESC LIMIT 10""", (self.doador_id,))
        conv = self._consulta("""SELECT b.nome AS banco, c.tipo_sanguineo, c.mensagem, cd.enviada_em FROM convocacao_doadores cd
                                 JOIN convocacoes c ON c.id=cd.convocacao_id JOIN bancos_sangue b ON b.id=c.banco_id
                                 WHERE cd.doador_id=%s AND cd.status='ENVIADA' AND cd.enviada_em > DATE_SUB(NOW(), INTERVAL 14 DAY)
                                 ORDER BY cd.enviada_em DESC""", (self.doador_id,))
        ag = self._consulta("""SELECT v.inicio, u.nome AS unidade, a.codigo FROM agenda_doacoes a JOIN vagas v ON v.id=a.vaga_id
                               JOIN unidades u ON u.id=a.unidade_id WHERE a.doador_id=%s AND a.status='AGENDADO'
                               AND v.inicio > NOW() ORDER BY v.inicio LIMIT 1""", (self.doador_id,), um=True)
        return {"cupons": [{"codigo": c["codigo"], "oferta": c["titulo"], "parceiro": c["parceiro"],
                            "situacao": f"usado em {_data(c['usado_em'])}" if c["usado_em"] else f"vale até {_data(c['expira_em'])}"}
                           for c in cupons],
                "convocacoes_abertas": [{"banco": c["banco"], "tipo": c["tipo_sanguineo"], "mensagem": c["mensagem"],
                                         "enviada_em": _data(c["enviada_em"])} for c in conv],
                "proximo_agendamento": {"quando": ag["inicio"].strftime("%d/%m/%Y às %H:%M"), "local": ag["unidade"],
                                        "codigo": ag["codigo"]} if ag else None}

    def locais_de_doacao(self, cidade: str = ""):
        sql = """SELECT u.nome, u.tipo, u.endereco, u.bairro, u.cidade, u.uf, u.horario, b.nome AS banco FROM unidades u
                 LEFT JOIN bancos_sangue b ON b.id=u.banco_id WHERE u.ativo=1 AND (u.tipo='PUBLICO' OR b.status='ATIVO')"""
        params = []
        if cidade:
            sql += " AND u.cidade LIKE %s"
            params.append(f"%{cidade}%")
        linhas = self._consulta(sql + " ORDER BY u.cidade, u.tipo, u.nome", params)
        return {"locais": [{"nome": l["nome"], "tipo": "Banco parceiro (agenda pelo app)" if l["tipo"] == "BANCO" else "Hemocentro público (agenda direto com o hemocentro)",
                            "endereco": ", ".join(x for x in (l["endereco"], l["bairro"]) if x) or "não cadastrado",
                            "cidade": f"{l['cidade']}/{l['uf']}", "horario": l["horario"] or "não cadastrado"} for l in linhas]
                or [{"aviso": "Nenhum local cadastrado para essa cidade."}]}

    # ---- definição para a IA (function calling) --------------------------------------
    def definicoes(self) -> list[dict]:
        """Ferramentas que a IA pode chamar. As do doador só aparecem quando há alguém logado."""
        def f(nome, descricao, props=None):
            return {"type": "function", "function": {"name": nome, "description": descricao, "parameters": {
                "type": "object", "properties": props or {}, "required": [], "additionalProperties": False}}}
        lista = [
            f("nivel_do_estoque", "Nível (Normal/Atenção/Crítico) e data de atualização de um tipo sanguíneo nos bancos parceiros.",
              {"tipo_sanguineo": {"type": "string", "description": "Ex.: O-, A+. Vazio = tipo do doador logado."},
               "banco": {"type": "string", "description": "Nome do banco ou cidade (opcional)."}}),
            f("locais_de_doacao", "Locais de doação cadastrados (endereço e horário), opcionalmente filtrando pela cidade.",
              {"cidade": {"type": "string", "description": "Cidade (opcional)."}}),
        ]
        if self.doador_id:
            lista += [
                f("quando_posso_doar", "Data a partir da qual o doador logado pode doar de novo (pré-checagem do app)."),
                f("minha_meta_isencao", "Progresso do doador logado na meta de doador regular (isenção em concursos do estado)."),
                f("meus_cupons_e_convocacoes", "Cupons, convocações abertas e próximo agendamento do doador logado."),
            ]
        return lista

    def executar(self, nome: str, argumentos: dict):
        permitidas = {d["function"]["name"] for d in self.definicoes()}
        if nome not in permitidas:
            return {"erro": "Ferramenta não disponível."}
        try:
            return getattr(self, nome)(**{k: v for k, v in (argumentos or {}).items() if isinstance(v, str)})
        except mysql.connector.Error:
            return {"erro": "Não consegui consultar o banco de dados agora."}


if __name__ == "__main__":
    f = Ferramentas()
    print(f.locais_de_doacao())
    print(f.nivel_do_estoque("O-"))
