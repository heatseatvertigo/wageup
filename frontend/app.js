const storageKey = "wageup-state-v1";
const authTokenKey = "wageup-auth-token";
const apiBaseUrl = window.WAGEUP_API_URL || "/api";
const googleClientId = window.WAGEUP_GOOGLE_CLIENT_ID || "";
let apiAvailable = true;
let authToken = localStorage.getItem(authTokenKey);
let currentUser = null;

const defaultState = {
  products: [
    { id: uid(), name: "Brownie premium", category: "Doces", cost: 4.5, price: 12, stock: 28 },
    { id: uid(), name: "Copo da felicidade", category: "Sobremesas", cost: 8, price: 22, stock: 14 },
    { id: uid(), name: "Kit festa pequeno", category: "Kits", cost: 38, price: 79, stock: 6 }
  ],
  transactions: [
    { id: uid(), description: "Vendas no PIX", type: "income", amount: 1800, occurred_at: daysAgoISO(0) },
    { id: uid(), description: "Insumos", type: "expense", amount: 420, occurred_at: daysAgoISO(0) },
    { id: uid(), description: "Encomenda corporativa", type: "income", amount: 960, occurred_at: daysAgoISO(3) },
    { id: uid(), description: "Embalagens", type: "expense", amount: 180, occurred_at: daysAgoISO(5) },
    { id: uid(), description: "Feira de domingo", type: "income", amount: 1240, occurred_at: daysAgoISO(34) },
    { id: uid(), description: "Reposição de estoque", type: "expense", amount: 510, occurred_at: daysAgoISO(38) },
    { id: uid(), description: "Encomendas do mês", type: "income", amount: 2100, occurred_at: daysAgoISO(66) },
    { id: uid(), description: "Taxa da maquininha", type: "expense", amount: 95, occurred_at: daysAgoISO(70) }
  ]
};

let state = loadState();
let currentPayments = [];

// Calendário da visão geral: mês atualmente em foco + rótulos pt-BR.
const CAL_MONTHS = [
  "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
];
const CAL_WEEKDAYS = ["Domingo", "Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado"];
let calendarCursor = new Date(new Date().getFullYear(), new Date().getMonth(), 1);

// Estado da tela de Movimentações. Fica aqui em cima porque render() roda no
// topo do arquivo: declarado mais abaixo, cairia na zona morta temporal.
const TX_SOURCE = {
  pix: { label: "Cobrança PIX", tone: "positive" },
  import: { label: "Extrato importado", tone: "neutral" },
  manual: { label: "Lançamento manual", tone: "neutral" }
};
let txFilter = "all";
let txMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
let txAllPeriods = false;
let txEditingId = null;
let txRange = { start: null, end: null };

const siteShell = document.querySelector(".site-shell");
const authShell = document.querySelector("#auth");

// uid e token do link de recuperação de senha, guardados só em memória
// enquanto a tela de nova senha está aberta. Declarado aqui, e não junto da
// função que o preenche, porque o boot chama essa função antes — um `let`
// abaixo dela cairia na temporal dead zone.
let passwordResetLink = null;
const onboardingShell = document.querySelector("#onboarding");
const appShell = document.querySelector("#app");
const sidebar = document.querySelector(".sidebar");
const title = document.querySelector("#view-title");
const viewTitles = {
  overview: "Visão geral",
  finance: "Movimentações",
  payments: "PIX",
  "finance-assistant": "Assistente de IA",
  products: "Produtos",
  "app-marketing": "Marketing",
  help: "Ajuda"
};

// Views que vivem dentro do grupo "Financeiro" na navegação lateral.
const FINANCE_VIEWS = ["finance", "payments", "finance-assistant"];

const demoContent = {
  overview: {
    title: "Visão do negócio",
    action: "Gerar relatório",
    metrics: [["Receita", "R$ 8.430"], ["Lucro", "R$ 3.120"], ["Estoque baixo", "4 itens"]],
    bars: [62, 38, 82, 54, 72],
    prompt: "Crie um post para vender o Kit Festa.",
    response: "Post sugerido com imagem, legenda e CTA prontos."
  },
  products: {
    title: "Catálogo e margem",
    action: "Novo produto",
    metrics: [["Produtos", "42"], ["Margem média", "58%"], ["Reposição", "4 itens"]],
    bars: [42, 78, 64, 36, 88],
    prompt: "Qual produto precisa de atenção hoje?",
    response: "Kit Festa tem boa margem e estoque baixo. Priorize reposição antes da próxima campanha."
  },
  finance: {
    title: "Controle financeiro",
    action: "Ver fluxo",
    metrics: [["Entradas", "R$ 8.430"], ["Saídas", "R$ 2.710"], ["Saldo", "R$ 5.720"]],
    bars: [74, 28, 66, 44, 81],
    prompt: "O mês está saudável?",
    response: "Saldo positivo, despesas sob controle e receita concentrada nos pedidos por PIX."
  },
  marketing: {
    title: "Marketing com IA",
    action: "Gerar campanha",
    metrics: [["Posts", "12"], ["Ideias", "36"], ["Canais", "3"]],
    bars: [34, 58, 86, 76, 48],
    prompt: "Crie mídia para vender mais no fim de semana.",
    response: "Sugestão: imagem clara do produto, oferta objetiva e CTA para finalizar pelo PIX."
  }
};

// ─── Event Listeners ─────────────────────────────────────────────────────────

document.querySelectorAll("[data-open-app]").forEach((button) => {
  button.addEventListener("click", () => openEntryFlow());
});

document.querySelectorAll("[data-close-app]").forEach((button) => {
  button.addEventListener("click", () => {
    appShell.classList.add("is-hidden");
    siteShell.classList.remove("is-hidden");
    sidebar.classList.remove("open");
    window.scrollTo({ top: 0, behavior: "instant" });
  });
});

document.querySelectorAll("[data-close-auth]").forEach((button) => {
  button.addEventListener("click", () => {
    authShell.classList.add("is-hidden");
    siteShell.classList.remove("is-hidden");
  });
});

const moduleDetails = new Map();
document.querySelectorAll(".module-detail").forEach((section) => {
  const key = section.id.replace(/^page-/, "");
  moduleDetails.set(key, section);
});

document.querySelectorAll("[data-open-module]").forEach((trigger) => {
  trigger.addEventListener("click", (event) => {
    event.preventDefault();
    openModulePage(trigger.dataset.openModule);
  });
});

document.querySelectorAll("[data-close-module]").forEach((button) => {
  button.addEventListener("click", () => closeModulePage());
});

function openModulePage(key) {
  const target = moduleDetails.get(key);
  if (!target) return;

  moduleDetails.forEach((section) => section.classList.add("is-hidden"));
  siteShell.classList.add("is-hidden");
  target.classList.remove("is-hidden");
  sidebar.classList.remove("open");
  window.scrollTo({ top: 0, behavior: "instant" });
}

function closeModulePage() {
  moduleDetails.forEach((section) => section.classList.add("is-hidden"));
  siteShell.classList.remove("is-hidden");
  window.scrollTo({ top: 0, behavior: "instant" });
}

document.querySelectorAll("[data-auth-tab]").forEach((button) => {
  button.addEventListener("click", () => setAuthTab(button.dataset.authTab));
});

document.querySelector("[data-logout]").addEventListener("click", async () => {
  await logout();
});

document.querySelector(".menu-button").addEventListener("click", () => {
  sidebar.classList.toggle("open");
});

document.querySelectorAll("[data-demo-view]").forEach((button) => {
  button.addEventListener("click", () => setDemoView(button.dataset.demoView));
});

document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => {
    if (button.dataset.adminOnly !== undefined && !canAccessFinance()) return;
    setView(button.dataset.view);
    sidebar.classList.remove("open");
  });
});

// ─── Grupo "Financeiro" na navegação lateral ────────────────────────────────
// O item não abre view nenhuma: passar o mouse revela os módulos financeiros
// em cascata e o clique apenas abre/recolhe essa cascata.

function setNavGroupOpen(group, open) {
  group.classList.toggle("is-open", open);
  group.querySelector(".nav-group__toggle")?.setAttribute("aria-expanded", String(open));
}

document.querySelectorAll("[data-nav-group]").forEach((group) => {
  const toggle = group.querySelector(".nav-group__toggle");

  toggle?.addEventListener("click", () => {
    setNavGroupOpen(group, !group.classList.contains("is-open"));
  });

  // Hover abre; ao sair, só recolhe se nenhuma view do grupo estiver ativa.
  group.addEventListener("mouseenter", () => setNavGroupOpen(group, true));
  group.addEventListener("mouseleave", () => {
    if (!group.classList.contains("has-active")) setNavGroupOpen(group, false);
  });

  // Teclado: abre ao focar qualquer item e recolhe ao sair do grupo.
  group.addEventListener("focusin", () => setNavGroupOpen(group, true));
  group.addEventListener("focusout", (event) => {
    if (group.contains(event.relatedTarget)) return;
    if (!group.classList.contains("has-active")) setNavGroupOpen(group, false);
  });
});

document.querySelector("#loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitAuthForm("/auth/login/", event.currentTarget);
});

document.querySelector("#registerForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitAuthForm("/auth/register/", event.currentTarget);
});

// Ações textuais do cartão de auth ("Esqueci minha senha", "Voltar para o
// login"). Atributo próprio porque data-auth-tab pertence às abas e carrega
// estado de aria-selected que estes botões não têm.
document.querySelectorAll("[data-auth-goto]").forEach((button) => {
  button.addEventListener("click", () => setAuthTab(button.dataset.authGoto));
});

document.querySelector("#forgotForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const error = document.querySelector("#authError");
  const success = document.querySelector("#authSuccess");
  error.textContent = "";
  success.textContent = "";

  const submitButton = form.querySelector("button[type=submit]");
  submitButton.disabled = true;
  try {
    const data = await apiRequest("/auth/password-reset/", {
      method: "POST",
      body: JSON.stringify({ email: new FormData(form).get("email") }),
      skipAuth: true
    });
    form.reset();
    // A mensagem vem do backend e é a mesma existindo a conta ou não.
    success.textContent = data.detail;
  } catch (requestError) {
    error.textContent = requestError.message;
  } finally {
    submitButton.disabled = false;
  }
});

document.querySelector("#resetForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const error = document.querySelector("#authError");
  error.textContent = "";
  document.querySelector("#authSuccess").textContent = "";

  const fields = new FormData(form);
  const password = fields.get("password");
  if (password !== fields.get("password_confirm")) {
    error.textContent = "As duas senhas precisam ser iguais.";
    return;
  }
  if (!passwordResetLink) {
    error.textContent = "Link inválido ou expirado. Peça um novo.";
    return;
  }

  const submitButton = form.querySelector("button[type=submit]");
  submitButton.disabled = true;
  try {
    await apiRequest("/auth/password-reset/confirm/", {
      method: "POST",
      body: JSON.stringify({ ...passwordResetLink, password }),
      skipAuth: true
    });
    form.reset();
    passwordResetLink = null;
    setAuthTab("login");
    document.querySelector("#authSuccess").textContent = "Senha alterada. Entre com a senha nova.";
  } catch (requestError) {
    error.textContent = requestError.message;
  } finally {
    submitButton.disabled = false;
  }
});

document.querySelector("#onboardingForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const businessName = form.get("business_name").trim();
  if (!businessName) return;

  try {
    currentUser = await apiRequest("/auth/onboarding/", {
      method: "PATCH",
      body: JSON.stringify({ business_name: businessName })
    });
  } catch {
    // If onboarding fails, proceed anyway.
  }

  onboardingShell.classList.add("is-hidden");
  await openApp();
});

// ─── Movimentações: criar, editar e filtrar ─────────────────────────────────

document.querySelector("#openTxModal")?.addEventListener("click", () => openTxModal(null));

document.querySelectorAll("[data-close-tx-modal]").forEach((el) =>
  el.addEventListener("click", closeTxModal)
);

document.querySelectorAll("[data-close-tx]").forEach((el) =>
  el.addEventListener("click", closeTxDrawer)
);

document.querySelector("#txAmount")?.addEventListener("input", (event) => {
  const input = event.target;
  input.value = centsFromMasked(input.value) ? maskMoney(input.value) : "";
});

document.querySelectorAll("[data-tx-filter]").forEach((chip) => {
  chip.addEventListener("click", () => {
    txFilter = chip.dataset.txFilter;
    document.querySelectorAll("[data-tx-filter]").forEach((outro) => {
      outro.classList.toggle("is-active", outro === chip);
    });
    renderTransactions();
  });
});

document.querySelector("#txRangeTrigger")?.addEventListener("click", (event) => {
  event.stopPropagation();
  setRangeMenuOpen(document.querySelector("#txRangePanel")?.hidden !== false);
});

document.querySelector("#txRangePrev")?.addEventListener("click", () => {
  txRangeCursor = new Date(txRangeCursor.getFullYear(), txRangeCursor.getMonth() - 1, 1);
  renderRangeCalendar();
});

document.querySelector("#txRangeNext")?.addEventListener("click", () => {
  txRangeCursor = new Date(txRangeCursor.getFullYear(), txRangeCursor.getMonth() + 1, 1);
  renderRangeCalendar();
});

document.querySelector("#txRangeApply")?.addEventListener("click", () => applyRange());
document.querySelector("#txRangeClear")?.addEventListener("click", () => clearRange());

document.querySelector("#txRangeGrid")?.addEventListener("click", (event) => {
  const celula = event.target.closest("[data-dia]");
  if (celula) pickRangeDay(celula.dataset.dia);
});

document.addEventListener("click", (event) => {
  const menu = document.querySelector("#txRangeMenu");
  if (!menu) return;
  // Escolher um dia redesenha o calendário: quando este listener roda, o botão
  // clicado já saiu do DOM e `contains` responderia "foi fora do menu",
  // fechando o painel no meio da seleção. O caminho do evento é capturado no
  // disparo e continua íntegro.
  const caminho = typeof event.composedPath === "function" ? event.composedPath() : [];
  if (caminho.includes(menu) || menu.contains(event.target)) return;
  setRangeMenuOpen(false);
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") setRangeMenuOpen(false);
});

document.querySelector("#txPrevMonth")?.addEventListener("click", () => shiftTxMonth(-1));
document.querySelector("#txNextMonth")?.addEventListener("click", () => shiftTxMonth(1));

document.querySelector("#txAllPeriods")?.addEventListener("click", (event) => {
  txAllPeriods = !txAllPeriods;
  txRange = { start: null, end: null };
  document.querySelector("#txRangeTrigger")?.classList.remove("is-active");
  event.currentTarget.classList.toggle("is-active", txAllPeriods);
  renderTransactions();
});

document.querySelector("#transactionForm")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formEl = event.currentTarget;
  const form = new FormData(formEl);
  const erro = document.querySelector("#txFormError");
  const submit = document.querySelector("#txSubmit");

  const centavos = centsFromMasked(form.get("amount"));
  if (centavos <= 0) {
    erro.textContent = "Informe um valor maior que zero.";
    erro.hidden = false;
    return;
  }

  const payload = {
    description: form.get("description").trim(),
    type: form.get("type"),
    amount: centavos / 100
  };
  const data = form.get("occurred_at");
  if (data) payload.occurred_at = `${data}T12:00:00`;

  erro.hidden = true;
  submit.disabled = true;
  const rotulo = submit.textContent;
  submit.textContent = "Salvando...";

  try {
    if (txEditingId) {
      const atualizada = apiAvailable
        ? await updateTransaction(txEditingId, payload)
        : { id: txEditingId, source: "manual", ...payload };
      const i = state.transactions.findIndex((t) => String(t.id) === String(txEditingId));
      if (i !== -1) state.transactions[i] = atualizada;
    } else {
      const criada = apiAvailable
        ? await createTransaction(payload)
        : { id: uid(), source: "manual", occurred_at: new Date().toISOString(), ...payload };
      state.transactions.unshift(criada);
    }
  } catch (requestError) {
    erro.textContent = requestError.message;
    erro.hidden = false;
    return;
  } finally {
    submit.disabled = false;
    submit.textContent = rotulo;
  }

  closeTxModal();
  persist();
  render();
});

document.querySelector("#productForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const formEl = event.currentTarget;
  const form = new FormData(formEl);
  const payload = {
    name: form.get("name").trim(),
    category: form.get("category").trim(),
    cost: Number(form.get("cost")),
    price: Number(form.get("price")),
    stock: Number(form.get("stock"))
  };

  const product = apiAvailable
    ? await createProduct(payload)
    : { id: uid(), ...payload };

  state.products.unshift(product);
  formEl.reset();
  persist();
  render();
});

document.querySelector("#campaignForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const formEl = event.currentTarget;
  const form = new FormData(formEl);
  const product = state.products.find((item) => item.id === form.get("product")) || state.products[0];
  const goal = form.get("goal");
  const channel = form.get("channel");
  const prompt = form.get("prompt").trim() || "criar uma campanha rápida";
  const margin = product ? product.price - product.cost : 0;
  const output = document.querySelector("#campaignOutput");
  const preview = document.querySelector("#imagePreview");

  if (!product) {
    output.innerHTML = `<article class="assistant-message">Cadastre um produto antes de gerar campanhas.</article>`;
    return;
  }

  output.insertAdjacentHTML("beforeend", `<article class="user-message">${escapeHtml(prompt)}</article>`);
  output.insertAdjacentHTML("beforeend", `<article class="assistant-message is-loading">Gerando campanha para ${escapeHtml(product.name)}...</article>`);
  output.scrollTop = output.scrollHeight;

  const answer = await askMarketingAi({ product, goal, channel, prompt, margin });
  output.querySelector(".is-loading").remove();
  output.insertAdjacentHTML("beforeend", `<article class="assistant-message">${answer.html}</article>`);

  preview.innerHTML = answer.imageLabel;
  formEl.reset();
  renderCampaignOptions();
  output.scrollTop = output.scrollHeight;
});

document.querySelector("#refreshPaymentsBtn").addEventListener("click", () => loadPayments());

// Filtro por status das cobranças
document.querySelectorAll("[data-status-filter]").forEach((chip) => {
  chip.addEventListener("click", () => {
    chargeFilter = chip.dataset.statusFilter;
    document.querySelectorAll("[data-status-filter]").forEach((other) => {
      other.classList.toggle("is-active", other === chip);
    });
    renderPaymentList();
  });
});

document.querySelectorAll("[data-close-charge]").forEach((el) =>
  el.addEventListener("click", closeChargeDrawer)
);

// ─── Cobrança PIX: abrir modal, criar e acompanhar ──────────────────────────

document.querySelector("#openChargeModal")?.addEventListener("click", () => openChargeModal());

document.querySelectorAll("[data-close-charge-modal]").forEach((el) =>
  el.addEventListener("click", closeChargeModal)
);

document.querySelector("#chargeProduct")?.addEventListener("change", (event) => {
  applyProductToCharge(event.target.value);
});

// Máscara de moeda: reescreve o campo a cada tecla, sempre no formato R$.
document.querySelector("#chargeAmount")?.addEventListener("input", (event) => {
  const input = event.target;
  input.value = centsFromMasked(input.value) ? maskMoney(input.value) : "";
});

document.querySelector("#pixScreenBack")?.addEventListener("click", () => closePixScreen());

document.querySelector("#pixCopyBtn")?.addEventListener("click", async (event) => {
  const button = event.currentTarget;
  try {
    await navigator.clipboard.writeText(document.querySelector("#pixBrCode").textContent);
    button.textContent = "Copiado!";
    window.setTimeout(() => { button.textContent = "Copiar código"; }, 2000);
  } catch {
    button.textContent = "Não foi possível copiar";
  }
});

document.querySelector("#chargeForm")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formEl = event.currentTarget;
  const form = new FormData(formEl);
  const error = document.querySelector("#chargeFormError");
  const submit = document.querySelector("#chargeSubmit");

  const cents = centsFromMasked(form.get("amount"));
  if (cents <= 0) {
    error.textContent = "Informe um valor maior que zero.";
    error.hidden = false;
    return;
  }

  error.hidden = true;
  submit.disabled = true;
  submit.textContent = "Gerando...";

  let payment;
  try {
    payment = await apiRequest("/payments/", {
      method: "POST",
      body: JSON.stringify({
        description: form.get("description").trim(),
        amount: cents / 100,
        customer_name: (form.get("customer_name") || "").trim(),
        customer_email: (form.get("customer_email") || "").trim(),
        customer_tax_id: (form.get("customer_tax_id") || "").trim(),
        customer_cellphone: (form.get("customer_cellphone") || "").trim()
      })
    });
  } catch (requestError) {
    error.textContent = requestError.message;
    error.hidden = false;
    return;
  } finally {
    submit.disabled = false;
    submit.textContent = "Gerar PIX";
  }

  // A cobrança existe a partir daqui: um erro de renderização não pode ser
  // reportado como falha na geração.
  currentPayments.unshift(payment);
  renderPaymentList();
  closeChargeModal();
  openPixScreen(payment);
});

// ─── Calendário (visão geral) ───────────────────────────────────────────────
document.querySelector("#calPrev")?.addEventListener("click", () => shiftCalendarMonth(-1));
document.querySelector("#calNext")?.addEventListener("click", () => shiftCalendarMonth(1));
document.querySelectorAll("[data-close-drawer]").forEach((el) =>
  el.addEventListener("click", closeDayDrawer)
);
let chartResizeTimer;
window.addEventListener("resize", () => {
  window.clearTimeout(chartResizeTimer);
  chartResizeTimer = window.setTimeout(() => renderSemesterChart(), 150);
});

// Legenda: clicar liga/desliga cada série do gráfico.
document.querySelectorAll("#chartLegend .chart-legend__item").forEach((button) => {
  button.addEventListener("click", () => {
    const key = button.dataset.series;
    const active = !chartSeries[key];
    // Mantém ao menos uma série visível.
    if (!active && Object.values(chartSeries).filter(Boolean).length === 1) return;
    chartSeries[key] = active;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
    renderSemesterChart();
  });
});

render();
// O link do e-mail vence a sessão salva: quem chega por ele quer trocar a
// senha, mesmo que o navegador ainda tenha um token válido guardado.
if (!openPasswordResetFromLink()) bootstrapSession();
initGoogleSignIn();
setDemoView("overview");
startWordRotator();

// ─── Auth & Session ───────────────────────────────────────────────────────────

function openPasswordResetFromLink() {
  const params = new URLSearchParams(window.location.search);
  const linkUid = params.get("uid");
  const linkToken = params.get("token");
  if (!linkUid || !linkToken) return false;

  passwordResetLink = { uid: linkUid, token: linkToken };

  // Tira uid e token da barra de endereço. Sem isso o token fica no histórico
  // do navegador e é reenviado se a pessoa recarregar a página depois de já
  // ter trocado a senha — o que só produziria um erro de link já usado.
  history.replaceState(null, "", window.location.pathname);

  siteShell.classList.add("is-hidden");
  appShell.classList.add("is-hidden");
  onboardingShell.classList.add("is-hidden");
  authShell.classList.remove("is-hidden");
  setAuthTab("reset");
  window.scrollTo({ top: 0, behavior: "instant" });
  return true;
}

async function bootstrapSession() {
  if (!authToken) return;
  try {
    currentUser = await apiRequest("/auth/me/");
    await openApp();
  } catch {
    localStorage.removeItem(authTokenKey);
    authToken = null;
    currentUser = null;
  }
}

function openEntryFlow() {
  if (authToken && currentUser) {
    openApp();
    return;
  }
  siteShell.classList.add("is-hidden");
  authShell.classList.remove("is-hidden");
  appShell.classList.add("is-hidden");
  onboardingShell.classList.add("is-hidden");
  setAuthTab("login");
  window.scrollTo({ top: 0, behavior: "instant" });
}

async function openApp() {
  if (!currentUser?.onboarding_completed) {
    showOnboarding();
    return;
  }
  siteShell.classList.add("is-hidden");
  authShell.classList.add("is-hidden");
  onboardingShell.classList.add("is-hidden");
  appShell.classList.remove("is-hidden");
  sidebar.classList.remove("open");
  applyUserPermissions();
  await initializeApp();
  setView(canAccessFinance() ? "overview" : "products");
  window.scrollTo({ top: 0, behavior: "instant" });
}

function showOnboarding() {
  siteShell.classList.add("is-hidden");
  authShell.classList.add("is-hidden");
  appShell.classList.add("is-hidden");
  onboardingShell.classList.remove("is-hidden");

  const input = document.querySelector("#ob-business");
  if (currentUser?.business_name) {
    input.value = currentUser.business_name;
  }
  window.scrollTo({ top: 0, behavior: "instant" });
}

function setAuthTab(tabName) {
  document.querySelectorAll("[data-auth-tab]").forEach((button) => {
    const isActive = button.dataset.authTab === tabName;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-selected", String(isActive));
    button.tabIndex = isActive ? 0 : -1;
  });
  document.querySelectorAll(".auth-form").forEach((form) => {
    form.classList.toggle("active", form.id === `${tabName}Form`);
  });
  // Nas telas de recuperação o cartão esconde as abas e o Google: no meio do
  // fluxo nenhum dos dois leva a lugar nenhum.
  const isRecovery = tabName === "forgot" || tabName === "reset";
  document.querySelector(".auth-card").classList.toggle("auth-card--recovery", isRecovery);
  document.querySelector("#authError").textContent = "";
  document.querySelector("#authSuccess").textContent = "";
}

async function submitAuthForm(path, formElement) {
  const error = document.querySelector("#authError");
  error.textContent = "";

  try {
    const payload = Object.fromEntries(new FormData(formElement).entries());
    const data = await apiRequest(path, {
      method: "POST",
      body: JSON.stringify(payload),
      skipAuth: true
    });
    authToken = data.token;
    currentUser = data.user;
    localStorage.setItem(authTokenKey, authToken);
    formElement.reset();
    await openApp();
  } catch (requestError) {
    error.textContent = requestError.message;
  }
}

async function logout() {
  if (authToken) {
    try {
      await apiRequest("/auth/logout/", { method: "POST" });
    } catch {
      // Token already invalid, local cleanup is enough.
    }
  }
  authToken = null;
  currentUser = null;
  localStorage.removeItem(authTokenKey);
  appShell.classList.add("is-hidden");
  onboardingShell.classList.add("is-hidden");
  siteShell.classList.remove("is-hidden");
  sidebar.classList.remove("open");
}

// ─── Google OAuth ─────────────────────────────────────────────────────────────

function initGoogleSignIn() {
  if (!googleClientId) {
    const fallback = document.querySelector("#googleFallback");
    if (fallback) fallback.classList.add("is-hidden");
    return;
  }

  window.handleGoogleCredential = async (response) => {
    const error = document.querySelector("#authError");
    error.textContent = "";
    try {
      const data = await apiRequest("/auth/google-signin/", {
        method: "POST",
        body: JSON.stringify({ credential: response.credential }),
        skipAuth: true
      });
      authToken = data.token;
      currentUser = data.user;
      localStorage.setItem(authTokenKey, authToken);
      await openApp();
    } catch (err) {
      error.textContent = err.message;
    }
  };

  window.addEventListener("load", () => {
    if (!window.google?.accounts) return;
    google.accounts.id.initialize({
      client_id: googleClientId,
      callback: window.handleGoogleCredential,
      ux_mode: "popup"
    });

    const wrapper = document.querySelector("#googleSignInWrapper");
    if (wrapper) {
      google.accounts.id.renderButton(wrapper, {
        type: "standard",
        shape: "rectangular",
        theme: "outline",
        size: "large",
        text: "continue_with",
        locale: "pt_BR",
        width: wrapper.offsetWidth || 340
      });
    }
  });
}

// ─── Permissions & Views ──────────────────────────────────────────────────────

function applyUserPermissions() {
  const name = currentUser?.name || currentUser?.email || "Conta";
  document.querySelector("#accountInitial").textContent = name.charAt(0).toUpperCase();
  document.querySelector("#accountName").textContent = name;
  document.querySelector("#accountRole").textContent = canAccessFinance() ? "Admin" : "Membro";

  document.querySelectorAll("[data-admin-only]").forEach((item) => {
    item.classList.toggle("is-hidden", !canAccessFinance());
  });
}

function canAccessFinance() {
  return Boolean(currentUser?.can_access_finance || currentUser?.is_admin);
}

function setView(viewName) {
  if (FINANCE_VIEWS.includes(viewName) && !canAccessFinance()) {
    viewName = "products";
  }
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("active", view.id === viewName);
  });
  document.querySelectorAll(".side-nav button").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === viewName);
  });

  // O grupo Financeiro fica aberto e destacado enquanto uma de suas views
  // estiver ativa, para o usuário não perder de vista onde está.
  const group = document.querySelector("[data-nav-group]");
  if (group) {
    const insideGroup = FINANCE_VIEWS.includes(viewName);
    group.classList.toggle("has-active", insideGroup);
    if (insideGroup) setNavGroupOpen(group, true);
  }

  title.textContent = viewTitles[viewName] || "Wage Up";
  // A tela do assistente esconde o título da página: a barra do chat basta.
  document.querySelector(".dashboard")?.classList.toggle("is-chat", viewName === "finance-assistant");
  // A navegação fica recolhida em trilha de ícones em toda a plataforma e se
  // abre ao passar o mouse ou receber foco pelo teclado.
  appShell.classList.add("is-rail");
  if (viewName === "overview") { renderSummary(); renderCalendar(); renderSemesterChart(); }
  if (viewName === "payments") loadPayments();
  // A conversa vive no servidor: ao abrir a tela, restaura o histórico.
  if (viewName === "finance-assistant" && !currentConversationId) startNewConversation();
}

function setDemoView(viewName) {
  const content = demoContent[viewName];
  if (!content) return;
  if (!document.querySelector("#demoTitle")) return;
  document.querySelectorAll("[data-demo-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.demoView === viewName);
  });
  document.querySelector("#demoTitle").textContent = content.title;
  document.querySelector("#demoAction").textContent = content.action;
  document.querySelector("#demoPrompt").textContent = content.prompt;
  document.querySelector("#demoResponse").textContent = content.response;

  const metricIds = [
    ["#demoMetricOneLabel", "#demoMetricOne"],
    ["#demoMetricTwoLabel", "#demoMetricTwo"],
    ["#demoMetricThreeLabel", "#demoMetricThree"]
  ];
  metricIds.forEach(([labelId, valueId], index) => {
    document.querySelector(labelId).textContent = content.metrics[index][0];
    document.querySelector(valueId).textContent = content.metrics[index][1];
  });
  document.querySelectorAll("#demoChart span").forEach((bar, index) => {
    bar.style.height = `${content.bars[index]}%`;
  });
}

const heroRotatorWords = [
  "vender mais",
  "organizar o catálogo",
  "controlar o financeiro",
  "criar campanhas com IA",
  "receber via PIX"
];

function startWordRotator() {
  const word = document.querySelector("#heroRotatorWord");
  if (!word) return;
  let index = 0;
  word.classList.add("is-entering");
  setInterval(() => {
    word.classList.remove("is-entering");
    word.classList.add("is-leaving");
    window.setTimeout(() => {
      index = (index + 1) % heroRotatorWords.length;
      word.textContent = heroRotatorWords[index];
      word.classList.remove("is-leaving");
      void word.offsetWidth;
      word.classList.add("is-entering");
    }, 340);
  }, 2600);
}

// ─── Render ───────────────────────────────────────────────────────────────────

function render() {
  renderSummary();
  renderTransactions();
  renderProducts();
  renderCampaignOptions();
  renderCalendar();
  renderSemesterChart();
}

// ─── Calendário e resumo por mês ────────────────────────────────────────────

function dateKey(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function transactionDate(transaction) {
  const raw = transaction.occurred_at || transaction.created_at;
  return raw ? new Date(raw) : new Date();
}

function transactionsByDay() {
  const map = {};
  state.transactions.forEach((transaction) => {
    const key = dateKey(transactionDate(transaction));
    if (!map[key]) map[key] = { income: 0, expense: 0, items: [] };
    const amount = Number(transaction.amount) || 0;
    if (transaction.type === "income") map[key].income += amount;
    else map[key].expense += amount;
    map[key].items.push(transaction);
  });
  return map;
}

function renderSummary() {
  const year = calendarCursor.getFullYear();
  const month = calendarCursor.getMonth();
  let income = 0;
  let expense = 0;
  state.transactions.forEach((transaction) => {
    const date = transactionDate(transaction);
    if (date.getFullYear() !== year || date.getMonth() !== month) return;
    const amount = Number(transaction.amount) || 0;
    if (transaction.type === "income") income += amount;
    else expense += amount;
  });

  const profit = income - expense;
  const profitEl = document.querySelector("#ov-profit");
  const expenseEl = document.querySelector("#ov-expenses");
  if (profitEl) {
    profitEl.textContent = formatMoney(profit);
    profitEl.classList.toggle("value-positive", profit >= 0);
    profitEl.classList.toggle("value-negative", profit < 0);
  }
  if (expenseEl) expenseEl.textContent = formatMoney(expense);
}

function renderCalendar() {
  const grid = document.querySelector("#calGrid");
  const label = document.querySelector("#calMonthLabel");
  if (!grid || !label) return;

  const year = calendarCursor.getFullYear();
  const month = calendarCursor.getMonth();
  label.textContent = `${CAL_MONTHS[month]} de ${year}`;

  const byDay = transactionsByDay();
  const firstWeekday = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const todayKey = dateKey(new Date());

  let cells = "";
  for (let i = 0; i < firstWeekday; i += 1) {
    cells += `<span class="calendar__cell calendar__cell--empty" aria-hidden="true"></span>`;
  }
  for (let day = 1; day <= daysInMonth; day += 1) {
    const key = dateKey(new Date(year, month, day));
    const info = byDay[key];
    const hasData = Boolean(info && info.items.length);
    const isToday = key === todayKey;
    cells += `
      <button type="button" role="gridcell"
        class="calendar__cell${isToday ? " is-today" : ""}${hasData ? " has-data" : ""}"
        data-day="${key}" aria-label="Dia ${day}${hasData ? ", com movimentações" : ""}">
        <span class="calendar__day">${day}</span>
        ${hasData ? `<span class="calendar__marks">
          ${info.income ? `<span class="calendar__mark calendar__mark--in" title="Entradas"></span>` : ""}
          ${info.expense ? `<span class="calendar__mark calendar__mark--out" title="Saídas"></span>` : ""}
        </span>` : ""}
      </button>`;
  }
  grid.innerHTML = cells;

  grid.querySelectorAll("[data-day]").forEach((cell) => {
    cell.addEventListener("click", () => openDayDrawer(cell.dataset.day));
  });
}

function shiftCalendarMonth(delta) {
  calendarCursor = new Date(calendarCursor.getFullYear(), calendarCursor.getMonth() + delta, 1);
  renderSummary();
  renderCalendar();
  renderSemesterChart();
}

function openDayDrawer(key) {
  const drawer = document.querySelector("#dayDrawer");
  if (!drawer) return;

  const info = transactionsByDay()[key] || { income: 0, expense: 0, items: [] };
  const [y, m, d] = key.split("-").map(Number);
  const dateObj = new Date(y, m - 1, d);

  document.querySelector("#drawerDate").textContent = `${d} de ${CAL_MONTHS[m - 1]} de ${y}`;
  document.querySelector("#drawerWeekday").textContent = CAL_WEEKDAYS[dateObj.getDay()];
  document.querySelector("#drawerIncome").textContent = formatMoney(info.income);
  document.querySelector("#drawerExpense").textContent = formatMoney(info.expense);

  const net = info.income - info.expense;
  const netEl = document.querySelector("#drawerNet");
  netEl.textContent = formatMoney(net);
  netEl.classList.toggle("value-positive", net >= 0);
  netEl.classList.toggle("value-negative", net < 0);

  const list = document.querySelector("#drawerList");
  if (!info.items.length) {
    list.innerHTML = `<p class="drawer__empty">Nenhuma movimentação registrada neste dia.</p>`;
  } else {
    list.innerHTML = info.items.map((transaction) => {
      const isIncome = transaction.type === "income";
      return `
        <div class="drawer__item">
          <div class="drawer__item-info">
            <strong>${escapeHtml(transaction.description)}</strong>
            <span class="drawer__item-type drawer__item-type--${isIncome ? "in" : "out"}">
              ${isIncome ? "Entrada" : "Saída"}
            </span>
          </div>
          <span class="value-currency ${isIncome ? "value-positive" : "value-negative"}">
            ${isIncome ? "+" : "−"} ${formatMoney(transaction.amount)}
          </span>
        </div>`;
    }).join("");
  }

  drawer.hidden = false;
  requestAnimationFrame(() => drawer.classList.add("is-open"));
  document.addEventListener("keydown", drawerEscHandler);
}

function closeDayDrawer() {
  const drawer = document.querySelector("#dayDrawer");
  if (!drawer) return;
  drawer.classList.remove("is-open");
  document.removeEventListener("keydown", drawerEscHandler);
  window.setTimeout(() => { drawer.hidden = true; }, 300);
}

function drawerEscHandler(event) {
  if (event.key === "Escape") closeDayDrawer();
}

// ─── Gráfico interativo do semestre ─────────────────────────────────────────

const CHART_MONTH_SHORT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const chartSeries = { income: true, expense: true, net: true };

function formatMoneyCompact(value) {
  const format = Math.abs(value) >= 1000
    ? { notation: "compact", maximumFractionDigits: 1 }
    : { maximumFractionDigits: 0 };
  return `R$ ${new Intl.NumberFormat("pt-BR", format).format(value || 0)}`;
}

// Passo "redondo" (1, 2, 2.5, 5, 10 × potência de 10) para a escala do eixo Y.
function niceStep(range, steps) {
  const raw = range / steps;
  if (raw <= 0) return 1;
  const power = Math.pow(10, Math.floor(Math.log10(raw)));
  const unit = raw / power;
  const nice = unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 2.5 ? 2.5 : unit <= 5 ? 5 : 10;
  return nice * power;
}

// Totais dos 6 meses que terminam no mês aberto no calendário.
function semesterData() {
  const months = [];
  for (let offset = 5; offset >= 0; offset -= 1) {
    const ref = new Date(calendarCursor.getFullYear(), calendarCursor.getMonth() - offset, 1);
    let income = 0;
    let expense = 0;
    state.transactions.forEach((transaction) => {
      const date = transactionDate(transaction);
      if (date.getFullYear() !== ref.getFullYear() || date.getMonth() !== ref.getMonth()) return;
      const amount = Number(transaction.amount) || 0;
      if (transaction.type === "income") income += amount;
      else expense += amount;
    });
    months.push({
      year: ref.getFullYear(),
      month: ref.getMonth(),
      label: `${CHART_MONTH_SHORT[ref.getMonth()]}/${String(ref.getFullYear()).slice(2)}`,
      fullLabel: `${CAL_MONTHS[ref.getMonth()]} de ${ref.getFullYear()}`,
      income,
      expense,
      net: income - expense,
      isCurrent: offset === 0
    });
  }
  return months;
}

function renderSemesterChart() {
  const container = document.querySelector("#semesterChart");
  if (!container || appShell.classList.contains("is-hidden")) return;
  const width = container.clientWidth;
  if (!width) return;

  const data = semesterData();
  const height = 260;
  const padT = 18;
  const padB = 34;
  const padL = 62;
  const padR = 14;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;

  const values = [0];
  data.forEach((month) => {
    if (chartSeries.income) values.push(month.income);
    if (chartSeries.expense) values.push(month.expense);
    if (chartSeries.net) values.push(month.net);
  });
  const hasData = values.some((value) => value !== 0);
  const step = niceStep(Math.max(Math.max(...values) - Math.min(...values), 1), 4);
  const yMax = Math.max(Math.ceil(Math.max(...values) / step) * step, step);
  const yMin = Math.min(Math.floor(Math.min(...values) / step) * step, 0);
  const span = yMax - yMin || 1;
  const yFor = (value) => padT + plotH - ((value - yMin) / span) * plotH;
  const zeroY = yFor(0);

  const slotW = plotW / data.length;
  const barW = Math.max(6, Math.min(26, (slotW - 26) / 2));

  let grid = "";
  for (let value = yMin; value <= yMax + step / 2; value += step) {
    const y = yFor(value);
    const isZero = Math.abs(value) < step / 1000;
    grid += `<line class="chart__gridline${isZero ? " chart__gridline--zero" : ""}" x1="${padL}" y1="${y}" x2="${width - padR}" y2="${y}" />`;
    grid += `<text class="chart__ylabel" x="${padL - 12}" y="${y}">${escapeHtml(formatMoneyCompact(value))}</text>`;
  }

  const columns = data.map((month, index) => {
    const center = padL + slotW * index + slotW / 2;
    let bars = "";

    if (chartSeries.income && month.income > 0) {
      const y = yFor(month.income);
      bars += `<rect class="chart__bar chart__bar--in" x="${center - barW - 2}" y="${y}" width="${barW}" height="${Math.max(zeroY - y, 1)}" rx="3"
        style="transform-origin:${center - barW - 2}px ${zeroY}px; animation-delay:${index * 55}ms" />`;
    }
    if (chartSeries.expense && month.expense > 0) {
      const y = yFor(month.expense);
      bars += `<rect class="chart__bar chart__bar--out" x="${center + 2}" y="${y}" width="${barW}" height="${Math.max(zeroY - y, 1)}" rx="3"
        style="transform-origin:${center + 2}px ${zeroY}px; animation-delay:${index * 55 + 25}ms" />`;
    }

    const aria = `${month.fullLabel}: ganhos ${formatMoney(month.income)}, despesas ${formatMoney(month.expense)}, saldo ${formatMoney(month.net)}`;
    return `
      <g class="chart__col${month.isCurrent ? " is-current" : ""}" data-index="${index}" tabindex="0" role="button" aria-label="${escapeHtml(aria)}">
        <rect class="chart__band" x="${padL + slotW * index}" y="${padT}" width="${slotW}" height="${plotH}" rx="6" />
        ${bars}
      </g>`;
  }).join("");

  let netLayer = "";
  if (chartSeries.net) {
    const points = data.map((month, index) => `${padL + slotW * index + slotW / 2},${yFor(month.net)}`).join(" ");
    const dots = data.map((month, index) => {
      const center = padL + slotW * index + slotW / 2;
      return `<circle class="chart__dot" data-dot="${index}" cx="${center}" cy="${yFor(month.net)}" r="4" />`;
    }).join("");
    netLayer = `<g class="chart__net"><polyline class="chart__netline" points="${points}" />${dots}</g>`;
  }

  const xLabels = data.map((month, index) => {
    const center = padL + slotW * index + slotW / 2;
    return `<text class="chart__xlabel${month.isCurrent ? " is-current" : ""}" data-label="${index}" x="${center}" y="${height - 12}">${escapeHtml(month.label)}</text>`;
  }).join("");

  const empty = hasData ? "" :
    `<text class="chart__empty" x="${padL + plotW / 2}" y="${padT + plotH / 2}">Sem movimentações neste período.</text>`;

  const tooltip = document.querySelector("#chartTooltip");
  container.querySelector(".chart__svg")?.remove();
  container.insertAdjacentHTML("beforeend", `
    <svg class="chart__svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img"
      aria-label="Ganhos, despesas e saldo dos últimos seis meses">
      <g class="chart__grid">${grid}</g>
      <g class="chart__cols">${columns}</g>
      ${netLayer}
      <g class="chart__xaxis">${xLabels}</g>
      ${empty}
    </svg>
  `);

  const svg = container.querySelector(".chart__svg");
  svg.querySelectorAll(".chart__col").forEach((col) => {
    const index = Number(col.dataset.index);
    const focus = () => focusChartMonth(index, { center: padL + slotW * index + slotW / 2, top: padT });
    col.addEventListener("mouseenter", focus);
    col.addEventListener("focus", focus);
    col.addEventListener("mouseleave", () => focusChartMonth(null));
    col.addEventListener("blur", () => focusChartMonth(null));
    col.addEventListener("click", () => goToChartMonth(index));
    col.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        goToChartMonth(index);
      }
    });
  });

  if (tooltip) tooltip.hidden = true;
  updateChartReadout(null);
}

function focusChartMonth(index, position) {
  const container = document.querySelector("#semesterChart");
  const tooltip = document.querySelector("#chartTooltip");
  if (!container || !tooltip) return;

  container.querySelectorAll(".chart__col").forEach((col) => {
    col.classList.toggle("is-focused", Number(col.dataset.index) === index);
  });
  container.querySelectorAll(".chart__dot, .chart__xlabel").forEach((el) => {
    const key = el.dataset.dot ?? el.dataset.label;
    el.classList.toggle("is-focused", Number(key) === index);
  });

  if (index === null) {
    tooltip.hidden = true;
    updateChartReadout(null);
    return;
  }

  const month = semesterData()[index];
  tooltip.innerHTML = `
    <strong>${escapeHtml(month.fullLabel)}</strong>
    <span><i class="chart-legend__dot chart-legend__dot--in"></i>Ganhos<b class="value-currency value-positive">${formatMoney(month.income)}</b></span>
    <span><i class="chart-legend__dot chart-legend__dot--out"></i>Despesas<b class="value-currency value-negative">${formatMoney(month.expense)}</b></span>
    <span><i class="chart-legend__dot chart-legend__dot--net"></i>Saldo<b class="value-currency ${month.net >= 0 ? "value-positive" : "value-negative"}">${formatMoney(month.net)}</b></span>
  `;
  tooltip.hidden = false;
  const left = Math.min(Math.max(position.center, 96), container.clientWidth - 96);
  tooltip.style.transform = `translate(${left}px, ${position.top}px) translateX(-50%)`;
  updateChartReadout(index);
}

function updateChartReadout(index) {
  const label = document.querySelector("#readoutLabel");
  if (!label) return;
  const data = semesterData();
  const source = index === null
    ? data.reduce((acc, month) => ({
        income: acc.income + month.income,
        expense: acc.expense + month.expense,
        net: acc.net + month.net
      }), { income: 0, expense: 0, net: 0 })
    : data[index];

  label.textContent = index === null ? "Últimos 6 meses" : data[index].fullLabel;
  document.querySelector("#readoutIncome").textContent = formatMoney(source.income);
  document.querySelector("#readoutExpense").textContent = formatMoney(source.expense);
  const netEl = document.querySelector("#readoutNet");
  netEl.textContent = formatMoney(source.net);
  netEl.classList.toggle("value-positive", source.net >= 0);
  netEl.classList.toggle("value-negative", source.net < 0);
}

// Clicar num mês do gráfico abre esse mês no calendário e nos cards.
function goToChartMonth(index) {
  const month = semesterData()[index];
  calendarCursor = new Date(month.year, month.month, 1);
  renderSummary();
  renderCalendar();
  renderSemesterChart();
  document.querySelector("#calGrid")?.scrollIntoView({ behavior: "smooth", block: "center" });
}

// ─── Movimentações ──────────────────────────────────────────────────────────

function txSourceInfo(source) {
  return TX_SOURCE[source] || TX_SOURCE.manual;
}

// Recorte atual: tipo + mês (ou tudo, quando o usuário abre o período inteiro).
function visibleTransactions() {
  return state.transactions.filter((item) => {
    if (txFilter !== "all" && item.type !== txFilter) return false;
    const date = transactionDate(item);

    // O período personalizado, quando existe, manda em cima do mês.
    if (txRange.start) {
      const dia = dateKey(date);
      return dia >= dateKey(txRange.start) && dia <= dateKey(txRange.end);
    }
    if (txAllPeriods) return true;
    return date.getFullYear() === txMonth.getFullYear() && date.getMonth() === txMonth.getMonth();
  });
}

function renderTransactionTotals(lista) {
  let entrou = 0;
  let saiu = 0;
  lista.forEach((item) => {
    const valor = Number(item.amount) || 0;
    if (item.type === "income") entrou += valor;
    else saiu += valor;
  });

  const saldo = entrou - saiu;
  document.querySelector("#txIncome").textContent = formatMoney(entrou);
  document.querySelector("#txExpense").textContent = formatMoney(saiu);
  const saldoEl = document.querySelector("#txBalance");
  saldoEl.textContent = formatMoney(saldo);
  saldoEl.classList.toggle("value-positive", saldo >= 0);
  saldoEl.classList.toggle("value-negative", saldo < 0);
}

function renderTransactions() {
  const container = document.querySelector("#transactionRows");
  if (!container) return;

  const rotulo = document.querySelector("#txMonthLabel");
  if (rotulo) {
    rotulo.textContent = txRange.start
      ? `${txRange.start.toLocaleDateString("pt-BR")} – ${txRange.end.toLocaleDateString("pt-BR")}`
      : txAllPeriods
      ? "Todo o período"
      : `${CAL_MONTHS[txMonth.getMonth()]} de ${txMonth.getFullYear()}`;
  }

  const lista = visibleTransactions()
    .slice()
    .sort((a, b) => transactionDate(b) - transactionDate(a));

  renderTransactionTotals(lista);

  if (!lista.length) {
    container.innerHTML = `<p class="empty-state">${
      state.transactions.length
        ? "Nenhuma movimentação neste recorte."
        : "Nenhuma movimentação ainda — registre a primeira entrada ou saída."
    }</p>`;
    return;
  }

  container.innerHTML = lista.map((item) => {
    const entrada = item.type === "income";
    const origem = txSourceInfo(item.source);
    const quando = transactionDate(item).toLocaleDateString("pt-BR");
    return `
      <button class="charge-row" type="button" data-tx="${escapeHtml(item.id)}">
        <span class="charge-row__main">
          <strong>${escapeHtml(item.description)}</strong>
          <small>${escapeHtml(quando)} · ${escapeHtml(origem.label)}</small>
        </span>
        <span class="charge-row__side">
          <span class="value-currency charge-row__amount ${entrada ? "value-positive" : "value-negative"}">
            ${entrada ? "+" : "−"} ${formatMoney(item.amount)}
          </span>
          <span class="status-badge status-badge--${entrada ? "positive" : "negative"}">${entrada ? "Entrada" : "Saída"}</span>
        </span>
        <span class="charge-row__chevron material-symbols-rounded" aria-hidden="true">chevron_right</span>
      </button>`;
  }).join("");

  container.querySelectorAll("[data-tx]").forEach((linha) => {
    linha.addEventListener("click", () => openTxDrawer(linha.dataset.tx));
  });
}

function shiftTxMonth(delta) {
  txAllPeriods = false;
  txRange = { start: null, end: null };
  document.querySelector("#txRangeTrigger")?.classList.remove("is-active");
  txMonth = new Date(txMonth.getFullYear(), txMonth.getMonth() + delta, 1);
  document.querySelector("#txAllPeriods")?.classList.remove("is-active");
  renderTransactions();
}

// ─── Filtro por período personalizado ───────────────────────────────────────

// Mês visível no calendário do filtro (independente do mês da lista).
let txRangeCursor = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
// Seleção em andamento, ainda não aplicada.
let txRangeDraft = { start: null, end: null };

function sameDay(a, b) {
  return a && b && dateKey(a) === dateKey(b);
}

function setRangeMenuOpen(open) {
  const panel = document.querySelector("#txRangePanel");
  const trigger = document.querySelector("#txRangeTrigger");
  if (!panel || !trigger) return;
  panel.hidden = !open;
  trigger.setAttribute("aria-expanded", String(open));
  if (open) {
    // Reabrir parte do que já está aplicado, para ajustar em vez de recomeçar.
    txRangeDraft = txRange.start
      ? { start: new Date(txRange.start), end: txRange.end ? new Date(txRange.end) : null }
      : { start: null, end: null };
    txRangeCursor = new Date((txRangeDraft.start || new Date()).getFullYear(), (txRangeDraft.start || new Date()).getMonth(), 1);
    renderRangeCalendar();
  }
}

function renderRangeCalendar() {
  const grid = document.querySelector("#txRangeGrid");
  const rotulo = document.querySelector("#txRangeMonth");
  const dica = document.querySelector("#txRangeHint");
  const aplicar = document.querySelector("#txRangeApply");
  if (!grid || !rotulo) return;

  const ano = txRangeCursor.getFullYear();
  const mes = txRangeCursor.getMonth();
  rotulo.textContent = `${CAL_MONTHS[mes]} de ${ano}`;

  const { start, end } = txRangeDraft;
  dica.textContent = !start
    ? "Escolha o dia de início."
    : !end
    ? "Agora escolha o dia final."
    : `De ${start.toLocaleDateString("pt-BR")} até ${end.toLocaleDateString("pt-BR")}.`;
  aplicar.disabled = !start;

  const primeiroDia = new Date(ano, mes, 1).getDay();
  const diasNoMes = new Date(ano, mes + 1, 0).getDate();
  const hoje = dateKey(new Date());

  let celulas = "";
  for (let i = 0; i < primeiroDia; i += 1) {
    celulas += `<span class="range__day range__day--empty" aria-hidden="true"></span>`;
  }
  for (let dia = 1; dia <= diasNoMes; dia += 1) {
    const data = new Date(ano, mes, dia);
    const chave = dateKey(data);
    const ponta = sameDay(data, start) || sameDay(data, end);
    const entre = start && end && data > start && data < end;
    celulas += `
      <button type="button" role="gridcell"
        class="range__day${ponta ? " is-edge" : ""}${entre ? " is-between" : ""}${chave === hoje ? " is-today" : ""}"
        data-dia="${chave}" aria-label="${data.toLocaleDateString("pt-BR")}">${dia}</button>`;
  }
  grid.innerHTML = celulas;
}

function pickRangeDay(chave) {
  const [ano, mes, dia] = chave.split("-").map(Number);
  const escolhido = new Date(ano, mes - 1, dia);
  const { start, end } = txRangeDraft;

  if (!start || end) {
    // Começa uma seleção nova.
    txRangeDraft = { start: escolhido, end: null };
  } else if (escolhido < start) {
    // Clicou antes do início: inverte, em vez de recusar o clique.
    txRangeDraft = { start: escolhido, end: start };
  } else {
    txRangeDraft = { start, end: escolhido };
  }
  renderRangeCalendar();
}

function applyRange() {
  const { start, end } = txRangeDraft;
  if (!start) return;
  // Um dia só é um intervalo válido de um dia.
  txRange = { start, end: end || start };
  txAllPeriods = false;
  document.querySelector("#txAllPeriods")?.classList.remove("is-active");
  document.querySelector("#txRangeTrigger")?.classList.add("is-active");
  setRangeMenuOpen(false);
  renderTransactions();
}

function clearRange() {
  txRange = { start: null, end: null };
  txRangeDraft = { start: null, end: null };
  document.querySelector("#txRangeTrigger")?.classList.remove("is-active");
  renderRangeCalendar();
  setRangeMenuOpen(false);
  renderTransactions();
}

// ─── Detalhes ───────────────────────────────────────────────────────────────

function openTxDrawer(id) {
  const drawer = document.querySelector("#txDrawer");
  const item = state.transactions.find((t) => String(t.id) === String(id));
  if (!drawer || !item) return;

  const entrada = item.type === "income";
  const origem = txSourceInfo(item.source);
  const doPix = item.source === "pix";

  document.querySelector("#txDrawerTitle").textContent = item.description;
  const kind = document.querySelector("#txDrawerKind");
  kind.textContent = entrada ? "Entrada" : "Saída";
  kind.className = `drawer__weekday ${entrada ? "status-text--positive" : "status-text--negative"}`;

  document.querySelector("#txDrawerBody").innerHTML = `
    <div class="drawer__amount">
      <span>Valor</span>
      <strong class="value-currency ${entrada ? "status-text--positive" : "status-text--negative"}">${formatMoney(item.amount)}</strong>
    </div>
    ${drawerRows("Movimentação", [
      ["Tipo", entrada ? "Entrada" : "Saída"],
      ["Data", transactionDate(item).toLocaleDateString("pt-BR")],
      ["Origem", origem.label],
      ["Registrada em", formatDateTime(item.created_at)]
    ])}
    ${doPix
      ? `<p class="drawer__note">Esta entrada foi criada automaticamente quando a cobrança PIX foi paga. Editar aqui faria o financeiro divergir da cobrança, então ela é somente leitura.</p>`
      : `<div class="drawer__actions">
           <button class="ghost-button" type="button" id="txEdit">Editar</button>
           <button class="ghost-button ghost-button--danger" type="button" id="txDelete">Excluir</button>
         </div>`}
  `;

  if (!doPix) {
    document.querySelector("#txEdit")?.addEventListener("click", () => {
      closeTxDrawer();
      openTxModal(item);
    });
    document.querySelector("#txDelete")?.addEventListener("click", () => removeTransaction(item.id));
  }

  drawer.hidden = false;
  requestAnimationFrame(() => drawer.classList.add("is-open"));
  document.addEventListener("keydown", txDrawerEscHandler);
}

function closeTxDrawer() {
  const drawer = document.querySelector("#txDrawer");
  if (!drawer) return;
  drawer.classList.remove("is-open");
  document.removeEventListener("keydown", txDrawerEscHandler);
  window.setTimeout(() => { drawer.hidden = true; }, 300);
}

function txDrawerEscHandler(event) {
  if (event.key === "Escape") closeTxDrawer();
}

async function removeTransaction(id) {
  if (apiAvailable) {
    try {
      await deleteTransaction(id);
    } catch {
      return;
    }
  }
  state.transactions = state.transactions.filter((item) => String(item.id) !== String(id));
  closeTxDrawer();
  persist();
  render();
}

// ─── Criar e editar ─────────────────────────────────────────────────────────

// ─── Importação de extrato ──────────────────────────────────────────────────
// São dois passos de propósito: primeiro o servidor lê o arquivo e devolve o
// que encontrou, depois o usuário confere e confirma. Extrato traz
// transferência entre contas próprias, que não é receita nem despesa —
// importar direto sujaria os totais.

let importPreview = null;

document.querySelector("#openImportModal")?.addEventListener("click", openImportModal);

document.querySelectorAll("[data-close-import]").forEach((el) =>
  el.addEventListener("click", closeImportModal)
);

document.querySelector("#importForm")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const erro = document.querySelector("#importFormError");
  const submit = document.querySelector("#importSubmit");
  const arquivo = document.querySelector("#importFile")?.files?.[0];

  if (!arquivo) {
    erro.textContent = "Escolha o arquivo do extrato.";
    erro.hidden = false;
    return;
  }

  const dados = new FormData();
  dados.append("file", arquivo);

  erro.hidden = true;
  submit.disabled = true;
  submit.textContent = "Lendo...";

  try {
    importPreview = await apiRequest("/transactions/import/preview/", { method: "POST", body: dados });
  } catch (requestError) {
    erro.textContent = requestError.message;
    erro.hidden = false;
    return;
  } finally {
    submit.disabled = false;
    submit.textContent = "Ler extrato";
  }

  renderImportReview();
});

document.querySelector("#importConfirm")?.addEventListener("click", async () => {
  const erro = document.querySelector("#importConfirmError");
  const botao = document.querySelector("#importConfirm");
  const linhas = selectedImportRows();

  if (!linhas.length) {
    erro.textContent = "Selecione pelo menos um lançamento.";
    erro.hidden = false;
    return;
  }

  erro.hidden = true;
  botao.disabled = true;
  botao.textContent = "Importando...";

  let resultado;
  try {
    resultado = await apiRequest("/transactions/import/confirm/", {
      method: "POST",
      body: JSON.stringify({
        filename: importPreview.filename,
        file_format: importPreview.file_format,
        file_hash: importPreview.file_hash,
        transactions: linhas
      })
    });
  } catch (requestError) {
    erro.textContent = requestError.message;
    erro.hidden = false;
    return;
  } finally {
    botao.disabled = false;
    botao.textContent = "Importar";
  }

  state.transactions = [...resultado.transactions, ...state.transactions];
  closeImportModal();
  persist();
  render();
});

// A conexão direta com o banco ainda não existe: esta tela só explica como ela
// funcionaria. Por isso não há chamada de API nenhuma aqui, e o botão carrega
// o selo "Em breve" — ninguém deve clicar achando que já funciona.

document.querySelector("#openBankModal")?.addEventListener("click", openBankModal);

document.querySelectorAll("[data-close-bank]").forEach((el) =>
  el.addEventListener("click", closeBankModal)
);

function openBankModal() {
  const modal = document.querySelector("#bankModal");
  if (!modal) return;
  modal.hidden = false;
  requestAnimationFrame(() => modal.classList.add("is-open"));
  document.addEventListener("keydown", bankModalEscHandler);
}

function closeBankModal() {
  const modal = document.querySelector("#bankModal");
  if (!modal) return;
  modal.classList.remove("is-open");
  document.removeEventListener("keydown", bankModalEscHandler);
  window.setTimeout(() => { modal.hidden = true; }, 300);
}

function bankModalEscHandler(event) {
  if (event.key === "Escape") closeBankModal();
}

function openImportModal() {
  const modal = document.querySelector("#importModal");
  if (!modal) return;

  importPreview = null;
  document.querySelector("#importForm").reset();
  document.querySelector("#importForm").hidden = false;
  document.querySelector("#importReview").hidden = true;

  ["#importFormError", "#importConfirmError"].forEach((seletor) => {
    const alvo = document.querySelector(seletor);
    alvo.hidden = true;
    alvo.textContent = "";
  });

  modal.hidden = false;
  requestAnimationFrame(() => modal.classList.add("is-open"));
  document.addEventListener("keydown", importModalEscHandler);
}

function closeImportModal() {
  const modal = document.querySelector("#importModal");
  if (!modal) return;
  modal.classList.remove("is-open");
  importPreview = null;
  document.removeEventListener("keydown", importModalEscHandler);
  window.setTimeout(() => { modal.hidden = true; }, 300);
}

function importModalEscHandler(event) {
  if (event.key === "Escape") closeImportModal();
}

function renderImportReview() {
  document.querySelector("#importForm").hidden = true;
  document.querySelector("#importReview").hidden = false;

  const lista = document.querySelector("#importRows");
  lista.innerHTML = importPreview.transactions.map((linha, indice) => {
    const entrada = linha.type === "income";
    const valor = Number(linha.amount);
    const quando = new Date(linha.occurred_at).toLocaleDateString("pt-BR");
    const id = `importRow${indice}`;
    return `
      <div class="import-row ${linha.duplicate ? "import-row--duplicate" : ""}" data-import-row
           data-external-id="${escapeHtml(linha.external_id)}"
           data-occurred-at="${escapeHtml(linha.occurred_at)}"
           data-amount="${escapeHtml(linha.amount)}">
        <input class="import-row__check" type="checkbox" id="${id}" data-import-check
               ${linha.duplicate ? "" : "checked"} />
        <label class="import-row__date" for="${id}">${escapeHtml(quando)}</label>
        <input class="import-row__field" data-import-desc aria-label="Descrição"
               value="${escapeHtml(linha.description)}" maxlength="180" />
        <select class="import-row__field" data-import-type aria-label="Tipo">
          <option value="income" ${entrada ? "selected" : ""}>Entrada</option>
          <option value="expense" ${entrada ? "" : "selected"}>Saída</option>
        </select>
        <span class="value-currency import-row__amount ${entrada ? "value-positive" : "value-negative"}">
          ${entrada ? "+" : "−"} ${formatMoney(valor)}
        </span>
        <span class="import-row__tag ${linha.duplicate ? "status-badge status-badge--neutral" : ""}">
          ${linha.duplicate ? "Já importado" : ""}
        </span>
      </div>`;
  }).join("");

  lista.querySelectorAll("[data-import-check]").forEach((caixa) =>
    caixa.addEventListener("change", updateImportSummary)
  );

  updateImportSummary();
}

function updateImportSummary() {
  const total = importPreview?.transactions.length || 0;
  const marcados = selectedImportRows().length;
  const duplicados = importPreview?.duplicates || 0;

  const partes = [`${marcados} de ${total} lançamentos selecionados`];
  if (duplicados) {
    partes.push(`${duplicados} já ${duplicados === 1 ? "existe" : "existem"} no financeiro e ${duplicados === 1 ? "veio desmarcado" : "vieram desmarcados"}`);
  }
  if (importPreview?.already_imported) {
    partes.push("este arquivo já foi importado antes");
  }

  document.querySelector("#importSummary").textContent = `${partes.join(" · ")}.`;
  document.querySelector("#importConfirm").textContent = marcados
    ? `Importar ${marcados}`
    : "Importar";
}

function selectedImportRows() {
  return [...document.querySelectorAll("[data-import-row]")]
    .filter((linha) => linha.querySelector("[data-import-check]").checked)
    .map((linha) => ({
      external_id: linha.dataset.externalId,
      occurred_at: linha.dataset.occurredAt,
      amount: linha.dataset.amount,
      type: linha.querySelector("[data-import-type]").value,
      // Descrição vazia quebraria a validação do servidor por um campo que o
      // usuário só apagou sem querer.
      description: linha.querySelector("[data-import-desc]").value.trim() || "Lançamento importado"
    }));
}

function openTxModal(item) {
  const modal = document.querySelector("#txModal");
  if (!modal) return;

  txEditingId = item ? item.id : null;
  document.querySelector("#txModalTitle").textContent = item ? "Editar movimentação" : "Nova movimentação";
  document.querySelector("#txSubmit").textContent = item ? "Salvar" : "Adicionar";

  document.querySelector("#txType").value = item ? item.type : "income";
  document.querySelector("#txDescription").value = item ? item.description : "";
  document.querySelector("#txAmount").value = item ? formatMoney(item.amount) : "";
  document.querySelector("#txDate").value = item ? dateKey(transactionDate(item)) : dateKey(new Date());

  const erro = document.querySelector("#txFormError");
  erro.hidden = true;
  erro.textContent = "";

  modal.hidden = false;
  requestAnimationFrame(() => modal.classList.add("is-open"));
  document.addEventListener("keydown", txModalEscHandler);
  document.querySelector("#txDescription")?.focus();
}

function closeTxModal() {
  const modal = document.querySelector("#txModal");
  if (!modal) return;
  modal.classList.remove("is-open");
  txEditingId = null;
  document.removeEventListener("keydown", txModalEscHandler);
  window.setTimeout(() => { modal.hidden = true; }, 300);
}

function txModalEscHandler(event) {
  if (event.key === "Escape") closeTxModal();
}

function renderProducts() {
  const grid = document.querySelector("#productGrid");
  grid.innerHTML = "";
  if (!state.products.length) {
    grid.innerHTML = `<p class="empty-state">Seu catálogo está vazio — cadastre o primeiro produto acima para começar a calcular margens automaticamente.</p>`;
    return;
  }
  state.products.forEach((product) => {
    const margin = product.price - product.cost;
    const marginPercent = product.price ? (margin / product.price) * 100 : 0;
    const card = document.createElement("article");
    card.className = "product-card";
    card.innerHTML = `
      <strong>${escapeHtml(product.name)}</strong>
      <span>${escapeHtml(product.category)}</span>
      <div class="product-meta">
        <span><b>Preço</b><em>${formatMoney(product.price)}</em></span>
        <span><b>Custo</b><em>${formatMoney(product.cost)}</em></span>
        <span><b>Margem</b><em>${formatMoney(margin)} · ${marginPercent.toFixed(0)}%</em></span>
        <span><b>Estoque</b><em>${product.stock} un.</em></span>
      </div>
    `;
    grid.appendChild(card);
  });
}

function renderCampaignOptions() {
  const select = document.querySelector("#campaignProduct");
  select.innerHTML = "";
  state.products.forEach((product) => {
    const option = document.createElement("option");
    option.value = product.id;
    option.textContent = product.name;
    select.appendChild(option);
  });
}

// ─── Criar cobrança e acompanhar o pagamento ────────────────────────────────

const PIX_POLL_MS = 3000;
let pixPollTimer = null;
let pixCountdownTimer = null;
let pixCurrentPayment = null;

// O valor é digitado em centavos e reescrito como moeda a cada tecla, para o
// usuário nunca ter que pensar em ponto ou vírgula.
function centsFromMasked(value) {
  const digits = String(value).replace(/\D/g, "");
  return digits ? parseInt(digits, 10) : 0;
}

function maskMoney(value) {
  const cents = centsFromMasked(value);
  return formatMoney(cents / 100);
}

function openChargeModal() {
  const modal = document.querySelector("#chargeModal");
  if (!modal) return;

  const form = document.querySelector("#chargeForm");
  form.reset();
  document.querySelector("#chargeAmount").value = "";
  const error = document.querySelector("#chargeFormError");
  error.hidden = true;
  error.textContent = "";

  renderChargeProducts();

  modal.hidden = false;
  requestAnimationFrame(() => modal.classList.add("is-open"));
  document.addEventListener("keydown", chargeModalEscHandler);
  document.querySelector("#chargeDescription")?.focus();
}

function closeChargeModal() {
  const modal = document.querySelector("#chargeModal");
  if (!modal) return;
  modal.classList.remove("is-open");
  document.removeEventListener("keydown", chargeModalEscHandler);
  window.setTimeout(() => { modal.hidden = true; }, 300);
}

function chargeModalEscHandler(event) {
  if (event.key === "Escape") closeChargeModal();
}

// A cobrança pode partir de um produto já cadastrado: escolher o produto
// preenche descrição e valor com o que está no catálogo.
function renderChargeProducts() {
  const select = document.querySelector("#chargeProduct");
  if (!select) return;
  select.innerHTML = `<option value="">Cobrança avulsa</option>`;
  state.products.forEach((product) => {
    const option = document.createElement("option");
    option.value = product.id;
    option.textContent = `${product.name} — ${formatMoney(product.price)}`;
    select.appendChild(option);
  });
}

function applyProductToCharge(productId) {
  const product = state.products.find((item) => String(item.id) === String(productId));
  if (!product) return;
  document.querySelector("#chargeDescription").value = product.name;
  const cents = Math.round(Number(product.price) * 100);
  document.querySelector("#chargeAmount").value = formatMoney(cents / 100);
}

// ─── Tela do QR Code ────────────────────────────────────────────────────────

function openPixScreen(payment) {
  const screen = document.querySelector("#pixScreen");
  if (!screen) return;

  pixCurrentPayment = payment;
  document.querySelector("#pixDescription").textContent =
    payment.metadata?.description || "Cobrança PIX";
  document.querySelector("#pixAmount").textContent = formatMoney(payment.amount);

  const qr = payment.metadata?.brCodeBase64;
  const qrImg = document.querySelector("#pixQr");
  document.querySelector("#pixQrWrap").hidden = !qr;
  if (qr) qrImg.src = qr;

  const brCode = payment.metadata?.brCode || "";
  document.querySelector("#pixBrCode").textContent = brCode;
  document.querySelector("#pixCodeBlock").hidden = !brCode;

  setPixState("pending", "Aguardando pagamento…");
  screen.hidden = false;
  requestAnimationFrame(() => screen.classList.add("is-open"));

  startPixPolling();
  startPixCountdown();
}

function closePixScreen() {
  const screen = document.querySelector("#pixScreen");
  if (!screen) return;
  stopPixWatchers();
  screen.classList.remove("is-open");
  window.setTimeout(() => { screen.hidden = true; }, 300);
  pixCurrentPayment = null;
}

function stopPixWatchers() {
  window.clearInterval(pixPollTimer);
  window.clearInterval(pixCountdownTimer);
  pixPollTimer = null;
  pixCountdownTimer = null;
}

function setPixState(state, text) {
  const card = document.querySelector("#pixScreenCard");
  const status = document.querySelector("#pixStatus");
  document.querySelector("#pixStatusText").textContent = text;
  card.dataset.state = state;
  status.dataset.state = state;
}

// Consulta o provedor a cada 3s. O webhook é o caminho rápido, mas não chega
// em desenvolvimento e depende de configuração em produção — perguntar é o
// que torna esta tela confiável.
function startPixPolling() {
  stopPixWatchers();
  pixPollTimer = window.setInterval(checkPixOnce, PIX_POLL_MS);
}

async function checkPixOnce() {
  if (!pixCurrentPayment) return;
  try {
    const updated = await apiRequest(`/payments/${pixCurrentPayment.id}/check/`, { method: "POST" });
    pixCurrentPayment = updated;

    const index = currentPayments.findIndex((item) => item.id === updated.id);
    if (index !== -1) currentPayments[index] = updated;
    renderPaymentList();

    if (updated.status === "paid") {
      stopPixWatchers();
      setPixState("paid", "Pagamento confirmado!");
      document.querySelector("#pixTimer").textContent = "O valor já entrou no seu financeiro.";
      document.querySelector("#pixCodeBlock").hidden = true;
      document.querySelector("#pixQrWrap").hidden = true;
    } else if (["expired", "canceled", "failed"].includes(updated.status)) {
      stopPixWatchers();
      const labels = {
        expired: "Esta cobrança expirou.",
        canceled: "Esta cobrança foi cancelada.",
        failed: "Esta cobrança falhou."
      };
      setPixState("expired", labels[updated.status]);
      document.querySelector("#pixTimer").textContent = "Gere uma nova cobrança para receber.";
      document.querySelector("#pixCodeBlock").hidden = true;
      document.querySelector("#pixQrWrap").hidden = true;
    }
  } catch (error) {
    // Uma falha isolada de rede não deve derrubar a tela: avisa e segue
    // tentando, já que a próxima consulta pode dar certo.
    setPixState("error", `Sem conexão com a Abacate Pay. Tentando de novo… (${error.message})`);
  }
}

function startPixCountdown() {
  const timer = document.querySelector("#pixTimer");
  const expiresAt = pixCurrentPayment?.metadata?.expiresAt;
  if (!expiresAt) {
    timer.textContent = "";
    return;
  }

  const tick = () => {
    const remaining = new Date(expiresAt).getTime() - Date.now();
    if (remaining <= 0) {
      timer.textContent = "Tempo esgotado. Confirmando com a Abacate Pay…";
      window.clearInterval(pixCountdownTimer);
      checkPixOnce();
      return;
    }
    const minutes = Math.floor(remaining / 60000);
    const seconds = Math.floor((remaining % 60000) / 1000);
    timer.textContent = `Expira em ${minutes}:${String(seconds).padStart(2, "0")}`;
  };

  tick();
  pixCountdownTimer = window.setInterval(tick, 1000);
}

async function loadPayments() {
  try {
    const data = await apiRequest("/payments/");
    currentPayments = Array.isArray(data) ? data : (data.results || []);
    renderPaymentList();
  } catch {
    // silently fail — don't block the view
  }
}

// ─── Cobranças PIX: lista, filtro e detalhes ────────────────────────────────

const CHARGE_STATUS = {
  pending: { label: "Pendente", tone: "warning" },
  paid: { label: "Pago", tone: "positive" },
  failed: { label: "Falhou", tone: "negative" },
  refunded: { label: "Reembolsado", tone: "neutral" },
  canceled: { label: "Cancelado", tone: "neutral" }
};

let chargeFilter = "all";

function chargeStatusInfo(status) {
  return CHARGE_STATUS[status] || { label: status || "—", tone: "neutral" };
}

function formatDateTime(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit"
  });
}

function visiblePayments() {
  if (chargeFilter === "all") return currentPayments;
  if (chargeFilter === "other") {
    return currentPayments.filter((payment) => !["pending", "paid"].includes(payment.status));
  }
  return currentPayments.filter((payment) => payment.status === chargeFilter);
}

function renderPaymentList() {
  const container = document.querySelector("#paymentsList");
  if (!container) return;

  const list = visiblePayments();
  if (!list.length) {
    container.innerHTML = `<p class="empty-state">${
      currentPayments.length
        ? "Nenhuma cobrança com esse status."
        : "Nenhuma cobrança gerada ainda."
    }</p>`;
    return;
  }

  container.innerHTML = list.map((payment) => {
    const info = chargeStatusInfo(payment.status);
    const description = payment.metadata?.description || "Cobrança PIX";
    const customer = payment.metadata?.customer?.name;
    const when = formatDateTime(payment.created_at) || "—";
    return `
      <button class="charge-row" type="button" data-charge="${escapeHtml(payment.id)}">
        <span class="charge-row__main">
          <strong>${escapeHtml(description)}</strong>
          <small>${escapeHtml(customer || "Sem cliente informado")} · ${escapeHtml(when)}</small>
        </span>
        <span class="charge-row__side">
          <span class="value-currency charge-row__amount">${formatMoney(payment.amount)}</span>
          <span class="status-badge status-badge--${info.tone}">${escapeHtml(info.label)}</span>
        </span>
        <span class="charge-row__chevron material-symbols-rounded" aria-hidden="true">chevron_right</span>
      </button>`;
  }).join("");

  container.querySelectorAll("[data-charge]").forEach((row) => {
    row.addEventListener("click", () => openChargeDrawer(row.dataset.charge));
  });
}

function drawerRows(title, rows) {
  const visible = rows.filter(([, value]) => value);
  if (!visible.length) return "";
  return `
    <section class="drawer__section">
      <h4 class="drawer__section-title">${escapeHtml(title)}</h4>
      <dl class="drawer__rows">
        ${visible.map(([label, value]) => `
          <div class="drawer__row">
            <dt>${escapeHtml(label)}</dt>
            <dd>${escapeHtml(String(value))}</dd>
          </div>`).join("")}
      </dl>
    </section>`;
}

function openChargeDrawer(id) {
  const drawer = document.querySelector("#chargeDrawer");
  const payment = currentPayments.find((item) => item.id === id);
  if (!drawer || !payment) return;

  const info = chargeStatusInfo(payment.status);
  const provider = payment.metadata?.abacatepay || {};
  const customer = payment.metadata?.customer || {};

  document.querySelector("#chargeDrawerTitle").textContent =
    payment.metadata?.description || "Cobrança PIX";
  const statusEl = document.querySelector("#chargeDrawerStatus");
  statusEl.textContent = info.label;
  statusEl.className = `drawer__weekday status-text--${info.tone}`;

  const brCode = payment.metadata?.brCode;
  const qr = payment.metadata?.brCodeBase64;
  const isOpen = payment.status === "pending";

  const body = [
    `<div class="drawer__amount">
       <span>Valor da cobrança</span>
       <strong class="value-currency status-text--${info.tone}">${formatMoney(payment.amount)}</strong>
     </div>`,

    drawerRows("Cobrança", [
      ["Status", info.label],
      ["Criada em", formatDateTime(payment.created_at)],
      ["Expira em", formatDateTime(payment.metadata?.expiresAt)],
      payment.status === "paid" ? ["Confirmada em", formatDateTime(payment.updated_at)] : ["", ""],
      typeof provider.platformFee === "number"
        ? ["Taxa da plataforma", formatMoney(provider.platformFee / 100)]
        : ["", ""]
    ]),

    drawerRows("Cliente", [
      ["Nome", customer.name],
      ["E-mail", customer.email],
      ["CPF/CNPJ", customer.tax_id],
      ["Celular", customer.cellphone]
    ]) || `<section class="drawer__section">
             <h4 class="drawer__section-title">Cliente</h4>
             <p class="drawer__empty">Cobrança gerada sem dados do cliente.</p>
           </section>`,

    drawerRows("Identificação", [
      ["ID na Abacate Pay", payment.provider_payment_id],
      ["ID interno", payment.id]
    ]),

    isOpen && qr
      ? `<section class="drawer__section">
           <h4 class="drawer__section-title">QR Code</h4>
           <img class="drawer__qr" src="${escapeHtml(qr)}" alt="QR Code para pagamento" />
         </section>`
      : "",

    isOpen && brCode
      ? `<section class="drawer__section">
           <h4 class="drawer__section-title">Copia e cola</h4>
           <p class="drawer__code">${escapeHtml(brCode)}</p>
           <button class="ghost-button" type="button" data-copy-brcode="${escapeHtml(brCode)}">Copiar código</button>
         </section>`
      : "",

    provider.receiptUrl
      ? `<section class="drawer__section">
           <a class="ghost-button" href="${escapeHtml(provider.receiptUrl)}" target="_blank" rel="noopener">Ver recibo</a>
         </section>`
      : "",

    `<p class="drawer__note">Todas as cobranças são recebidas na conta única da plataforma configurada na Abacate Pay.</p>`
  ].join("");

  document.querySelector("#chargeDrawerBody").innerHTML = body;

  const copyBtn = drawer.querySelector("[data-copy-brcode]");
  copyBtn?.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(copyBtn.dataset.copyBrcode);
      copyBtn.textContent = "Copiado!";
      window.setTimeout(() => { copyBtn.textContent = "Copiar código"; }, 2000);
    } catch {
      copyBtn.textContent = "Não foi possível copiar";
    }
  });

  drawer.hidden = false;
  requestAnimationFrame(() => drawer.classList.add("is-open"));
  document.addEventListener("keydown", chargeDrawerEscHandler);
}

function closeChargeDrawer() {
  const drawer = document.querySelector("#chargeDrawer");
  if (!drawer) return;
  drawer.classList.remove("is-open");
  document.removeEventListener("keydown", chargeDrawerEscHandler);
  window.setTimeout(() => { drawer.hidden = true; }, 300);
}

function chargeDrawerEscHandler(event) {
  if (event.key === "Escape") closeChargeDrawer();
}

// ─── Assistente financeiro ──────────────────────────────────────────────────

const ASSISTANT_GREETING =
  "Oi! Eu leio os números do seu negócio e explico em português claro. " +
  "Posso dizer quanto sobrou no mês, comparar com os anteriores, apontar " +
  "qual produto rende mais e quais cobranças ainda não foram pagas.";

// A conversa mora no servidor: aqui guardamos só qual está aberta.
let currentConversationId = null;
let assistantBusy = false;
let suggestionIndex = -1;

function assistantThread() {
  return document.querySelector("#assistantThread");
}

function appendAssistantMessage(role, text, variant) {
  const thread = assistantThread();
  if (!thread) return null;

  const article = document.createElement("article");
  article.className = `msg msg--${role === "user" ? "user" : "bot"}`;
  if (variant) article.classList.add(`msg--${variant}`);

  // Parágrafos entram como texto, nunca como HTML.
  String(text).split(/\n{2,}/).forEach((paragraph) => {
    const p = document.createElement("p");
    p.textContent = paragraph.replace(/\n/g, " ").trim();
    article.appendChild(p);
  });

  thread.appendChild(article);
  thread.scrollTop = thread.scrollHeight;
  return article;
}

function setSuggestionsVisible(visible) {
  document.querySelector("#assistantSuggestions")?.classList.toggle("is-hidden", !visible);
  if (!visible) highlightSuggestion(-1);
}

function suggestionButtons() {
  return [...document.querySelectorAll("#assistantSuggestionList .suggestion")];
}

function highlightSuggestion(index) {
  const items = suggestionButtons();
  suggestionIndex = index;
  items.forEach((item, i) => {
    const active = i === index;
    item.classList.toggle("is-active", active);
    item.setAttribute("aria-selected", String(active));
    if (active) item.scrollIntoView({ block: "nearest" });
  });
}

function setAssistantBusy(busy) {
  assistantBusy = busy;
  const send = document.querySelector("#assistantSend");
  const input = document.querySelector("#assistantInput");
  if (send) send.disabled = busy;
  if (input) input.disabled = busy;
}

// ─── Histórico de conversas ─────────────────────────────────────────────────

// Agrupa por quando a conversa foi mexida pela última vez: saber "quando"
// ajuda a reencontrar uma conversa tanto quanto o título.
function conversationGroup(updatedAt) {
  const data = new Date(updatedAt);
  if (Number.isNaN(data.getTime())) return "Anteriores";

  const hoje = new Date();
  const inicioDeHoje = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate());
  const dias = Math.floor((inicioDeHoje - new Date(data.getFullYear(), data.getMonth(), data.getDate())) / 86400000);

  if (dias <= 0) return "Hoje";
  if (dias === 1) return "Ontem";
  if (dias <= 7) return "Últimos 7 dias";
  if (dias <= 30) return "Últimos 30 dias";
  return "Anteriores";
}

async function loadConversations() {
  const list = document.querySelector("#chatHistoryList");
  if (!list) return;

  let conversas = [];
  try {
    conversas = await apiRequest("/finance/assistant/conversations/");
  } catch {
    list.innerHTML = `<p class="chat-aside__empty">Não foi possível carregar as conversas.</p>`;
    return;
  }

  if (!conversas.length) {
    list.innerHTML = `<p class="chat-aside__empty">Suas conversas aparecem aqui depois da primeira pergunta.</p>`;
    return;
  }

  const grupos = new Map();
  conversas.forEach((conversa) => {
    const chave = conversationGroup(conversa.updated_at);
    if (!grupos.has(chave)) grupos.set(chave, []);
    grupos.get(chave).push(conversa);
  });

  list.innerHTML = [...grupos.entries()].map(([rotulo, itens]) => `
    <div class="chat-group">
      <p class="chat-group__label">${escapeHtml(rotulo)}</p>
      ${itens.map((conversa) => `
        <div class="chat-item${conversa.id === currentConversationId ? " is-active" : ""}">
          <button class="chat-item__open" type="button" data-abrir="${escapeHtml(conversa.id)}"
                  title="${escapeHtml(conversa.title || "Nova conversa")}">${escapeHtml(conversa.title || "Nova conversa")}</button>
          <button class="chat-item__delete" type="button" data-apagar="${escapeHtml(conversa.id)}" aria-label="Apagar conversa">
            <span class="material-symbols-rounded" aria-hidden="true">delete</span>
          </button>
        </div>`).join("")}
    </div>`).join("");

  list.querySelectorAll("[data-abrir]").forEach((botao) => {
    botao.addEventListener("click", () => {
      openConversation(botao.dataset.abrir);
      // No celular a lista cobre o chat: escolher uma conversa recolhe.
      if (window.matchMedia("(max-width: 768px)").matches) setAsideOpen(false);
    });
  });
  list.querySelectorAll("[data-apagar]").forEach((botao) => {
    botao.addEventListener("click", () => deleteConversation(botao.dataset.apagar));
  });
}

function setAsideOpen(open) {
  const shell = document.querySelector("#assistantShell");
  const toggle = document.querySelector("#asideToggle");
  if (!shell) return;
  shell.classList.toggle("is-collapsed", !open);
  toggle?.setAttribute("aria-expanded", String(open));
}

function setAssistantTitle(texto) {
  const el = document.querySelector("#assistantTitle");
  if (el) el.textContent = texto || "Nova conversa";
}

async function openConversation(id) {
  const thread = assistantThread();
  if (!thread) return;

  try {
    const conversa = await apiRequest(`/finance/assistant/conversations/${id}/`);
    currentConversationId = conversa.id;
    setAssistantTitle(conversa.title);
    thread.innerHTML = "";
    conversa.messages.forEach((m) => appendAssistantMessage(m.role, m.content));
    setSuggestionsVisible(conversa.messages.length === 0);
    loadConversations();
  } catch {
    appendAssistantMessage("bot", "Não foi possível abrir essa conversa.", "error");
  }
}

async function deleteConversation(id) {
  try {
    await apiRequest(`/finance/assistant/conversations/${id}/`, { method: "DELETE" });
  } catch {
    return;
  }
  if (id === currentConversationId) startNewConversation();
  else loadConversations();
}

function startNewConversation() {
  const thread = assistantThread();
  if (!thread) return;
  currentConversationId = null;
  setAssistantTitle(null);
  thread.innerHTML = "";
  appendAssistantMessage("bot", ASSISTANT_GREETING);
  setSuggestionsVisible(true);
  highlightSuggestion(-1);
  loadConversations();
  document.querySelector("#assistantInput")?.focus();
}

// ─── Perguntar ──────────────────────────────────────────────────────────────

async function askAssistant(question) {
  const text = String(question || "").trim();
  if (!text || assistantBusy) return;

  setSuggestionsVisible(false);
  appendAssistantMessage("user", text);

  const pending = appendAssistantMessage("bot", "Analisando seus números…", "pending");
  setAssistantBusy(true);

  try {
    const data = await apiRequest("/finance/assistant/", {
      method: "POST",
      body: JSON.stringify({ message: text, conversation_id: currentConversationId })
    });
    pending?.remove();
    appendAssistantMessage("bot", data.message);
    currentConversationId = data.conversation.id;
    setAssistantTitle(data.conversation.title);
    loadConversations();
  } catch (error) {
    pending?.remove();
    appendAssistantMessage("bot", error.message, "error");
  } finally {
    setAssistantBusy(false);
    document.querySelector("#assistantInput")?.focus();
  }
}

document.querySelector("#assistantForm")?.addEventListener("submit", (event) => {
  event.preventDefault();
  const input = document.querySelector("#assistantInput");
  const question = input.value;
  input.value = "";
  askAssistant(question);
});

document.querySelector("#assistantNew")?.addEventListener("click", () => startNewConversation());

document.querySelector("#asideToggle")?.addEventListener("click", () => {
  const recolhida = document.querySelector("#assistantShell")?.classList.contains("is-collapsed");
  setAsideOpen(recolhida);
});


suggestionButtons().forEach((item) => {
  item.addEventListener("click", () => askAssistant(item.dataset.ask));
});

// Teclado no campo: setas navegam as sugestões, Enter escolhe a destacada
// (ou envia o que foi digitado) e Esc fecha a lista.
document.querySelector("#assistantInput")?.addEventListener("keydown", (event) => {
  const items = suggestionButtons();
  const visible = !document.querySelector("#assistantSuggestions")?.classList.contains("is-hidden");

  if (event.key === "ArrowDown" && visible && items.length) {
    event.preventDefault();
    highlightSuggestion((suggestionIndex + 1) % items.length);
  } else if (event.key === "ArrowUp" && visible && items.length) {
    event.preventDefault();
    highlightSuggestion(suggestionIndex <= 0 ? items.length - 1 : suggestionIndex - 1);
  } else if (event.key === "Enter" && visible && suggestionIndex >= 0) {
    event.preventDefault();
    askAssistant(items[suggestionIndex].dataset.ask);
  } else if (event.key === "Escape" && visible) {
    setSuggestionsVisible(false);
  }
});

// ─── Marketing AI ─────────────────────────────────────────────────────────────

function campaignHeadline(goal, productName) {
  const headlines = {
    promocao: `${productName} com oferta especial por tempo limitado`,
    lancamento: `Chegou ${productName}: feito para encantar no primeiro pedido`,
    relacionamento: `Seu dia fica melhor com ${productName}`
  };
  return headlines[goal] || headlines.promocao;
}

function imagePrompt(goal, productName) {
  const prompts = {
    promocao: `foto clara de ${productName}, selo de oferta e fundo verde suave`,
    lancamento: `${productName} em destaque, composição premium e textura bege`,
    relacionamento: `cliente usando ${productName}, clima próximo e chamada acolhedora`
  };
  return prompts[goal] || prompts.promocao;
}

async function askMarketingAi({ product, goal, channel, prompt, margin }) {
  try {
    const response = await fetch(`${apiBaseUrl}/marketing/chat/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Token ${authToken}` },
      body: JSON.stringify({ product, goal, channel, prompt })
    });
    if (response.ok) {
      const data = await response.json();
      const rawText = data.message || data.text || "";
      return {
        html: escapeHtml(rawText).replaceAll("\n", "<br>").replaceAll("**", "<strong>").replace(/<strong>(.*?)<\/strong>/g, "<strong>$1</strong>"),
        imageLabel: escapeHtml(data.image_label || `${product.name}<br>${channel}`)
      };
    }
  } catch {
    // Fallback to local demo if API unavailable.
  }

  return {
    html:
      `<strong>Campanha para ${escapeHtml(channel)}</strong><br><br>` +
      `<b>Chamada:</b> ${escapeHtml(campaignHeadline(goal, product.name))}<br><br>` +
      `<b>Ideia de imagem:</b> ${escapeHtml(imagePrompt(goal, product.name))}<br><br>` +
      `<b>Legenda:</b> Hoje é um bom dia para garantir ${escapeHtml(product.name)}. Visual caprichado, entrega rápida. Margem de ${formatMoney(margin)} por unidade.<br><br>` +
      `<b>CTA:</b> Chame no direct ou finalize pelo PIX.`,
    imageLabel: `${escapeHtml(product.name)}<br>${escapeHtml(channel)}`
  };
}

// ─── API ──────────────────────────────────────────────────────────────────────

async function initializeApp() {
  try {
    const remoteState = await loadRemoteState();
    state = remoteState;
    apiAvailable = true;
    render();
  } catch {
    apiAvailable = false;
    state = loadState();
    render();
  }
}

async function loadRemoteState() {
  const products = await apiRequest("/products/");
  const transactions = canAccessFinance() ? await apiRequest("/transactions/") : [];
  return { products, transactions };
}

async function createProduct(payload) {
  try {
    return await apiRequest("/products/", { method: "POST", body: JSON.stringify(payload) });
  } catch {
    apiAvailable = false;
    persist();
    return { id: uid(), ...payload };
  }
}

async function updateTransaction(id, payload) {
  // Diferente do create, aqui um erro precisa chegar ao usuário: salvar uma
  // edição só na memória daria a impressão de que gravou.
  return apiRequest(`/transactions/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

async function createTransaction(payload) {
  try {
    return await apiRequest("/transactions/", { method: "POST", body: JSON.stringify(payload) });
  } catch {
    apiAvailable = false;
    persist();
    return { id: uid(), ...payload };
  }
}

async function deleteTransaction(id) {
  try {
    await apiRequest(`/transactions/${id}/`, { method: "DELETE" });
  } catch {
    apiAvailable = false;
  }
}

async function apiRequest(path, options = {}) {
  const { skipAuth, ...fetchOptions } = options;
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  // Upload de arquivo: o navegador precisa montar o Content-Type sozinho, com
  // o boundary do multipart. Definir aqui quebraria o envio.
  if (fetchOptions.body instanceof FormData) delete headers["Content-Type"];
  if (authToken && !skipAuth) headers.Authorization = `Token ${authToken}`;

  const response = await fetch(`${apiBaseUrl}${path}`, { ...fetchOptions, headers });

  if (!response.ok) {
    let detail = `Erro ${response.status}`;
    try {
      const data = await response.json();
      detail = data.detail || data.non_field_errors?.[0] || Object.values(data).flat().join(" ");
    } catch {
      // Keep status-based message.
    }
    throw new Error(detail);
  }

  if (response.status === 204) return null;
  return response.json();
}

// ─── Utilities ────────────────────────────────────────────────────────────────

function formatMoney(value) {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(value || 0);
}

function loadState() {
  try {
    const saved = localStorage.getItem(storageKey);
    return saved ? JSON.parse(saved) : clone(defaultState);
  } catch {
    return clone(defaultState);
  }
}

function persist() {
  if (apiAvailable) return;
  localStorage.setItem(storageKey, JSON.stringify(state));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function uid() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") return window.crypto.randomUUID();
  return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function daysAgoISO(days) {
  const date = new Date();
  date.setDate(date.getDate() - days);
  date.setHours(12, 0, 0, 0);
  return date.toISOString();
}

function clone(value) {
  if (typeof structuredClone === "function") return structuredClone(value);
  return JSON.parse(JSON.stringify(value));
}
