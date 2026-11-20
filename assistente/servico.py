"""Assistente HemoFlow — serviço local que a aba "Assistente" do app usa.

Roda no mesmo computador do HemoFlow e só aceita conexões de 127.0.0.1.
O HemoFlow manda a pergunta e o id do doador logado (ou nada, para parceiros) junto com o
segredo ASSISTENTE_SEGREDO do .env; sem o segredo certo, a resposta é 403.

Uso (pasta assistente, .venv ativado):  python servico.py
Rotas:  GET /saude   ·   POST /perguntar  {"pergunta": "...", "doador_id": 11 | null}
"""
import hmac
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import busca
import config
from agente import Assistente


class Servico(BaseHTTPRequestHandler):
    server_version = "AssistenteHemoFlow/1.0"

    def responder_json(self, dados, status=200):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def autorizado(self):
        recebido = self.headers.get("X-Assistente-Segredo", "")
        return bool(config.SERVICO_SEGREDO) and hmac.compare_digest(recebido, config.SERVICO_SEGREDO)

    def do_GET(self):
        if self.path == "/saude":
            return self.responder_json({"ok": True, "modelo": config.LLM_MODELO, "trechos": len(busca.carregar()[2])})
        self.responder_json({"erro": "não encontrado"}, 404)

    def do_POST(self):
        if self.path != "/perguntar":
            return self.responder_json({"erro": "não encontrado"}, 404)
        if not self.autorizado():
            return self.responder_json({"erro": "acesso negado"}, 403)
        try:
            tamanho = min(int(self.headers.get("Content-Length", "0")), 10_000)
            dados = json.loads(self.rfile.read(tamanho) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self.responder_json({"erro": "JSON inválido"}, 400)
        doador_id = dados.get("doador_id")
        doador_id = int(doador_id) if isinstance(doador_id, int) or (isinstance(doador_id, str) and doador_id.isdigit()) else None
        inicio = time.time()
        try:
            r = Assistente(doador_id).responder(str(dados.get("pergunta", "")))
        except Exception as exc:  # noqa: BLE001 - erro da IA ou do banco vira mensagem amigável
            print("Erro ao responder:", type(exc).__name__, exc)
            return self.responder_json({"erro": "O assistente não conseguiu responder agora. Tente de novo em instantes."}, 502)
        print(f"[{time.strftime('%H:%M:%S')}] respondido em {time.time() - inicio:.1f}s"
              + (f" · ferramentas: {', '.join(r['ferramentas'])}" if r["ferramentas"] else ""))
        self.responder_json({"resposta": r["resposta"], "fontes": r.get("fontes", []), "ferramentas": r["ferramentas"]})

    def log_message(self, *args):  # sem log de cada requisição (as perguntas podem ter dados pessoais)
        pass


def main():
    if not config.SERVICO_SEGREDO:
        raise SystemExit("Falta ASSISTENTE_SEGREDO no .env (rode scripts/criar_usuario_leitura.py ou preencha à mão).")
    print("Carregando o modelo de embeddings e o índice…")
    busca.carregar()
    servidor = ThreadingHTTPServer(("127.0.0.1", config.SERVICO_PORTA), Servico)
    print(f"Assistente HemoFlow pronto em http://127.0.0.1:{config.SERVICO_PORTA} (só neste computador). Ctrl+C para parar.")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nAssistente encerrado.")


if __name__ == "__main__":
    main()
