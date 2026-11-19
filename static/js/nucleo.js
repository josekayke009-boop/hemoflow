/*
 * HemoFlow 2.0 — peças comuns do front-end
 *   api() ............ conversa com o servidor (/api/...) e trata erros
 *   esc() / html ..... monta HTML com texto sempre escapado (segurança contra XSS)
 *   aviso() .......... mensagem rápida no rodapé (toast)
 *   janela() ......... janela (modal) reutilizável
 *   preferencias ..... tema claro/escuro, tamanho da letra, alto contraste, menos movimento
 *   icone() .......... ícones SVG desenhados aqui mesmo (sem biblioteca externa)
 *   SEM INTERNET ..... guarda a última resposta de cada consulta (só da conta logada, apagada ao Sair),
 *                      mostra a faixa "Sem internet · dados de ..." e guarda na fila as confirmações
 *                      de doação feitas offline, enviando quando a conexão volta.
 */

export class ErroApi extends Error {
  constructor(mensagem, status) {
    super(mensagem);
    this.status = status;
  }
}

/* ---- SEM INTERNET: cache das consultas e fila --------------------------- */
let dono = null; // id do usuário logado: o cache é separado por conta
const FILA = "hf-fila";
const PODE_ENFILEIRAR = ["/api/banco/confirmar"]; // único envio guardado offline (o servidor recusa código repetido)
const chave = (caminho) => (caminho === "/api/session" ? "hf-cache:sessao" : `hf-cache:${dono}:${caminho}`);
function guardar(caminho, dados) {
  if (caminho !== "/api/session" && !dono) return;
  try {
    localStorage.setItem(chave(caminho), JSON.stringify({ em: Date.now(), dados }));
  } catch {
    /* armazenamento cheio ou bloqueado: segue sem cache */
  }
}
function lerCache(caminho) {
  try {
    return JSON.parse(localStorage.getItem(chave(caminho)) || "null");
  } catch {
    return null;
  }
}
const lerFila = () => {
  try {
    return JSON.parse(localStorage.getItem(FILA) || "[]");
  } catch {
    return [];
  }
};
const salvarFila = (f) => {
  try {
    localStorage.setItem(FILA, JSON.stringify(f));
  } catch {
    /* sem armazenamento */
  }
};
export function definirDono(id) {
  if (dono !== null && dono !== id) limparDadosLocais();
  dono = id;
}
/** Apaga tudo o que foi guardado neste aparelho (chamado ao Sair e ao trocar de conta). */
export function limparDadosLocais() {
  try {
    Object.keys(localStorage)
      .filter((k) => k.startsWith("hf-cache:") || k === FILA)
      .forEach((k) => localStorage.removeItem(k));
  } catch {
    /* nada guardado */
  }
}
function faixa() {
  let f = document.getElementById("faixa-offline");
  if (!f) {
    f = document.createElement("div");
    f.id = "faixa-offline";
    f.setAttribute("role", "status");
    document.body.prepend(f);
  }
  return f;
}
function mostrarOffline(em) {
  const d = new Date(em);
  const quando = `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")} às ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  const pendentes = lerFila().length;
  faixa().textContent = `⚠ Sem internet · mostrando dados de ${quando}` + (pendentes ? ` · ${pendentes} confirmação(ões) na fila` : "");
  document.body.classList.add("sem-internet");
}
function mostrarOnline() {
  document.body.classList.remove("sem-internet");
}
export async function enviarFila() {
  const fila = lerFila();
  if (!fila.length || !navigator.onLine) return;
  const sobra = [];
  let enviados = 0;
  for (const item of fila) {
    try {
      const r = await fetch(item.caminho, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(item.corpo) });
      const dados = await r.json().catch(() => ({}));
      if (r.ok) enviados++;
      else aviso(`Confirmação guardada (código ${item.corpo.codigo}) não foi aceita: ${dados.erro || "erro"}`, "erro");
    } catch {
      sobra.push(item); // continua sem conexão: tenta depois
    }
  }
  salvarFila(sobra);
  if (enviados) aviso(`${enviados} confirmação(ões) guardada(s) sem internet foram enviadas.`);
}
addEventListener("online", async () => {
  mostrarOnline();
  await enviarFila();
  document.dispatchEvent(new CustomEvent("hemoflow:online"));
});

/** Guarda em segundo plano as telas principais, para a consulta sem internet funcionar mesmo nas não abertas. */
export function preCarregar(caminhos) {
  if (!navigator.onLine) return;
  setTimeout(() => caminhos.forEach((c) => api(c).catch(() => {})), 1500);
}

export async function api(caminho, corpo, metodo) {
  const opcoes = { method: metodo || (corpo === undefined ? "GET" : "POST"), credentials: "same-origin", headers: {} };
  if (corpo !== undefined) {
    opcoes.headers["Content-Type"] = "application/json";
    opcoes.body = JSON.stringify(corpo);
  }
  let resposta;
  try {
    resposta = await fetch(caminho, opcoes);
  } catch {
    if (opcoes.method === "GET") {
      const c = lerCache(caminho);
      if (c) {
        mostrarOffline(c.em);
        return c.dados;
      }
      throw new ErroApi("Sem internet. Esta tela precisa de conexão para ser aberta pela primeira vez neste aparelho.", 0);
    }
    if (PODE_ENFILEIRAR.includes(caminho)) {
      salvarFila([...lerFila(), { caminho, corpo, em: Date.now() }]);
      mostrarOffline(Date.now());
      return { ok: true, enfileirado: true, mensagem: "Sem internet: confirmação guardada. Ela será enviada assim que a conexão voltar." };
    }
    throw new ErroApi("Sem internet: esta ação precisa de conexão. Os dados continuam disponíveis para consulta.", 0);
  }
  let dados = {};
  try {
    dados = await resposta.json();
  } catch {
    /* resposta sem JSON */
  }
  if (resposta.status === 401 && !caminho.startsWith("/api/login")) {
    document.dispatchEvent(new CustomEvent("hemoflow:sessao-expirada"));
  }
  if (!resposta.ok) throw new ErroApi(dados.erro || "Não foi possível concluir. Tente de novo.", resposta.status);
  if (opcoes.method === "GET") {
    guardar(caminho, dados);
    mostrarOnline();
  }
  return dados;
}

/* ---- HTML seguro -------------------------------------------------------- */
const MAPA = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => MAPA[c]);
/** Template que escapa tudo, menos o que vier marcado com cru(). */
export class Cru {
  constructor(t) {
    this.t = t;
  }
  toString() {
    return this.t;
  }
}
export const cru = (t) => new Cru(t);
export function html(partes, ...valores) {
  let s = partes[0];
  valores.forEach((v, i) => {
    if (Array.isArray(v)) s += v.map((x) => (x instanceof Cru ? x.t : esc(x))).join("");
    else s += v instanceof Cru ? v.t : esc(v);
    s += partes[i + 1];
  });
  return cru(s);
}
export const $ = (sel, raiz = document) => raiz.querySelector(sel);
export const $$ = (sel, raiz = document) => [...raiz.querySelectorAll(sel)];

/* ---- formatação --------------------------------------------------------- */
const DIAS = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
export function dataBR(iso) {
  if (!iso) return "—";
  const [a, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${a}`;
}
export const hora = (iso) => (iso ? iso.slice(11, 16) : "");
export function diaSemana(iso) {
  const [a, m, d] = iso.slice(0, 10).split("-").map(Number);
  return DIAS[new Date(a, m - 1, d).getDay()];
}
export function hojeISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
export const NIVEL_TEXTO = { CRITICO: "Crítico", ATENCAO: "Atenção", NORMAL: "Normal" };
export const NIVEL_ALTURA = { CRITICO: 18, ATENCAO: 48, NORMAL: 86 };
export const TIPOS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];
export const UFS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(" ");
export const TIPO_PARCEIRO = {
  COMERCIO: "Comércio",
  CURSINHO_CONCURSO: "Cursinho para concursos",
  PRE_ENEM: "Pré-Enem",
  FACULDADE: "Faculdade",
  OUTRO: "Outro",
};
export function opcoesUF(selecionada = "PE") {
  return UFS.map((u) => `<option${u === selecionada ? " selected" : ""}>${u}</option>`).join("");
}

/* ---- avisos e janela ---------------------------------------------------- */
export function aviso(texto, tipo = "") {
  const div = document.createElement("div");
  div.className = "toast" + (tipo === "erro" ? " erro-t" : "");
  div.textContent = texto;
  $("#toasts").append(div);
  setTimeout(() => div.remove(), tipo === "erro" ? 6000 : 3800);
}
export function erro(e) {
  aviso(e?.message || String(e), "erro");
}

export function janela(titulo, conteudo) {
  const d = $("#janela");
  $("#janela-titulo").textContent = titulo;
  $("#janela-corpo").innerHTML = String(conteudo);
  if (!d.open) d.showModal();
  return $("#janela-corpo");
}
export const fecharJanela = () => $("#janela").open && $("#janela").close();

/** Envia um formulário: junta os campos, mostra erro dentro dele e trava o botão enquanto envia. */
export function aoEnviar(form, acao) {
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const botao = form.querySelector('button[type="submit"]');
    const caixaErro = form.querySelector(".erro");
    caixaErro?.classList.add("hidden");
    const dados = {};
    for (const campo of form.elements) {
      if (!campo.name) continue;
      dados[campo.name] = campo.type === "checkbox" ? campo.checked : campo.value.trim();
    }
    if (botao) botao.disabled = true;
    try {
      await acao(dados, form);
    } catch (e) {
      if (caixaErro) {
        caixaErro.textContent = e.message;
        caixaErro.classList.remove("hidden");
      } else erro(e);
    } finally {
      if (botao) botao.disabled = false;
    }
  });
}

/* ---- preferências (ficam só neste aparelho) ----------------------------- */
const CHAVE = "hemoflow-preferencias";
export const preferencias = {
  ler() {
    try {
      return { tema: "claro", fonte: "0", contraste: "normal", movimento: "normal", ...JSON.parse(localStorage.getItem(CHAVE) || "{}") };
    } catch {
      return { tema: "claro", fonte: "0", contraste: "normal", movimento: "normal" };
    }
  },
  salvar(mudanca) {
    const p = { ...this.ler(), ...mudanca };
    try {
      localStorage.setItem(CHAVE, JSON.stringify(p));
    } catch {
      /* navegador sem armazenamento: vale só nesta visita */
    }
    this.aplicar(p);
    return p;
  },
  aplicar(p = this.ler()) {
    const r = document.documentElement;
    r.dataset.tema = p.tema;
    r.dataset.fonte = p.fonte;
    r.dataset.contraste = p.contraste;
    r.dataset.movimento = p.movimento;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", p.tema === "escuro" ? "#0e1120" : "#b0102a");
  },
};

/** Bloco de acessibilidade usado no Perfil do doador e no menu dos painéis. */
export function blocoAcessibilidade() {
  const p = preferencias.ler();
  const botao = (campo, valor, texto) =>
    `<button type="button" class="chip${p[campo] === valor ? " ativo" : ""}" data-pref="${campo}" data-valor="${valor}" aria-pressed="${p[campo] === valor}">${texto}</button>`;
  return `
    <h3>Aparência</h3>
    <div class="chips" style="margin-bottom:16px">${botao("tema", "claro", "☀ Claro")}${botao("tema", "escuro", "☾ Escuro")}</div>
    <h3>Tamanho da letra</h3>
    <div class="chips" style="margin-bottom:16px">${botao("fonte", "0", "A Normal")}${botao("fonte", "1", "A+ Maior")}${botao("fonte", "2", "A++ Bem maior")}</div>
    <h3>Contraste</h3>
    <div class="chips" style="margin-bottom:16px">${botao("contraste", "normal", "Normal")}${botao("contraste", "alto", "Alto contraste")}</div>
    <h3>Animações</h3>
    <div class="chips">${botao("movimento", "normal", "Com animações")}${botao("movimento", "reduzido", "Menos movimento")}</div>`;
}
export function ligarAcessibilidade(raiz) {
  raiz.addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-pref]");
    if (!b) return;
    preferencias.salvar({ [b.dataset.pref]: b.dataset.valor });
    $$(`[data-pref="${b.dataset.pref}"]`, raiz).forEach((x) => {
      const ativo = x === b;
      x.classList.toggle("ativo", ativo);
      x.setAttribute("aria-pressed", ativo);
    });
  });
}

/* ---- termômetro (opção A) ----------------------------------------------- */
export function termometro(nivel, rotulo, comMarcas = true) {
  const altura = NIVEL_ALTURA[nivel] ?? 0;
  return `
    <div class="termometro nivel-${esc(nivel)}" role="img" aria-label="Estoque ${esc(rotulo)}: ${esc(NIVEL_TEXTO[nivel] || "sem dado")}">
      <div class="tubo"><div class="liquido" style="height:${altura}%"></div></div>
      <div class="bulbo">${esc(rotulo)}</div>
      ${comMarcas ? '<div class="marcas"><span>Normal</span><span>Atenção</span><span>Crítico</span></div>' : ""}
    </div>`;
}

/* ---- ícones ------------------------------------------------------------- */
const P = {
  inicio: '<path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
  agenda: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  presente: '<rect x="3" y="8" width="18" height="13" rx="2"/><path d="M12 8v13M3 12h18M12 8c-2-4-6-4-6-1s6 1 6 1zm0 0c2-4 6-4 6-1s-6 1-6 1z"/>',
  pessoa: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
  sino: '<path d="M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8M10 20a2 2 0 0 0 4 0"/>',
  gota: '<path d="M12 3s7 7.5 7 12a7 7 0 0 1-14 0c0-4.5 7-12 7-12z"/>',
  megafone: '<path d="M3 11v2a1 1 0 0 0 1 1h3l6 4V6L7 10H4a1 1 0 0 0-1 1zM17 8a5 5 0 0 1 0 8"/>',
  check: '<path d="M4 12l5 5L20 6"/>',
  grafico: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  lista: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  predio: '<path d="M4 21V5l8-3 8 3v16M9 21v-4h6v4M8 8h.01M12 8h.01M16 8h.01M8 12h.01M12 12h.01M16 12h.01"/>',
  loja: '<path d="M3 9l2-5h14l2 5M4 9v11h16V9M3 9h18M9 20v-6h6v6"/>',
  chave: '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M17 6l3 3"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  sair: '<path d="M15 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4M10 17l5-5-5-5M15 12H3"/>',
  ajustes: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2"/>',
  ajuda: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.7M12 17h.01"/>',
  ticket: '<path d="M3 8a2 2 0 0 0 0 4v0a2 2 0 0 1 0 4v2h18v-2a2 2 0 0 1 0-4 2 2 0 0 0 0-4V6H3z"/>',
};
export const icone = (nome) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[nome] || ""}</svg>`;

/* ---- avisos do sino ----------------------------------------------------- */
export async function abrirAvisos(aoMudar, aoLink) {
  try {
    const r = await api("/api/avisos");
    const itens = r.avisos.length
      ? r.avisos
          .map(
            (a) => `<li><div class="principal"><strong>${a.lido_em ? "" : "● "}${esc(a.titulo)}</strong>
              <span class="muted pequeno">${esc(a.mensagem)}</span><br><span class="muted pequeno">${dataBR(a.criado_em)} ${hora(a.criado_em)}</span></div>
              ${a.link && aoLink ? `<button type="button" class="btn btn-pequeno btn-claro" data-aviso-link="${esc(a.link)}">Abrir</button>` : ""}</li>`,
          )
          .join("")
      : '<li class="vazio">Nenhum aviso por enquanto.</li>';
    const corpo = janela("Avisos", `<ul class="lista">${itens}</ul>`);
    corpo.querySelectorAll("[data-aviso-link]").forEach((b) =>
      b.addEventListener("click", () => {
        fecharJanela();
        aoLink(b.dataset.avisoLink);
      }),
    );
    if (r.nao_lidos) {
      await api("/api/avisos/lidos", {});
      aoMudar?.(0);
    }
  } catch (e) {
    erro(e);
  }
}
export async function contarAvisos() {
  try {
    return (await api("/api/avisos")).nao_lidos;
  } catch {
    return 0;
  }
}
