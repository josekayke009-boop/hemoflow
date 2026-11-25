"""Assistente HemoFlow — PASSO 2 do RAG: buscar os trechos mais relevantes para a pergunta.

A pergunta vira um vetor (mesmo modelo da indexação) e é comparada com todos os trechos
pela semelhança de cosseno (como os vetores são normalizados, é só um produto escalar).
"""
import hashlib
import json

import numpy as np

import config

_modelo = None
_vetores = None
_vetores_pergunta = None
_trechos = None


def carregar():
    """Carrega o índice e o modelo uma vez só (o modelo demora alguns segundos)."""
    global _modelo, _vetores, _vetores_pergunta, _trechos
    if config.EMBEDDINGS == "openai":
        return _carregar_nuvem()
    if _vetores is None:
        arquivo = config.PASTA_INDICE / "trechos.json"
        if not arquivo.exists():
            raise RuntimeError("Índice não encontrado. Rode antes:  python indexar.py")
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        atual = hashlib.sha256(config.ARQUIVO_FAQ.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
        if atual != dados["faq_sha256"]:
            print("Aviso: o FAQ mudou depois da indexação. Rode  python indexar.py  de novo.")
        _trechos = dados["trechos"]
        _vetores = np.load(config.PASTA_INDICE / "vetores.npy")
        _vetores_pergunta = np.load(config.PASTA_INDICE / "vetores_pergunta.npy")
    if _modelo is None:
        from sentence_transformers import SentenceTransformer
        _modelo = SentenceTransformer(config.MODELO_EMBEDDINGS)
    return _modelo, _vetores, _trechos


def _embeddings_nuvem(textos):
    """Vetores normalizados pela API da OpenAI (modo nuvem)."""
    from openai import OpenAI
    if not config.OPENAI_API_KEY:
        raise RuntimeError("Falta a chave da IA (OPENAI_API_KEY).")
    r = OpenAI(api_key=config.OPENAI_API_KEY).embeddings.create(model=config.MODELO_EMBEDDINGS_NUVEM, input=textos)
    v = np.array([d.embedding for d in r.data], dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


class _ModeloNuvem:
    def encode(self, textos, normalize_embeddings=True):
        return _embeddings_nuvem(textos)


def _carregar_nuvem():
    """Na nuvem, o índice é montado na primeira pergunta (116 textos em uma chamada) e fica na memória."""
    global _modelo, _vetores, _vetores_pergunta, _trechos
    if _vetores is None:
        from indexar import dividir_em_trechos
        trechos = dividir_em_trechos(config.ARQUIVO_FAQ.read_text(encoding="utf-8"))
        vetores = _embeddings_nuvem([t["texto"] for t in trechos] + [t["pergunta"] for t in trechos])
        _trechos, _vetores, _vetores_pergunta = trechos, vetores[:len(trechos)], vetores[len(trechos):]
        _modelo = _ModeloNuvem()
    return _modelo, _vetores, _trechos


def buscar(pergunta: str, k: int = config.TOP_K) -> list[dict]:
    """Devolve os k trechos mais parecidos com a pergunta, com a nota de semelhança (0 a 1)."""
    modelo, vetores, trechos = carregar()
    q = modelo.encode([pergunta], normalize_embeddings=True)[0]
    # média de "parecido com a pergunta do FAQ" e "parecido com o trecho inteiro"
    # (medido nos testes: a média põe o trecho certo entre os 6 primeiros em 10 de 11 perguntas)
    notas = (vetores @ q + _vetores_pergunta @ q) / 2
    melhores = np.argsort(-notas)[:k]
    return [{**trechos[i], "semelhanca": float(notas[i])} for i in melhores]


if __name__ == "__main__":
    import sys
    pergunta = " ".join(sys.argv[1:]) or "Quanto tempo preciso esperar entre doações?"
    for t in buscar(pergunta):
        print(f"{t['semelhanca']:.3f}  [{t['secao']}]  {t['pergunta']}")
