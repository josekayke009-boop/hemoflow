"""Assistente HemoFlow — PASSO 3 do RAG: responder com a IA usando SÓ os trechos recuperados.

Fluxo de uma pergunta:
  1. busca.buscar()  -> trechos mais parecidos do FAQ (top-k)
  2. se nem o melhor trecho for minimamente parecido (assunto fora do HemoFlow) e a pergunta
     não for sobre os dados do usuário, responde que não sabe (sem gastar chamada da IA)
  3. a IA recebe: regras (prompt de sistema) + trechos + pergunta, e pode chamar as
     ferramentas somente leitura (dados do próprio usuário logado)
  4. a resposta volta com a seção do FAQ usada como fonte
"""
import json

from openai import OpenAI

import busca
import config
from ferramentas import Ferramentas

PROMPT_SISTEMA = """Você é o Assistente HemoFlow, que tira dúvidas de doadores de sangue e de parceiros sobre o aplicativo HemoFlow e sobre doação de sangue.

REGRAS (siga todas, sempre):
1. Responda em português do Brasil, de forma curta e clara (no máximo 5 frases ou uma lista curta).
2. Use SOMENTE as informações dos TRECHOS DO FAQ abaixo e dos resultados das ferramentas. Não use conhecimento próprio.
3. Se a resposta não estiver nos trechos nem nas ferramentas, diga que não sabe e sugira falar com o banco de sangue, com o HEMOPE ou com a equipe pela aba Ajuda do app.
4. Não dê diagnóstico nem orientação médica individual. Em dúvidas de saúde (remédios, doenças, tatuagem, piercing, viagem, vacina, cirurgia, gravidez etc.), oriente procurar a triagem do hemocentro ou do banco de sangue.
5. Nunca invente números, datas, endereços, horários ou níveis de estoque. Endereços, horários, estoque e dados do usuário só podem vir das ferramentas.
6. Para dados pessoais do usuário (quando pode doar, meta de isenção, cupons, convocações), use as ferramentas. Se a ferramenta disser que é preciso entrar no app, repasse isso.
7. Termine a resposta com uma linha "Fonte:" citando a seção do FAQ usada (ex.: "Fonte: FAQ, seção 3. Intervalos e limites entre doações"). Quando usar ferramenta, cite: "seu cadastro no HemoFlow" (dados do usuário), "níveis informados pelos bancos parceiros" (estoque) ou "cadastro de locais do HemoFlow" (endereços). Se não souber, escreva "Fonte: não encontrada na base do HemoFlow".
8. Sobre metas e benefícios, informe o progresso, mas lembre que a comprovação oficial é a declaração da entidade coletora; não afirme que o usuário já "tem direito" garantido.
9. Responda só o que foi perguntado. Se um trecho não for sobre a pergunta, ignore-o."""

# Perguntas sobre o próprio usuário (respondidas por ferramenta mesmo sem trecho parecido no FAQ)
PALAVRAS_PESSOAIS = ("meu", "minha", "meus", "minhas", "posso doar", "quando eu", "estoque", "nível", "nivel",
                     "onde doar", "endereço", "endereco", "horário", "horario", "cupom", "cupons", "convoca")


class Assistente:
    def __init__(self, doador_id: int | None = None, cliente: OpenAI | None = None):
        self.ferramentas = Ferramentas(doador_id)
        self.cliente = cliente

    def _llm(self) -> OpenAI:
        if self.cliente is None:
            if not config.OPENAI_API_KEY:
                raise RuntimeError("Falta a chave da IA: coloque OPENAI_API_KEY no arquivo assistente/.env")
            self.cliente = OpenAI(api_key=config.OPENAI_API_KEY, base_url=config.LLM_BASE_URL)
        return self.cliente

    def responder(self, pergunta: str) -> dict:
        pergunta = (pergunta or "").strip()[:500]
        if not pergunta:
            return {"resposta": "Escreva a sua dúvida sobre doação de sangue ou sobre o HemoFlow.", "fontes": [], "ferramentas": []}
        trechos = busca.buscar(pergunta)
        relevantes = trechos if trechos and trechos[0]["semelhanca"] >= config.LIMIAR_SEMELHANCA else []
        pessoal = any(p in pergunta.lower() for p in PALAVRAS_PESSOAIS)
        if not relevantes and not pessoal:
            return {"resposta": "Não encontrei essa informação na base do HemoFlow. Para essa dúvida, procure o banco de sangue, "
                                "o HEMOPE ou a equipe pela aba Ajuda do app.\nFonte: não encontrada na base do HemoFlow",
                    "fontes": [], "ferramentas": [], "trechos": trechos}

        contexto = "\n\n".join(f"[{t['secao']}]\n{t['pergunta']}\n{t['resposta']}" for t in relevantes) or "(nenhum trecho relevante)"
        mensagens = [
            {"role": "system", "content": PROMPT_SISTEMA},
            {"role": "system", "content": f"TRECHOS DO FAQ:\n{contexto}"},
            {"role": "user", "content": pergunta},
        ]
        usadas = []
        for _ in range(4):  # no máximo 3 rodadas de ferramentas + a resposta final
            r = self._llm().chat.completions.create(model=config.LLM_MODELO, messages=mensagens, temperature=0.2,
                                                    tools=self.ferramentas.definicoes(), max_tokens=450)
            msg = r.choices[0].message
            if not msg.tool_calls:
                return {"resposta": (msg.content or "").strip(), "fontes": sorted({t["secao"] for t in relevantes}),
                        "ferramentas": usadas, "trechos": trechos}
            mensagens.append({"role": "assistant", "content": msg.content or "",
                              "tool_calls": [c.model_dump() for c in msg.tool_calls]})
            for chamada in msg.tool_calls:
                try:
                    args = json.loads(chamada.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                resultado = self.ferramentas.executar(chamada.function.name, args)
                usadas.append(chamada.function.name)
                mensagens.append({"role": "tool", "tool_call_id": chamada.id,
                                  "content": json.dumps(resultado, ensure_ascii=False, default=str)})
        return {"resposta": "Não consegui concluir a resposta agora. Tente perguntar de outro jeito.", "fontes": [],
                "ferramentas": usadas, "trechos": trechos}
