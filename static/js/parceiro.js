/*
 * HemoFlow 2.0 — painel do parceiro (comércio, cursinho, pré-Enem, faculdade…)
 *   Validar cupom ... digita o código que o doador mostra (uso único)
 *   Ofertas ......... cadastra ofertas; elas aparecem no app depois da aprovação do admin
 *   Alunos .......... (cursinhos e faculdades) código para os alunos e relatório só com números gerais
 */
import { api, $, esc, aviso, aoEnviar, dataBR, TIPO_PARCEIRO } from "./nucleo.js";
import { montarPainel } from "./painel.js";

let painel;
const STATUS = { PENDENTE: "Aguardando aprovação", APROVADA: "No ar", RECUSADA: "Recusada" };

export async function montar(raiz, usuario, ctx) {
  const inicial = await api("/api/parceiro/painel");
  const itens = [
    { id: "validar", titulo: "Validar cupom", icone: "ticket", tela: telaValidar, depois: ligarValidar },
    { id: "ofertas", titulo: "Ofertas", icone: "loja", tela: telaOfertas, depois: ligarOfertas },
  ];
  if (inicial.parceiro.codigo_alunos) itens.push({ id: "alunos", titulo: "Alunos", icone: "pessoa", tela: telaAlunos });
  painel = montarPainel(raiz, { subtitulo: inicial.parceiro.nome, usuario, ctx, itens });
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
      .map((o) => `<li><div class="principal"><strong>${esc(o.titulo)}</strong><span class="muted pequeno">${[o.descricao && esc(o.descricao), o.validade && "até " + dataBR(o.validade), `${o.usados} uso(s)`].filter(Boolean).join(" · ")}</span></div>
        <span class="selo ${o.status === "APROVADA" ? "ok" : o.status === "RECUSADA" ? "critico" : "atencao"}">${STATUS[o.status]}</span></li>`)
      .join("")}</ul>` : '<p class="vazio">Nenhuma oferta ainda.</p>'}</section>
    <section class="cartao"><h2>Nova oferta</h2>
      <form id="f-oferta"><label>Título <input name="titulo" maxlength="120" required placeholder="Ex.: 10% de desconto para doadores" /></label>
      <label>Detalhes <textarea name="descricao" maxlength="400" placeholder="Como usar, regras, endereço…"></textarea></label>
      <label>Válida até (opcional) <input name="validade" type="date" /></label>
      <p class="erro hidden"></p><button class="btn btn-primario cheio" type="submit">Enviar para aprovação</button></form>
      <p class="muted pequeno">Tipo de parceiro: ${esc(TIPO_PARCEIRO[r.parceiro.tipo] || r.parceiro.tipo)}. Só doadores com doação verificada nos últimos 6 meses conseguem gerar o cupom.</p></section></div>`;
}
function ligarOfertas(corpo) {
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
    <p class="muted pequeno">Por privacidade, o relatório só mostra números gerais e só a partir de ${rel.minimo_para_mostrar} alunos vinculados. Nenhum nome ou dado de saúde é exibido.</p>`;
}
