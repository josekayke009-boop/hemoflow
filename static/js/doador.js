/*
 * HemoFlow 2.0 — app do doador (pensado para celular; instalado como PWA pelo QR code)
 *   Início ...... termômetro do seu tipo, convocações, próximo agendamento, contagem para a próxima
 *                 doação, nível e medalhas (com comemoração), card para compartilhar e aviso de impacto
 *   Agendar ..... escolhe o local, o dia e o horário (o banco de sangue é avisado na hora)
 *   Vantagens ... ofertas de parceiros e cupons (liberados com doação verificada nos últimos 6 meses)
 *   Perfil ...... direitos, grupos, histórico, dados, acessibilidade e sair
 */
import {
  api, $, $$, esc, cru, html, aviso, erro, janela, fecharJanela, aoEnviar, dataBR, hora, diaSemana, hojeISO,
  NIVEL_TEXTO, TIPOS, TIPO_PARCEIRO, icone, termometro, abrirAvisos, blocoAcessibilidade, ligarAcessibilidade, opcoesUF,
  preCarregar,
} from "./nucleo.js";
import { telaAjuda, ligarAjuda } from "./ajuda.js";

let raiz, ctxApp, usuario;
let aba = "inicio";
let cache = {};
let agendarCom = null; // { unidade_id, convocacao_id } quando vem de uma convocação

export async function montar(elemento, u, ctx) {
  raiz = elemento;
  usuario = u;
  ctxApp = ctx;
  aba = "inicio";
  raiz.innerHTML = `
    ${ctx.faixa}
    <header class="topo">
      <img src="/img/hemoflow-icone.png" alt="" width="36" height="36" />
      <span class="marca-nome">HemoFlow</span><span class="espaco"></span>
      <button class="icone-btn" id="d-ajuda" aria-label="Ajuda">${icone("ajuda")}</button>
      <button class="icone-btn" id="d-sino" aria-label="Avisos">${icone("sino")}<span class="bolinha hidden" id="d-bolinha"></span></button>
    </header>
    <main class="app-doador" id="d-conteudo" tabindex="-1"></main>
    <nav class="menu-inferior" aria-label="Menu principal">
      ${[["inicio", "Início"], ["agendar", "Agendar"], ["vantagens", "Vantagens"], ["perfil", "Perfil"]]
        .map(([id, t]) => `<button type="button" data-aba="${id}">${icone({ inicio: "inicio", agendar: "agenda", vantagens: "presente", perfil: "pessoa" }[id])}${t}</button>`)
        .join("")}
    </nav>`;
  $$(".menu-inferior button", raiz).forEach((b) => b.addEventListener("click", () => irPara(b.dataset.aba)));
  $("#d-sino", raiz).addEventListener("click", () => abrirAvisos(marcarSino, (link) => irPara(link === "agendar" ? "agendar" : "inicio")));
  document.addEventListener("hemoflow:online", () => document.body.contains(raiz) && irPara(aba));
  $("#d-ajuda", raiz).addEventListener("click", () => irPara("ajuda"));
  $("#d-conteudo", raiz).addEventListener("click", cliques);
  await irPara("inicio");
  preCarregar(["/api/doador/vantagens", "/api/doador/historico", "/api/doador/direitos", "/api/doador/grupos",
    "/api/doador/perfil", "/api/doador/locais", "/api/avisos"]);
}

function marcarSino(n) {
  const b = $("#d-bolinha");
  if (!b) return;
  b.textContent = n;
  b.classList.toggle("hidden", !n);
}

async function irPara(nova, extra) {
  aba = nova;
  $$(".menu-inferior button", raiz).forEach((b) => {
    const ativo = b.dataset.aba === nova || (nova.startsWith("perfil") && b.dataset.aba === "perfil");
    b.classList.toggle("ativo", ativo);
    b.setAttribute("aria-current", ativo ? "page" : "false");
  });
  const area = $("#d-conteudo", raiz);
  area.innerHTML = '<p class="vazio">Carregando…</p>';
  scrollTo(0, 0);
  try {
    const telas = { inicio, agendar, vantagens, perfil, direitos, grupos, historico, dados, acessibilidade, ajuda };
    area.innerHTML = String(await telas[nova](extra));
    if (nova === "acessibilidade") ligarAcessibilidade(area);
    if (nova === "ajuda") ligarAjuda(area);
    ligarFormularios(area);
  } catch (e) {
    area.innerHTML = `<div class="cartao erro">${esc(e.message)}</div>`;
  }
}

/* ---- INÍCIO ---------------------------------------------------------------- */
async function inicio() {
  const r = (cache.inicio = await api("/api/doador/inicio"));
  marcarSino(r.avisos_nao_lidos);
  const d = r.doador;
  const apt = r.aptidao;
  const partes = [];
  partes.push(html`<div class="saudacao"><p class="muted" style="margin:0">Olá,</p>
    <h1>${d.primeiro_nome} <span class="selo" style="vertical-align:middle">${d.tipo_sanguineo}</span></h1></div>`);

  if (r.impacto) {
    partes.push(html`<section class="cartao impacto" role="status">
      <h2>Doações como a sua salvam vidas 💛</h2><p style="margin:0">${r.impacto.mensagem}</p></section>`);
  }

  if (r.proximo_agendamento) {
    const p = r.proximo_agendamento;
    partes.push(html`<section class="cartao">
      <div class="cartao-titulo">${cru(icone("agenda"))}<h2>Sua doação está marcada</h2></div>
      <p><strong>${diaSemana(p.inicio)}, ${dataBR(p.inicio)} às ${hora(p.inicio)}</strong><br>${p.unidade}<br>
      <span class="muted">${p.endereco || ""} ${p.cidade ? "· " + p.cidade : ""}</span></p>
      <p class="muted pequeno" style="margin-bottom:6px">Mostre este código no balcão:</p>
      <div class="codigo-grande" aria-label="Código ${p.codigo.split("").join(" ")}">${p.codigo}</div>
      <p class="muted pequeno" style="margin-top:10px">Leve documento com foto, durma bem e coma algo leve. A aptidão final é confirmada na triagem.</p>
      <button type="button" class="btn btn-perigo cheio" data-cancelar="${p.id}">Não vou poder ir · cancelar</button>
    </section>`);
  }

  for (const c of r.convocacoes) {
    partes.push(html`<section class="cartao destaque-acao">
      <h2>${c.banco} precisa de ${c.tipo_sanguineo}</h2>
      <p>${c.mensagem}</p>
      <button type="button" class="btn cheio" data-convocacao="${c.id}" data-unidade="${c.unidade_id}">Quero doar · escolher horário</button>
    </section>`);
  }

  partes.push(cru(cartaoContagem(r)));
  partes.push(cru(cartaoNivel(r)));

  // Termômetro (opção A): o tipo do doador em destaque + grade dos 8 tipos
  if (r.bancos.length) {
    const dest = r.destaque;
    const primeiro = r.bancos.find((b) => b.unidade_id === dest?.unidade_id) || r.bancos[0];
    partes.push(html`<section class="cartao">
      <h2>Estoque de sangue na sua região</h2>
      ${dest ? cru(`<div class="termometro-bloco">${termometro(dest.nivel, d.tipo_sanguineo)}
        <div><span class="selo ${esc(dest.nivel)}">${esc(NIVEL_TEXTO[dest.nivel])}</span>
        <p style="margin-top:8px"><strong>${esc(dest.banco)}</strong><br>${esc(textoNivel(dest.nivel, d.tipo_sanguineo))}</p>
        <p class="muted pequeno" style="margin:0">Atualizado em ${esc(dataBR(dest.atualizado_em))} por ${esc(dest.fonte)}</p></div></div>`) : ""}
      <h3 style="margin-top:18px">Todos os tipos</h3>
      ${r.bancos.length > 1 ? cru(`<label class="visualmente-oculto" for="d-banco">Banco de sangue</label>
        <select id="d-banco" style="margin-bottom:12px">${r.bancos.map((b) => `<option value="${b.unidade_id}"${b === primeiro ? " selected" : ""}>${esc(b.unidade)} · ${esc(b.cidade)}</option>`).join("")}</select>`) : cru(`<p class="muted">${esc(primeiro.unidade)}</p>`)}
      <div id="d-grade">${cru(gradeTipos(primeiro, d.tipo_sanguineo))}</div>
      <p class="muted pequeno" style="margin-top:10px">Cores informadas pelos bancos de sangue. Vermelho = falta muito.</p>
    </section>`);
  } else {
    partes.push(html`<section class="cartao"><h2>Estoque de sangue</h2><p class="muted">Ainda não há bancos parceiros no seu estado. Você pode doar em um hemocentro público — veja em Agendar.</p></section>`);
  }

  partes.push(html`<section class="grade-numeros">
    <div class="numero"><strong>${r.doacoes}</strong><span>doações registradas</span></div>
    <div class="numero"><strong>${r.vidas}</strong><span>vidas que você pode ter ajudado</span></div>
  </section>`);
  setTimeout(() => {
    $("#d-banco")?.addEventListener("change", (ev) => {
      const b = cache.inicio.bancos.find((x) => String(x.unidade_id) === ev.target.value);
      $("#d-grade").innerHTML = gradeTipos(b, d.tipo_sanguineo);
    });
    comemorarNivel(r);
  });
  return partes.join("");
}

/* Contagem para a próxima doação: anel que enche conforme os dias passam desde a última doação */
function diasAte(iso) {
  const [a, m, d] = iso.split("-").map(Number);
  const hoje = new Date();
  return Math.round((new Date(a, m - 1, d) - new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate())) / 86400000);
}
function cartaoContagem(r) {
  const apt = r.aptidao;
  const faltam = apt.apto ? 0 : Math.max(0, diasAte(apt.a_partir_de));
  const intervalo = r.intervalo_dias || 60;
  const pct = apt.apto ? 100 : Math.max(4, Math.min(100, Math.round(100 * (1 - faltam / intervalo))));
  const centro = apt.apto ? `<b>✓</b><small>liberado</small>` : `<b>${faltam}</b><small>dia${faltam === 1 ? "" : "s"}</small>`;
  const texto = apt.apto
    ? r.doacoes
      ? "Você já pode doar de novo! Escolha um horário: o banco de sangue é avisado na hora."
      : "Escolha um horário em Agendar. A triagem no banco de sangue confirma se está tudo certo."
    : `Faltam ${faltam} dia${faltam === 1 ? "" : "s"}: você poderá doar a partir de <strong>${esc(dataBR(apt.a_partir_de))}</strong>. Avisamos você no dia.`;
  return `<section class="cartao contagem">
    <div class="anel-contagem${apt.apto ? " pronto" : ""}" style="--pct:${pct}" role="img" aria-label="${apt.apto ? "Liberado para doar" : `Faltam ${faltam} dias`}"><div>${centro}</div></div>
    <div><h2>${apt.apto ? "Você já pode doar" : "Próxima doação"}</h2><p style="margin:0 0 6px">${texto}</p>
    ${apt.motivo ? `<p class="muted pequeno" style="margin:0 0 6px">${esc(apt.motivo)}</p>` : ""}
    <p class="muted pequeno" style="margin:0">Doações nos últimos 12 meses: ${apt.doacoes_12m} de ${apt.limite_anual}.</p>
    ${apt.apto ? '<button type="button" class="btn btn-primario" data-ir-aba="agendar" style="margin-top:10px">Agendar agora</button>' : ""}</div>
  </section>`;
}

/* Nível do doador (medalhas) + botão de compartilhar */
function cartaoNivel(r) {
  const n = r.nivel;
  const prox = n.proximo ? `<p class="muted pequeno" style="margin:6px 0 0">Mais ${n.faltam} ${n.faltam === 1 ? "doação" : "doações"} para ${esc(n.proximo)}</p>
      <div class="progresso" role="progressbar" aria-valuenow="${n.progresso}" aria-valuemin="0" aria-valuemax="100"><span style="width:${n.progresso}%;background:var(--marca)"></span></div>`
    : '<p class="muted pequeno" style="margin:6px 0 0">Você chegou ao nível máximo. Obrigado!</p>';
  return `<section class="cartao nivel-doador">
    <div class="medalha" aria-hidden="true">${n.emoji}</div>
    <div style="flex:1"><span class="muted pequeno">Seu nível</span><h2 style="margin:0">${esc(n.nome)}</h2>${prox}
      <div class="linha-flex" style="margin-top:12px">
        <span class="muted pequeno">${r.doacoes} doaç${r.doacoes === 1 ? "ão" : "ões"} · até ${r.vidas} vidas</span><span class="espaco"></span>
        ${r.doacoes ? '<button type="button" class="btn btn-pequeno btn-claro" data-compartilhar>📣 Compartilhar</button>' : ""}
      </div></div>
  </section>`;
}

/* Comemoração quando o doador sobe de nível (lembra o último nível visto neste aparelho) */
function comemorarNivel(r) {
  const chave = `hf-nivel:${usuario.id}`;
  let visto = null;
  try {
    visto = localStorage.getItem(chave);
    localStorage.setItem(chave, r.nivel.nome);
  } catch {
    return;
  }
  if (!visto || visto === r.nivel.nome || !r.doacoes) return;
  const c = janela("Novo nível!", `<div class="comemoracao"><div class="confete" aria-hidden="true">${"<i></i>".repeat(18)}</div>
    <div class="medalha grande">${r.nivel.emoji}</div><h2>${esc(r.nivel.nome)}</h2>
    <p>Você subiu de nível com ${r.doacoes} doações. Cada doação pode ajudar até 4 pessoas.</p>
    <button type="button" class="btn btn-primario cheio" data-compartilhar-janela>📣 Compartilhar</button></div>`);
  c.querySelector("[data-compartilhar-janela]").addEventListener("click", () => compartilhar(r));
}

/* Card para compartilhar (story 1080×1920) desenhado em canvas */
function carregarImagem(src) {
  return new Promise((ok) => {
    const img = new Image();
    img.onload = () => ok(img);
    img.onerror = () => ok(null);
    img.src = src;
  });
}
async function compartilhar(r) {
  const c = document.createElement("canvas");
  c.width = 1080;
  c.height = 1920;
  const g = c.getContext("2d");
  const fundo = g.createLinearGradient(0, 0, 1080, 1920);
  fundo.addColorStop(0, "#3a0209");
  fundo.addColorStop(0.5, "#a50d22");
  fundo.addColorStop(1, "#4b030c");
  g.fillStyle = fundo;
  g.fillRect(0, 0, 1080, 1920);
  g.fillStyle = "rgba(255,255,255,0.07)";
  for (let i = 0; i < 14; i++) {
    g.beginPath();
    g.arc((i * 233) % 1080, (i * 389) % 1920, 40 + ((i * 37) % 90), 0, Math.PI * 2);
    g.fill();
  }
  const logo = await carregarImagem("/img/hemoflow-icone.png");
  if (logo) g.drawImage(logo, 440, 260, 200, 200);
  g.textAlign = "center";
  g.fillStyle = "#fff";
  g.font = "800 64px Manrope, 'DM Sans', sans-serif";
  g.fillText("HemoFlow", 540, 560);
  g.font = "800 120px Manrope, 'DM Sans', sans-serif";
  g.fillText("EU DOEI", 540, 860);
  g.fillText("SANGUE", 540, 990);
  g.font = "160px sans-serif";
  g.fillText(r.nivel.emoji, 540, 1230);
  g.font = "700 56px 'DM Sans', sans-serif";
  g.fillText(r.nivel.nome, 540, 1340);
  g.fillStyle = "#ffd7db";
  g.font = "500 46px 'DM Sans', sans-serif";
  g.fillText(`${r.doacoes} doaç${r.doacoes === 1 ? "ão" : "ões"} · posso ter ajudado até ${r.vidas} vidas`, 540, 1430);
  g.fillStyle = "#fff";
  g.font = "800 58px Manrope, 'DM Sans', sans-serif";
  g.fillText("Doe. Volte. Salve vidas.", 540, 1680);
  g.fillStyle = "#ffd7db";
  g.font = "500 38px 'DM Sans', sans-serif";
  g.fillText(location.host, 540, 1760);
  const blob = await new Promise((ok) => c.toBlob(ok, "image/png"));
  const arquivo = new File([blob], "eu-doei-sangue-hemoflow.png", { type: "image/png" });
  const texto = "Eu doei sangue! Doe você também. 🩸 HemoFlow · Doe. Volte. Salve vidas.";
  try {
    if (navigator.canShare && navigator.canShare({ files: [arquivo] })) {
      await navigator.share({ files: [arquivo], text: texto });
      return;
    }
  } catch (e) {
    if (e?.name === "AbortError") return; // a pessoa fechou o compartilhamento
  }
  // Computador ou navegador sem compartilhamento: mostra a imagem para salvar
  // (data: URL, porque a política de segurança do site só aceita imagens do próprio HemoFlow ou data:)
  const url = c.toDataURL("image/png");
  return janela("Seu card", `<img src="${url}" alt="Card Eu doei sangue" style="width:100%;max-height:60vh;object-fit:contain;border-radius:14px" />
    <a class="btn btn-primario cheio" style="margin-top:12px" href="${url}" download="eu-doei-sangue-hemoflow.png">Baixar imagem</a>
    <p class="muted pequeno" style="margin-top:8px">Depois é só postar no story do Instagram ou mandar no WhatsApp.</p>`);
}

function textoNivel(nivel, tipo) {
  if (nivel === "CRITICO") return `O estoque de ${tipo} está crítico. Sua doação faz muita falta agora.`;
  if (nivel === "ATENCAO") return `O estoque de ${tipo} está baixando. Doar nos próximos dias ajuda bastante.`;
  return `O estoque de ${tipo} está normal. Mantenha sua doação em dia.`;
}
function gradeTipos(banco, meuTipo) {
  return `<div class="grade-tipos">${TIPOS.map((t) => {
    const n = banco.niveis[t];
    return `<div class="tipo ${n || ""}${t === meuTipo ? " meu" : ""}"><b>${t}</b><small>${n ? NIVEL_TEXTO[n] : "—"}</small></div>`;
  }).join("")}</div>`;
}

/* ---- AGENDAR ----------------------------------------------------------------- */
async function agendar() {
  const locais = (cache.locais = await api("/api/doador/locais"));
  const bancos = locais.filter((l) => l.tipo === "BANCO");
  const publicos = locais.filter((l) => l.tipo === "PUBLICO");
  const escolhido = agendarCom?.unidade_id || bancos[0]?.id;
  let corpo = `<div class="saudacao"><h1>Agendar doação</h1><p class="muted">Escolha onde, o dia e o horário. O banco de sangue recebe o aviso na hora.</p></div>`;
  if (agendarCom?.convocacao_id) corpo += `<p class="aviso-suave">Você está respondendo a uma convocação. Obrigado!</p>`;
  if (bancos.length) {
    corpo += `<section class="cartao"><label>Local
      <select id="d-local">${bancos.map((b) => `<option value="${b.id}"${b.id === escolhido ? " selected" : ""}>${esc(b.nome)} · ${esc(b.cidade)}</option>`).join("")}</select></label>
      <div id="d-vagas"></div></section>`;
    setTimeout(() => {
      $("#d-local").addEventListener("change", (ev) => carregarVagas(Number(ev.target.value)));
      carregarVagas(Number($("#d-local").value));
    });
  } else {
    corpo += `<section class="cartao"><p class="muted">Ainda não há bancos de sangue parceiros com agenda no seu estado.</p></section>`;
  }
  if (publicos.length) {
    corpo += `<section class="cartao"><h2>Hemocentros públicos</h2><p class="muted pequeno">A agenda deles é feita direto com o hemocentro. Depois, registre a doação em Perfil › Histórico.</p>
      <ul class="lista">${publicos.map((p) => `<li><div class="principal"><strong>${esc(p.nome)}</strong><span class="muted pequeno">${esc(p.endereco || "")} ${p.bairro ? "· " + esc(p.bairro) : ""} · ${esc(p.cidade)}<br>${esc(p.horario || "")}</span></div></li>`).join("")}</ul></section>`;
  }
  return corpo;
}

async function carregarVagas(unidadeId) {
  const caixa = $("#d-vagas");
  caixa.innerHTML = '<p class="vazio">Buscando horários…</p>';
  try {
    const r = await api(`/api/doador/vagas?unidade_id=${unidadeId}`);
    const livres = r.vagas.filter((v) => v.livres > 0);
    if (!livres.length) {
      caixa.innerHTML = '<p class="vazio">Sem horários livres nos próximos dias. Tente outro local.</p>';
      return;
    }
    const porDia = {};
    livres.forEach((v) => (porDia[v.inicio.slice(0, 10)] ||= []).push(v));
    const dias = Object.keys(porDia);
    caixa.innerHTML = `<p class="muted pequeno">${esc(r.unidade.endereco || "")} · ${esc(r.unidade.cidade)}</p>
      <h3>Dia</h3><div class="dias" role="radiogroup" aria-label="Dia">${dias
        .map((d, i) => `<button type="button" class="chip${i === 0 ? " ativo" : ""}" data-dia="${d}" role="radio" aria-checked="${i === 0}"><small>${d === hojeISO() ? "hoje" : diaSemana(d)}</small>${dataBR(d).slice(0, 5)}</button>`)
        .join("")}</div>
      <h3>Horário</h3><div class="horarios" id="d-horas"></div>`;
    const mostrarHoras = (dia) => {
      $("#d-horas").innerHTML = porDia[dia]
        .map((v) => `<button type="button" class="chip" data-vaga="${v.id}" data-quando="${v.inicio}">${hora(v.inicio)}</button>`)
        .join("");
    };
    mostrarHoras(dias[0]);
    $$("[data-dia]", caixa).forEach((b) =>
      b.addEventListener("click", () => {
        $$("[data-dia]", caixa).forEach((x) => {
          x.classList.toggle("ativo", x === b);
          x.setAttribute("aria-checked", x === b);
        });
        mostrarHoras(b.dataset.dia);
      }),
    );
  } catch (e) {
    caixa.innerHTML = `<p class="erro">${esc(e.message)}</p>`;
  }
}

function confirmarVaga(botao) {
  const quando = botao.dataset.quando;
  const local = $("#d-local").selectedOptions[0].textContent;
  const corpo = janela(
    "Confirmar agendamento",
    html`<p><strong>${diaSemana(quando)}, ${dataBR(quando)} às ${hora(quando)}</strong><br>${local}</p>
      <p class="muted pequeno">Antes de ir: leve documento com foto, não doe em jejum, evite gordura 3 horas antes e não beba álcool nas 12 horas anteriores.</p>
      <button type="button" class="btn btn-primario cheio" id="d-confirmar">Confirmar</button>`,
  );
  $("#d-confirmar", corpo).addEventListener("click", async (ev) => {
    ev.target.disabled = true;
    try {
      const r = await api("/api/doador/agendar", { vaga_id: Number(botao.dataset.vaga), convocacao_id: agendarCom?.convocacao_id || null });
      agendarCom = null;
      fecharJanela();
      aviso(r.mensagem);
      irPara("inicio");
    } catch (e) {
      ev.target.disabled = false;
      erro(e);
    }
  });
}

/* ---- VANTAGENS --------------------------------------------------------------- */
async function vantagens() {
  const r = await api("/api/doador/vantagens");
  const ofertas = r.ofertas.length
    ? r.ofertas
        .map(
          (o) => `<article class="cartao oferta${o.emergencia ? " emergencia" : ""}">
        ${o.emergencia ? `<span class="selo CRITICO">🚨 Oferta de emergência para quem é ${esc(cache.inicio?.doador?.tipo_sanguineo || "do seu tipo")}</span>` : ""}
        <span class="parceiro">${esc(o.parceiro)} · ${esc(TIPO_PARCEIRO[o.tipo] || o.tipo)}</span>
        <h3>${esc(o.titulo)}</h3>
        ${o.descricao ? `<p class="muted" style="margin:0">${esc(o.descricao)}</p>` : ""}
        <p class="muted pequeno" style="margin:0">${esc(o.cidade)}${o.endereco ? " · " + esc(o.endereco) : ""}${o.validade ? " · até " + dataBR(o.validade) : ""}</p>
        <button type="button" class="btn ${r.pode_gerar ? "btn-primario" : "btn-claro"}" data-oferta="${o.id}" ${r.pode_gerar ? "" : "disabled"}>${r.pode_gerar ? "Gerar cupom" : "Doe para liberar"}</button>
      </article>`,
        )
        .join("")
    : '<p class="vazio">Ainda não há ofertas no seu estado.</p>';
  const cupons = r.cupons.length
    ? `<section class="cartao"><h2>Meus cupons</h2><ul class="lista">${r.cupons
        .map(
          (c) => `<li><div class="principal"><strong>${esc(c.codigo)}</strong><span class="muted pequeno">${esc(c.titulo)} · ${esc(c.parceiro)}</span></div>
          <span class="selo ${c.usado_em ? "" : "ok"}">${c.usado_em ? "usado " + dataBR(c.usado_em) : "vale até " + dataBR(c.expira_em)}</span></li>`,
        )
        .join("")}</ul></section>`
    : "";
  return `<div class="saudacao"><h1>Vantagens</h1><p class="muted">${esc(r.regra)}</p></div>
    ${r.pode_gerar ? "" : '<p class="aviso-suave">Seus cupons são liberados quando o banco de sangue confirmar uma doação sua.</p>'}
    ${cupons}${ofertas}
    <section class="cartao"><h2>Estuda em um cursinho ou faculdade parceira?</h2>
      <p class="muted pequeno">Digite o código que a instituição passou. Ela só vê números gerais da turma, nunca seus dados.</p>
      <form id="f-codigo-parceiro" class="linha-flex"><input name="codigo" placeholder="Ex.: APROVA-25" style="flex:1;min-width:160px" required />
        <button class="btn btn-claro" type="submit">Vincular</button><p class="erro hidden" style="width:100%"></p></form></section>`;
}

/* ---- PERFIL ------------------------------------------------------------------ */
async function perfil() {
  return `<div class="saudacao"><h1>${esc(usuario.nome)}</h1><p class="muted" style="margin:0">${esc(usuario.email)}</p></div>
    <section class="cartao menu-perfil">
      <button type="button" data-ir="direitos">⚖️ Meus direitos e conquistas</button>
      <button type="button" data-ir="grupos">👥 Grupos de doação</button>
      <button type="button" data-ir="historico">📋 Histórico de doações</button>
      <button type="button" data-ir="dados">✏️ Meus dados e avisos</button>
      <button type="button" data-ir="acessibilidade">🔠 Letra, contraste e tema</button>
      <button type="button" data-ir="ajuda">❓ Ajuda e fale conosco</button>
    </section>
    <button type="button" class="btn btn-claro cheio" id="d-sair">${icone("sair")} Sair da conta</button>
    <p class="muted pequeno centro" style="margin-top:18px">HemoFlow · Doe. Volte. Salve vidas.<br>
      <a href="/termos.html" target="_blank" rel="noopener">Termos de Uso</a> · <a href="/privacidade.html" target="_blank" rel="noopener">Política de Privacidade</a></p>`;
}
const voltarPerfil = '<button type="button" class="voltar" data-ir="perfil">‹ Perfil</button>';

async function direitos() {
  const r = await api("/api/doador/direitos");
  return `${voltarPerfil}<h1>Meus direitos</h1>
    ${r.beneficios
      .map((b) => {
        let meta = "";
        if (b.meta) {
          const pct = Math.min(100, Math.round((100 * b.meta.feitas) / b.meta.alvo));
          meta = `<p class="pequeno" style="margin:8px 0 4px"><strong>${b.meta.feitas} de ${b.meta.alvo}</strong> doações verificadas nos últimos ${b.janela_meses || 12} meses ${b.meta.cumprida ? "· ✅ meta cumprida" : ""}</p>
            <div class="progresso" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"><span style="width:${pct}%"></span></div>`;
        }
        return `<section class="cartao"><span class="selo">${b.uf ? esc(b.uf) : "Todo o Brasil"}</span><h3 style="margin-top:8px">${esc(b.titulo)}</h3><p class="muted" style="margin:0">${esc(b.descricao)}</p>${meta}</section>`;
      })
      .join("")}
    <section class="cartao"><h2>Conquistas</h2><div class="conquistas">${r.conquistas
      .map((c) => `<div class="conquista${c.ganhou ? " ganha" : ""}"><b>${c.ganhou ? "🏅" : "🔒"}</b>${esc(c.titulo)}</div>`)
      .join("")}</div></section>
    <p class="muted pequeno">${esc(r.aviso)}</p>`;
}

async function grupos() {
  const lista = await api("/api/doador/grupos");
  const cards = lista.length
    ? lista
        .map((g) => {
          const pct = Math.min(100, Math.round((100 * g.total) / g.meta));
          return `<section class="cartao"><div class="cartao-titulo"><h3>${esc(g.nome)}</h3><span class="espaco"></span><span class="selo">${esc(g.codigo)}</span></div>
            <p class="pequeno" style="margin-bottom:4px"><strong>${g.total} de ${g.meta}</strong> doações nos últimos 6 meses</p>
            <div class="progresso"><span style="width:${pct}%"></span></div>
            <ul class="lista" style="margin-top:8px">${g.membros.map((m) => `<li><span class="principal">${esc(m.nome)}</span><span class="muted">${m.doacoes} 🩸</span></li>`).join("")}</ul></section>`;
        })
        .join("")
    : '<p class="vazio">Você ainda não está em um grupo.</p>';
  return `${voltarPerfil}<h1>Grupos de doação</h1><p class="muted">Doe junto com a turma, o trabalho ou a família e acompanhem a meta.</p>
    ${cards}
    <section class="cartao"><h2>Entrar em um grupo</h2>
      <form id="f-entrar-grupo" class="linha-flex"><input name="codigo" placeholder="Código do grupo" style="flex:1;min-width:160px" required />
      <button class="btn btn-claro" type="submit">Entrar</button><p class="erro hidden" style="width:100%"></p></form></section>
    <section class="cartao"><h2>Criar um grupo</h2>
      <form id="f-criar-grupo"><label>Nome do grupo <input name="nome" required placeholder="Ex.: Turma C · ADS" /></label>
      <label>Meta de doações em 6 meses <input name="meta" type="number" min="1" max="1000" value="10" /></label>
      <p class="erro hidden"></p><button class="btn btn-primario cheio" type="submit">Criar grupo</button></form></section>`;
}

async function historico() {
  const r = await api("/api/doador/historico");
  const itens = r.doacoes.length
    ? r.doacoes
        .map(
          (h) => `<li><div class="principal"><strong>${dataBR(h.data)}</strong><span class="muted pequeno">${esc(h.local || "")}</span></div>
          <span class="selo ${h.status === "VERIFICADA" ? "ok" : ""}">${h.status === "VERIFICADA" ? "Verificada" : "Declarada"}</span></li>`,
        )
        .join("")
    : '<li class="vazio">Nenhuma doação registrada ainda.</li>';
  return `${voltarPerfil}<h1>Histórico</h1>
    <section class="grade-numeros"><div class="numero"><strong>${r.total}</strong><span>doações</span></div>
    <div class="numero"><strong>${r.vidas}</strong><span>vidas ajudadas</span></div></section>
    <section class="cartao"><ul class="lista">${itens}</ul>
    <p class="muted pequeno">“Verificada” = confirmada pelo banco de sangue. “Declarada” = informada por você (conta para o intervalo, mas não libera cupons).</p></section>
    <section class="cartao"><h2>Doou em outro lugar?</h2>
      <form id="f-declarar"><div class="duas"><label>Data <input name="data" type="date" max="${hojeISO()}" required /></label>
      <label>Local <input name="local" required placeholder="Ex.: HEMOPE Recife" /></label></div>
      <p class="erro hidden"></p><button class="btn btn-claro cheio" type="submit">Registrar doação</button></form></section>`;
}

async function dados() {
  const p = await api("/api/doador/perfil");
  return `${voltarPerfil}<h1>Meus dados</h1>
    <section class="cartao"><ul class="lista">
      <li><span class="principal muted">Nome</span><strong>${esc(p.nome)}</strong></li>
      <li><span class="principal muted">CPF</span><strong>${esc(p.cpf_mascarado)}</strong></li>
      <li><span class="principal muted">Nascimento</span><strong>${dataBR(p.data_nascimento)}</strong></li>
      <li><span class="principal muted">Tipo sanguíneo</span><strong>${esc(p.tipo_sanguineo)}</strong></li>
    </ul><p class="muted pequeno">Para corrigir nome, CPF ou tipo sanguíneo, fale com a equipe HemoFlow (o tipo é confirmado pelo banco de sangue).</p></section>
    <section class="cartao"><form id="f-perfil">
      <label>Celular <input name="telefone" type="tel" value="${esc(p.telefone || "")}" /></label>
      <div class="duas"><label>Cidade <input name="cidade" value="${esc(p.cidade)}" required /></label>
      <label>Estado <select name="uf">${opcoesUF(p.uf)}</select></label></div>
      <label class="check"><input type="checkbox" name="consentimento_convocacao" ${p.consentimento_convocacao ? "checked" : ""} /> Quero receber convocações quando meu tipo fizer falta.</label>
      <p class="erro hidden"></p><button class="btn btn-primario cheio" type="submit">Salvar</button></form></section>
    ${p.parceiros?.length ? `<section class="cartao"><h3>Instituições vinculadas</h3><ul class="lista">${p.parceiros
      .map((x) => `<li><span class="principal">${esc(x.nome)}</span>${x.tipo !== "COMERCIO" ? `<button type="button" class="btn btn-pequeno btn-claro" data-declaracao="${x.id}">📄 Declaração de doação</button>` : ""}</li>`)
      .join("")}</ul><p class="muted pequeno">A declaração lista suas doações verificadas e tem um código que a instituição confere no HemoFlow.</p></section>` : ""}`;
}

async function acessibilidade() {
  return `${voltarPerfil}<h1>Letra, contraste e tema</h1><section class="cartao">${blocoAcessibilidade()}</section>`;
}

async function ajuda() {
  return `${voltarPerfil}<h1>Ajuda</h1><p class="muted">Dúvidas mais comuns sobre doar sangue e usar o app.</p>${telaAjuda("DOADOR")}`;
}

/* ---- AÇÕES ------------------------------------------------------------------- */
async function cliques(ev) {
  const alvo = ev.target.closest("button");
  if (!alvo) return;
  if (alvo.dataset.ir) return irPara(alvo.dataset.ir);
  if (alvo.id === "d-sair") return ctxApp.sair();
  if (alvo.dataset.convocacao) {
    agendarCom = { convocacao_id: Number(alvo.dataset.convocacao), unidade_id: Number(alvo.dataset.unidade) };
    return irPara("agendar");
  }
  if (alvo.dataset.vaga) return confirmarVaga(alvo);
  if (alvo.dataset.irAba) return irPara(alvo.dataset.irAba);
  if ("compartilhar" in alvo.dataset) return compartilhar(cache.inicio).catch(erro);
  if (alvo.dataset.declaracao) return emitirDeclaracao(Number(alvo.dataset.declaracao), alvo);
  if (alvo.dataset.cancelar) {
    const corpo = janela("Cancelar agendamento?", `<p>O banco de sangue será avisado e a vaga fica livre para outra pessoa.</p>
      <div class="linha-flex"><button class="btn btn-claro" type="button" id="nao">Manter</button><button class="btn btn-perigo" type="button" id="sim">Cancelar doação</button></div>`);
    $("#nao", corpo).onclick = fecharJanela;
    $("#sim", corpo).onclick = async () => {
      try {
        const r = await api(`/api/doador/agendamentos/${alvo.dataset.cancelar}/cancelar`, {});
        fecharJanela();
        aviso(r.mensagem);
        irPara("inicio");
      } catch (e) {
        erro(e);
      }
    };
    return;
  }
  if (alvo.dataset.oferta) {
    alvo.disabled = true;
    try {
      const r = await api("/api/doador/cupons", { oferta_id: Number(alvo.dataset.oferta) });
      janela("Seu cupom", `<p>Mostre este código no parceiro:</p><div class="codigo-grande">${esc(r.cupom.codigo)}</div>
        <p class="muted pequeno" style="margin-top:10px">Vale até ${dataBR(r.cupom.expira_em)} e pode ser usado uma vez.</p>`);
      $("#janela").addEventListener("close", () => aba === "vantagens" && irPara("vantagens"), { once: true });
    } catch (e) {
      alvo.disabled = false;
      erro(e);
    }
  }
}

/* Declaração de doação para cursinho/faculdade: abre uma página pronta para imprimir ou salvar em PDF */
async function emitirDeclaracao(parceiroId, botao) {
  botao.disabled = true;
  try {
    const r = await api("/api/doador/declaracoes", { parceiro_id: parceiroId });
    const linhas = r.doacoes.map((x) => `<tr><td>${dataBR(x.data)}</td><td>${esc(x.local || "")}</td></tr>`).join("");
    const w = window.open("", "_blank");
    if (!w) throw new Error("O navegador bloqueou a nova janela. Permita pop-ups para o HemoFlow.");
    w.document.write(`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Declaração ${esc(r.codigo)}</title>
      <style>body{font:15px/1.6 Arial,sans-serif;color:#151a2d;max-width:720px;margin:40px auto;padding:0 24px}
      h1{font-size:22px;margin:0 0 4px}.cab{display:flex;align-items:center;gap:14px;border-bottom:3px solid #b0102a;padding-bottom:14px;margin-bottom:24px}
      .cab img{width:56px;height:56px;border-radius:14px}table{width:100%;border-collapse:collapse;margin:16px 0}td,th{border-bottom:1px solid #ddd;padding:8px;text-align:left}
      .cod{font:700 18px monospace;letter-spacing:2px;background:#f5f6fa;padding:10px 14px;border-radius:8px;display:inline-block}
      .rod{margin-top:32px;font-size:12px;color:#5d6785}</style></head><body>
      <div class="cab"><img src="${location.origin}/img/hemoflow-icone.png" alt=""><div><h1>Declaração de doação de sangue</h1>HemoFlow · Doe. Volte. Salve vidas.</div></div>
      <p>Declaramos, para fins de apresentação a <strong>${esc(r.instituicao)}</strong>, que <strong>${esc(r.nome)}</strong> (CPF ${esc(r.cpf_mascarado)})
      tem <strong>${r.doacoes.length} doação(ões) de sangue verificada(s)</strong> por bancos de sangue parceiros do HemoFlow:</p>
      <table><tr><th>Data</th><th>Local</th></tr>${linhas}</table>
      <p>Código de verificação: <span class="cod">${esc(r.codigo)}</span></p>
      <p>A instituição confere a autenticidade no HemoFlow (área do parceiro › Alunos › Verificar declaração).</p>
      <p class="rod">Emitida em ${dataBR(r.emitida_em)}. O HemoFlow não substitui documento oficial do banco de sangue; para comprovação legal, vale a declaração emitida pelo próprio banco.</p>
      </body></html>`);
    w.document.close();
    w.focus();
    setTimeout(() => w.print(), 600); // abre a janela de imprimir (dá para escolher "Salvar como PDF")
    aviso(`Declaração ${r.codigo} emitida.`);
  } catch (e) {
    erro(e);
  } finally {
    botao.disabled = false;
  }
}

function ligarFormularios(area) {
  const f = (id) => $("#" + id, area);
  if (f("f-codigo-parceiro"))
    aoEnviar(f("f-codigo-parceiro"), async (d) => {
      aviso((await api("/api/doador/codigo-parceiro", d)).mensagem);
      f("f-codigo-parceiro").reset();
    });
  if (f("f-entrar-grupo"))
    aoEnviar(f("f-entrar-grupo"), async (d) => {
      aviso((await api("/api/doador/grupos/entrar", d)).mensagem);
      irPara("grupos");
    });
  if (f("f-criar-grupo"))
    aoEnviar(f("f-criar-grupo"), async (d) => {
      aviso((await api("/api/doador/grupos", { nome: d.nome, meta: Number(d.meta) })).mensagem);
      irPara("grupos");
    });
  if (f("f-declarar"))
    aoEnviar(f("f-declarar"), async (d) => {
      aviso((await api("/api/doador/doacao-declarada", d)).mensagem);
      irPara("historico");
    });
  if (f("f-perfil"))
    aoEnviar(f("f-perfil"), async (d) => {
      aviso((await api("/api/doador/perfil", d)).mensagem);
    });
}
