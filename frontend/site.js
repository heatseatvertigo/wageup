// ─── Site público: páginas por endereço, demos e movimento ────────────────
// A home e as páginas de módulo vivem no mesmo index.html, cada uma num
// .lp-page. O endereço (/, /vendas, /pix…) escolhe qual aparece; o Django
// serve o mesmo HTML nesses caminhos (config/urls.py).
//
// Movimento só com opacity e transform, sem nada em loop (design-system.md,
// seção 8). Sem o GSAP (CDN fora do ar, bloqueador) ou com movimento reduzido,
// tudo continua visível e funcionando; só a animação some.
(function () {
  const shell = document.querySelector(".site-shell");
  if (!shell) return;

  const hasGsap = typeof gsap !== "undefined" && typeof ScrollTrigger !== "undefined";
  // data-reduce-motion vem do sistema ou do painel de acessibilidade (a11y.js).
  const reduced = () => !hasGsap || document.documentElement.hasAttribute("data-reduce-motion");
  if (hasGsap) gsap.registerPlugin(ScrollTrigger);

  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const fmt = (v, dec) => v.toLocaleString("pt-BR", { minimumFractionDigits: dec, maximumFractionDigits: dec });
  // "R$ 1.234,56", com o sinal de menos tipográfico antes do R$.
  const money = (v) => (v < 0 ? "−" : "") + "R$ " + fmt(Math.abs(v), 2);

  // ─── Rolagem suave ───────────────────────────────────────────────────────
  // Lenis dá inércia à roda do mouse; o toque e o teclado seguem nativos.
  // Só no site público e sem "menos movimento": no app, nos painéis e para
  // quem pediu menos movimento, a rolagem é a do navegador.
  let lenis = null;
  const tick = (t) => lenis && lenis.raf(t * 1000);
  function ligarRolagem() {
    if (lenis || !hasGsap || reduced() || typeof Lenis === "undefined" || shell.classList.contains("is-hidden")) return;
    lenis = new Lenis({ duration: 1.05, smoothWheel: true });
    lenis.on("scroll", ScrollTrigger.update);
    gsap.ticker.add(tick);
    gsap.ticker.lagSmoothing(0);
  }
  function desligarRolagem() {
    if (!lenis) return;
    gsap.ticker.remove(tick);
    lenis.destroy();
    lenis = null;
  }
  function rolarPara(alvo, { imediato = false } = {}) {
    if (lenis) lenis.scrollTo(alvo, { immediate: imediato, offset: typeof alvo === "number" ? 0 : -88 });
    else if (typeof alvo === "number") window.scrollTo({ top: alvo, behavior: imediato || reduced() ? "instant" : "smooth" });
    else alvo.scrollIntoView({ behavior: imediato || reduced() ? "auto" : "smooth" });
  }

  // ─── Páginas ─────────────────────────────────────────────────────────────
  const ROUTES = {
    "/": "home",
    "/vendas": "vendas",
    "/financeiro": "financeiro",
    "/pix": "pix",
    "/marketing": "marketing",
    "/assistente": "assistente",
    "/para-quem": "para-quem",
    "/acessibilidade": "acessibilidade",
    "/perguntas": "perguntas"
  };
  const pages = new Map($$(".lp-page", shell).map((el) => [el.dataset.page, el]));
  const main = $("#inicio");
  let current = null;
  let motion = null; // gsap.context da página aberta

  const routeOf = (pathname) => ROUTES[pathname.replace(/\/+$/, "") || "/"] || null;

  function markCurrent(path) {
    $$("a[data-route]", shell).forEach((a) => {
      const url = new URL(a.getAttribute("href"), location.origin);
      const same = url.pathname === path && !url.hash && path !== "/";
      if (same) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
  }

  function show(name, { hash = "", focus = false } = {}) {
    const page = pages.get(name) || pages.get("home");
    if (!page) return;
    const changed = current !== page.dataset.page;

    if (changed) {
      pages.forEach((el) => { el.hidden = el !== page; });
      current = page.dataset.page;
      document.title = page.dataset.title || document.title;
      markCurrent(location.pathname);
      animatePage(page);
      // A página nova aparece aos poucos: a troca não parece um corte. Só
      // opacidade: transform aqui quebraria o topo preso (position: fixed).
      if (!reduced() && hasGsap) gsap.fromTo(page, { opacity: 0 }, { opacity: 1, duration: 0.3, ease: "power1.out", clearProps: "opacity" });
      if (focus) {
        // Quem usa leitor de tela não vê a página trocar: o foco vai para o
        // conteúdo e o nome da página é anunciado.
        main?.focus({ preventScroll: true });
        window.a11yAnnounce?.(`${page.dataset.title.split("|")[0].trim()}. Página aberta.`);
      }
    }
    closeMenus();

    setTimeout(paintNav, 0);
    const target = hash && document.getElementById(hash.slice(1));
    if (target) {
      // Espera a página nova ter altura antes de rolar até a seção.
      setTimeout(() => rolarPara(target, { imediato: changed }));
    } else if (changed) {
      rolarPara(0, { imediato: true });
    }
  }

  // Links internos trocam a página sem recarregar.
  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-route]");
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey) return;
    const url = new URL(link.getAttribute("href"), location.origin);
    const name = routeOf(url.pathname);
    if (!name) return;
    event.preventDefault();
    if (url.pathname !== location.pathname || url.hash !== location.hash) {
      history.pushState({ page: name }, "", url.pathname + url.hash);
    }
    show(name, { hash: url.hash, focus: true });
  });

  document.addEventListener("click", (event) => {
    const link = event.target.closest('.site-shell a[href^="#"]:not(.skip-link)');
    if (!link || link.getAttribute("href").length < 2) return;
    const alvo = document.getElementById(link.getAttribute("href").slice(1));
    if (!alvo) return;
    event.preventDefault();
    rolarPara(alvo);
  });

  window.addEventListener("popstate", () => {
    show(routeOf(location.pathname) || "home", { hash: location.hash });
  });

  // ─── Menus ───────────────────────────────────────────────────────────────
  const nav = $("#lpNav");
  const navToggle = $(".lp-nav__toggle", nav);
  const menu = $(".lp-menu", nav);
  const menuTrigger = $(".lp-menu__trigger", nav);
  const desktop = window.matchMedia("(min-width: 60rem)");

  function setMenu(open) {
    if (!menu) return;
    menu.classList.toggle("is-open", open);
    menuTrigger.setAttribute("aria-expanded", String(open));
  }
  function setSheet(open) {
    nav.classList.toggle("is-open", open);
    navToggle.setAttribute("aria-expanded", String(open));
    navToggle.setAttribute("aria-label", open ? "Fechar menu" : "Abrir menu");
    $(".material-symbols-rounded", navToggle).textContent = open ? "close" : "menu";
    paintNav();
  }
  function closeMenus() { setMenu(false); setSheet(false); }

  // O mouse abre o painel ao passar e o clique chega logo depois: sem esta
  // folga, o clique fecharia o que o mouse acabou de abrir.
  let abertoPeloMouse = 0;
  menuTrigger?.addEventListener("click", () => {
    if (Date.now() - abertoPeloMouse < 500) return;
    setMenu(!menu.classList.contains("is-open"));
  });
  navToggle?.addEventListener("click", () => setSheet(!nav.classList.contains("is-open")));

  // No desktop o painel também abre com o mouse; um respiro evita fechar
  // no caminho entre o botão e o painel.
  let hoverTimer = null;
  menu?.addEventListener("pointerenter", (e) => {
    if (e.pointerType !== "mouse" || !desktop.matches) return;
    clearTimeout(hoverTimer);
    if (!menu.classList.contains("is-open")) abertoPeloMouse = Date.now();
    setMenu(true);
  });
  menu?.addEventListener("pointerleave", (e) => {
    if (e.pointerType !== "mouse" || !desktop.matches) return;
    hoverTimer = setTimeout(() => setMenu(false), 180);
  });
  document.addEventListener("click", (e) => {
    if (menu && !menu.contains(e.target)) setMenu(false);
    if (!nav.contains(e.target)) setSheet(false);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (menu?.classList.contains("is-open")) { setMenu(false); menuTrigger.focus(); }
    if (nav.classList.contains("is-open")) { setSheet(false); navToggle.focus(); }
  });
  desktop.addEventListener("change", () => closeMenus());

  // ─── Cabeçalho: escuro sobre as faixas escuras, claro sobre o resto ──────
  // Como no Olist: a cor acompanha a seção que está passando por baixo dele.
  const lockup = $(".lp-lockup__text", nav);
  const progresso = $(".lp-progress i", nav);
  let rotuloAtual = "";

  // Como na referência: ao rolar, o nome da página (ou da seção, na home)
  // desliza para junto do logo — "wageup▲pix". Na primeira vez entra pela
  // esquerda, saindo de trás do ▲; entre seções, o nome rola para cima.
  function trocarRotulo(novo) {
    if (novo === rotuloAtual) return;
    const anterior = rotuloAtual;
    rotuloAtual = novo;
    if (!novo) { nav.classList.remove("has-lockup"); return; }
    const colocar = () => { lockup.innerHTML = ""; const r = document.createElement("span"); r.className = "lp-lockup__roll"; r.textContent = novo; lockup.append(r); medirRotulo(); return r; };
    if (!anterior || !nav.classList.contains("has-lockup") || reduced() || !hasGsap) {
      colocar();
      nav.classList.add("has-lockup");
      return;
    }
    const velho = $(".lp-lockup__roll", lockup);
    gsap.to(velho, {
      yPercent: -100, opacity: 0, duration: 0.18, ease: "power2.in",
      onComplete: () => {
        if (rotuloAtual !== novo) return;
        const novoEl = colocar();
        gsap.fromTo(novoEl, { yPercent: 100, opacity: 0 }, { yPercent: 0, opacity: 1, duration: 0.28, ease: "power3.out" });
      }
    });
  }

  // O nome fica ao lado do logo, por cima da barra: se não couber antes do
  // primeiro link ou botão, não aparece, em vez de passar por cima deles.
  const linksDoMenu = $(".lp-nav__links", nav);
  const acoesDoMenu = $(".lp-nav__actions", nav);
  function medirRotulo() {
    const texto = $(".lp-lockup__roll", lockup);
    if (!texto) return;
    const inicio = $(".lp-nav__logo", nav).getBoundingClientRect().right;
    const vizinho = getComputedStyle(linksDoMenu).position === "static" ? linksDoMenu : acoesDoMenu;
    const espaco = vizinho.getBoundingClientRect().left - inicio - 24;
    nav.classList.toggle("is-lockup-tight", texto.scrollWidth > espaco);
  }

  function paintNav() {
    const linha = nav.getBoundingClientRect().bottom;
    // Quanto da página já foi lido.
    const total = document.documentElement.scrollHeight - window.innerHeight;
    progresso.style.transform = `scaleX(${total > 0 ? Math.min(1, window.scrollY / total) : 0})`;
    // Rótulo: a última marca que já passou por baixo do cabeçalho.
    const pagina = current && pages.get(current);
    let rotulo = "";
    if (pagina) $$("[data-lockup]", pagina).forEach((el) => {
      if (el.getBoundingClientRect().top <= linha + 4) rotulo = el.dataset.lockup;
    });
    trocarRotulo(rotulo);
    medirRotulo();

    if (nav.classList.contains("is-open")) { nav.classList.remove("is-light"); return; }
    const escuras = $$("[data-nav='dark']", shell).filter((el) => !el.closest(".lp-page[hidden]"));
    const sobreEscura = escuras.some((el) => {
      const r = el.getBoundingClientRect();
      return r.top <= linha && r.bottom > linha;
    });
    nav.classList.toggle("is-light", !sobreEscura);
  }
  // Direto no evento: são poucas medidas, e requestAnimationFrame para quando
  // a aba fica em segundo plano.
  window.addEventListener("scroll", paintNav, { passive: true });
  window.addEventListener("resize", paintNav);

  // ─── Perguntas: só a pergunta aparece; a resposta abre em cascata ────────
  // Abre ao passar o mouse (com uma pausa curta, para não abrir tudo no
  // caminho) e no clique ou Enter, para toque e teclado. Uma aberta por vez.
  // A altura não anima (design-system.md, seção 8): ela muda de uma vez e a
  // rolagem é compensada, para a pergunta sob o mouse não fugir dele.
  $$("[data-faq]", shell).forEach((lista) => {
    const itens = $$(".lp-faq__item", lista);

    // Cada frase da resposta vira um pedaço com atraso próprio: a cascata.
    itens.forEach((item) => {
      const p = $(".lp-faq__a p", item);
      const frases = p.textContent.match(/[^.!?]+[.!?]+(\s|$)/g) || [p.textContent];
      p.textContent = "";
      frases.forEach((frase, i) => {
        const pedaco = document.createElement("span");
        pedaco.className = "lp-faq__line";
        pedaco.style.setProperty("--i", i);
        pedaco.textContent = frase;
        p.append(pedaco, " ");
      });
    });

    function abrir(alvo) {
      const antes = alvo ? alvo.getBoundingClientRect().top : 0;
      itens.forEach((item) => {
        const aberto = item === alvo;
        if (item.classList.contains("is-open") === aberto) return;
        item.classList.toggle("is-open", aberto);
        $(".lp-faq__btn", item).setAttribute("aria-expanded", String(aberto));
        $(".lp-faq__a", item).hidden = !aberto;
      });
      if (alvo) {
        const depois = alvo.getBoundingClientRect().top;
        if (Math.abs(depois - antes) > 1) window.scrollBy(0, depois - antes);
      }
    }

    let espera = 0;
    itens.forEach((item) => {
      const botao = $(".lp-faq__btn", item);
      botao.addEventListener("click", () => abrir(item.classList.contains("is-open") ? null : item));
      item.addEventListener("pointerenter", (e) => {
        if (e.pointerType !== "mouse") return;
        clearTimeout(espera);
        espera = setTimeout(() => abrir(item), 120);
      });
      item.addEventListener("pointerleave", (e) => {
        if (e.pointerType === "mouse") clearTimeout(espera);
      });
    });
    // Saiu da lista com o mouse: fecha. Abaixo dela não há nada que pule.
    lista.addEventListener("pointerleave", (e) => {
      if (e.pointerType !== "mouse") return;
      clearTimeout(espera);
      espera = setTimeout(() => abrir(null), 250);
    });
  });

  // Página de acessibilidade: o botão abre o painel de verdade (a11y.js).
  $$("[data-open-a11y]", shell).forEach((botao) => {
    botao.addEventListener("click", (event) => {
      // Sem isto o clique sobe até o documento e o a11y.js o trata como
      // "clique fora do painel", fechando o que acabou de abrir.
      event.stopPropagation();
      document.getElementById("a11yTrigger")?.click();
    });
  });

  // ─── A conta de uma venda: a mesma do Product (models.py) e de productMargin() ──
  // margem = preço − (custo + embalagem/frete) − preço × (taxa% + imposto%)
  (function () {
    const form = $("#lpReceipt");
    if (!form) return;
    const inputs = { price: $("#lpPrice"), cost: $("#lpCost"), other: $("#lpOther"), fee: $("#lpFee"), tax: $("#lpTax") };
    const total = $("#lpTotal"), value = $("#lpMarginValue"), verdict = $("#lpVerdict");
    const feeAmount = $("#lpFeeAmount"), taxAmount = $("#lpTaxAmount");
    const picks = $$(".lp-pick", form);

    // Produtos da conta de demonstração (seed_demo), com os números de lá.
    const EXEMPLOS = {
      fatia:      { cada: "Cada fatia vendida",      em: "em cada fatia",      price: 7,  cost: 6,   other: 1.2, fee: 4, tax: 6 },
      brigadeiro: { cada: "Cada brigadeiro vendido", em: "em cada brigadeiro", price: 4,  cost: 1.2, other: 0.3, fee: 3, tax: 6 },
      pote:       { cada: "Cada pote vendido",       em: "em cada pote",       price: 15, cost: 5,   other: 1,   fee: 3, tax: 6 },
      seu:        { cada: "Cada venda",              em: "em cada venda",      price: 0,  cost: 0,   other: 0,   fee: 0, tax: 0 }
    };
    let unidade = EXEMPLOS.fatia;

    const parse = (el) => {
      const raw = (el.value || "").replace(/\s/g, "").replace(/R\$|%/g, "").replace(/\./g, "").replace(",", ".");
      const n = parseFloat(raw);
      return isFinite(n) && n > 0 ? n : 0;
    };
    const showNum = (n) => (n ? fmt(n, 2) : "");
    const showPct = (n) => (n ? fmt(n, n % 1 ? 1 : 0) : "");

    let shown = null;
    const paint = (margem) => { value.textContent = money(margem); };

    const update = () => {
      const price = parse(inputs.price), cost = parse(inputs.cost), other = parse(inputs.other);
      const fee = parse(inputs.fee), tax = parse(inputs.tax);
      const taxa = (price * fee) / 100, imposto = (price * tax) / 100;
      const margem = price - cost - other - taxa - imposto;
      const pct = price ? (margem / price) * 100 : 0;

      feeAmount.textContent = money(-taxa).replace("−R$ 0,00", "R$ 0,00");
      taxAmount.textContent = money(-imposto).replace("−R$ 0,00", "R$ 0,00");
      total.classList.toggle("is-negative", margem < 0);

      if (!price) verdict.innerHTML = "Digite o preço e os custos do seu produto.";
      else if (margem < 0) verdict.innerHTML = "<b>Prejuízo.</b> " + unidade.cada + " tira " + money(-margem) + " do caixa.";
      else if (margem === 0) verdict.innerHTML = "<b>Empate.</b> A venda paga os custos e não deixa nada.";
      else verdict.innerHTML = "<b>Lucro.</b> Sobram " + fmt(pct, 1) + "% do preço " + unidade.em + ".";

      // O número rola até o novo valor; com movimento reduzido, troca direto.
      if (reduced() || shown === null) {
        shown = { v: margem };
        paint(margem);
      } else {
        gsap.to(shown, { v: margem, duration: 0.4, ease: "power2.out", overwrite: true, onUpdate: () => paint(shown.v) });
      }
    };

    const setActive = (key) => picks.forEach((b) => {
      const on = b.dataset.pick === key;
      b.classList.toggle("is-active", on);
      b.setAttribute("aria-pressed", String(on));
    });

    const choose = (key) => {
      const ex = EXEMPLOS[key];
      if (!ex) return;
      unidade = ex;
      inputs.price.value = showNum(ex.price);
      inputs.cost.value = showNum(ex.cost);
      inputs.other.value = showNum(ex.other);
      inputs.fee.value = showPct(ex.fee);
      inputs.tax.value = showPct(ex.tax);
      setActive(key);
      update();
      if (key === "seu") inputs.price.focus();
    };

    picks.forEach((b) => b.addEventListener("click", () => choose(b.dataset.pick)));
    Object.values(inputs).forEach((el) => {
      el.addEventListener("input", () => {
        // Mexeu num número: o exemplo deixa de ser o da Ana e vira o seu.
        const ativo = picks.find((b) => b.classList.contains("is-active"));
        if (ativo && ativo.dataset.pick !== "seu") { setActive("seu"); unidade = EXEMPLOS.seu; }
        update();
      });
    });
    form.addEventListener("submit", (e) => e.preventDefault());
    update();
  })();

  // QR Code ilustrativo (não pode ser pago), desenhado com os tokens.
  function drawQr(svg) {
    const size = 25;
    let seed = 20260908;
    const rand = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
    const grid = Array.from({ length: size }, () => Array(size).fill(0));
    const finder = (r0, c0) => {
      for (let r = 0; r < 7; r++) for (let c = 0; c < 7; c++) {
        const border = r === 0 || r === 6 || c === 0 || c === 6;
        const core = r >= 2 && r <= 4 && c >= 2 && c <= 4;
        grid[r0 + r][c0 + c] = border || core ? 1 : 0;
      }
    };
    finder(0, 0); finder(0, size - 7); finder(size - 7, 0);
    for (let i = 8; i < size - 8; i++) {
      grid[6][i] = i % 2 === 0 ? 1 : 0;
      grid[i][6] = i % 2 === 0 ? 1 : 0;
    }
    for (let r = 0; r < size; r++) for (let c = 0; c < size; c++) {
      if (r < 9 && c < 9) continue;
      if (r < 9 && c >= size - 8) continue;
      if (r >= size - 8 && c < 9) continue;
      if (r === 6 || c === 6) continue;
      grid[r][c] = rand() > 0.5 ? 1 : 0;
    }
    let rects = "";
    for (let r = 0; r < size; r++) for (let c = 0; c < size; c++) {
      if (grid[r][c]) rects += `<rect x="${c}" y="${r}" width="1" height="1"/>`;
    }
    svg.innerHTML = rects;
  }

  // O celular do topo mostra um QR ilustrativo, como o da página do PIX.
  $$("[data-qr]", shell).forEach(drawQr);

  // ─── Demonstração de cobrança PIX (/pix) ────────────────────────────────
  (function () {
    const wrap = $("#lpQrWrap"), qr = $("#lpQr"), statusEl = $("#lpPixStatus"),
          statusText = $("#lpPixStatusText"), check = $("#lpPixCheck"), btn = $("#lpSimulate");
    if (!wrap || !btn || !qr) return;

    const state = { recebido: 2140, pendente: 360, ativas: 2 };
    const VALOR = 180;
    let fase = "nova"; // nova → aguardando → paga
    let timer = null;

    const setText = (sel, txt) => { const el = $(sel); if (el) el.textContent = txt; };
    const render = () => {
      setText("#lpPixTotal", money(state.recebido + state.pendente));
      setText("#lpRecebido", money(state.recebido));
      setText("#lpPendente", money(state.pendente));
      setText("#lpAtivas", String(Math.round(state.ativas)));
    };

    drawQr(qr);

    const pagar = () => {
      const alvo = { pendente: state.pendente - VALOR, recebido: state.recebido + VALOR, ativas: state.ativas - 1 };
      statusText.textContent = "Pago. Entrou no caixa como venda.";
      statusEl.classList.add("is-paid");
      wrap.classList.add("is-paid");
      const mostrarCheck = () => {
        check.hidden = false;
        if (!reduced()) gsap.fromTo(check, { scale: 0.6, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.35, ease: "back.out(2)" });
      };
      if (reduced()) { Object.assign(state, alvo); render(); mostrarCheck(); }
      else gsap.to(state, { ...alvo, duration: 0.4, ease: "power3.out", onUpdate: render, onComplete: mostrarCheck });
      fase = "paga";
      btn.textContent = "Gerar outra cobrança";
      btn.disabled = false;
    };

    btn.addEventListener("click", () => {
      if (fase === "aguardando") return;
      fase = "aguardando";
      btn.disabled = true;
      btn.textContent = "Esperando o cliente pagar";
      state.pendente += VALOR;
      state.ativas += 1;
      render();
      wrap.hidden = false;
      wrap.classList.remove("is-paid");
      check.hidden = true;
      statusEl.hidden = false;
      statusEl.classList.remove("is-paid");
      statusText.textContent = "Aguardando pagamento";
      if (!reduced()) gsap.fromTo(wrap, { scale: 0.9, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.35, ease: "power3.out" });
      window.clearTimeout(timer);
      timer = window.setTimeout(pagar, 2200);
    });
  })();

  // ─── Movimento ───────────────────────────────────────────────────────────
  // Cada página monta o próprio movimento quando abre e desmonta ao sair,
  // para os gatilhos de rolagem não medirem páginas escondidas.
  const REVEAL = [
    ".lp-head > *", "[data-ui]", ".lp-who__card", ".lp-mod", ".lp-step", ".mp-step",
    ".mp-feature", ".lp-stat", ".lp-faq__item", ".lp-access__item", ".mp-next__card",
    ".mp-split__copy > *", ".lp-calc__copy > *", ".lp-campaign", ".lp-h2"
  ].join(", ");

  function countUp(el, { decimals = 0, prefix = "", suffix = "" } = {}) {
    const alvo = parseFloat(el.dataset.count);
    const n = { v: 0 };
    const paint = () => { el.textContent = prefix + fmt(n.v, decimals) + suffix; };
    paint();
    return gsap.to(n, { v: alvo, duration: 1.2, ease: "power2.out", onUpdate: paint });
  }

  function animatePage(page) {
    if (motion) { motion.revert(); motion = null; }
    if (reduced()) return;

    motion = gsap.context(() => {
      let limpar = null;
      // Topo da home: a manchete palavra por palavra, depois o palco.
      const top = $(".lp-top", page);
      if (top) {
        const intro = gsap.timeline({ defaults: { ease: "power3.out", duration: 0.4 } });
        intro
          .from($(".lp-eyebrow", top), { y: 12, opacity: 0 })
          .from($(".lp-top__title", top), { y: 32, opacity: 0 }, "-=0.2")
          .from([$(".lp-top__lead", top), $(".lp-top__actions", top), $(".lp-top__proof", top)], { y: 16, opacity: 0, stagger: 0.07 }, "-=0.15")
          .from($(".lp-laptop", top), { y: 40, opacity: 0, duration: 0.5 }, 0.15)
          .from($(".lp-phone", top), { y: 56, opacity: 0, duration: 0.5 }, 0.35)
          .from($$(".lp-screen__track i", top), { scaleX: 0, duration: 0.6, stagger: 0.08, ease: "power2.out" }, 0.55);

        // O PIX do celular: aguardando e, um instante depois, pago.
        const status = $("[data-phone-status]", top);
        if (status) {
          const texto = $("[data-phone-text]", status);
          const icone = $(".material-symbols-rounded", status);
          const estado = (pago) => {
            status.classList.toggle("is-waiting", !pago);
            texto.textContent = pago ? "Pago" : "Aguardando";
            icone.textContent = pago ? "check_circle" : "schedule";
          };
          estado(false);
          intro.call(() => estado(true), null, 1.6)
            .from(status, { scale: 0.85, duration: 0.3, ease: "back.out(2)" }, 1.6);
          limpar = () => estado(true);
        }

        // Na rolagem o celular sobe um pouco mais rápido que o computador.
        gsap.to($(".lp-devices__phone", top), {
          yPercent: -14,
          ease: "none",
          scrollTrigger: { trigger: top, start: "top top", end: "bottom top", scrub: true }
        });
      }

      // Topo das páginas de módulo.
      const hero = $(".mp-hero", page);
      if (hero) {
        gsap.timeline({ defaults: { ease: "power3.out", duration: 0.4 } })
          .from($$(".mp-hero__copy > *", hero), { y: 20, opacity: 0, stagger: 0.07 })
          .from($(".mp-hero__inner > :last-child", hero), { y: 32, opacity: 0 }, 0.15);
      }

      // O "▲" do fundo desce devagar com a rolagem.
      $$(".lp-top, .mp-hero", page).forEach((el) => {
        gsap.to(el, {
          "--sprout-y": "160px",
          ease: "none",
          scrollTrigger: { trigger: el, start: "top top", end: "bottom top", scrub: true }
        });
      });

      // O resto entra quando aparece, seção por seção, em cascata.
      $$(":scope > section", page).forEach((section) => {
        if (section.matches(".lp-top, .mp-hero")) return;
        const partes = $$(REVEAL, section).filter((el) => !el.closest(".lp-top, .mp-hero") && !el.parentElement.closest("[data-ui]"));
        if (!partes.length) return;
        gsap.from(partes, {
          y: 24, opacity: 0, duration: 0.4, ease: "power3.out", stagger: 0.06,
          scrollTrigger: { trigger: section, start: "top 80%", once: true }
        });
      });

      // O caminho: a linha enche com a rolagem e cada passo acende ao chegar.
      const path = $(".lp-path", page);
      if (path) {
        gsap.fromTo($(".lp-path__track i", path), { scaleX: 0 }, {
          scaleX: 1, ease: "none",
          scrollTrigger: { trigger: $(".lp-path__steps", path), start: "top 80%", end: "bottom 55%", scrub: true }
        });
        $$(".lp-step", path).forEach((step) => {
          gsap.fromTo(step, { opacity: 0.3, y: 16 }, {
            opacity: 1, y: 0, ease: "none",
            scrollTrigger: { trigger: step, start: "top 85%", end: "top 55%", scrub: true }
          });
        });
      }

      // Barras enchem e números contam quando aparecem.
      $$(".lp-goal__bar i, .mp-bar__track i", page).forEach((barra) => {
        gsap.from(barra, { scaleX: 0, duration: 1, ease: "power2.out", scrollTrigger: { trigger: barra, start: "top 90%", once: true } });
      });
      $$(".lp-stat__value [data-count]", page).forEach((el) => {
        ScrollTrigger.create({
          trigger: el, start: "top 88%", once: true,
          onEnter: () => countUp(el, { suffix: el.dataset.suffix || "" })
        });
      });

      return limpar;
    }, page);

    ScrollTrigger.refresh();
  }

  // A landing some (vira app) e volta (logout): recalcula as posições e liga
  // ou desliga a rolagem suave, que é só do site.
  new MutationObserver(() => {
    if (shell.classList.contains("is-hidden")) { desligarRolagem(); return; }
    ligarRolagem();
    if (hasGsap) ScrollTrigger.refresh();
  }).observe(shell, { attributes: true, attributeFilter: ["class"] });

  // Pediu menos movimento no painel de acessibilidade: a rolagem volta a ser
  // a do navegador na hora, sem recarregar.
  new MutationObserver(() => {
    if (reduced()) desligarRolagem(); else ligarRolagem();
  }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-reduce-motion"] });

  ligarRolagem();

  // Primeira página: a do endereço.
  show(routeOf(location.pathname) || "home", { hash: location.hash });
})();
