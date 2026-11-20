"""Assistente HemoFlow — PASSO 1 do RAG: indexar a base de conhecimento.

1. Lê o FAQ (base/faq_hemoflow.txt).
2. Divide em trechos: UM trecho por pergunta + resposta, com o título da seção
   (assim a resposta do agente consegue dizer de qual seção veio).
3. Gera DOIS embeddings por trecho com o modelo local (sentence-transformers):
   - só a pergunta do FAQ (parece com o jeito curto que as pessoas perguntam);
   - o trecho inteiro (seção + pergunta + resposta), para achar pelo conteúdo.
   Na busca vale a média das duas notas. Salva o índice em indice/.

Uso:  python indexar.py        (rode de novo sempre que mudar o FAQ)
"""
import hashlib
import json
import re
import time

import numpy as np

import config

SECAO = re.compile(r"^(\d+)\.\s+(.+)$")


def dividir_em_trechos(texto: str) -> list[dict]:
    """Seção "N. TÍTULO" -> perguntas (linhas que terminam em "?") -> respostas (linhas seguintes)."""
    trechos, secao, pergunta, resposta = [], None, None, []

    def fechar():
        if secao and pergunta and resposta:
            trechos.append({"secao": secao, "pergunta": pergunta, "resposta": "\n".join(resposta).strip()})

    for linha in texto.splitlines():
        limpa = linha.strip()
        if not limpa or limpa.startswith("FAQ E MANUAL"):
            continue
        m = SECAO.match(limpa)
        if m and limpa.upper() == limpa:  # títulos de seção estão em MAIÚSCULAS
            fechar()
            secao, pergunta, resposta = f"{m.group(1)}. {m.group(2).capitalize()}", None, []
        elif limpa.endswith("?") and not limpa.startswith("-"):
            fechar()
            pergunta, resposta = limpa, []
        else:
            resposta.append(limpa)
    fechar()
    for i, t in enumerate(trechos):
        t["id"] = i
        t["texto"] = f"{t['secao']}\n{t['pergunta']}\n{t['resposta']}"
    return trechos


def main():
    texto = config.ARQUIVO_FAQ.read_text(encoding="utf-8")
    trechos = dividir_em_trechos(texto)
    print(f"FAQ: {len(trechos)} trechos em {len({t['secao'] for t in trechos})} seções.")
    from sentence_transformers import SentenceTransformer  # importa aqui: o carregamento demora

    inicio = time.time()
    print(f"Carregando o modelo {config.MODELO_EMBEDDINGS} (na 1ª vez ele é baixado, ~470 MB)…")
    modelo = SentenceTransformer(config.MODELO_EMBEDDINGS)
    vetores = modelo.encode([t["texto"] for t in trechos], normalize_embeddings=True, show_progress_bar=False)
    vetores_pergunta = modelo.encode([t["pergunta"] for t in trechos], normalize_embeddings=True, show_progress_bar=False)
    config.PASTA_INDICE.mkdir(exist_ok=True)
    np.save(config.PASTA_INDICE / "vetores.npy", vetores.astype(np.float32))
    np.save(config.PASTA_INDICE / "vetores_pergunta.npy", vetores_pergunta.astype(np.float32))
    (config.PASTA_INDICE / "trechos.json").write_text(json.dumps({
        "modelo": config.MODELO_EMBEDDINGS,
        "faq_sha256": hashlib.sha256(texto.encode("utf-8")).hexdigest(),
        "trechos": trechos,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Índice salvo em {config.PASTA_INDICE} ({vetores.shape[0]} vetores de {vetores.shape[1]} dimensões) "
          f"em {time.time() - inicio:.1f} s.")


if __name__ == "__main__":
    main()
