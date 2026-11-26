# HemoFlow — imagem para hospedagem em nuvem (Railway, Render, Koyeb, Fly.io, VPS...).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HEMOFLOW_ENV=production \
    HEMOFLOW_HOST=0.0.0.0 \
    TZ=America/Recife \
    ASSISTENTE_EMBEDDINGS=openai

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Só o necessário para rodar: backend + interface.
# Versão 2.0: servidor + rotas (rotas_v2.py) + regras de negócio (regras.py).
# dados_demo.py só cria dados FICTÍCIOS quando alguém roda "python dados_demo.py" no console.
COPY servidor.py rotas_v2.py regras.py dados_demo.py ./
COPY scripts/criar_administrador.py scripts/migracao_004_cpf_doador.py scripts/migracao_005_v2.py scripts/migracao_006_v21.py scripts/backup_interno.py ./scripts/
COPY static ./static
# Assistente HemoFlow (IA com RAG) no modo nuvem: só o código e o FAQ. Os embeddings vêm da API da OpenAI,
# então a imagem não leva PyTorch nem o modelo local. Liga quando OPENAI_API_KEY existir nas variáveis.
COPY assistente/config.py assistente/busca.py assistente/agente.py assistente/ferramentas.py assistente/indexar.py ./assistente/
COPY assistente/base/faq_hemoflow.txt ./assistente/base/
# Estrutura do banco para a instalação automática (HEMOFLOW_AUTO_INSTALL=1) e migração 005.
COPY banco/instalacao ./banco/instalacao
COPY banco/migracoes/005_v2_captacao.sql banco/migracoes/005_v2_dados.sql banco/migracoes/006_v21_diferenciais.sql ./banco/migracoes/

# Não roda como root dentro do contêiner.
RUN useradd --create-home --uid 10001 hemoflow
USER hemoflow

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT', os.environ.get('HEMOFLOW_PORT', '8000')), timeout=4)"

CMD ["python", "servidor.py"]
