/*
 * HemoFlow 2.0 — painel do administrador (equipe HemoFlow: acesso total)
 *   Resumo ...... números gerais e pendências (bancos, parceiros e ofertas para aprovar)
 *   Bancos ...... cadastro de bancos de sangue e unidades; "entrar como" o banco
 *   Parceiros ... comércios, cursinhos, pré-Enem, faculdades…; aprovar ofertas; "entrar como"
 *   Doadores .... busca, edição (fica registrado como "editado pelo admin") e "entrar como"
 *   Contas ...... criar logins de admin, banco e parceiro; bloquear/reativar
 * Toda ação do admin vai para a auditoria no servidor.
 */
import { api, $, $$, esc, aviso, erro, janela, fecharJanela, aoEnviar, dataBR, opcoesUF, TIPOS, TIPO_PARCEIRO } from "./nucleo.js";
import { montarPainel } from "./painel.js";
import { telaAjuda, ligarAjuda } from "./ajuda.js";

let painel, ctxApp;
const SELO = { ATIVO: "ok", PENDENTE: "atencao", SUSPENSO: "critico", INATIVO: "", BLOQUEADO: "critico", APROVADA: "ok", RECUSADA: "critico" };
const selo = (s) => `<span class="selo ${SELO[s] ?? ""}">${esc(s.toLowerCase())}</span>`;

export async function montar(raiz, usuario, ctx) {
  ctxApp = ctx;
  painel = montarPainel(raiz, {
    subtitulo: "Administração",
    usuario,
    ctx,
    itens: [
      { id: "resumo", titulo: "Resumo", icone: "grafico", tela: telaResumo, depois: ligarAcoes },
      { id: "bancos", titulo: "Bancos de sangue", icone: "predio", tela: telaBancos, depois: ligarAcoes },
      { id: "parceiros", titulo: "Parceiros", icone: "loja", tela: telaParceiros, depois: ligarAcoes },
      { id: "doadores", titulo: "Doadores", icone: "gota", tela: telaDoadores, depois: ligarDoadores },
      { id: "contas", titulo: "Contas de acesso", icone: "chave", tela: telaContas, depois: ligarContas },
      { id: "ajuda", titulo: "Ajuda", icone: "ajuda", tela: async () => telaAjuda("ADMINISTRADOR"), depois: ligarAjuda },
    ],
  });
}

/* ---- RESUMO ------------------------------------------------------------------ */
async function telaResumo() {
  const r = await api("/api/admin/resumo");
  const p = r.pendentes;
  const pend = [
    ...p.bancos.map((b) => `<li><div class="principal"><strong>${esc(b.nome)}</strong><span class="muted pequeno">Banco de sangue · ${esc(b.cidade)}/${esc(b.uf)}</span></div><button class="btn btn-pequeno btn-claro" data-ir="bancos">Revisar</button></li>`),
    ...p.parceiros.map((x) => `<li><div class="principal"><strong>${esc(x.nome)}</strong><span class="muted pequeno">${esc(TIPO_PARCEIRO[x.tipo] || x.tipo)} · ${esc(x.cidade)}/${esc(x.uf)}</span></div><button class="btn btn-pequeno btn-claro" data-ir="parceiros">Revisar</button></li>`),
    ...p.ofertas.map((o) => `<li><div class="principal"><strong>${esc(o.titulo)}</strong><span class="muted pequeno">Oferta de ${esc(o.parceiro)}${o.descricao ? " · " + esc(o.descricao) : ""}</span></div>
      <button class="btn btn-pequeno btn-ok" data-oferta="${o.id}" data-status="APROVADA">Aprovar</button><button class="btn btn-pequeno btn-perigo" data-oferta="${o.id}" data-status="RECUSADA">Recusar</button></li>`),
  ];
  return `<div class="grade-numeros">
      <div class="numero"><strong>${r.doadores}</strong><span>doadores com conta</span></div>
      <div class="numero"><strong>${r.bancos}</strong><span>bancos de sangue ativos</span></div>
      <div class="numero"><strong>${r.parceiros}</strong><span>parceiros ativos</span></div>
      <div class="numero"><strong>${r.doacoes_verificadas}</strong><span>doações verificadas</span></div>
      <div class="numero"><strong>${r.convocacoes}</strong><span>convocações</span></div>
      <div class="numero"><strong>${r.cupons_usados}</strong><span>cupons usados</span></div></div>
    <section class="cartao"><h2>Pendências</h2>${pend.length ? `<ul class="lista">${pend.join("")}</ul>` : '<p class="vazio">Nada pendente. 🎉</p>'}</section>`;
}

/* ---- BANCOS ------------------------------------------------------------------ */
let cacheBancos = [];
async function telaBancos() {
  const r = await api("/api/admin/bancos");
  cacheBancos = r.bancos;
  return `<div class="linha-flex" style="margin-bottom:16px"><button class="btn btn-primario" data-novo-banco>+ Novo banco de sangue</button></div>
    <section class="cartao"><div class="tabela-wrap"><table><thead><tr><th>Banco</th><th>Cidade</th><th>Unidades</th><th>Situação</th><th></th></tr></thead><tbody>${r.bancos
      .map((b) => `<tr><td><strong>${esc(b.nome)}</strong><br><span class="muted pequeno">${esc(b.email || "")} ${esc(b.telefone || "")}</span></td><td>${esc(b.cidade)}/${esc(b.uf)}</td>
        <td>${b.unidades.map((u) => esc(u.nome)).join("<br>")}</td><td>${selo(b.status)}</td>
        <td><div class="linha-flex"><button class="btn btn-pequeno btn-claro" data-editar-banco="${b.id}">Editar</button><button class="btn btn-pequeno btn-claro" data-unidade-banco="${b.id}">+ Unidade</button>
        <button class="btn btn-pequeno btn-claro" data-como="BANCO" data-id="${b.id}">Entrar como</button></div></td></tr>`)
      .join("")}</tbody></table></div></section>
    <section class="cartao"><h2>Hemocentros públicos (só informação para o doador)</h2><ul class="lista">${r.publicos
      .map((u) => `<li><div class="principal"><strong>${esc(u.nome)}</strong><span class="muted pequeno">${esc(u.endereco || "")} · ${esc(u.cidade)}/${esc(u.uf)} · ${esc(u.horario || "")}</span></div>${u.ativo ? "" : selo("INATIVO")}</li>`)
      .join("")}</ul><button class="btn btn-claro" data-unidade-banco="">+ Hemocentro público</button></section>`;
}
function formBanco(b = {}) {
  const c = janela(b.id ? "Editar banco de sangue" : "Novo banco de sangue", `<form id="f-banco">
    <label>Nome <input name="nome" value="${esc(b.nome || "")}" required /></label>
    <div class="duas"><label>Cidade <input name="cidade" value="${esc(b.cidade || "")}" required /></label><label>UF <select name="uf">${opcoesUF(b.uf || "PE")}</select></label></div>
    <div class="duas"><label>CNPJ <input name="cnpj" value="${esc(b.cnpj || "")}" inputmode="numeric" /></label><label>Telefone <input name="telefone" value="${esc(b.telefone || "")}" /></label></div>
    <label>E-mail de contato <input name="email" type="email" value="${esc(b.email || "")}" /></label>
    ${b.id ? "" : `<label>Endereço da primeira unidade <input name="endereco" /></label><div class="duas"><label>Bairro <input name="bairro" /></label><label>Horário <input name="horario" placeholder="Seg a sex, 7h às 17h" /></label></div>`}
    <label>Situação <select name="status">${["ATIVO", "PENDENTE", "SUSPENSO"].map((s) => `<option${s === (b.status || "ATIVO") ? " selected" : ""}>${s}</option>`).join("")}</select></label>
    <p class="erro hidden"></p><button class="btn btn-primario cheio" type="submit">Salvar</button></form>`);
  aoEnviar($("#f-banco", c), async (d) => {
    aviso((await api("/api/admin/bancos", { ...d, id: b.id || null })).mensagem);
    fecharJanela();
    painel.ir("bancos");
  });
}
function formUnidade(bancoId) {
  const c = janela(bancoId ? "Nova unidade do banco" : "Novo hemocentro público", `<form id="f-unidade">
    <label>Nome da unidade <input name="nome" required /></label>
    <label>Endereço <input name="endereco" /></label>
    <div class="duas"><label>Bairro <input name="bairro" /></label><label>Horário <input name="horario" /></label></div>
    <div class="duas"><label>Cidade <input name="cidade" required /></label><label>UF <select name="uf">${opcoesUF("PE")}</select></label></div>
    <p class="erro hidden"></p><button class="btn btn-primario cheio" type="submit">Salvar</button></form>`);
  aoEnviar($("#f-unidade", c), async (d) => {
    aviso((await api("/api/admin/unidades", { ...d, banco_id: bancoId || null, tipo: bancoId ? "BANCO" : "PUBLICO", ativo: true })).mensagem);
    fecharJanela();
    painel.ir("bancos");
  });
}

/* ---- PARCEIROS --------------------------------------------------------------- */
let cacheParceiros = [];
async function telaParceiros() {
  const r = await api("/api/admin/parceiros");
  cacheParceiros = r.parceiros;
  return `<div class="linha-flex" style="margin-bottom:16px"><button class="btn btn-primario" data-novo-parceiro>+ Novo parceiro</button></div>
    <section class="cartao"><h2>Parceiros</h2><div class="tabela-wrap"><table><thead><tr><th>Parceiro</th><th>Tipo</th><th>Cidade</th><th>Código alunos</th><th>Situação</th><th></th></tr></thead><tbody>${r.parceiros
      .map((p) => `<tr><td><strong>${esc(p.nome)}</strong></td><td>${esc(TIPO_PARCEIRO[p.tipo] || p.tipo)}</td><td>${esc(p.cidade)}/${esc(p.uf)}</td><td>${esc(p.codigo_alunos || "—")}</td><td>${selo(p.status)}</td>
        <td><div class="linha-flex"><button class="btn btn-pequeno btn-claro" data-editar-parceiro="${p.id}">Editar</button><button class="btn btn-pequeno btn-claro" data-como="PARCEIRO" data-id="${p.id}">Entrar como</button></div></td></tr>`)
      .join("")}</tbody></table></div></section>
    <section class="cartao"><h2>Ofertas</h2><div class="tabela-wrap"><table><thead><tr><th>Oferta</th><th>Parceiro</th><th>Validade</th><th>Situação</th><th></th></tr></thead><tbody>${r.ofertas
      .map((o) => `<tr><td><strong>${esc(o.titulo)}</strong>${o.destaque ? ' <span class="selo">destaque</span>' : ""}<br><span class="muted pequeno">${esc(o.descricao || "")}</span></td><td>${esc(o.parceiro)}</td><td>${o.validade ? dataBR(String(o.validade)) : "—"}</td><td>${selo(o.status)}</td>
        <td><div class="linha-flex">${o.status !== "APROVADA" ? `<button class="btn btn-pequeno btn-ok" data-oferta="${o.id}" data-status="APROVADA">Aprovar</button>` : `<button class="btn btn-pequeno btn-claro" data-oferta="${o.id}" data-status="APROVADA" data-destaque="${o.destaque ? "" : "1"}">${o.destaque ? "Tirar destaque" : "Destacar"}</button>`}
        ${o.status !== "RECUSADA" ? `<button class="btn btn-pequeno btn-perigo" data-oferta="${o.id}" data-status="RECUSADA">Recusar</button>` : ""}</div></td></tr>`)
      .join("")}</tbody></table></div></section>`;
}
function formParceiro(p = {}) {
  const c = janela(p.id ? "Editar parceiro" : "Novo parceiro", `<form id="f-parceiro">
    <label>Nome <input name="nome" value="${esc(p.nome || "")}" required /></label>
    <label>Tipo <select name="tipo">${Object.entries(TIPO_PARCEIRO).map(([k, v]) => `<option value="${k}"${k === p.tipo ? " selected" : ""}>${v}</option>`).join("")}</select></label>
    <div class="duas"><label>Cidade <input name="cidade" value="${esc(p.cidade || "")}" required /></label><label>UF <select name="uf">${opcoesUF(p.uf || "PE")}</select></label></div>
    <div class="duas"><label>CNPJ <input name="cnpj" value="${esc(p.cnpj || "")}" inputmode="numeric" /></label><label>Código dos alunos <input name="codigo_alunos" value="${esc(p.codigo_alunos || "")}" placeholder="gerado se vazio" /></label></div>
    <label>Endereço <input name="endereco" value="${esc(p.endereco || "")}" /></label>
    <label>Situação <select name="status">${["ATIVO", "PENDENTE", "SUSPENSO"].map((s) => `<option${s === (p.status || "ATIVO") ? " selected" : ""}>${s}</option>`).join("")}</select></label>
    <p class="muted pequeno">Comércios não usam código de alunos. Cursinhos, pré-Enem e faculdades recebem um código para os alunos.</p>
    <p class="erro hidden"></p><button class="btn btn-primario cheio" type="submit">Salvar</button></form>`);
  aoEnviar($("#f-parceiro", c), async (d) => {
    if (d.tipo === "COMERCIO") d.codigo_alunos = "";
    const r = await api("/api/admin/parceiros", { ...d, id: p.id || null });
    aviso(r.mensagem + (r.codigo_alunos ? ` Código dos alunos: ${r.codigo_alunos}` : ""));
    fecharJanela();
    painel.ir("parceiros");
  });
}

/* ---- AÇÕES COMUNS (aprovar oferta, entrar como, abrir formulários) ------------ */
function ligarAcoes(corpo) {
  corpo.addEventListener("click", async (ev) => {
    const b = ev.target.closest("button");
    if (!b) return;
    const ds = b.dataset;
    try {
      if (ds.ir) return painel.ir(ds.ir);
      if ("novoBanco" in ds) return formBanco();
      if (ds.editarBanco) return formBanco(cacheBancos.find((x) => x.id === Number(ds.editarBanco)));
      if ("unidadeBanco" in ds) return formUnidade(Number(ds.unidadeBanco) || null);
      if ("novoParceiro" in ds) return formParceiro();
      if (ds.editarParceiro) return formParceiro(cacheParceiros.find((x) => x.id === Number(ds.editarParceiro)));
      if (ds.oferta) {
        aviso((await api(`/api/admin/ofertas/${ds.oferta}/status`, { status: ds.status, destaque: !!ds.destaque })).mensagem);
        return painel.ir(painel.atual() === "Resumo" ? "resumo" : "parceiros");
      }
      if (ds.como) {
        aviso((await api("/api/admin/entrar-como", { papel: ds.como, id: Number(ds.id) })).mensagem);
        return ctxApp.recarregar();
      }
    } catch (e) {
      erro(e);
    }
  });
}

/* ---- DOADORES ---------------------------------------------------------------- */
let buscaDoador = "";
let cacheDoadores = [];
async function telaDoadores() {
  cacheDoadores = await api(`/api/admin/doadores?q=${encodeURIComponent(buscaDoador)}`);
  return `<form id="f-busca" class="linha-flex" style="margin-bottom:16px"><input name="q" value="${esc(buscaDoador)}" placeholder="Buscar por nome, e-mail, cidade ou CPF" style="flex:1;min-width:220px" />
      <button class="btn btn-claro" type="submit">Buscar</button></form>
    <section class="cartao"><div class="tabela-wrap"><table><thead><tr><th>Doador</th><th>Tipo</th><th>Cidade</th><th>Doações</th><th>Avisos</th><th>Situação</th><th></th></tr></thead><tbody>${
      cacheDoadores.length
        ? cacheDoadores
            .map((d) => `<tr><td><strong>${esc(d.nome)}</strong><br><span class="muted pequeno">${esc(d.email || "")} · CPF ${esc(d.cpf_mascarado)}</span></td><td>${esc(d.tipo_sanguineo)}</td><td>${esc(d.cidade)}/${esc(d.uf)}</td>
          <td>${d.verificadas}</td><td>${d.consentimento_convocacao ? "sim" : "não"}</td><td>${selo(d.status)}</td>
          <td><div class="linha-flex"><button class="btn btn-pequeno btn-claro" data-editar-doador="${d.id}">Editar</button>${d.usuario_id ? `<button class="btn btn-pequeno btn-claro" data-como="DOADOR" data-id="${d.id}">Entrar como</button>` : ""}</div></td></tr>`)
            .join("")
        : '<tr><td colspan="7" class="vazio">Nenhum doador encontrado.</td></tr>'
    }</tbody></table></div><p class="muted pequeno">Mostrando até 300 resultados.</p></section>`;
}
function ligarDoadores(corpo) {
  ligarAcoes(corpo);
  aoEnviar($("#f-busca", corpo), async (d) => {
    buscaDoador = d.q;
    painel.ir("doadores");
  });
  corpo.addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-editar-doador]");
    if (!b) return;
    const d = cacheDoadores.find((x) => x.id === Number(b.dataset.editarDoador));
    const c = janela("Editar doador", `<form id="f-doador">
      <label>Nome <input name="nome" value="${esc(d.nome)}" required /></label>
      <div class="duas"><label>Tipo sanguíneo <select name="tipo_sanguineo">${TIPOS.map((t) => `<option${t === d.tipo_sanguineo ? " selected" : ""}>${t}</option>`).join("")}</select></label>
      <label>Telefone <input name="telefone" value="${esc(d.telefone || "")}" /></label></div>
      <div class="duas"><label>Cidade <input name="cidade" value="${esc(d.cidade)}" required /></label><label>UF <select name="uf">${opcoesUF(d.uf)}</select></label></div>
      <label>Situação <select name="status">${["ATIVO", "INATIVO", "BLOQUEADO"].map((s) => `<option${s === d.status ? " selected" : ""}>${s}</option>`).join("")}</select></label>
      <p class="muted pequeno">A alteração fica registrada na auditoria como feita pelo admin.</p>
      <p class="erro hidden"></p><button class="btn btn-primario cheio" type="submit">Salvar</button></form>`);
    aoEnviar($("#f-doador", c), async (dados) => {
      aviso((await api(`/api/admin/doadores/${d.id}`, dados)).mensagem);
      fecharJanela();
      painel.ir("doadores");
    });
  });
}

/* ---- CONTAS ------------------------------------------------------------------ */
async function telaContas() {
  const [contas, bancos, parceiros] = await Promise.all([api("/api/admin/contas"), api("/api/admin/bancos"), api("/api/admin/parceiros")]);
  const PAPEL = { ADMINISTRADOR: "Admin", BANCO: "Banco de sangue", PARCEIRO: "Parceiro" };
  return `<div class="colunas">
    <section class="cartao" style="grid-column:1/-1"><h2>Contas</h2><div class="tabela-wrap"><table><thead><tr><th>Nome</th><th>Tipo</th><th>Vínculo</th><th>Último acesso</th><th>Situação</th><th></th></tr></thead><tbody>${contas
      .map((c) => `<tr><td><strong>${esc(c.nome)}</strong><br><span class="muted pequeno">${esc(c.email)}</span></td><td>${PAPEL[c.papel] || esc(c.papel)}</td><td>${esc(c.banco || c.parceiro || "—")}</td>
        <td>${c.ultimo_login ? dataBR(c.ultimo_login) : "nunca"}</td><td>${selo(c.status)}</td>
        <td>${c.status === "ATIVO" ? `<button class="btn btn-pequeno btn-perigo" data-conta="${c.id}" data-status="BLOQUEADO">Bloquear</button>` : `<button class="btn btn-pequeno btn-ok" data-conta="${c.id}" data-status="ATIVO">Reativar</button>`}</td></tr>`)
      .join("")}</tbody></table></div></section>
    <section class="cartao"><h2>Nova conta</h2><form id="f-conta">
      <label>Tipo <select name="papel" id="papel-conta"><option value="BANCO">Banco de sangue</option><option value="PARCEIRO">Parceiro</option><option value="ADMINISTRADOR">Administrador</option></select></label>
      <label class="v-banco">Banco de sangue <select name="banco_id">${bancos.bancos.map((b) => `<option value="${b.id}">${esc(b.nome)}</option>`).join("")}</select></label>
      <label class="v-parceiro hidden">Parceiro <select name="parceiro_id">${parceiros.parceiros.map((p) => `<option value="${p.id}">${esc(p.nome)}</option>`).join("")}</select></label>
      <label>Nome da pessoa <input name="nome" required /></label>
      <label>E-mail <input name="email" type="email" required /></label>
      <label>Senha inicial <span class="campo-senha"><input name="senha" type="password" autocomplete="new-password" minlength="10" required placeholder="10+ caracteres, letras e números" /><button type="button" class="ver-senha" aria-label="Mostrar senha">Ver</button></span></label>
      <p class="muted pequeno">Passe a senha à pessoa por um canal seguro e peça que ela troque em “Esqueci minha senha”.</p>
      <p class="erro hidden"></p><button class="btn btn-primario cheio" type="submit">Criar conta</button></form></section></div>`;
}
function ligarContas(corpo) {
  $("#papel-conta", corpo).addEventListener("change", (ev) => {
    $$(".v-banco", corpo).forEach((e) => e.classList.toggle("hidden", ev.target.value !== "BANCO"));
    $$(".v-parceiro", corpo).forEach((e) => e.classList.toggle("hidden", ev.target.value !== "PARCEIRO"));
  });
  aoEnviar($("#f-conta", corpo), async (d) => {
    aviso((await api("/api/admin/contas", d)).mensagem);
    painel.ir("contas");
  });
  corpo.addEventListener("click", async (ev) => {
    const b = ev.target.closest("[data-conta]");
    if (!b) return;
    try {
      aviso((await api(`/api/admin/contas/${b.dataset.conta}/status`, { status: b.dataset.status })).mensagem);
      painel.ir("contas");
    } catch (e) {
      erro(e);
    }
  });
}
