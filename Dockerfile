# HemoFlow — imagem para hospedagem em nuvem (Railway, Render, Koyeb, Fly.io, VPS...).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HEMOFLOW_ENV=production \
    HEMOFLOW_HOST=0.0.0.0 \
    TZ=America/Recife

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Só o necessário para rodar: backend + interface.
COPY servidor.py ./
COPY scripts/criar_administrador.py scripts/migracao_004_cpf_doador.py ./scripts/
COPY static ./static
# Estrutura do banco para a instalação automática (HEMOFLOW_AUTO_INSTALL=1).
COPY banco/instalacao ./banco/instalacao

# Não roda como root dentro do contêiner.
RUN useradd --create-home --uid 10001 hemoflow
USER hemoflow

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT', os.environ.get('HEMOFLOW_PORT', '8000')), timeout=4)"

CMD ["python", "servidor.py"]
