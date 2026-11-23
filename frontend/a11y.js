// ─── Acessibilidade ─────────────────────────────────────────────────────────
// Painel de preferências (tamanho do texto, contraste, espaçamento, animações,
// leitura em voz alta), atalho para o VLibras (tradutor de Libras do governo
// federal, carregado em index.html), foco preso nos diálogos e o
// "pular para o conteúdo". Carregado no <head> sem defer: as preferências
// salvas entram no <html> antes da primeira pintura, sem piscar a tela.
//
// Quem usa leitor de tela (NVDA, JAWS, VoiceOver, TalkBack) já tem o próprio
// programa: o papel da plataforma é ser lida corretamente por ele (rótulos,
// regiões, avisos). A leitura em voz alta daqui é para quem enxerga pouco ou
// lê com dificuldade e não tem leitor instalado.
(function () {
  const STORAGE_KEY = "wageup:a11y";
  const DEFAULTS = { font: "100", contrast: false, spacing: false, motion: false, speech: false };
  const FONT_SIZES = ["100", "115", "130"];
  const root = document.documentElement;

  // localStorage pode faltar (aba anônima, site bloqueado): sem ele, o painel
  // funciona e só não lembra a escolha.
  function load() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
      return { ...DEFAULTS, ...saved };
    } catch (_) {
      return { ...DEFAULTS };
    }
  }

  function save(prefs) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs)); } catch (_) { /* sem armazenamento */ }
  }

  let prefs = load();
  if (!FONT_SIZES.includes(prefs.font)) prefs.font = DEFAULTS.font;

  function applyToRoot() {
    root.dataset.font = prefs.font;
    root.toggleAttribute("data-contrast", prefs.contrast);
    root.toggleAttribute("data-spacing", prefs.spacing);
    // O "reduzir animações" do sistema operacional vale mesmo sem marcar aqui.
    const systemReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    root.toggleAttribute("data-reduce-motion", prefs.motion || systemReduced);
  }

  applyToRoot();

  // Avisos para leitor de tela: uma região "polite" fora da tela. Esvaziar e
  // preencher no quadro seguinte faz o leitor repetir um texto igual ao anterior.
  function announce(message) {
    const region = document.getElementById("a11yAnnouncer");
    if (!region) return;
    region.textContent = "";
    window.setTimeout(() => { region.textContent = message; }, 60);
  }
  window.a11yAnnounce = announce;

  // ─── Leitura em voz alta ────────────────────────────────────────────────
  const synth = "speechSynthesis" in window ? window.speechSynthesis : null;
  let readingEl = null;

  function ptVoice() {
    if (!synth) return null;
    const voices = synth.getVoices();
    return voices.find((v) => v.lang === "pt-BR") || voices.find((v) => v.lang?.startsWith("pt")) || null;
  }

  function stopSpeech() {
    if (synth) synth.cancel();
    readingEl?.classList.remove("is-a11y-reading");
    readingEl = null;
  }

  function speak(text, el) {
    if (!synth || !text) return;
    stopSpeech();
    const utterance = new SpeechSynthesisUtterance(text.replace(/\s+/g, " ").trim().slice(0, 1200));
    utterance.lang = "pt-BR";
    const voice = ptVoice();
    if (voice) utterance.voice = voice;
    utterance.rate = 1;
    if (el) {
      readingEl = el;
      el.classList.add("is-a11y-reading");
    }
    utterance.onend = utterance.onerror = () => {
      if (readingEl === el) stopSpeech();
    };
    synth.speak(utterance);
  }

  // Nome que um controle mostra a quem o ouve: rótulo explícito, depois texto.
  function accessibleName(el) {
    const labelledby = el.getAttribute("aria-labelledby");
    if (labelledby) {
      const text = labelledby.split(/\s+/).map((id) => document.getElementById(id)?.textContent || "").join(" ").trim();
      if (text) return text;
    }
    if (el.getAttribute("aria-label")) return el.getAttribute("aria-label");
    if (el.labels?.length) return el.labels[0].textContent;
    if (el.placeholder) return el.placeholder;
    return el.textContent;
  }

  const TEXT_SELECTOR = "p, h1, h2, h3, h4, h5, h6, li, td, th, dt, dd, figcaption, blockquote, label, legend, strong, small, span, article";
  const CONTROL_SELECTOR = "button, a[href], [role='button'], [role='tab'], [role='switch'], input, select, textarea";

  function onReadClick(event) {
    if (!prefs.speech) return;
    if (event.target.closest("#a11yPanel, #a11yTrigger, #vlibras-access-wrapper, #vlibras-app-root")) return;
    // Texto selecionado tem prioridade: quem seleciona quer ouvir só aquilo.
    const selection = window.getSelection()?.toString().trim();
    if (selection) { speak(selection); return; }

    const control = event.target.closest(CONTROL_SELECTOR);
    if (control) {
      // Lê o nome e deixa o clique seguir: o botão continua funcionando.
      speak(accessibleName(control), control);
      return;
    }
    const block = event.target.closest(TEXT_SELECTOR);
    if (block && block.textContent.trim()) speak(block.textContent, block);
  }

  // ─── Diálogos: foco preso e devolvido ───────────────────────────────────
  // Modais e drawers abrem por classe/atributo em app.js; daqui só observamos.
  // Ao abrir, o foco entra; Tab não escapa para a tela de trás; ao fechar, o
  // foco volta para o botão que abriu.
  const DIALOG_HOSTS = ".modal, .drawer, .pix-screen";
  const FOCUSABLE = "a[href], button:not([disabled]), input:not([disabled]):not([type='hidden']), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])";
  let lastOpener = null;

  function isShown(el) {
    return !el.hidden && el.getClientRects().length > 0;
  }

  function openDialogHost() {
    return [...document.querySelectorAll(DIALOG_HOSTS)].filter(isShown).pop() || null;
  }

  function focusables(container) {
    return [...container.querySelectorAll(FOCUSABLE)].filter((el) => el.getClientRects().length > 0 && !el.closest("[hidden]"));
  }

  function rememberOpener(event) {
    const el = event.target.closest?.(FOCUSABLE);
    if (el && !el.closest(DIALOG_HOSTS) && !el.closest("#a11yPanel")) lastOpener = el;
  }

  function watchDialogs() {
    const observer = new MutationObserver((mutations) => {
      mutations.forEach(({ target }) => {
        if (!(target instanceof HTMLElement) || !target.matches(DIALOG_HOSTS)) return;
        if (!target.hidden) {
          // app.js costuma focar o primeiro campo logo depois de abrir.
          // Só entra aqui quando ele não focou nada lá dentro.
          window.setTimeout(() => {
            if (!isShown(target) || target.contains(document.activeElement)) return;
            const dialog = target.querySelector("[role='dialog']") || target;
            const first = focusables(dialog)[0];
            if (first) first.focus();
            else { dialog.setAttribute("tabindex", "-1"); dialog.focus(); }
          }, 80);
        } else {
          const active = document.activeElement;
          const lost = !active || active === document.body || target.contains(active);
          const otherOpen = openDialogHost();
          if (lost && !otherOpen && lastOpener?.isConnected && lastOpener.getClientRects().length) {
            lastOpener.focus();
          }
        }
      });
    });
    observer.observe(document.body, { subtree: true, attributes: true, attributeFilter: ["hidden"] });
  }

  function trapTab(event) {
    if (event.key !== "Tab") return;
    const host = openDialogHost();
    if (!host) return;
    const items = focusables(host);
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    const active = document.activeElement;
    if (!host.contains(active)) {
      event.preventDefault();
      (event.shiftKey ? last : first).focus();
    } else if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }

  // ─── Pular para o conteúdo ──────────────────────────────────────────────
  // Um link só serve às três telas: vai para o que estiver visível.
  function onSkipLink(event) {
    const link = event.target.closest(".skip-link");
    if (!link) return;
    const candidates = ["#appMain", "#auth", "#onboarding", "#inicio"];
    const target = candidates.map((sel) => document.querySelector(sel)).find((el) => el && el.getClientRects().length);
    if (!target) return;
    event.preventDefault();
    if (!target.hasAttribute("tabindex")) target.setAttribute("tabindex", "-1");
    target.focus();
  }

  // ─── Animações da landing (GSAP) ────────────────────────────────────────
  // Ligar "reduzir animações" com a página aberta: as animações que ainda não
  // rodaram terminam na hora, para nada ficar invisível esperando a rolagem.
  function finishGsap() {
    if (typeof ScrollTrigger === "undefined") return;
    ScrollTrigger.getAll().forEach((trigger) => {
      trigger.animation?.progress(1);
      trigger.kill();
    });
  }

  // ─── Painel ─────────────────────────────────────────────────────────────
  function setupPanel() {
    const trigger = document.getElementById("a11yTrigger");
    const panel = document.getElementById("a11yPanel");
    if (!trigger || !panel) return;

    const switches = {
      contrast: panel.querySelector("[data-a11y='contrast']"),
      spacing: panel.querySelector("[data-a11y='spacing']"),
      motion: panel.querySelector("[data-a11y='motion']"),
      speech: panel.querySelector("[data-a11y='speech']"),
    };
    const fontInputs = [...panel.querySelectorAll("input[name='a11yFont']")];
    const librasButton = panel.querySelector("[data-a11y-libras]");
    const librasNote = panel.querySelector("[data-a11y-libras-note]");

    if (!synth) {
      const row = switches.speech?.closest(".a11y__option");
      if (row) row.hidden = true;
    }

    function syncControls() {
      fontInputs.forEach((input) => { input.checked = input.value === prefs.font; });
      Object.entries(switches).forEach(([key, input]) => { if (input) input.checked = Boolean(prefs[key]); });
    }

    function update(changes) {
      prefs = { ...prefs, ...changes };
      save(prefs);
      applyToRoot();
      if (changes.motion) finishGsap();
      if (changes.speech === false) stopSpeech();
    }

    function setOpen(open) {
      panel.hidden = !open;
      trigger.setAttribute("aria-expanded", String(open));
      if (open) {
        requestAnimationFrame(() => panel.classList.add("is-open"));
        (panel.querySelector("input:checked") || focusables(panel)[0])?.focus();
      } else {
        panel.classList.remove("is-open");
      }
    }

    trigger.addEventListener("click", () => setOpen(panel.hidden));
    panel.querySelector("[data-a11y-close]")?.addEventListener("click", () => {
      setOpen(false);
      trigger.focus();
    });

    fontInputs.forEach((input) => input.addEventListener("change", () => {
      update({ font: input.value });
      announce(`Tamanho do texto: ${input.closest("label")?.getAttribute("data-label") || input.value + "%"}.`);
    }));

    Object.entries(switches).forEach(([key, input]) => {
      input?.addEventListener("change", () => {
        update({ [key]: input.checked });
        const name = input.closest(".a11y__option")?.querySelector(".a11y__option-name")?.textContent || "";
        announce(`${name} ${input.checked ? "ligado" : "desligado"}.`);
        if (key === "speech" && input.checked) speak("Leitura em voz alta ligada. Clique em um texto para ouvir. Esc para parar.");
      });
    });

    panel.querySelector("[data-a11y-reset]")?.addEventListener("click", () => {
      prefs = { ...DEFAULTS };
      save(prefs);
      applyToRoot();
      stopSpeech();
      syncControls();
      announce("Preferências de acessibilidade restauradas.");
    });

    // VLibras: o script do governo cria sozinho o botão oficial na lateral
    // direita; este atalho abre o mesmo tradutor. Sem internet ou com o site
    // do governo fora do ar, avisa em vez de não fazer nada.
    librasButton?.addEventListener("click", () => {
      const widget = window.VLibrasWidget;
      if (widget && typeof widget.open === "function") {
        setOpen(false);
        widget.open();
      } else if (librasNote) {
        librasNote.hidden = false;
        librasNote.textContent = "O tradutor VLibras não carregou. Confira a conexão com a internet e recarregue a página.";
      }
    });

    // Clique fora fecha, como os menus da plataforma.
    document.addEventListener("click", (event) => {
      if (panel.hidden) return;
      if (event.target.closest("#a11yPanel, #a11yTrigger")) return;
      setOpen(false);
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        if (readingEl || synth?.speaking) stopSpeech();
        if (!panel.hidden) {
          setOpen(false);
          trigger.focus();
        }
      }
      // Alt + A (Option + A no Mac) abre e fecha o painel de qualquer tela.
      if (event.altKey && !event.ctrlKey && !event.metaKey && event.code === "KeyA") {
        event.preventDefault();
        const willOpen = panel.hidden;
        setOpen(willOpen);
        if (!willOpen) trigger.focus();
      }
    });

    syncControls();
  }

  document.addEventListener("DOMContentLoaded", () => {
    setupPanel();
    watchDialogs();
    document.addEventListener("click", onSkipLink);
    document.addEventListener("click", onReadClick);
    // Quem abriu o diálogo: o Safari não foca botão no clique, e clique
    // disparado por código não passa por pointerdown nem focus. O click, na
    // fase de captura, chega antes do handler do app.js que abre o modal.
    document.addEventListener("pointerdown", rememberOpener, true);
    document.addEventListener("click", rememberOpener, true);
    document.addEventListener("focusin", rememberOpener);
    document.addEventListener("keydown", trapTab);
    // As vozes do navegador chegam depois do carregamento em alguns sistemas.
    if (synth && typeof synth.onvoiceschanged !== "undefined") synth.onvoiceschanged = () => synth.getVoices();
  });
})();
