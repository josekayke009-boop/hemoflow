/* HemoFlow — fundo animado da tela de login.
 *
 * - Glóbulos vermelhos flutuando em três camadas de profundidade (perto: maiores e
 *   nítidos; longe: menores e desfocados), com efeito de profundidade (parallax) ao
 *   mexer o mouse ou inclinar o celular.
 * - Logo do HemoFlow em 3D, inclinando na direção do mouse/celular.
 * - Leveza: só roda enquanto a tela de login está visível e a aba está aberta;
 *   menos células no celular; com "reduzir movimento" ligado, fica parado.
 */
(() => {
  "use strict";
  const canvas = document.getElementById("login-cells");
  const hero = document.getElementById("login-hero");
  if (!canvas || !canvas.getContext) return;
  const ctx = canvas.getContext("2d");
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const isLoginVisible = () => document.body.classList.contains("auth-required") && !document.hidden;

  let width = 0,
    height = 0,
    dpr = 1,
    cells = [],
    frame = null,
    last = 0;
  // Posição do "olhar" (-1 a 1), suavizada para o movimento não ficar brusco.
  const pointer = { x: 0, y: 0, tx: 0, ty: 0 };

  // Cada camada de profundidade: tamanho, velocidade, opacidade, desfoque e quanto se move com o parallax.
  const LAYERS = [
    { size: [10, 18], speed: 0.1, alpha: 0.35, blur: 5, parallax: 8 },
    { size: [20, 32], speed: 0.18, alpha: 0.6, blur: 2, parallax: 18 },
    { size: [36, 58], speed: 0.3, alpha: 0.92, blur: 0, parallax: 36 },
  ];

  const rand = (a, b) => a + Math.random() * (b - a);

  function makeCell(layerIndex, anywhere) {
    const layer = LAYERS[layerIndex];
    const r = rand(layer.size[0], layer.size[1]);
    return {
      layer: layerIndex,
      r,
      x: rand(-r, width + r),
      y: anywhere ? rand(-r, height + r) : height + r + rand(0, 80),
      vx: rand(-0.25, 0.25) * layer.speed * 2,
      vy: -rand(0.6, 1.1) * layer.speed,
      angle: rand(0, Math.PI * 2),
      spin: rand(-0.004, 0.004),
      flip: rand(0, Math.PI * 2), // giro no espaço: de frente (disco) até de lado (achatada)
      flipSpeed: rand(0.002, 0.008),
      squash: 1,
      wobble: rand(0, Math.PI * 2),
    };
  }

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    canvas.style.width = width + "px";
    canvas.style.height = height + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const small = width < 700;
    const counts = small ? [7, 6, 4] : [16, 12, 8];
    cells = [];
    counts.forEach((n, i) => {
      for (let k = 0; k < n; k++) cells.push(makeCell(i, true));
    });
    cells.sort((a, b) => a.layer - b.layer); // as de longe desenhadas primeiro
  }

  // Glóbulo vermelho: disco com a borda mais escura e o centro mais claro (formato bicôncavo).
  // Cada célula é desenhada UMA vez numa imagem própria (com o desfoque da camada) e depois
  // só é movida/girada a cada quadro: muito mais leve que redesenhar tudo.
  function renderSprite(r, layer) {
    const pad = Math.ceil(layer.blur * 3) + 2;
    const size = Math.ceil((r + pad) * 2 * dpr);
    const off = document.createElement("canvas");
    off.width = off.height = size;
    const g = off.getContext("2d");
    g.scale(dpr, dpr);
    g.translate(r + pad, r + pad);
    if (layer.blur) g.filter = `blur(${layer.blur}px)`;
    // Corpo: borda escura, anel vermelho vivo, centro mais claro.
    const body = g.createRadialGradient(0, 0, 0, 0, 0, r);
    body.addColorStop(0, "#c94a55");
    body.addColorStop(0.32, "#b52434");
    body.addColorStop(0.58, "#d3283a");
    body.addColorStop(0.78, "#b3142a");
    body.addColorStop(0.93, "#7c0716");
    body.addColorStop(1, "rgba(80, 3, 12, 0.85)");
    g.fillStyle = body;
    g.beginPath();
    g.arc(0, 0, r, 0, Math.PI * 2);
    g.fill();
    // Volume: luz vindo de cima à esquerda, sombra embaixo à direita.
    const light = g.createLinearGradient(-r, -r, r, r);
    light.addColorStop(0, "rgba(255, 170, 175, 0.28)");
    light.addColorStop(0.5, "rgba(255, 170, 175, 0)");
    light.addColorStop(1, "rgba(40, 0, 6, 0.38)");
    g.fillStyle = light;
    g.beginPath();
    g.arc(0, 0, r, 0, Math.PI * 2);
    g.fill();
    // Centro afundado: sombra fina na borda de cima da "covinha" e reflexo na de baixo.
    g.lineWidth = Math.max(1, r * 0.09);
    g.strokeStyle = "rgba(90, 0, 12, 0.45)";
    g.beginPath();
    g.arc(0, 0, r * 0.42, Math.PI * 1.05, Math.PI * 1.95);
    g.stroke();
    g.strokeStyle = "rgba(255, 190, 195, 0.35)";
    g.beginPath();
    g.arc(0, 0, r * 0.42, Math.PI * 0.1, Math.PI * 0.9);
    g.stroke();
    // Brilho úmido no anel superior.
    const shine = g.createRadialGradient(-r * 0.42, -r * 0.5, 0, -r * 0.42, -r * 0.5, r * 0.45);
    shine.addColorStop(0, "rgba(255, 255, 255, 0.42)");
    shine.addColorStop(1, "rgba(255, 255, 255, 0)");
    g.fillStyle = shine;
    g.beginPath();
    g.arc(0, 0, r, 0, Math.PI * 2);
    g.fill();
    return { img: off, half: r + pad };
  }

  function drawCell(c, offsetX, offsetY) {
    const layer = LAYERS[c.layer];
    if (!c.sprite) c.sprite = renderSprite(c.r, layer);
    ctx.save();
    ctx.translate(c.x + offsetX * layer.parallax, c.y + offsetY * layer.parallax);
    ctx.rotate(c.angle);
    ctx.scale(1, c.squash);
    ctx.globalAlpha = layer.alpha;
    ctx.drawImage(c.sprite.img, -c.sprite.half, -c.sprite.half, c.sprite.half * 2, c.sprite.half * 2);
    ctx.restore();
  }

  function draw() {
    ctx.clearRect(0, 0, width, height);
    for (const c of cells) drawCell(c, pointer.x, pointer.y);
  }

  function step(time) {
    frame = null;
    if (!isLoginVisible()) return; // tela de login fechada ou aba em segundo plano: para
    const dt = Math.min((time - last) / 16.67 || 1, 3);
    last = time;
    pointer.x += (pointer.tx - pointer.x) * 0.05;
    pointer.y += (pointer.ty - pointer.y) * 0.05;
    for (const c of cells) {
      c.wobble += 0.01 * dt;
      c.x += (c.vx + Math.sin(c.wobble) * 0.15) * dt;
      c.y += c.vy * dt;
      c.angle += c.spin * dt;
      c.flip += c.flipSpeed * dt;
      c.squash = 0.22 + 0.78 * Math.abs(Math.cos(c.flip));
      if (c.y < -c.r * 2 || c.x < -c.r * 3 || c.x > width + c.r * 3)
        Object.assign(c, makeCell(c.layer, false), { sprite: null });
    }
    draw();
    tiltHero();
    frame = requestAnimationFrame(step);
  }

  function tiltHero() {
    if (!hero) return;
    hero.style.setProperty("--tilt-x", (-pointer.y * 14).toFixed(2) + "deg");
    hero.style.setProperty("--tilt-y", (pointer.x * 18).toFixed(2) + "deg");
  }

  function start() {
    if (reduceMotion) {
      draw();
      return;
    }
    if (!frame && isLoginVisible()) {
      last = performance.now();
      frame = requestAnimationFrame(step);
    }
  }

  // Mouse (computador) e inclinação (celular) movem a cena.
  window.addEventListener(
    "pointermove",
    (e) => {
      pointer.tx = (e.clientX / width) * 2 - 1;
      pointer.ty = (e.clientY / height) * 2 - 1;
    },
    { passive: true },
  );
  window.addEventListener(
    "deviceorientation",
    (e) => {
      if (e.gamma == null || e.beta == null) return;
      pointer.tx = Math.max(-1, Math.min(1, e.gamma / 30));
      pointer.ty = Math.max(-1, Math.min(1, (e.beta - 45) / 30));
    },
    { passive: true },
  );
  window.addEventListener("resize", () => {
    resize();
    draw();
  });
  document.addEventListener("visibilitychange", start);
  // Quando a pessoa sai (logout) a tela de login volta: retoma a animação.
  new MutationObserver(start).observe(document.body, { attributes: true, attributeFilter: ["class"] });

  resize();
  draw();
  start();
})();
