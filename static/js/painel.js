/*
 * HemoFlow 2.0 — molde dos painéis web (banco de sangue, parceiro e admin)
 * Menu lateral no computador; no celular o menu abre pelo botão ☰.
 */
import { $, $$, esc, icone, abrirAvisos, contarAvisos, janela, blocoAcessibilidade, ligarAcessibilidade } from "./nucleo.js";

/**
 * itens: [{ id, titulo, icone, tela: async (corpo) => html, depois?: (corpo) => void }]
 */
export function montarPainel(raiz, { subtitulo, itens, usuario, ctx }) {
  raiz.innerHTML = `${ctx.faixa}
    <div class="painel">
      <aside class="lateral" aria-label="Menu">
        <div class="marca"><img src="/img/hemoflow-icone.png" alt="" width="40" height="40" />
          <div><strong>HemoFlow</strong><small>${esc(subtitulo)}</small></div></div>
        <nav>${itens.map((i) => `<button type="button" data-tela="${i.id}">${icone(i.icone)}${esc(i.titulo)}</button>`).join("")}</nav>
        <div class="rodape">
          <span class="muted pequeno" style="padding:0 12px">${esc(usuario.nome)}</span>
          <nav><button type="button" id="p-aparencia">${icone("ajustes")}Letra e tema</button>
          <button type="button" id="p-sair">${icone("sair")}Sair</button></nav>
        </div>
      </aside>
      <div class="conteudo">
        <header class="conteudo-topo">
          <button class="icone-btn so-celular" id="p-menu" aria-label="Abrir menu">${icone("menu")}</button>
          <h1 id="p-titulo"></h1><span class="espaco"></span>
          <button class="icone-btn" id="p-sino" aria-label="Avisos">${icone("sino")}<span class="bolinha hidden" id="p-bolinha"></span></button>
        </header>
        <main class="conteudo-corpo" id="p-corpo" tabindex="-1"></main>
      </div>
    </div>`;
  const painel = $(".painel", raiz);
  let corpo = $("#p-corpo", raiz);
  const marcar = (n) => {
    $("#p-bolinha").textContent = n;
    $("#p-bolinha").classList.toggle("hidden", !n);
  };
  async function ir(id) {
    const item = itens.find((i) => i.id === id) || itens[0];
    $$(".lateral nav button[data-tela]", raiz).forEach((b) => {
      b.classList.toggle("ativo", b.dataset.tela === item.id);
      b.setAttribute("aria-current", b.dataset.tela === item.id ? "page" : "false");
    });
    painel.classList.remove("menu-aberto");
    $("#p-titulo").textContent = item.titulo;
    // corpo novo a cada tela: os ouvintes de clique da tela anterior não se acumulam
    const novo = corpo.cloneNode(false);
    corpo.replaceWith(novo);
    corpo = novo;
    corpo.innerHTML = '<p class="vazio">Carregando…</p>';
    try {
      corpo.innerHTML = String(await item.tela(corpo));
      item.depois?.(corpo);
    } catch (e) {
      corpo.innerHTML = `<div class="cartao erro">${esc(e.message)}</div>`;
    }
    contarAvisos().then(marcar);
  }
  $$(".lateral nav button[data-tela]", raiz).forEach((b) => b.addEventListener("click", () => ir(b.dataset.tela)));
  $("#p-menu").addEventListener("click", () => painel.classList.add("menu-aberto"));
  painel.addEventListener("click", (ev) => {
    if (painel.classList.contains("menu-aberto") && !ev.target.closest(".lateral") && !ev.target.closest("#p-menu"))
      painel.classList.remove("menu-aberto");
  });
  $("#p-sino").addEventListener("click", () => abrirAvisos(marcar));
  $("#p-sair").addEventListener("click", ctx.sair);
  $("#p-aparencia").addEventListener("click", () => ligarAcessibilidade(janela("Letra e tema", blocoAcessibilidade())));
  ir(itens[0].id);
  return { ir, atual: () => $("#p-titulo").textContent };
}
