(() => {
  "use strict";
  const $ = (s, root=document) => root.querySelector(s);
  const $$ = (s, root=document) => [...root.querySelectorAll(s)];
  const bloodTypes = ["A+","A-","B+","B-","AB+","AB-","O+","O-"];
  const state = {page:"registrations", bags:[], movements:[], donors:[], summary:null, user:null, donorType:"donor", notifications:{ativas:true,total:0,itens:[]}, notifSeq:0};
  const titles = {
    registrations:["Cadastros","Profissionais licenciados e doadores"],
    overview:["Visão geral","Atualizado hoje"],
    stock:["Estoque de sangue","Atualizado hoje"],
    donors:["Doadores","Atualizado hoje"],
    movements:["Movimentações","Atualizado hoje"],
    bags:["Registro de bolsas","Atualizado hoje"],
    alerts:["Quadro de atenção","Atualizado hoje"],
    reports:["Relatórios","Atualizado hoje"],
    settings:["Configurações","Preferências do sistema"],
    accessAccounts:["Contas de acesso","Gerenciamento de usuários e perfis"]
  };
  const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const fmtDate = value => {
    if (!value) return "—";
    const d = new Date(String(value).length===10 ? value+"T00:00:00" : value);
    return Number.isNaN(d.getTime()) ? esc(value) : d.toLocaleDateString("pt-BR");
  };
  const statusLabel = s => ({DISPONIVEL:"Disponível",RESERVADA:"Reservada",TRANSFUNDIDA:"Transfundida",DESCARTADA:"Descartada",QUARENTENA:"Quarentena"}[s] || s || "—");
  const statusClass = s => s==="DISPONIVEL" ? "green" : (s==="QUARENTENA" || s==="RESERVADA" ? "amber" : "red");
  // Aviso na tela: type = "success" (verde), "error" (vermelho) ou "info" (escuro).
  function toast(message,type="info"){const el=$("#toast");$("#toast-text").textContent=message;$("#toast-icon").textContent={success:"✓",error:"!",info:"i"}[type]||"i";el.className=`toast toast-${type}`;clearTimeout(toast.timer);toast.timer=setTimeout(()=>el.classList.add("hidden"),type==="error"?6000:4000);}
  // Janela de confirmação do próprio sistema (substitui o confirm() do navegador).
  function confirmDialog({title,message,confirmLabel="Confirmar",danger=false}){
    return new Promise(resolve=>{
      const d=$("#confirm-dialog"),ok=$("#confirm-ok");
      $("#confirm-title").textContent=title;$("#confirm-message").textContent=message;
      ok.textContent=confirmLabel;ok.classList.toggle("btn-danger",danger);
      $("#confirm-icon").classList.toggle("danger",danger);$("#confirm-icon").textContent=danger?"!":"?";
      d.returnValue="";d.addEventListener("close",()=>resolve(d.returnValue==="ok"),{once:true});
      d.showModal();$("#confirm-cancel").focus();
    });
  }
  // Máscaras: formatam enquanto a pessoa digita (o servidor valida de novo).
  const onlyDigits=v=>String(v||"").replace(/\D/g,"");
  const masks={
    phone(v){const d=onlyDigits(v).slice(0,11);if(!d)return"";if(d.length<3)return`(${d}`;const r=d.slice(2);if(r.length<=4)return`(${d.slice(0,2)}) ${r}`;if(d.length<=10)return`(${d.slice(0,2)}) ${r.slice(0,4)}-${r.slice(4)}`;return`(${d.slice(0,2)}) ${r.slice(0,5)}-${r.slice(5)}`;},
    cpf(v){const d=onlyDigits(v).slice(0,11);return d.replace(/^(\d{3})(\d)/,"$1.$2").replace(/^(\d{3})\.(\d{3})(\d)/,"$1.$2.$3").replace(/\.(\d{3})(\d{1,2})$/,".$1-$2");},
    cep(v){const d=onlyDigits(v).slice(0,8);return d.length>5?`${d.slice(0,5)}-${d.slice(5)}`:d;}
  };
  // "Olhinho": mostra/oculta o que foi digitado em todos os campos de senha.
  const EYE='<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>';
  const EYE_OFF='<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9.9 4.2A10.4 10.4 0 0 1 12 4c6.5 0 10 8 10 8a17.6 17.6 0 0 1-3 4.2M6.6 6.6C3.8 8.4 2 12 2 12s3.5 7 10 7a9.7 9.7 0 0 0 5.4-1.6"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/><path d="M2 2l20 20"/></svg>';
  function enhancePasswordFields(root=document){
    $$('input[type="password"]',root).forEach(input=>{
      if(input.dataset.reveal)return;input.dataset.reveal="1";
      const wrap=document.createElement("span");wrap.className="pw-wrap";input.parentNode.insertBefore(wrap,input);wrap.appendChild(input);
      const btn=document.createElement("button");btn.type="button";btn.className="pw-toggle";btn.innerHTML=EYE;btn.setAttribute("aria-label","Mostrar senha");btn.title="Mostrar senha";
      btn.addEventListener("click",()=>{const show=input.type==="password";input.type=show?"text":"password";btn.innerHTML=show?EYE_OFF:EYE;const label=show?"Ocultar senha":"Mostrar senha";btn.setAttribute("aria-label",label);btn.title=label;input.focus();});
      wrap.appendChild(btn);
    });
  }
  enhancePasswordFields();
  document.addEventListener("input",e=>{const el=e.target,m=el&&el.dataset&&el.dataset.mask;if(m&&masks[m]){const v=masks[m](el.value);if(v!==el.value)el.value=v;}});
  async function api(url, options={}) {
    const res=await fetch(url,{credentials:"same-origin",headers:{"Content-Type":"application/json",...(options.headers||{})},...options});
    let data={};try{data=await res.json();}catch{}
    // Sem mensagem em JSON (ex.: 501 de um servidor antigo/desatualizado): explica em vez de um erro genérico.
    if(!res.ok){if(res.status===401){showLogin();}const fallback=[404,405,501].includes(res.status)?"Esta função não está disponível no servidor em execução. Reinicie o HemoFlow para carregar a versão atual.":"Não foi possível concluir a operação.";const error=new Error(data.erro||fallback);error.status=res.status;throw error;}
    return data;
  }
  // Permissões vindas do MySQL (perfil_permissoes). Servem só para esconder botões;
  // o servidor continua validando cada operação.
  const can = code => !!state.user && (state.user.is_admin || (state.user.permissoes||[]).includes(code));
  const transitionPermission = {RESERVADA:"estoque.bolsa.reservar",DISPONIVEL:"estoque.bolsa.liberar",TRANSFUNDIDA:"estoque.bolsa.transfundir",DESCARTADA:"estoque.bolsa.descartar",QUARENTENA:"estoque.bolsa.editar"};
  const canMove = () => Object.values(transitionPermission).some(can);
  // Com a tela de recuperação aberta (link do e-mail), o login não pode ficar por cima dela.
  function showLogin(){document.body.classList.add("auth-required");if($("#recovery-screen").style.display==="flex")return;$("#login-screen").style.display="flex";}
  function showApp(user){
    state.user=user||null;
    const adminLink=$("#admin-accounts-nav");
    if(adminLink) adminLink.classList.toggle("hidden",!state.user?.is_admin);
    if(!state.user?.is_admin && state.page==="accessAccounts") state.page="overview";
    if(!state.user?.is_admin && state.donorType==="staff") state.donorType="donor";
    document.body.classList.remove("auth-required");
    $("#login-screen").style.display="none";
    $("#new-movement").classList.toggle("hidden",!canMove());
    $("#operator-label").textContent=state.user?.nome||"Usuário";
    $("#operator-avatar").textContent=(state.user?.nome||"HF").split(/\s+/).filter(Boolean).slice(0,2).map(x=>x[0]).join("").toUpperCase();
    renderPage();
  }
  // Ao recarregar a página com sessão ativa, carrega os dados na hora (antes só vinham após 60 s).
  async function checkSession(){if(new URLSearchParams(location.search).get("reset_token"))return;try{const s=await api("/api/session");if(s.autenticado){showApp(s.usuario);await refreshData();}else showLogin();}catch{showLogin();}}
  $("#login-form").addEventListener("submit",async e=>{e.preventDefault();const btn=$("#login-submit"),err=$("#login-error");btn.disabled=true;btn.textContent="Entrando...";err.classList.add("hidden");try{const result=await api("/api/login",{method:"POST",body:JSON.stringify({email:$("#login-email").value.trim(),senha:$("#login-password").value})});showApp(result.usuario);await refreshData();}catch(error){err.textContent=error.message;err.classList.remove("hidden");}finally{btn.disabled=false;btn.textContent="Entrar no sistema";}});
  const recoveryScreen = $("#recovery-screen");
  const loginScreen = $("#login-screen");
  const recoveryForm = $("#recovery-form");
  let recoveryMode = "request";
  function showRecovery(mode="request") {
    recoveryMode = mode;
    loginScreen.style.display = "none";
    recoveryScreen.style.display = "flex";
    $("#recovery-error").classList.add("hidden");
    $("#recovery-success").classList.add("hidden");
    const resetting = mode === "reset";
    $("#recovery-title").textContent = resetting ? "Criar nova senha" : "Esqueceu sua senha?";
    $("#recovery-description").textContent = resetting
      ? "Defina uma nova senha para sua conta HemoFlow."
      : "Informe seu e-mail cadastrado para receber um link de recuperação.";
    $("#recovery-email-label").classList.toggle("hidden", resetting);
    $("#recovery-email").required = !resetting;
    $("#recovery-password-label").classList.toggle("hidden", !resetting);
    $("#recovery-password").required = resetting;
    $("#recovery-confirm-label").classList.toggle("hidden", !resetting);
    $("#recovery-confirm").required = resetting;
    $("#recovery-submit").textContent = resetting ? "Salvar nova senha" : "Enviar link de recuperação";
    document.body.classList.add("auth-required");
  }
  function backToLogin() {
    recoveryScreen.style.display = "none";
    loginScreen.style.display = "flex";
    $("#recovery-error").classList.add("hidden");
    $("#recovery-success").classList.add("hidden");
  }
  $("#forgot-password").addEventListener("click", e => { e.preventDefault(); history.replaceState(null, "", "/"); showRecovery("request"); });
  $("#back-to-login").addEventListener("click", e => { e.preventDefault(); history.replaceState(null, "", "/"); backToLogin(); });
  recoveryForm.addEventListener("submit", async e => {
    e.preventDefault();
    if (recoveryMode === "done") { $("#recovery-password").disabled = false; $("#recovery-confirm").disabled = false; backToLogin(); return; }
    const button = $("#recovery-submit"), error = $("#recovery-error"), success = $("#recovery-success");
    error.classList.add("hidden"); success.classList.add("hidden");
    button.disabled = true;
    try {
      if (recoveryMode === "request") {
        const result = await api("/api/forgot-password", {method:"POST", body:JSON.stringify({email:$("#recovery-email").value.trim()})});
        success.textContent = result.mensagem;
        success.classList.remove("hidden");
        recoveryForm.reset();
      } else {
        if ($("#recovery-password").value !== $("#recovery-confirm").value) throw new Error("As senhas não conferem. Digite a mesma senha nos dois campos.");
        const token = new URLSearchParams(location.search).get("reset_token") || "";
        const result = await api("/api/reset-password", {method:"POST", body:JSON.stringify({token, senha:$("#recovery-password").value})});
        success.textContent = result.mensagem;
        success.classList.remove("hidden");
        // O link é de uso único: tira o token do endereço e leva ao login.
        history.replaceState(null, "", "/");
        recoveryForm.reset();
        $("#recovery-password").disabled = true; $("#recovery-confirm").disabled = true;
        button.textContent = "Entrar com a nova senha";
        recoveryMode = "done";
      }
    } catch (err) {
      error.textContent = err.message;
      error.classList.remove("hidden");
    } finally {
      button.disabled = false;
    }
  });
  const initialResetToken = new URLSearchParams(location.search).get("reset_token");
  if (initialResetToken) showRecovery("reset");

  $("#logout-button").addEventListener("click",async()=>{try{await api("/api/logout",{method:"POST",body:"{}"});}catch{}state.user=null;showLogin();});
  $("#main-nav").addEventListener("click",e=>{const a=e.target.closest("[data-page]");if(!a)return;e.preventDefault();navigate(a.dataset.page);});
  function navigate(page){
    if(page==="accessAccounts"&&!state.user?.is_admin){toast("Somente o administrador pode gerenciar contas de acesso.");return;}
    state.page=page in titles?page:"overview";
    history.replaceState(null,"","#"+state.page);
    $$(".nav[data-page]").forEach(a=>a.classList.toggle("active",a.dataset.page===state.page));
    // No celular o menu inferior rola na horizontal: mantém o item atual visível.
    if(matchMedia("(max-width:650px)").matches){const cur=$("#main-nav .nav.active");if(cur)cur.scrollIntoView({inline:"center",block:"nearest"});}
    renderPage();
    if(["overview","stock","movements","bags","alerts","donors","reports"].includes(state.page))refreshData();
  }
  $("#new-movement").addEventListener("click",()=>openTransition());
  $("#global-search").addEventListener("input",()=>{const q=$("#global-search").value.trim().toLowerCase();const input=$("#table-search");if(input){input.value=q;renderTable(q);}});
  $("#notifications-button").addEventListener("click",e=>{e.stopPropagation();toggleNotifications();});
  document.addEventListener("click",e=>{if(!e.target.closest(".notif-wrap"))closeNotifications();});
  document.addEventListener("keydown",e=>{if(e.key==="Escape")closeNotifications();});
  $("#close-modal").addEventListener("click",closeBag);$("#cancel-modal").addEventListener("click",closeBag);
  function closeBag(){$("#bag-dialog").close();$("#bag-error").classList.add("hidden");}
  function openBag(){$("#bag-form").reset();const today=new Date().toISOString().slice(0,10);$("#bag-collected").value=today;$("#bag-expiry").value=today;$("#bag-error").classList.add("hidden");$("#bag-dialog").showModal();}
  $("#bag-form").addEventListener("submit",async e=>{e.preventDefault();const error=$("#bag-error");error.classList.add("hidden");const payload={tipo_sanguineo:$("#bag-blood").value,volume_ml:Number($("#bag-volume").value),localizacao:$("#bag-location").value.trim(),data_coleta:$("#bag-collected").value,data_validade:$("#bag-expiry").value,status:$("#bag-status").value,observacoes:$("#bag-notes").value.trim()};try{await api("/api/bags",{method:"POST",body:JSON.stringify(payload)});closeBag();toast("Bolsa registrada com sucesso.","success");await refreshData();navigate("bags");}catch(err){error.textContent=err.message;error.classList.remove("hidden");}});
  $("#close-transition").addEventListener("click",closeTransition);$("#cancel-transition").addEventListener("click",closeTransition);
  function closeTransition(){$("#transition-dialog").close();$("#transition-error").classList.add("hidden");}
  function openTransition(bag=null){if(!state.bags.length){toast("Cadastre ou carregue uma bolsa antes de movimentar.");navigate("bags");return;}const chosen=bag||state.bags.find(b=>["DISPONIVEL","RESERVADA","QUARENTENA"].includes(b.status))||state.bags[0];$("#transition-id").value=chosen.id;$("#transition-bag-label").textContent=`Bolsa ${chosen.codigo} · status atual: ${statusLabel(chosen.status)}`;const allowed=(({DISPONIVEL:["RESERVADA","TRANSFUNDIDA","DESCARTADA","QUARENTENA"],RESERVADA:["DISPONIVEL","TRANSFUNDIDA","DESCARTADA"],QUARENTENA:["DISPONIVEL","DESCARTADA"]}[chosen.status])||[]).filter(s=>can(transitionPermission[s]));if(!allowed.length){toast(`Seu perfil não pode movimentar bolsas com status ${statusLabel(chosen.status)}.`);return;}$("#transition-status").innerHTML=allowed.map(s=>`<option value="${s}">${statusLabel(s)}</option>`).join("");$("#transition-note").value="";$("#transition-error").classList.add("hidden");$("#transition-dialog").showModal();}
  $("#transition-form").addEventListener("submit",async e=>{e.preventDefault();const error=$("#transition-error");error.classList.add("hidden");try{await api(`/api/bags/${encodeURIComponent($("#transition-id").value)}/transition`,{method:"POST",body:JSON.stringify({status:$("#transition-status").value,observacao:$("#transition-note").value.trim()})});closeTransition();toast("Movimentação registrada.","success");await refreshData();navigate("movements");}catch(err){error.textContent=err.message;error.classList.remove("hidden");}});
  // allSettled: a falta de permissão em um módulo (403) não impede o carregamento dos demais.
  async function refreshData(){const notifSeq=++state.notifSeq;const results=await Promise.allSettled([api("/api/summary"),api("/api/bags"),api("/api/movements"),api("/api/donors"),api("/api/notifications")]);const [summary,bags,movements,donors,notifications]=results.map(r=>r.status==="fulfilled"?r.value:null);if(notifications&&Array.isArray(notifications.itens)&&notifSeq===state.notifSeq){state.notifications=notifications;renderNotificationBadge();}state.summary=summary&&typeof summary==="object"&&!Array.isArray(summary)?summary:null;state.bags=Array.isArray(bags)?bags:[];state.movements=Array.isArray(movements)?movements:[];state.donors=Array.isArray(donors)?donors:[];if(document.body.classList.contains("auth-required"))return;const failure=results.find(r=>r.status==="rejected"&&r.reason?.status!==403&&r.reason?.status!==401);if(failure)toast(failure.reason.message,"error");if(state.page!=="registrations"&&state.page!=="accessAccounts")renderPage();}
  function pageHeading(title,subtitle,button=""){return `<div class="page-heading"><div><h1>${title}</h1><p>${subtitle}</p></div>${button}</div>`;}
  function btnNewBag(){if(!can("estoque.bolsa.criar"))return "";return `<button class="btn btn-primary" data-action="new-bag"><span>＋</span> Registrar bolsa</button>`;}
  function stat(label,value,note,icon,cls){return `<article class="stat-card"><div class="stat-top"><span>${label}</span><span class="stat-icon ${cls}">${icon}</span></div><strong>${value??"—"}</strong><small>${note}</small></article>`;}
  function stockCount(type){return state.bags.filter(b=>b.tipo_sanguineo===type&&b.status==="DISPONIVEL"&&!b.vencida).length;}
  function stockStatus(count){if(count<=5)return ["Crítico","status-critical","red"];if(count<=10)return ["Baixo","status-low","amber"];if(count<=15)return ["Atenção","status-low","amber"];return ["Estável","status-good",""];}
  function renderOverview(){const s=state.summary||{};return pageHeading("Visão geral","Acompanhe o estoque e as movimentações de hemocomponentes.",btnNewBag())+`<section class="stats">${stat("Total de bolsas",s.total,"cadastradas no sistema","▤","icon-red")}${stat("Disponíveis",s.disponiveis,"válidas para uso","✓","icon-green")}${stat("Vencem em 7 dias",s.vencem_em_7_dias,"exigem atenção","◷","icon-amber")}${stat("Vencidas",s.vencidas,"não disponíveis para uso","!","icon-blue")}</section><section class="content-grid"><div class="panel"><div class="panel-heading"><div><h2>Estoque por tipo sanguíneo</h2><p>Níveis disponíveis por bolsa</p></div><button class="table-action" data-page="stock">Ver detalhes ›</button></div><div class="stock-grid">${bloodTypes.map(t=>{const n=(s.por_tipo||{})[t]??stockCount(t);const st=stockStatus(n);const pct=Math.min(100,Math.round(n/Math.max(1,...bloodTypes.map(x=>(s.por_tipo||{})[x]||0))*100));return `<div class="stock-row"><div class="stock-meta"><span class="blood-type">${t}</span><div><span class="stock-number">${n}</span><span class="stock-sub">bolsas</span></div><span class="stock-status ${st[1]}">${st[0]}</span></div><div class="progress"><span class="${st[2]}" style="width:${pct}%"></span></div></div>`}).join("")}</div></div><div class="panel"><div class="panel-heading"><div><h2>Movimentações recentes</h2><p>Últimas atualizações no estoque</p></div></div>${movementRows(state.movements.slice(0,5))}</div></section>`;}
  function renderStock(){return pageHeading("Estoque de sangue","Controle de disponibilidade por tipo sanguíneo e validade.",btnNewBag())+`<div class="stock-cards">${bloodTypes.map(t=>{const n=(state.summary?.por_tipo||{})[t]??stockCount(t);const st=stockStatus(n);const pct=Math.min(100,Math.round(n/Math.max(1,...bloodTypes.map(x=>(state.summary?.por_tipo||{})[x]||0))*100));const near=state.bags.filter(b=>b.tipo_sanguineo===t&&b.status==="DISPONIVEL").sort((a,b)=>String(a.data_validade).localeCompare(String(b.data_validade)))[0];return `<article class="stock-card"><div class="stock-card-top"><span class="blood-type">${t}</span><span class="stock-status ${st[1]}">${st[0]}</span></div><div class="stock-big">${n}</div><span class="stock-sub">bolsas disponíveis <span style="float:right">${pct}%</span></span><div class="progress"><span class="${st[2]}" style="width:${pct}%"></span></div><div class="expiry"><span>Próx. validade</span><b>${near?fmtDate(near.data_validade):"—"}</b></div></article>`}).join("")}</div><div class="panel" style="margin-top:25px"><div class="panel-heading"><div><h2>Lista de bolsas</h2><p>Todas as bolsas do estoque</p></div><input id="table-search" class="table-search" placeholder="Buscar bolsa..."></div><div id="bag-table">${bagTable(state.bags)}</div></div>`;}
  function bagTable(bags){if(!bags.length)return `<div class="empty-state">Nenhuma bolsa encontrada no banco.</div>`;return `<div class="table-wrap"><table><thead><tr><th>Código</th><th>Tipo</th><th>Volume</th><th>Validade</th><th>Localização</th><th>Status</th><th>Ação</th></tr></thead><tbody>${bags.map(b=>`<tr><td><strong>${esc(b.codigo)}</strong></td><td><strong style="color:var(--red)">${esc(b.tipo_sanguineo)}</strong></td><td>${esc(b.volume_ml)} ml</td><td>${fmtDate(b.data_validade)} ${b.vencida?'<span class="pill red">Vencida</span>':""}</td><td>${esc(b.localizacao)}</td><td><span class="pill ${statusClass(b.status)}">${statusLabel(b.status)}</span></td><td>${["DISPONIVEL","RESERVADA","QUARENTENA"].includes(b.status)&&canMove()?`<button class="table-action" data-action="transition" data-id="${esc(b.id)}">Movimentar</button>`:"—"}</td></tr>`).join("")}</tbody></table></div>`;}
  function movementRows(rows){if(!rows.length)return `<div class="empty-state">Ainda não há movimentações registradas.</div>`;return `<div class="table-wrap"><table><thead><tr><th>Bolsa</th><th>De</th><th>Para</th><th>Responsável</th><th>Data</th></tr></thead><tbody>${rows.map(m=>`<tr><td><strong>${esc(m.codigo||("Bolsa #"+m.bolsa_id))}</strong></td><td>${statusLabel(m.status_anterior)}</td><td><span class="pill ${statusClass(m.status_novo)}">${statusLabel(m.status_novo)}</span></td><td>${esc(m.responsavel||"Operador")}</td><td>${fmtDate(m.criado_em)}</td></tr>`).join("")}</tbody></table></div>`;}
  function renderMovements(){return pageHeading("Movimentações","Histórico completo de entradas e saídas do estoque.",canMove()?`<button class="btn btn-primary" data-action="new-transition"><span>＋</span> Nova movimentação</button>`:"")+`<section class="mini-stats"><article class="mini-stat"><strong>${state.movements.length}</strong><span>Movimentações carregadas</span></article><article class="mini-stat"><strong>${state.movements.filter(m=>m.status_novo==="DISPONIVEL").length}</strong><span>Liberações / entradas</span></article><article class="mini-stat"><strong>${state.movements.filter(m=>["TRANSFUNDIDA","DESCARTADA"].includes(m.status_novo)).length}</strong><span>Saídas registradas</span></article></section><div class="panel"><div class="panel-heading"><div><h2>Movimentações recentes</h2><p>Alterações de status das bolsas</p></div><input id="table-search" class="table-search" placeholder="Buscar movimentação..."></div><div id="movement-table">${movementRows(state.movements)}</div></div>`;}
  function renderBags(){return pageHeading("Registro de bolsas","Registre entradas e acompanhe as bolsas do estoque.",btnNewBag())+`<div class="panel"><div class="panel-heading"><div><h2>Bolsas cadastradas</h2><p>Todas as bolsas registradas</p></div><button class="btn btn-primary" data-action="new-bag"><span>＋</span> Nova bolsa</button></div><div id="bag-table">${bagTable(state.bags)}</div></div>`;}
  function renderRegistrations(){if(!can("doadores.criar")&&!state.user?.is_admin)return pageHeading("Cadastros","Cadastre doadores e profissionais licenciados com segurança.")+`<section class="panel"><div class="empty-state">Seu perfil (${esc((state.user?.perfis||[]).join(", ").replaceAll("_"," ")||"sem perfil")}) não tem permissão para cadastrar doadores. Consulte a lista em <a href="#donors" data-page="donors">Doadores</a>.</div></section>`;return pageHeading("Cadastros","Cadastre doadores e profissionais licenciados com segurança.")+`<section class="panel choice-panel"><p class="eyebrow choice-label">TIPO DE CADASTRO</p><button class="choice-option ${state.donorType==="donor"?"active":""}" data-action="donor-type" data-value="donor"><span class="choice-icon">♢</span><span><b>Novo doador</b><small>Dados pessoais e clínicos</small></span></button>${state.user?.is_admin?`<button class="choice-option ${state.donorType==="staff"?"active":""}" data-action="donor-type" data-value="staff"><span class="choice-icon">♙</span><span><b>Pessoa licenciada</b><small>Equipe profissional (sem login)</small></span></button>`:""}<div class="privacy-note"><b>♧ &nbsp; Dados protegidos</b><p>As informações são armazenadas de acordo com as normas da LGPD.</p></div></section><section class="form-panel"><div class="form-panel-heading"><span class="choice-icon" style="background:var(--red-pale);color:var(--red)">♢</span><div><h2>${state.donorType==="donor"?"Cadastro de doador":"Cadastro de pessoa licenciada"}</h2><p>Preencha os campos obrigatórios indicados com *</p></div></div><div class="form-body"><h3>Informações pessoais</h3><form id="visual-registration-form"><div class="form-grid"><label>Nome completo *<input name="nome" required maxlength="120" placeholder="Digite o nome completo"></label><label>CPF *<input name="cpf" data-mask="cpf" inputmode="numeric" maxlength="14" autocomplete="off" placeholder="000.000.000-00"></label>${state.donorType==="donor"?`<label>Data de nascimento *<input name="data_nascimento" type="date" required></label>`:""}<label>E-mail *<input name="email" type="email" required maxlength="254" placeholder="nome@exemplo.com"></label><label>Telefone *<input name="telefone" data-mask="phone" inputmode="tel" maxlength="15" required placeholder="(00) 00000-0000"></label>${state.donorType==="donor"?`<label>Tipo sanguíneo *<select name="tipo_sanguineo" required><option value="">Selecione</option>${bloodTypes.map(t=>`<option>${t}</option>`).join("")}</select></label><label>Peso (kg) *<input name="peso_kg" type="number" min="1" max="500" step="0.1" placeholder="Ex.: 72" required></label><label class="span-2">Observações<textarea name="observacoes" rows="3" maxlength="2000" placeholder="Informações adicionais"></textarea></label>`:`<label>Função *<select name="cargo" required><option value="">Selecione</option><option>Enfermagem</option><option>Laboratório</option><option>Administração</option><option>Responsável técnico</option></select></label><label>Conselho profissional<input name="registro_profissional" maxlength="80" placeholder="Ex.: COREN, CRBM"></label><label class="span-2">Observações<textarea name="observacoes" rows="3" maxlength="2000"></textarea></label>`}</div>${state.donorType==="donor"?`<h3 class="form-section-title">Endereço</h3><div class="form-grid"><label>CEP<input name="cep" data-mask="cep" inputmode="numeric" maxlength="9" placeholder="00000-000"></label><label>Rua / Avenida *<input name="logradouro" required maxlength="150" placeholder="Ex.: Rua da Aurora"></label><label>Número *<input name="numero" required maxlength="10" placeholder="Ex.: 123 ou S/N"></label><label>Complemento<input name="complemento" maxlength="80" placeholder="Apto, bloco, casa…"></label><label>Bairro *<input name="bairro" required maxlength="80" placeholder="Bairro"></label><label>Cidade *<input name="cidade" required maxlength="80" placeholder="Cidade"></label><label>Estado (UF) *<select name="uf" required><option value="">Selecione</option><option>AC</option><option>AL</option><option>AP</option><option>AM</option><option>BA</option><option>CE</option><option>DF</option><option>ES</option><option>GO</option><option>MA</option><option>MT</option><option>MS</option><option>MG</option><option>PA</option><option>PB</option><option>PR</option><option selected>PE</option><option>PI</option><option>RJ</option><option>RN</option><option>RS</option><option>RO</option><option>RR</option><option>SC</option><option>SP</option><option>SE</option><option>TO</option></select></label></div>`:""}<div class="form-error hidden" id="registration-note"></div><div class="modal-actions"><button class="btn btn-primary" type="submit">Validar cadastro</button></div></form></div></section>`;}
  function renderDonors(){const donors=state.donors||[];return pageHeading("Doadores","Gerencie os doadores cadastrados.",`<button class="btn btn-primary" data-page="registrations">Cadastrar doador</button>`)+`<section class="mini-stats"><article class="mini-stat"><strong>${donors.length}</strong><span>Doadores cadastrados</span></article><article class="mini-stat"><strong>${donors.filter(d=>d.status==="ATIVO").length}</strong><span>Cadastros ativos</span></article><article class="mini-stat"><strong>${donors.filter(d=>d.tipo_sanguineo).length}</strong><span>Com tipo sanguíneo</span></article></section><section class="panel"><div class="panel-heading"><div><h2>Lista de doadores</h2><p>Todos os doadores cadastrados</p></div><input id="donor-search" class="table-search" placeholder="Buscar doador..."></div><div id="donor-table">${donorRows(donors)}</div></section>`;}
  function donorRows(donors){if(!donors.length)return `<div class="empty-state">Nenhum doador cadastrado ainda.</div>`;return `<div class="table-wrap"><table><thead><tr><th>Código</th><th>Nome</th><th>Tipo sanguíneo</th><th>Telefone</th><th>Cidade</th><th>Status</th>${can("doadores.editar")?"<th>Ação</th>":""}</tr></thead><tbody>${donors.map(d=>`<tr><td><strong>${esc(d.codigo_ficticio)}</strong></td><td>${esc(d.nome)}${d.revisao_pendente?' <span class="pill amber" title="Cadastro sem atualização há mais de 1 ano">Atualizar cadastro</span>':""}</td><td><strong style="color:var(--red)">${esc(d.tipo_sanguineo||"—")}</strong></td><td>${esc(d.telefone||"—")}</td><td>${d.cidade?esc(d.cidade+(d.uf?"/"+d.uf:"")):"—"}</td><td><span class="pill ${d.status==="ATIVO"?"green":"amber"}">${esc(d.status||"—")}</span></td>${can("doadores.editar")?`<td class="row-actions">${d.revisao_pendente?`<button class="table-action" data-action="review-donor" data-id="${esc(d.id)}">Revisado</button>`:""}<button class="table-action danger" data-action="delete-donor" data-id="${esc(d.id)}">Excluir</button></td>`:""}</tr>`).join("")}</tbody></table></div>`;}
  function renderAlerts(){const low=bloodTypes.map(t=>({t,n:(state.summary?.por_tipo||{})[t]??stockCount(t)})).filter(x=>x.n<=15).sort((a,b)=>a.n-b.n);return pageHeading("Quadro de atenção","Prioridades que precisam de acompanhamento da equipe hoje.")+`<section class="mini-stats"><article class="mini-stat"><strong style="color:var(--red)">${low.filter(x=>x.n<=5).length}</strong><span>Estoques críticos</span></article><article class="mini-stat"><strong style="color:#bd6a00">${low.filter(x=>x.n>5).length}</strong><span>Estoques baixos</span></article><article class="mini-stat"><strong>${state.summary?.vencem_em_7_dias??"—"}</strong><span>Bolsas próximas da validade</span></article></section><section class="panel"><div class="panel-heading"><div><h2>Prioridades de estoque</h2><p>Ordenadas por menor quantidade disponível</p></div></div>${low.length?low.map(x=>`<div class="priority-row"><span class="blood-type">${x.t}</span><div class="priority-copy"><b>${x.n<=5?"Reposição imediata necessária":"Nível abaixo do recomendado"}</b><small>${x.n} bolsas disponíveis</small></div><span class="pill ${x.n<=5?"red":"amber"}">${x.n<=5?"Crítico":"Baixo"}</span><button class="table-action" data-page="stock">Resolver</button></div>`).join(""):`<div class="empty-state">Nenhum nível de estoque baixo identificado.</div>`}</section>`;}
  function renderReports(){return pageHeading("Relatórios","Indicadores e resumos do estoque disponível.")+`<section class="report-grid"><article class="report-card"><strong>${state.summary?.total??"—"}</strong><p>Bolsas cadastradas</p><span class="pill blue">Total geral</span></article><article class="report-card"><strong>${state.summary?.disponiveis??"—"}</strong><p>Bolsas disponíveis</p><span class="pill green">Estoque atual</span></article><article class="report-card"><strong>${state.summary?.vencem_em_7_dias??"—"}</strong><p>Vencem em até 7 dias</p><span class="pill amber">Acompanhar</span></article><article class="report-card"><strong>${state.summary?.vencidas??"—"}</strong><p>Bolsas vencidas</p><span class="pill red">Atenção</span></article></section><section class="panel" style="margin-top:24px"><div class="panel-heading"><div><h2>Distribuição por tipo sanguíneo</h2><p>Quantidade disponível por tipo sanguíneo</p></div></div><div class="bars">${bloodTypes.map(t=>{const n=(state.summary?.por_tipo||{})[t]??stockCount(t);const max=Math.max(1,...bloodTypes.map(x=>(state.summary?.por_tipo||{})[x]||0));return `<span title="${t}: ${n}" style="height:${Math.max(8,n/max*100)}%"></span>`}).join("")}</div><div style="display:flex;justify-content:space-around;padding:15px 0;color:var(--muted)">${bloodTypes.map(t=>`<small>${t}</small>`).join("")}</div></section>`;}
  function renderAccessAccounts(){
    if(!state.user?.is_admin){state.page="overview";return renderOverview();}
    return pageHeading("Contas de acesso","Crie usuários e defina um dos quatro perfis do HemoFlow.")+
      `<section class="panel"><div class="panel-heading"><div><h2>Nova conta de acesso</h2><p>Somente o administrador pode criar contas.</p></div></div>
      <form id="access-account-form" class="form-body"><div class="form-grid">
      <label>Nome completo *<input name="nome" maxlength="120" required placeholder="Nome do usuário"></label>
      <label>E-mail de acesso *<input name="email" type="email" maxlength="254" required placeholder="usuario@hemoflow.local"></label>
      <label>Senha inicial *<input name="senha" type="password" minlength="10" maxlength="128" required autocomplete="new-password" placeholder="Mínimo de 10 caracteres"></label>
      <label>Perfil de acesso *<select name="perfil" required><option value="">Carregando perfis...</option></select></label>
      </div><div id="access-account-note" class="form-error hidden" role="status"></div>
      <div class="modal-actions"><button class="btn btn-primary" type="submit">Criar conta</button></div></form></section>
      <section class="panel"><div class="panel-heading"><div><h2>Contas cadastradas</h2><p>Usuários registrados no banco de dados.</p></div></div><div id="access-account-table"><div class="empty-state">Carregando contas...</div></div></section>`;
  }
  function accessAccountRows(accounts){
    if(!accounts.length)return `<div class="empty-state">Nenhuma conta encontrada.</div>`;
    return `<div class="table-wrap"><table><thead><tr><th>Nome</th><th>E-mail</th><th>Perfil</th><th>Status</th></tr></thead><tbody>${accounts.map(u=>`<tr><td><strong>${esc(u.nome)}</strong></td><td>${esc(u.email)}</td><td>${esc((u.perfil||"—").replaceAll("_"," "))}</td><td><span class="pill ${u.status==="ATIVO"?"green":"amber"}">${esc(u.status||"—")}</span></td></tr>`).join("")}</tbody></table></div>`;
  }
  async function loadAccessAccounts(){
    const table=$("#access-account-table"),select=$("#access-account-form select[name='perfil']");
    try{const data=await api("/api/access-accounts");if(table)table.innerHTML=accessAccountRows(data.usuarios||[]);if(select)select.innerHTML=`<option value="">Selecione o perfil</option>`+(data.perfis||[]).map(p=>`<option value="${esc(p.nome)}">${esc(p.nome.replaceAll("_"," "))}</option>`).join("");}
    catch(err){if(table)table.innerHTML=`<div class="empty-state">${esc(err.message)}</div>`;if(select)select.innerHTML=`<option value="">Não foi possível carregar os perfis</option>`;const note=$("#access-account-note");if(note){note.classList.remove("hidden");note.style.color="var(--red)";note.textContent=err.message;}}
  }
  function renderSettings(){const on=state.notifications.ativas!==false;return pageHeading("Configurações","Preferências e informações do sistema.")+`<section class="panel"><div class="panel-heading"><div><h2>Notificações do sistema</h2><p>Alertas de estoque baixo, validade das bolsas e cadastros de doadores sem atualização há mais de 1 ano.</p></div></div><div class="form-body"><label class="switch-row"><span><b>Receber notificações</b><small id="notif-pref-status">${on?"Ativadas: os alertas aparecem no sino do topo.":"Desativadas: nenhum alerta será exibido."}</small></span><input type="checkbox" id="notif-toggle" class="switch" ${on?"checked":""}></label></div></section><section class="panel"><div class="panel-heading"><div><h2>Informações do sistema</h2><p>HemoFlow · Gestão de hemocentro</p></div></div><div class="form-body"><p><b>Usuário conectado:</b> ${esc(state.user?.nome||"Usuário")}</p><p><b>E-mail:</b> ${esc(state.user?.email||"—")}</p><p><b>Banco de dados:</b> MySQL (conectado)</p><p><b>Autenticação:</b> sessão HTTP</p></div></section>`;}
  function renderPage(){if(document.body.classList.contains("auth-required"))return;$$(".nav[data-page]").forEach(a=>a.classList.toggle("active",a.dataset.page===state.page));const [title,subtitle]=titles[state.page]||titles.overview;$("#top-title").textContent=title;$("#top-subtitle").textContent=subtitle;let html="";switch(state.page){case"overview":html=renderOverview();break;case"stock":html=renderStock();break;case"movements":html=renderMovements();break;case"bags":html=renderBags();break;case"registrations":html=renderRegistrations();break;case"donors":html=renderDonors();break;case"alerts":html=renderAlerts();break;case"reports":html=renderReports();break;case"settings":html=renderSettings();break;case"accessAccounts":html=renderAccessAccounts();break;default:html=renderOverview();}$("#page-content").innerHTML=html;bindPageActions();}
  function bindPageActions(){enhancePasswordFields($("#page-content"));const tableSearch=$("#table-search");if(tableSearch)tableSearch.addEventListener("input",()=>renderTable(tableSearch.value));const donorSearch=$("#donor-search");if(donorSearch)donorSearch.addEventListener("input",()=>{const q=donorSearch.value.toLowerCase();$("#donor-table").innerHTML=donorRows((state.donors||[]).filter(d=>[d.nome,d.codigo_ficticio,d.email,d.telefone,d.tipo_sanguineo].some(v=>String(v||"").toLowerCase().includes(q))));});const reg=$("#visual-registration-form");if(reg)reg.addEventListener("submit",async e=>{e.preventDefault();const note=$("#registration-note"),btn=reg.querySelector('button[type="submit"]');note.classList.remove("hidden");note.textContent="Salvando...";btn.disabled=true;try{const values=Object.fromEntries(new FormData(reg).entries());const endpoint=state.donorType==="donor"?"/api/donors":"/api/professionals";if(state.donorType==="staff"){values.observacoes=values.observacoes||"";}const result=await api(endpoint,{method:"POST",body:JSON.stringify(values)});note.textContent=result.mensagem||"Cadastro salvo com sucesso.";note.style.color="var(--green)";reg.reset();if(state.donorType==="donor"){toast("Doador cadastrado com sucesso.","success");await refreshData();}else{toast("Profissional cadastrado com sucesso.","success");}}catch(err){note.textContent=err.message;note.style.color="var(--red)";}finally{btn.disabled=false;}});const notifToggle=$("#notif-toggle");if(notifToggle)notifToggle.addEventListener("change",()=>setNotificationPreference(notifToggle.checked,notifToggle));const accountForm=$("#access-account-form");if(accountForm){loadAccessAccounts();accountForm.addEventListener("submit",async e=>{e.preventDefault();if(!state.user?.is_admin){toast("Acesso restrito ao administrador.");return;}const note=$("#access-account-note"),button=accountForm.querySelector('button[type="submit"]');note.classList.remove("hidden");note.style.color="var(--muted)";note.textContent="Criando conta...";button.disabled=true;try{const values=Object.fromEntries(new FormData(accountForm).entries());const result=await api("/api/access-accounts",{method:"POST",body:JSON.stringify(values)});note.style.color="var(--green)";note.textContent=result.mensagem||"Conta criada.";accountForm.reset();await loadAccessAccounts();}catch(err){note.style.color="var(--red)";note.textContent=err.message;}finally{button.disabled=false;}});}}
  // ---------- Notificações ----------
  const levelLabel={critico:"Crítico",atencao:"Atenção"};
  function renderNotificationBadge(){
    const badge=$("#notif-count"),n=state.notifications.ativas?state.notifications.total:0;
    badge.textContent=n>9?"9+":String(n);badge.classList.toggle("hidden",!n);
    $("#notifications-button").setAttribute("aria-label",n?`Notificações: ${n} não lida(s)`:"Notificações");
    if(!$("#notif-panel").classList.contains("hidden"))renderNotificationPanel();
  }
  function renderNotificationPanel(){
    const nt=state.notifications;let body;
    if(nt.ativas===false)body=`<div class="notif-empty">As notificações estão desativadas.</div>`;
    else if(!nt.itens.length)body=`<div class="notif-empty">Nenhum alerta no momento.</div>`;
    else body=nt.itens.map((i,idx)=>`<button class="notif-item ${i.nivel==="critico"?"critical":"warning"} ${i.lida?"read":""}" data-notif-index="${idx}"><span class="notif-dot"></span><span><b>${esc(i.titulo)}</b><small>${esc(i.mensagem)}</small></span><em>${i.lida?"Vista":esc(levelLabel[i.nivel]||"")}</em></button>`).join("");
    const status=nt.ativas===false?"Desativadas":(nt.total?`${nt.total} não lida(s)`:"Todas vistas");
    const markAll=nt.ativas!==false&&nt.total?`<button class="notif-markall" id="notif-markall">Marcar todas como vistas</button>`:"";
    $("#notif-panel").innerHTML=`<div class="notif-head"><b>Notificações</b><span>${status}</span></div>${markAll}<div class="notif-list">${body}</div><button class="notif-foot" data-notif-page="settings">Configurar notificações</button>`;
    $$("#notif-panel [data-notif-index]").forEach(b=>b.addEventListener("click",()=>{const item=nt.itens[Number(b.dataset.notifIndex)];closeNotifications();if(item&&!item.lida)markNotificationsRead({chaves:[item.chave]},[item]);navigate(item?item.pagina:"overview");}));
    $$("#notif-panel [data-notif-page]").forEach(b=>b.addEventListener("click",()=>{closeNotifications();navigate(b.dataset.notifPage);}));
    const all=$("#notif-markall");if(all)all.addEventListener("click",e=>{e.stopPropagation();markNotificationsRead({todas:true},nt.itens);});
  }
  // Dá baixa na hora (o número diminui sem esperar o servidor) e confirma no banco.
  async function markNotificationsRead(body,items){
    items.forEach(i=>{i.lida=true;});
    state.notifications.total=state.notifications.itens.filter(i=>!i.lida).length;
    renderNotificationBadge();
    // Uma busca que começou antes da baixa traria a lista antiga: ela é ignorada (notifSeq)
    // e a lista é buscada de novo depois que a baixa foi gravada.
    const seq=++state.notifSeq;
    try{await api("/api/notifications/read",{method:"POST",body:JSON.stringify(body)});const fresh=await api("/api/notifications");if(seq===state.notifSeq){state.notifications=fresh;renderNotificationBadge();}}
    catch(err){toast(err.message,"error");}
  }
  function toggleNotifications(){const panel=$("#notif-panel");if(panel.classList.contains("hidden")){renderNotificationPanel();panel.classList.remove("hidden");$("#notifications-button").setAttribute("aria-expanded","true");}else closeNotifications();}
  function closeNotifications(){const panel=$("#notif-panel");if(panel&&!panel.classList.contains("hidden")){panel.classList.add("hidden");$("#notifications-button").setAttribute("aria-expanded","false");}}
  async function setNotificationPreference(on,input){
    input.disabled=true;
    try{const r=await api("/api/notifications/preferences",{method:"POST",body:JSON.stringify({ativas:on})});toast(r.mensagem,"success");
      const seq=++state.notifSeq;const fresh=await api("/api/notifications");if(seq===state.notifSeq){state.notifications=fresh;renderNotificationBadge();}
      const s=$("#notif-pref-status");if(s)s.textContent=on?"Ativadas: os alertas aparecem no sino do topo.":"Desativadas: nenhum alerta será exibido.";}
    catch(err){input.checked=!on;toast(err.message,"error");}
    finally{input.disabled=false;}
  }
  async function reviewDonor(id){
    const donor=(state.donors||[]).find(d=>String(d.id)===String(id));if(!donor)return;
    if(!await confirmDialog({title:"Confirmar revisão do cadastro",message:`Os dados de ${donor.nome} foram conferidos e estão atualizados?`,confirmLabel:"Confirmar revisão"}))return;
    try{const r=await api(`/api/donors/${encodeURIComponent(id)}/review`,{method:"POST",body:"{}"});toast(r.mensagem,"success");await refreshData();}
    catch(err){toast(err.message,"error");}
  }
  async function deleteDonor(id){
    const donor=(state.donors||[]).find(d=>String(d.id)===String(id));
    if(!donor)return;
    if(!await confirmDialog({title:"Excluir doador?",message:`O cadastro de ${donor.nome} (${donor.codigo_ficticio||"sem código"}) será excluído permanentemente. Esta ação não pode ser desfeita.`,confirmLabel:"Excluir",danger:true}))return;
    try{await api(`/api/donors/${encodeURIComponent(id)}`,{method:"DELETE"});toast(`Doador ${donor.nome} excluído com sucesso.`,"success");await refreshData();}
    catch(err){toast(err.message,"error");}
  }
  function renderTable(query=""){const q=query.toLowerCase();if($("#bag-table")){$("#bag-table").innerHTML=bagTable(state.bags.filter(b=>[b.codigo,b.tipo_sanguineo,b.status,b.localizacao].some(v=>String(v||"").toLowerCase().includes(q))));}if($("#movement-table"))$("#movement-table").innerHTML=movementRows(state.movements.filter(m=>[m.codigo,m.status_anterior,m.status_novo,m.responsavel].some(v=>String(v||"").toLowerCase().includes(q))));}
  document.addEventListener("click",e=>{const action=e.target.closest("[data-action]");if(action){const a=action.dataset.action;if(a==="new-bag")openBag();if(a==="new-transition")openTransition();if(a==="transition"){const bag=state.bags.find(b=>String(b.id)===action.dataset.id);if(bag)openTransition(bag);}if(a==="delete-donor"){deleteDonor(action.dataset.id);return;}if(a==="review-donor"){reviewDonor(action.dataset.id);return;}if(a==="donor-type"){if(action.dataset.value==="staff"&&!state.user?.is_admin){toast("Somente o administrador pode cadastrar profissionais.");return;}state.donorType=action.dataset.value;renderPage();}return;}const page=e.target.closest("[data-page]");if(page&&page.tagName!=="A"){navigate(page.dataset.page);}});
  window.addEventListener("hashchange",()=>{const page=location.hash.slice(1);if(page in titles&&page!==state.page)navigate(page);});
  if(location.hash.slice(1) in titles)state.page=location.hash.slice(1);
  checkSession();
  setInterval(()=>{if(!document.body.classList.contains("auth-required"))refreshData();},60000);
})();
