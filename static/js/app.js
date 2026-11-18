/*
 * HemoFlow 2.0 — início do front-end
 *   1. Preferências e service worker (PWA)
 *   2. Entrada: login com senha ou com código por e-mail, cadastro de doador, recuperar senha
 *   3. Depois do login: abre a área certa conforme o perfil
 *        DOADOR -> js/doador.js (app de celular)   BANCO -> js/banco.js
 *        PARCEIRO -> js/parceiro.js                 ADMINISTRADOR -> js/admin.js
 * Concepção da versão 2.0 e proposta do novo front-end: João Manoel da Silva Oliveira.
 */
import { api, $, $$, aoEnviar, preferencias, opcoesUF, aviso, esc } from "./nucleo.js";

/* 1. PREFERÊNCIAS E PWA ---------------------------------------------------- */
preferencias.aplicar();
if ("serviceWorker" in navigator) {
  addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}

/* 2. ENTRADA ----------------------------------------------------------------- */
const telas = ["tela-login", "tela-cadastro", "tela-esqueci"];
function mostrarTela(id) {
  telas.forEach((t) => $("#" + t).classList.toggle("hidden", t !== id));
  $("#cartao-entrada").scrollTop = 0;
  const primeiro = $(`#${id} input`);
  if (primeiro && matchMedia("(min-width: 700px)").matches) primeiro.focus();
}
function mostrarEntrada() {
  document.body.classList.add("auth-required");
  $("#sistema").classList.add("hidden");
  $("#sistema").innerHTML = "";
  mostrarTela(new URLSearchParams(location.search).get("reset_token") ? "tela-esqueci" : "tela-login");
}

// "Ver" senha
document.addEventListener("click", (ev) => {
  const b = ev.target.closest(".ver-senha");
  if (!b) return;
  const campo = b.previousElementSibling;
  const mostrar = campo.type === "password";
  campo.type = mostrar ? "text" : "password";
  b.textContent = mostrar ? "Ocultar" : "Ver";
  b.setAttribute("aria-label", mostrar ? "Ocultar senha" : "Mostrar senha");
});

// Login: abas "com senha" / "código por e-mail"
let modoLogin = "senha";
$$("#tela-login .aba").forEach((aba) =>
  aba.addEventListener("click", () => {
    modoLogin = aba.dataset.modo;
    $$("#tela-login .aba").forEach((a) => {
      a.classList.toggle("ativa", a === aba);
      a.setAttribute("aria-selected", a === aba);
    });
    $$("#tela-login .so-senha").forEach((e) => e.classList.toggle("hidden", modoLogin !== "senha"));
    $$("#tela-login .so-codigo").forEach((e) => e.classList.toggle("hidden", modoLogin !== "codigo"));
    $("#botao-login").textContent = modoLogin === "senha" ? "Entrar" : "Entrar com o código";
  }),
);
$("#botao-enviar-codigo").addEventListener("click", async () => {
  const email = $("#form-login").email.value.trim();
  const caixa = $("#form-login .erro");
  if (!email) {
    caixa.textContent = "Digite seu e-mail para receber o código.";
    caixa.classList.remove("hidden");
    return;
  }
  try {
    const r = await api("/api/login/codigo/enviar", { email });
    caixa.classList.add("hidden");
    aviso(r.mensagem);
    $("#form-login").codigo.focus();
  } catch (e) {
    caixa.textContent = e.message;
    caixa.classList.remove("hidden");
  }
});
aoEnviar($("#form-login"), async (d) => {
  if (!d.email) throw new Error("Digite seu e-mail.");
  const r =
    modoLogin === "senha"
      ? await api("/api/login", { email: d.email, senha: d.senha })
      : await api("/api/login/codigo/entrar", { email: d.email, codigo: d.codigo });
  $("#form-login").reset();
  abrirSistema(r.usuario);
});

// Cadastro de doador
$("#form-cadastro .lista-ufs").innerHTML = opcoesUF("PE");
$("#link-cadastro").addEventListener("click", (ev) => {
  ev.preventDefault();
  mostrarTela("tela-cadastro");
});
$$(".voltar-login").forEach((a) =>
  a.addEventListener("click", (ev) => {
    ev.preventDefault();
    history.replaceState(null, "", "/");
    mostrarTela("tela-login");
  }),
);
function idade(iso) {
  if (!iso) return 99;
  const [a, m, d] = iso.split("-").map(Number);
  const h = new Date();
  return h.getFullYear() - a - (h.getMonth() + 1 < m || (h.getMonth() + 1 === m && h.getDate() < d) ? 1 : 0);
}
$("#form-cadastro").data_nascimento.addEventListener("change", (ev) => {
  const anos = idade(ev.target.value);
  $("#bloco-responsavel").classList.toggle("hidden", !(anos >= 16 && anos < 18));
});
$("#form-cadastro").cpf.addEventListener("input", (ev) => {
  const n = ev.target.value.replace(/\D/g, "").slice(0, 11);
  ev.target.value = n.replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d{1,2})$/, "$1-$2");
});
aoEnviar($("#form-cadastro"), async (d) => {
  if (idade(d.data_nascimento) < 16) throw new Error("O cadastro de doador é permitido a partir dos 16 anos.");
  const r = await api("/api/cadastro", d);
  $("#form-cadastro").reset();
  aviso("Conta criada! Bem-vindo ao HemoFlow.");
  abrirSistema(r.usuario);
});

// Recuperar senha (pedido do link e criação da nova senha)
const tokenReset = () => new URLSearchParams(location.search).get("reset_token");
$("#link-esqueci").addEventListener("click", (ev) => {
  ev.preventDefault();
  mostrarTela("tela-esqueci");
});
function prepararEsqueci() {
  const comToken = !!tokenReset();
  $("#titulo-esqueci").textContent = comToken ? "Crie sua nova senha" : "Esqueceu a senha?";
  $("#texto-esqueci").textContent = comToken
    ? "Use pelo menos 10 caracteres, com letras e números."
    : "Informe seu e-mail e enviaremos um link para criar uma nova senha.";
  $$("#form-esqueci .so-pedido").forEach((e) => e.classList.toggle("hidden", comToken));
  $$("#form-esqueci .so-nova").forEach((e) => e.classList.toggle("hidden", !comToken));
}
aoEnviar($("#form-esqueci"), async (d, form) => {
  const ok = form.querySelector(".sucesso");
  if (tokenReset()) {
    const r = await api("/api/reset-password", { token: tokenReset(), senha: d.senha });
    history.replaceState(null, "", "/");
    aviso(r.mensagem || "Senha alterada. Entre com a nova senha.");
    prepararEsqueci();
    mostrarTela("tela-login");
  } else {
    const r = await api("/api/forgot-password", { email: d.email });
    ok.textContent = r.mensagem || "Se o e-mail estiver cadastrado, enviamos o link.";
    ok.classList.remove("hidden");
  }
});

/* 3. DEPOIS DO LOGIN ----------------------------------------------------------- */
const MODULOS = {
  DOADOR: () => import("./doador.js"),
  BANCO: () => import("./banco.js"),
  PARCEIRO: () => import("./parceiro.js"),
  ADMINISTRADOR: () => import("./admin.js"),
};

export async function sair() {
  try {
    await api("/api/logout", {});
  } catch {
    /* mesmo sem rede, volta para o login */
  }
  mostrarEntrada();
}
export async function voltarAoAdmin() {
  await api("/api/sair-como", {});
  await iniciar();
}
export async function recarregar() {
  await iniciar();
}

async function abrirSistema(usuario) {
  const carregar = MODULOS[usuario.papel];
  if (!carregar) {
    aviso("Esta conta não tem uma área no HemoFlow. Procure a equipe.", "erro");
    return mostrarEntrada();
  }
  document.body.classList.remove("auth-required");
  const raiz = $("#sistema");
  raiz.classList.remove("hidden");
  raiz.innerHTML = '<p class="vazio">Carregando…</p>';
  const modulo = await carregar();
  const faixa = usuario.entrou_como
    ? `<div class="faixa-como" role="status">Você está vendo como <strong>${esc(usuario.entrou_como)}</strong> (admin)
         <span class="espaco"></span><button type="button" class="btn btn-pequeno" id="sair-como">Voltar ao painel admin</button></div>`
    : "";
  await modulo.montar(raiz, usuario, { sair, recarregar, faixa });
  $("#sair-como")?.addEventListener("click", voltarAoAdmin);
}

async function iniciar() {
  prepararEsqueci();
  try {
    const s = await api("/api/session");
    if (s.autenticado && !tokenReset()) return abrirSistema(s.usuario);
  } catch {
    /* sem rede: mostra o login */
  }
  mostrarEntrada();
}
document.addEventListener("hemoflow:sessao-expirada", () => {
  if (!document.body.classList.contains("auth-required")) {
    aviso("Sua sessão terminou. Entre de novo.", "erro");
    mostrarEntrada();
  }
});
iniciar();
