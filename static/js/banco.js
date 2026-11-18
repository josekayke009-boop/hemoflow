/*
 * HemoFlow 2.0 — painel do banco de sangue
 *   Estoque ...... termômetro dos 8 tipos por unidade (+1 / −1, ajuste e limites)
 *   Convocar ..... o sistema sugere quantos doadores chamar; a equipe revisa e envia
 *   Agenda ....... horários do dia, quem agendou, marcar falta e abrir novos horários
 *   Confirmar .... digita o código do doador no balcão -> doação verificada
 *   Resultados ... convocados, comparecimento e taxa de retorno
 */
import { api, $, $$, esc, aviso, erro, janela, fecharJanela, aoEnviar, dataBR, hora, hojeISO, NIVEL_TEXTO, TIPOS, termometro } from "./nucleo.js";
import { montarPainel } from "./painel.js";

let dados = null; // resposta de /api/banco/painel
let unidadeId = null;
let painel;

export async function montar(raiz, usuario, ctx) {
  dados = await api("/api/banco/painel");
  unidadeId = dados.unidades[0]?.id;
  painel = montarPainel(raiz, {
    subtitulo: dados.banco.nome,
    usuario,
    ctx,
    itens: [
      { id: "estoque", titulo: "Estoque", icone: "gota", tela: telaEstoque, depois: ligarEstoque },
      { id: "convocar", titulo: "Convocar doadores", icone: "megafone", tela: telaConvocar, depois: ligarConvocar },
      { id: "agenda", titulo: "Agenda", icone: "agenda", tela: telaAgenda, depois: ligarAgenda },
      { id: "confirmar", titulo: "Confirmar doação", icone: "check", tela: telaConfirmar, depois: ligarConfirmar },
      { id: "resultados", titulo: "Resultados", icone: "grafico", tela: telaResultados },
    ],
  });
}

const unidade = () => dados.unidades.find((u) => u.id === unidadeId);
function seletorUnidade() {
  if (dados.unidades.length < 2) return `<p class="muted">${esc(unidade()?.nome || "Nenhuma unidade cadastrada")}</p>`;
  return `<label style="max-width:420px">Unidade <select data-unidade>${dados.unidades
    .map((u) => `<option value="${u.id}"${u.id === unidadeId ? " selected" : ""}>${esc(u.nome)}</option>`)
    .join("")}</select></label>`;
}
function ligarSeletor(corpo, telaId) {
  $("[data-unidade]", corpo)?.addEventListener("change", (ev) => {
    unidadeId = Number(ev.target.value);
    painel.ir(telaId);
  });
}

/* ---- ESTOQUE ---------------------------------------------------------------- */
async function telaEstoque() {
  dados = await api("/api/banco/painel");
  const u = unidade();
  if (!u) return '<p class="vazio">Este banco ainda não tem unidades. Fale com a equipe HemoFlow.</p>';
  const criticos = u.termometro.filter((t) => t.nivel === "CRITICO");
  return `${seletorUnidade()}
    ${criticos.length ? `<div class="aviso-suave"><strong>Atenção:</strong> ${criticos.map((t) => esc(t.tipo)).join(", ")} em nível crítico. <button type="button" class="btn btn-pequeno btn-primario" data-ir-convocar="${esc(criticos[0].tipo)}">Convocar doadores</button></div>` : ""}
    <section class="cartao"><div class="cartao-titulo"><h2>Bolsas por tipo</h2><span class="espaco"></span><span class="muted pequeno">Toque no tipo para ajustar ou mudar os limites</span></div>
    <div class="estoque-grade">${u.termometro
      .map(
        (t) => `<div class="estoque-item cartao" style="margin:0">
          <button type="button" data-ajustar="${esc(t.tipo)}" style="border:0;background:none;width:100%" aria-label="Ajustar ${esc(t.tipo)}">${termometro(t.nivel, t.tipo, false)}</button>
          <div class="qtd">${t.quantidade}</div><span class="selo ${t.nivel}">${NIVEL_TEXTO[t.nivel]}</span>
          <div class="muted pequeno" style="margin-top:4px">crítico ≤ ${t.limite_critico} · atenção ≤ ${t.limite_atencao}${t.editado_admin ? "<br>editado pelo admin" : ""}</div>
          <div class="botoes"><button type="button" data-mov="SAIDA" data-tipo="${esc(t.tipo)}" aria-label="Saída de 1 bolsa ${esc(t.tipo)}">−</button>
          <button type="button" data-mov="ENTRADA" data-tipo="${esc(t.tipo)}" aria-label="Entrada de 1 bolsa ${esc(t.tipo)}">+</button></div></div>`,
      )
      .join("")}</div></section>
    <section class="cartao"><h2>Últimos movimentos</h2>
    ${u.movimentos.length ? `<div class="tabela-wrap"><table><thead><tr><th>Quando</th><th>Tipo</th><th>Movimento</th><th>Qtd.</th><th>Motivo</th></tr></thead><tbody>${u.movimentos
      .map((m) => `<tr><td>${dataBR(m.criado_em)} ${hora(m.criado_em)}</td><td>${esc(m.tipo_sanguineo)}</td><td>${esc(m.movimento)}</td><td>${m.quantidade}</td><td>${esc(m.motivo || "")}</td></tr>`)
      .join("")}</tbody></table></div>` : '<p class="vazio">Nenhum movimento ainda.</p>'}</section>`;
}
function ligarEstoque(corpo) {
  ligarSeletor(corpo, "estoque");
  corpo.addEventListener("click", async (ev) => {
    const b = ev.target.closest("button");
    if (!b) return;
    if (b.dataset.irConvocar) {
      tipoConvocar = b.dataset.irConvocar;
      return painel.ir("convocar");
    }
    if (b.dataset.mov) {
      b.disabled = true;
      try {
        const r = await api("/api/banco/estoque/movimento", { unidade_id: unidadeId, tipo_sanguineo: b.dataset.tipo, movimento: b.dataset.mov, quantidade: 1, motivo: b.dataset.mov === "ENTRADA" ? "Entrada rápida" : "Saída rápida" });
        aviso(r.mensagem);
        painel.ir("estoque");
      } catch (e) {
        b.disabled = false;
        erro(e);
      }
    }
    if (b.dataset.ajustar) abrirAjuste(b.dataset.ajustar);
  });
}
function abrirAjuste(tipo) {
  const t = unidade().termometro.find((x) => x.tipo === tipo);
  const c = janela(`Estoque ${tipo}`, `
    <form id="f-mov"><h3>Movimento</h3><div class="duas">
      <label>Tipo de movimento <select name="movimento"><option value="ENTRADA">Entrada</option><option value="SAIDA">Saída</option><option value="AJUSTE">Ajuste (contagem)</option></select></label>
      <label>Quantidade <input name="quantidade" type="number" min="0" value="1" required /></label></div>
      <label>Motivo <input name="motivo" placeholder="Ex.: coleta do dia, transfusão, contagem" /></label>
      <p class="erro hidden"></p><button class="btn btn-primario cheio" type="submit">Registrar</button></form>
    <form id="f-lim" style="margin-top:20px"><h3>Limites do termômetro</h3><div class="duas">
      <label>Crítico até <input name="limite_critico" type="number" min="0" value="${t.limite_critico}" /></label>
      <label>Atenção até <input name="limite_atencao" type="number" min="0" value="${t.limite_atencao}" /></label></div>
      <p class="erro hidden"></p><button class="btn btn-claro cheio" type="submit">Salvar limites</button></form>`);
  aoEnviar($("#f-mov", c), async (d) => {
    aviso((await api("/api/banco/estoque/movimento", { ...d, quantidade: Number(d.quantidade), unidade_id: unidadeId, tipo_sanguineo: tipo })).mensagem);
    fecharJanela();
    painel.ir("estoque");
  });
  aoEnviar($("#f-lim", c), async (d) => {
    aviso((await api("/api/banco/estoque/limites", { limite_critico: Number(d.limite_critico), limite_atencao: Number(d.limite_atencao), unidade_id: unidadeId, tipo_sanguineo: tipo })).mensagem);
    fecharJanela();
    painel.ir("estoque");
  });
}

/* ---- CONVOCAR --------------------------------------------------------------- */
let tipoConvocar = null;
async function telaConvocar() {
  const u = unidade();
  if (!u) return '<p class="vazio">Sem unidades.</p>';
  // Começa pelo tipo mais grave: crítico antes de atenção; depois, o que está mais abaixo do limite.
  const ordem = { CRITICO: 0, ATENCAO: 1, NORMAL: 2 };
  if (!tipoConvocar)
    tipoConvocar = ([...u.termometro].sort((a, b) => ordem[a.nivel] - ordem[b.nivel] || a.quantidade - a.limite_atencao - (b.quantidade - b.limite_atencao))[0] || {}).tipo || "O-";
  const lista = await api("/api/banco/convocacoes");
  return `${seletorUnidade()}
    <section class="cartao"><h2>Qual tipo precisa de doadores?</h2>
      <div class="chips" role="radiogroup">${u.termometro
        .map((t) => `<button type="button" class="chip${t.tipo === tipoConvocar ? " ativo" : ""}" data-tipo-conv="${esc(t.tipo)}" role="radio" aria-checked="${t.tipo === tipoConvocar}">${esc(t.tipo)} · <span class="selo ${t.nivel}" style="padding:2px 8px">${NIVEL_TEXTO[t.nivel]}</span></button>`)
        .join("")}</div>
      <div id="sugestao" style="margin-top:16px"><p class="vazio">Calculando sugestão…</p></div></section>
    <section class="cartao"><h2>Convocações enviadas</h2>
    ${lista.length ? `<div class="tabela-wrap"><table><thead><tr><th>Data</th><th>Tipo</th><th>Unidade</th><th>Convocados</th><th>Agendaram</th><th>Doaram</th></tr></thead><tbody>${lista
      .map((c) => `<tr><td>${dataBR(c.criado_em)}</td><td><strong>${esc(c.tipo_sanguineo)}</strong></td><td>${esc(c.unidade)}</td><td>${c.convocados}</td><td>${c.agendaram}</td><td>${c.doaram}</td></tr>`)
      .join("")}</tbody></table></div>` : '<p class="vazio">Nenhuma convocação ainda.</p>'}</section>`;
}
async function carregarSugestao(corpo) {
  const caixa = $("#sugestao", corpo);
  try {
    const s = await api(`/api/banco/convocacao/sugestao?unidade_id=${unidadeId}&tipo=${encodeURIComponent(tipoConvocar)}`);
    caixa.innerHTML = `
      <div class="grade-numeros">
        <div class="numero"><strong>${s.quantidade}</strong><span>bolsas de ${esc(s.tipo)} hoje</span></div>
        <div class="numero"><strong>${s.faltam}</strong><span>faltam para sair da atenção</span></div>
        <div class="numero"><strong>${s.aptos}</strong><span>doadores aptos em ${esc(s.regiao)} (de ${s.cadastrados_regiao})</span></div>
        <div class="numero"><strong>${s.vagas_livres}</strong><span>vagas livres em 7 dias</span></div>
      </div>
      <p>Doadores compatíveis: <strong>${s.compativeis.map(esc).join(", ")}</strong>. Sugestão do HemoFlow: convocar <strong>${s.convocar}</strong> (considera que cerca de metade comparece).</p>
      ${s.convocar ? `<form id="f-conv">
        <label>Quantos convocar <input name="quantidade" type="number" min="1" max="${Math.max(1, Math.min(s.aptos, s.vagas_livres))}" value="${s.convocar}" required /></label>
        <label>Mensagem para os doadores <textarea name="mensagem" maxlength="500" required>${esc(s.mensagem_sugerida || "")}</textarea></label>
        <p class="erro hidden"></p><button class="btn btn-primario" type="submit">Enviar convocação</button></form>`
        : `<p class="aviso-suave">${s.faltam ? (s.aptos ? "Abra mais horários na Agenda para poder convocar." : "Não há doadores aptos deste tipo na região agora.") : "O estoque deste tipo não precisa de convocação agora."}</p>`}`;
    const f = $("#f-conv", caixa);
    if (f)
      aoEnviar(f, async (d) => {
        const r = await api("/api/banco/convocacoes", { unidade_id: unidadeId, tipo_sanguineo: tipoConvocar, mensagem: d.mensagem, quantidade: Number(d.quantidade) });
        aviso(r.mensagem);
        painel.ir("convocar");
      });
  } catch (e) {
    caixa.innerHTML = `<p class="erro">${esc(e.message)}</p>`;
  }
}
function ligarConvocar(corpo) {
  ligarSeletor(corpo, "convocar");
  carregarSugestao(corpo);
  $$("[data-tipo-conv]", corpo).forEach((b) =>
    b.addEventListener("click", () => {
      tipoConvocar = b.dataset.tipoConv;
      $$("[data-tipo-conv]", corpo).forEach((x) => {
        x.classList.toggle("ativo", x === b);
        x.setAttribute("aria-checked", x === b);
      });
      carregarSugestao(corpo);
    }),
  );
}

/* ---- AGENDA ------------------------------------------------------------------ */
let diaAgenda = hojeISO();
const STATUS = { AGENDADO: "Agendado", COMPARECEU: "Doou", FALTOU: "Faltou" };
async function telaAgenda() {
  if (!unidade()) return '<p class="vazio">Sem unidades.</p>';
  const r = await api(`/api/banco/agenda?unidade_id=${unidadeId}&dia=${diaAgenda}`);
  const vagas = r.vagas.length
    ? r.vagas
        .map(
          (v) => `<li style="align-items:flex-start"><strong style="min-width:60px;font-size:1.1rem">${hora(v.inicio)}</strong>
        <div class="principal">${v.agendados.length ? v.agendados
          .map((a) => `<div class="linha-flex" style="margin-bottom:6px"><span><strong>${esc(a.nome)}</strong> · ${esc(a.tipo_sanguineo)} · código ${esc(a.codigo)} ${a.origem === "CONVOCACAO" ? '<span class="selo">convocado</span>' : ""}</span>
            <span class="selo ${a.status === "COMPARECEU" ? "ok" : a.status === "FALTOU" ? "critico" : ""}">${STATUS[a.status] || esc(a.status)}</span>
            ${a.status === "AGENDADO" ? `<button type="button" class="btn btn-pequeno btn-claro" data-faltou="${a.id}">Marcar falta</button>` : ""}</div>`)
          .join("") : '<span class="muted">Ninguém agendado</span>'}</div>
        <span class="selo">${v.livres} livre${v.livres === 1 ? "" : "s"} de ${v.capacidade}</span></li>`,
        )
        .join("")
    : '<li class="vazio">Nenhum horário aberto neste dia.</li>';
  return `${seletorUnidade()}
    <div class="linha-flex" style="margin-bottom:12px"><label style="margin:0">Dia <input type="date" id="dia-agenda" value="${diaAgenda}" /></label></div>
    <section class="cartao"><h2>Horários de ${dataBR(diaAgenda)}</h2><ul class="lista">${vagas}</ul></section>
    <section class="cartao"><h2>Abrir horários</h2>
      <form id="f-vagas"><div class="duas"><label>Dia <input name="dia" type="date" min="${hojeISO()}" value="${diaAgenda >= hojeISO() ? diaAgenda : hojeISO()}" required /></label>
      <label>Doadores por horário <input name="capacidade" type="number" min="1" max="100" value="4" /></label></div>
      <label>Horários (separados por vírgula) <input name="horarios" value="08:00, 09:00, 10:00, 11:00, 14:00, 15:00" required /></label>
      <p class="erro hidden"></p><button class="btn btn-primario" type="submit">Abrir horários</button></form></section>`;
}
function ligarAgenda(corpo) {
  ligarSeletor(corpo, "agenda");
  $("#dia-agenda", corpo).addEventListener("change", (ev) => {
    diaAgenda = ev.target.value || hojeISO();
    painel.ir("agenda");
  });
  corpo.addEventListener("click", async (ev) => {
    const b = ev.target.closest("[data-faltou]");
    if (!b) return;
    try {
      aviso((await api(`/api/banco/agendamentos/${b.dataset.faltou}/faltou`, {})).mensagem);
      painel.ir("agenda");
    } catch (e) {
      erro(e);
    }
  });
  aoEnviar($("#f-vagas", corpo), async (d) => {
    const horarios = d.horarios.split(/[,;\s]+/).filter(Boolean);
    aviso((await api("/api/banco/vagas", { unidade_id: unidadeId, dia: d.dia, capacidade: Number(d.capacidade), horarios })).mensagem);
    diaAgenda = d.dia;
    painel.ir("agenda");
  });
}

/* ---- CONFIRMAR DOAÇÃO -------------------------------------------------------- */
async function telaConfirmar() {
  return `<section class="cartao" style="max-width:520px">
    <h2>Doador no balcão</h2><p class="muted">Peça o código de 6 dígitos que aparece no app do doador. Confirme depois da triagem e da coleta.</p>
    <form id="f-confirmar"><label>Código <input name="codigo" inputmode="numeric" maxlength="6" autocomplete="off" class="codigo-grande" style="min-height:76px" required /></label>
    <p class="erro hidden"></p><button class="btn btn-ok cheio" type="submit">Confirmar doação</button></form>
    <div id="confirmado"></div></section>`;
}
function ligarConfirmar(corpo) {
  $("#f-confirmar input", corpo).focus();
  aoEnviar($("#f-confirmar", corpo), async (d, form) => {
    const r = await api("/api/banco/confirmar", { codigo: d.codigo });
    $("#confirmado", corpo).innerHTML = `<p class="sucesso" style="margin-top:14px">✅ ${esc(r.mensagem)}</p>`;
    form.reset();
    aviso("Doação verificada. Obrigado!");
  });
}

/* ---- RESULTADOS -------------------------------------------------------------- */
async function telaResultados() {
  const m = await api("/api/banco/metricas");
  const pct = (a, b) => (b ? Math.round((100 * a) / b) + "%" : "—");
  return `<p class="muted">Últimos ${m.periodo_dias} dias.</p>
    <div class="grade-numeros">
      <div class="numero"><strong>${m.convocados}</strong><span>doadores convocados</span></div>
      <div class="numero"><strong>${pct(m.agendaram, m.convocados)}</strong><span>dos convocados agendaram</span></div>
      <div class="numero"><strong>${m.agendamentos}</strong><span>agendamentos (${m.espontaneos} espontâneos)</span></div>
      <div class="numero"><strong>${pct(m.compareceram, m.compareceram + m.faltaram)}</strong><span>de comparecimento (${m.faltaram} faltas)</span></div>
      <div class="numero"><strong>${m.taxa_retorno}%</strong><span>dos doadores voltaram a doar (${m.voltaram} de ${m.doadores_unicos})</span></div>
    </div>
    <section class="cartao"><h2>Doações verificadas por tipo</h2>
    ${m.por_tipo.length ? `<ul class="lista">${m.por_tipo.map((t) => `<li><strong style="min-width:48px">${esc(t.tipo)}</strong><div class="principal"><div class="progresso"><span style="width:${Math.round((100 * t.doacoes) / m.por_tipo[0].doacoes)}%;background:var(--marca)"></span></div></div><span>${t.doacoes}</span></li>`).join("")}</ul>` : '<p class="vazio">Sem doações verificadas no período.</p>'}</section>
    <p class="muted pequeno">Tipos: ${TIPOS.join(" · ")}. Os dados de cada doador ficam protegidos; aqui aparecem só números gerais.</p>`;
}
