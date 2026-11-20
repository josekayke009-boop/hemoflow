/*
 * HemoFlow — aba "Assistente" (mini agente de IA com RAG, pasta assistente/ do projeto)
 * Responde dúvidas usando SÓ o FAQ do HemoFlow e, para o doador logado, os dados do próprio cadastro.
 * A conversa fica só na tela (não é salva). Usado no app do doador e no painel do parceiro.
 */
import { api, esc } from "./nucleo.js";

const SUGESTOES = {
  DOADOR: ["Quando posso doar de novo?", "Para quem posso doar?", "Como está minha meta de isenção?", "Tenho cupons?", "Onde posso doar em Caruaru?"],
  PARCEIRO: ["Quem pode usar as minhas ofertas?", "Como funciona a oferta de emergência?", "O que a faculdade vê dos alunos?"],
};
let conversa = []; // [{quem: "voce"|"assistente", texto, fonte}]

export function telaAssistente(perfil = "DOADOR") {
  return `
    <section class="cartao assistente">
      <div class="assistente-topo"><span class="assistente-avatar" aria-hidden="true">🩸</span>
        <div><h2 style="margin:0">Assistente HemoFlow</h2>
        <p class="muted pequeno" style="margin:0">Respondo com base no FAQ do HemoFlow${perfil === "DOADOR" ? " e nos dados do seu cadastro" : ""}. Não dou orientação médica: isso é com a triagem.</p></div></div>
      <div id="assistente-status" class="hidden"></div>
      <div id="assistente-conversa" class="assistente-conversa" aria-live="polite"></div>
      <div class="chips assistente-sugestoes">${SUGESTOES[perfil].map((s) => `<button type="button" class="chip" data-sugestao="${esc(s)}">${esc(s)}</button>`).join("")}</div>
      <form id="f-assistente" class="assistente-envio">
        <label class="visualmente-oculto" for="assistente-pergunta">Sua pergunta</label>
        <input id="assistente-pergunta" name="pergunta" maxlength="500" autocomplete="off" placeholder="Escreva sua dúvida…" required />
        <button class="btn btn-primario" type="submit">Enviar</button>
      </form>
      <p class="muted pequeno" style="margin:10px 0 0">As perguntas são processadas por um serviço de IA (OpenAI). Não escreva CPF, senhas ou dados de saúde.</p>
    </section>`;
}

function formatar(texto) {
  // separa a linha "Fonte:" para mostrar em letra menor
  const partes = texto.split(/\n?\s*(Fonte:.*)$/s);
  return { corpo: esc(partes[0].trim()).replace(/\n/g, "<br>"), fonte: partes[1] ? esc(partes[1].trim()) : "" };
}

function desenhar(caixa) {
  caixa.innerHTML = conversa.length
    ? conversa
        .map((m) => {
          if (m.quem === "voce") return `<div class="msg msg-voce">${esc(m.texto)}</div>`;
          if (m.carregando) return `<div class="msg msg-assistente carregando"><span></span><span></span><span></span></div>`;
          const f = formatar(m.texto);
          return `<div class="msg msg-assistente${m.erro ? " msg-erro" : ""}">${f.corpo}${f.fonte ? `<small class="msg-fonte">${f.fonte}</small>` : ""}</div>`;
        })
        .join("")
    : `<div class="msg msg-assistente">Olá! Sou o assistente do HemoFlow. Pergunte sobre doação de sangue, sobre o app ou toque numa sugestão abaixo.</div>`;
  caixa.scrollTop = caixa.scrollHeight;
}

export function ligarAssistente(corpo, rota) {
  const caixa = corpo.querySelector("#assistente-conversa");
  const form = corpo.querySelector("#f-assistente");
  const campo = form.querySelector("input");
  const botao = form.querySelector("button");
  desenhar(caixa);
  api("/api/assistente/status")
    .then((r) => {
      if (r.disponivel) return;
      const aviso = corpo.querySelector("#assistente-status");
      aviso.className = "aviso-suave";
      aviso.textContent = "O assistente está desligado neste servidor. Ele roda no computador da equipe (python servico.py, na pasta assistente).";
      campo.disabled = botao.disabled = true;
      corpo.querySelectorAll("[data-sugestao]").forEach((b) => (b.disabled = true));
    })
    .catch(() => {});

  async function perguntar(texto) {
    texto = texto.trim();
    if (!texto || botao.disabled) return;
    conversa.push({ quem: "voce", texto }, { quem: "assistente", carregando: true });
    desenhar(caixa);
    campo.value = "";
    campo.disabled = botao.disabled = true;
    try {
      const r = await api(rota, { pergunta: texto });
      conversa[conversa.length - 1] = { quem: "assistente", texto: r.resposta };
    } catch (e) {
      conversa[conversa.length - 1] = { quem: "assistente", texto: e.message, erro: true };
    } finally {
      conversa = conversa.slice(-30);
      campo.disabled = botao.disabled = false;
      desenhar(caixa);
      campo.focus();
    }
  }
  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    perguntar(campo.value);
  });
  corpo.querySelectorAll("[data-sugestao]").forEach((b) => b.addEventListener("click", () => perguntar(b.dataset.sugestao)));
}

/** Apaga a conversa da tela (chamado ao sair da conta). */
export function limparConversa() {
  conversa = [];
}
