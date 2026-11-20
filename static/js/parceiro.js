/*
 * HemoFlow 2.0 — painel do parceiro (comércio, cursinho, pré-Enem, faculdade…)
 *   Impacto ......... quantos doadores o parceiro ajudou + selo "Parceiro HemoFlow" para a vitrine
 *   Validar cupom ... digita o código que o doador mostra (uso único)
 *   Ofertas ......... cadastra ofertas (aprovadas pelo admin) e ativa a OFERTA DE EMERGÊNCIA
 *                     para um tipo sanguíneo em falta na cidade, por 7 dias
 *   Alunos .......... (cursinhos e faculdades) código, relatório só com números gerais e
 *                     verificação das declarações de doação dos alunos
 */
import { api, $, esc, aviso, erro, aoEnviar, dataBR, janela, fecharJanela, TIPO_PARCEIRO, TIPOS } from "./nucleo.js";
import { montarPainel } from "./painel.js";
import { telaAjuda, ligarAjuda } from "./ajuda.js";
import { telaAssistente, ligarAssistente } from "./assistente.js";

let painel;
const STATUS = { PENDENTE: "Aguardando aprovação", APROVADA: "No ar", RECUSADA: "Recusada" };

export async function montar(raiz, usuario, ctx) {
  const inicial = await api("/api/parceiro/painel");
  const itens = [
    { id: "impacto", titulo: "Impacto e selo", icone: "grafico", tela: telaImpacto, depois: ligarImpacto },
    { id: "validar", titulo: "Validar cupom", icone: "ticket", tela: telaValidar, depois: ligarValidar },
    { id: "ofertas", titulo: "Ofertas", icone: "loja", tela: telaOfertas, depois: ligarOfertas },
  ];
  if (inicial.parceiro.codigo_alunos) itens.push({ id: "alunos", titulo: "Alunos", icone: "pessoa", tela: telaAlunos, depois: ligarAlunos });
  const assistente = await api("/api/assistente/status").catch(() => ({ disponivel: false }));
  if (assistente.disponivel)  // só onde o serviço do Assistente (IA) está ligado
    itens.push({ id: "assistente", titulo: "Assistente", icone: "conversa", tela: async () => telaAssistente("PARCEIRO"),
      depois: (corpo) => ligarAssistente(corpo, "/api/parceiro/assistente") });
  itens.push({ id: "ajuda", titulo: "Ajuda", icone: "ajuda", tela: async () => telaAjuda("PARCEIRO"), depois: ligarAjuda });
  painel = montarPainel(raiz, { subtitulo: inicial.parceiro.nome, usuario, ctx, itens, aoLink: () => painel.ir("ofertas") });
}

/* ---- IMPACTO E SELO -------------------------------------------------------------- */
async function telaImpacto() {
  const r = await api("/api/parceiro/painel");
  const im = r.impacto;
  return `<section class="cartao impacto-parceiro">
      <span class="muted">Neste mês</span>
      <h2 style="font-size:1.6rem;margin:4px 0">${esc(r.parceiro.nome)} ajudou ${im.doadores_mes} doador${im.doadores_mes === 1 ? "" : "es"} 💛</h2>
      <p class="muted" style="margin:0">São doadores que usaram um cupom seu depois de doar sangue. Desde o início: ${im.doadores_total}.</p></section>
    <div class="grade-numeros">
      <div class="numero"><strong>${r.cupons_usados_mes}</strong><span>cupons usados no mês</span></div>
      <div class="numero"><strong>${im.doadores_total}</strong><span>doadores ajudados no total</span></div>
      <div class="numero"><strong>${r.ofertas.filter((o) => o.status === "APROVADA").length}</strong><span>ofertas no ar</span></div>
    </div>
    ${r.criticos_cidade.length ? `<div class="alerta-critico"><strong>🔴 Falta sangue ${r.criticos_cidade.map(esc).join(", ")} em ${esc(r.parceiro.cidade)}.</strong>
      <span>Ative uma oferta de emergência para atrair esses doadores.</span> <button type="button" class="btn btn-pequeno btn-primario" data-ir-ofertas>Ativar em Ofertas</button></div>` : ""}
    <section class="cartao selo-parceiro"><div>
      <h2>Selo “Parceiro HemoFlow”</h2>
      <p class="muted">Imprima e cole na vitrine ou no caixa. O QR Code leva ao app: quem doa sangue ganha as suas vantagens.</p>
      <button type="button" class="btn btn-primario" data-imprimir-selo>🖨 Imprimir selo</button></div>
      <div class="selo-mini" aria-hidden="true"><img src="/img/qrcode-hemoflow.png" alt="" /><strong>Parceiro HemoFlow</strong><small>Doe sangue e ganhe vantagens aqui</small></div>
    </section>`;
}
function ligarImpacto(corpo) {
  corpo.querySelector("[data-ir-ofertas]")?.addEventListener("click", () => painel.ir("ofertas"));
  corpo.querySelector("[data-imprimir-selo]").addEventListener("click", imprimirSelo);
}
function imprimirSelo() {
  const nome = document.querySelector(".lateral .marca small")?.textContent || "";
  const w = window.open("", "_blank");
  if (!w) return erro(new Error("O navegador bloqueou a nova janela. Permita pop-ups para o HemoFlow."));
  w.document.write(`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Selo Parceiro HemoFlow</title>
    <style>@page{size:A5;margin:0}body{margin:0;font-family:Arial,sans-serif}
    .selo{width:148mm;height:210mm;box-sizing:border-box;padding:14mm;text-align:center;color:#fff;
      background:linear-gradient(150deg,#3a0209,#a50d22 60%,#4b030c);-webkit-print-color-adjust:exact;print-color-adjust:exact;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:5mm}
    .selo img.logo{width:22mm;height:22mm;border-radius:6mm}.selo h1{font-size:30pt;margin:0}.selo h2{font-size:15pt;margin:0;color:#ffd7db;font-weight:400}
    .qr{background:#fff;padding:5mm;border-radius:5mm}.qr img{width:62mm;height:62mm;display:block}
    .nome{font-size:13pt;font-weight:700}.lema{font-size:12pt;color:#ffd7db}</style></head><body>
    <div class="selo"><img class="logo" src="${location.origin}/img/hemoflow-icone.png" alt="">
      <h1>Parceiro HemoFlow</h1><h2>Doou sangue? Aqui você tem vantagens.</h2>
      <div class="qr"><img src="${location.origin}/img/qrcode-hemoflow.png" alt="QR Code do HemoFlow"></div>
      <div class="nome">${esc(nome)}</div><div class="lema">Doe. Volte. Salve vidas.</div></div></body></html>`);
  w.document.close();
  w.focus();
  setTimeout(() => w.print(), 700);
}

async function telaValidar() {
  const r = await api("/api/parceiro/painel");
  return `<section class="cartao" style="max-width:520px">
      <h2>Cupom do doador</h2><p class="muted">Peça o código que aparece no app HemoFlow do cliente (ex.: DOA-7KJ2).</p>
      <form id="f-validar"><label>Código <input name="codigo" autocomplete="off" class="codigo-grande" style="min-height:76px;text-transform:uppercase" required /></label>
      <p class="erro hidden"></p><button class="btn btn-ok cheio" type="submit">Validar e registrar uso</button></form>
      <div id="validado"></div></section>
    <div class="grade-numeros" style="max-width:520px"><div class="numero"><strong>${r.cupons_usados_mes}</strong><span>cupons usados neste mês</span></div></div>`;
}
function ligarValidar(corpo) {
  $("#f-validar input", corpo).focus();
  aoEnviar($("#f-validar", corpo), async (d, form) => {
    const r = await api("/api/parceiro/cupons/validar", { codigo: d.codigo });
    $("#validado", corpo).innerHTML = `<p class="sucesso" style="margin-top:14px">✅ ${esc(r.mensagem)}</p>`;
    form.reset();
  });
}

async function telaOfertas() {
  const r = await api("/api/parceiro/painel");
  return `<div class="colunas">
    <section class="cartao"><h2>Minhas ofertas</h2>
    ${r.ofertas.length ? `<ul class="lista">${r.ofertas
      .map((o) => `<li style="flex-wrap:wrap"><div class="principal"><strong>${esc(o.titulo)}</strong><span class="muted pequeno">${[o.descricao && esc(o.descricao), o.validade && "até " + dataBR(o.validade), `${o.usados} uso(s)`].filter(Boolean).join(" · ")}</span>
        ${o.emergencia ? `<span class="selo CRITICO" style="margin-top:4px">🚨 Emergência ${esc(o.emergencia)} até ${dataBR(o.emergencia_ate)}</span>` : ""}</div>
        <span class="selo ${o.status === "APROVADA" ? "ok" : o.status === "RECUSADA" ? "critico" : "atencao"}">${STATUS[o.status]}</span>
        ${o.status === "APROVADA" ? `<button type="button" class="btn btn-pequeno ${o.emergencia ? "btn-claro" : "btn-perigo"}" data-emergencia="${o.id}" data-ativa="${o.emergencia ? "1" : ""}">${o.emergencia ? "Desligar emergência" : "🚨 Emergência"}</button>` : ""}</li>`)
      .join("")}</ul>` : '<p class="vazio">Nenhuma oferta ainda.</p>'}</section>
    <section class="cartao"><h2>Nova oferta</h2>
      <form id="f-oferta"><label>Título <input name="titulo" maxlength="120" required placeholder="Ex.: 10% de desconto para doadores" /></label>
      <label>Detalhes <textarea name="descricao" maxlength="400" placeholder="Como usar, regras, endereço…"></textarea></label>
      <label>Válida até (opcional) <input name="validade" type="date" /></label>
      <p class="erro hidden"></p><button class="btn btn-primario cheio" type="submit">Enviar para aprovação</button></form>
      <p class="muted pequeno">Tipo de parceiro: ${esc(TIPO_PARCEIRO[r.parceiro.tipo] || r.parceiro.tipo)}. Só doadores com doação verificada nos últimos 6 meses conseguem gerar o cupom.</p></section></div>
    <p class="muted pequeno">🚨 Oferta de emergência: por 7 dias, a oferta aparece em primeiro lugar e destacada para os doadores do tipo escolhido.
      ${r.criticos_cidade.length ? `Agora falta sangue <strong>${r.criticos_cidade.map(esc).join(", ")}</strong> em ${esc(r.parceiro.cidade)}.` : ""}</p>`;
}
function abrirEmergencia(ofertaId, criticos) {
  const c = janela("Oferta de emergência", `<p>Escolha o tipo sanguíneo em falta. Por 7 dias, os doadores desse tipo veem esta oferta em primeiro lugar.</p>
    <div class="chips">${TIPOS.map((t) => `<button type="button" class="chip${criticos.includes(t) ? " ativo" : ""}" data-tipo-emerg="${t}">${t}${criticos.includes(t) ? " 🔴" : ""}</button>`).join("")}</div>
    <p class="muted pequeno" style="margin-top:12px">🔴 = em nível crítico na sua cidade agora.</p>`);
  c.querySelectorAll("[data-tipo-emerg]").forEach((b) =>
    b.addEventListener("click", async () => {
      try {
        const r = await api(`/api/parceiro/ofertas/${ofertaId}/emergencia`, { tipo: b.dataset.tipoEmerg });
        fecharJanela();
        aviso(r.mensagem);
        painel.ir("ofertas");
      } catch (e) {
        erro(e);
      }
    }),
  );
}
let criticosCache = [];
function ligarOfertas(corpo) {
  api("/api/parceiro/painel").then((r) => (criticosCache = r.criticos_cidade)).catch(() => {});
  corpo.addEventListener("click", async (ev) => {
    const b = ev.target.closest("[data-emergencia]");
    if (!b) return;
    if (!b.dataset.ativa) return abrirEmergencia(b.dataset.emergencia, criticosCache);
    try {
      aviso((await api(`/api/parceiro/ofertas/${b.dataset.emergencia}/emergencia`, { tipo: null })).mensagem);
      painel.ir("ofertas");
    } catch (e) {
      erro(e);
    }
  });
  aoEnviar($("#f-oferta", corpo), async (d) => {
    aviso((await api("/api/parceiro/ofertas", d)).mensagem);
    painel.ir("ofertas");
  });
}

async function telaAlunos() {
  const r = await api("/api/parceiro/painel");
  const rel = r.relatorio;
  return `<section class="cartao"><h2>Código para os alunos</h2>
      <div class="codigo-grande" style="max-width:420px">${esc(r.parceiro.codigo_alunos)}</div>
      <p class="muted" style="margin-top:12px">Divulgue este código. O aluno digita em Vantagens, no app HemoFlow.</p></section>
    <div class="grade-numeros"><div class="numero"><strong>${rel.alunos}</strong><span>alunos vinculados</span></div>
    ${rel.alunos >= rel.minimo_para_mostrar ? `<div class="numero"><strong>${rel.em_dia_meta}</strong><span>com a meta de doador regular em dia</span></div>` : ""}</div>
    <p class="muted pequeno">Por privacidade, o relatório só mostra números gerais e só a partir de ${rel.minimo_para_mostrar} alunos vinculados. Nenhum nome ou dado de saúde é exibido.</p>
    <section class="cartao" style="max-width:560px"><h2>Verificar declaração de doação</h2>
      <p class="muted">O aluno gera a declaração no app (Perfil › Meus dados). Digite o código para conferir se é verdadeira.</p>
      <form id="f-declaracao" class="linha-flex"><input name="codigo" placeholder="DEC-XXXXXX" style="flex:1;min-width:180px;text-transform:uppercase" required />
      <button class="btn btn-claro" type="submit">Verificar</button><p class="erro hidden" style="width:100%"></p></form>
      <div id="declaracao-ok"></div></section>`;
}
function ligarAlunos(corpo) {
  aoEnviar($("#f-declaracao", corpo), async (d) => {
    const r = await api(`/api/publico/declaracoes/${encodeURIComponent(d.codigo.toUpperCase())}`);
    $("#declaracao-ok", corpo).innerHTML = `<p class="sucesso">✅ Declaração ${esc(r.codigo)} é verdadeira: ${esc(r.nome)}, ${r.total_doacoes} doação(ões)
      verificada(s), última em ${dataBR(r.ultima_doacao)}. Emitida em ${dataBR(r.emitida_em)} para ${esc(r.instituicao)}.</p>`;
  });
}
