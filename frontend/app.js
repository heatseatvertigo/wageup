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
    { id: uid(), description: "Vendas no PIX", type: "income", amount: 1800 },
    { id: uid(), description: "Insumos", type: "expense", amount: 420 },
    { id: uid(), description: "Encomenda corporativa", type: "income", amount: 960 },
    { id: uid(), description: "Embalagens", type: "expense", amount: 180 }
  ]
};

let state = loadState();
let currentPayments = [];

const siteShell = document.querySelector(".site-shell");
const authShell = document.querySelector("#auth");
const onboardingShell = document.querySelector("#onboarding");
const appShell = document.querySelector("#app");
const sidebar = document.querySelector(".sidebar");
const title = document.querySelector("#view-title");
const viewTitles = {
  overview: "Visão geral",
  finance: "Financeiro",
  payments: "PIX",
  products: "Produtos",
  "app-marketing": "Marketing",
  help: "Ajuda"
};

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

document.querySelector("#loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitAuthForm("/auth/login/", event.currentTarget);
});

document.querySelector("#registerForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitAuthForm("/auth/register/", event.currentTarget);
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

document.querySelector("#transactionForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = {
    description: form.get("description").trim(),
    type: form.get("type"),
    amount: Number(form.get("amount"))
  };

  const transaction = apiAvailable
    ? await createTransaction(payload)
    : { id: uid(), ...payload };

  state.transactions.unshift(transaction);
  event.currentTarget.reset();
  persist();
  render();
});

document.querySelector("#productForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
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
  event.currentTarget.reset();
  persist();
  render();
});

document.querySelector("#campaignForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
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
  event.currentTarget.reset();
  renderCampaignOptions();
  output.scrollTop = output.scrollHeight;
});

document.querySelector("#refreshPaymentsBtn").addEventListener("click", () => loadPayments());

document.querySelector("#paymentForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const result = document.querySelector("#paymentResult");
  result.innerHTML = `<strong>Gerando cobrança...</strong><span>Conectando com a Abacate Pay.</span>`;

  try {
    const payment = await apiRequest("/payments/", {
      method: "POST",
      body: JSON.stringify({
        description: form.get("description").trim(),
        amount: Number(form.get("amount")),
        customer_name: form.get("customer_name").trim(),
        customer_email: form.get("customer_email").trim(),
        customer_tax_id: form.get("customer_tax_id").trim(),
        customer_cellphone: form.get("customer_cellphone").trim()
      })
    });
    currentPayments.unshift(payment);
    renderPaymentResult(payment);
    renderPaymentList();
    event.currentTarget.reset();
  } catch (error) {
    result.innerHTML = `<strong>Não foi possível gerar o PIX</strong><span>${escapeHtml(error.message)}</span>`;
  }
});

window.addEventListener("resize", () => drawChart());

render();
bootstrapSession();
initGoogleSignIn();
setDemoView("overview");
startWordRotator();

// ─── Auth & Session ───────────────────────────────────────────────────────────

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
    button.classList.toggle("active", button.dataset.authTab === tabName);
  });
  document.querySelectorAll(".auth-form").forEach((form) => {
    form.classList.toggle("active", form.id === `${tabName}Form`);
  });
  document.querySelector("#authError").textContent = "";
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
  if ((viewName === "finance" || viewName === "payments") && !canAccessFinance()) {
    viewName = "products";
  }
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("active", view.id === viewName);
  });
  document.querySelectorAll(".side-nav button").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === viewName);
  });
  title.textContent = viewTitles[viewName] || "Wage Up";
  if (viewName === "overview") drawChart();
  if (viewName === "payments") loadPayments();
}

function setDemoView(viewName) {
  const content = demoContent[viewName];
  if (!content) return;
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
  renderInsights();
  drawChart();
}

function renderSummary() {
  const income = sumByType("income");
  const expense = sumByType("expense");
  document.querySelector("#total-revenue").textContent = formatMoney(income);
  document.querySelector("#total-expenses").textContent = formatMoney(expense);
  document.querySelector("#total-profit").textContent = formatMoney(income - expense);
  document.querySelector("#total-products").textContent = state.products.length;
}

function renderTransactions() {
  const rows = document.querySelector("#transactionRows");
  rows.innerHTML = "";
  if (!state.transactions.length) {
    rows.innerHTML = `<tr class="empty-row"><td colspan="4">Nenhuma movimentação ainda — registre a primeira entrada ou saída acima.</td></tr>`;
    return;
  }
  state.transactions.forEach((transaction) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${escapeHtml(transaction.description)}</td>
      <td>${transaction.type === "income" ? "Entrada" : "Saída"}</td>
      <td>${formatMoney(transaction.amount)}</td>
      <td><button class="delete-button" aria-label="Excluir" data-delete-transaction="${transaction.id}">×</button></td>
    `;
    rows.appendChild(row);
  });
  rows.querySelectorAll("[data-delete-transaction]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (apiAvailable) await deleteTransaction(button.dataset.deleteTransaction);
      state.transactions = state.transactions.filter((item) => item.id !== button.dataset.deleteTransaction);
      persist();
      render();
    });
  });
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

function renderPaymentResult(payment) {
  const result = document.querySelector("#paymentResult");
  const brCode = payment.metadata?.brCode || "";
  const qrCode = payment.metadata?.brCodeBase64 || "";
  const expiresAt = payment.metadata?.expiresAt;
  const expiryText = expiresAt
    ? `<span class="payment-result__expiry">Válido até ${new Date(expiresAt).toLocaleString("pt-BR")}</span>`
    : "";
  const statusLabel = { pending: "Pendente", paid: "Pago", failed: "Falhou", refunded: "Reembolsado", canceled: "Cancelado" };
  result.innerHTML = `
    <strong>PIX gerado</strong>
    ${qrCode ? `<img src="${qrCode}" alt="QR Code PIX" />` : ""}
    ${brCode ? `<code>${escapeHtml(brCode)}</code>` : "<span>Código PIX não retornado pela Abacate Pay.</span>"}
    <span class="payment-result__status payment-status status--${escapeHtml(payment.status)}">${statusLabel[payment.status] || escapeHtml(payment.status)}</span>
    ${expiryText}
    <div class="payment-result__actions">
      ${brCode ? `<button class="secondary-button" type="button" data-copy-pix>Copiar código</button>` : ""}
      <button class="ghost-button" type="button" data-refresh-pix="${escapeHtml(payment.id)}">Verificar pagamento ↻</button>
    </div>
  `;
  const copyButton = result.querySelector("[data-copy-pix]");
  if (copyButton) {
    copyButton.addEventListener("click", async () => {
      await navigator.clipboard.writeText(brCode);
      copyButton.textContent = "Código copiado!";
    });
  }
  const refreshBtn = result.querySelector("[data-refresh-pix]");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", async () => {
      refreshBtn.textContent = "Verificando...";
      refreshBtn.disabled = true;
      try {
        const updated = await apiRequest(`/payments/${refreshBtn.dataset.refreshPix}/`);
        const idx = currentPayments.findIndex((p) => p.id === updated.id);
        if (idx !== -1) currentPayments[idx] = updated;
        renderPaymentResult(updated);
        renderPaymentList();
      } catch {
        refreshBtn.textContent = "Erro ao verificar";
        refreshBtn.disabled = false;
      }
    });
  }
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

function renderPaymentList() {
  const container = document.querySelector("#paymentsList");
  if (!container) return;

  if (!currentPayments.length) {
    container.innerHTML = `<p class="empty-state">Nenhuma cobrança gerada ainda.</p>`;
    return;
  }

  const statusLabel = { pending: "Pendente", paid: "Pago", failed: "Falhou", refunded: "Reembolsado", canceled: "Cancelado" };

  container.innerHTML = `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Descrição</th>
            <th>Valor</th>
            <th>Status</th>
            <th>Data</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${currentPayments.map((p) => `
            <tr>
              <td>${escapeHtml(p.metadata?.description || "—")}</td>
              <td><span class="value-currency">${formatMoney(p.amount)}</span></td>
              <td><span class="payment-status status--${escapeHtml(p.status)}">${statusLabel[p.status] || escapeHtml(p.status)}</span></td>
              <td>${new Date(p.created_at).toLocaleDateString("pt-BR")}</td>
              <td class="payment-list__actions">
                ${p.metadata?.brCode ? `<button class="ghost-button" data-list-show-pix="${escapeHtml(p.id)}">Ver QR</button>` : ""}
                <button class="ghost-button" data-list-refresh="${escapeHtml(p.id)}">↻</button>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;

  container.querySelectorAll("[data-list-show-pix]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const payment = currentPayments.find((p) => p.id === btn.dataset.listShowPix);
      if (payment) {
        renderPaymentResult(payment);
        document.querySelector("#paymentResult").scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    });
  });

  container.querySelectorAll("[data-list-refresh]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.listRefresh;
      btn.textContent = "...";
      try {
        const updated = await apiRequest(`/payments/${id}/`);
        const idx = currentPayments.findIndex((p) => p.id === id);
        if (idx !== -1) currentPayments[idx] = updated;
        renderPaymentList();
      } catch {
        btn.textContent = "↻";
      }
    });
  });
}

function renderInsights() {
  const container = document.querySelector("#insights");
  const income = sumByType("income");
  const expense = sumByType("expense");
  const lowStock = state.products.filter((product) => product.stock <= 8).length;
  const bestMargin = [...state.products].sort((a, b) => (b.price - b.cost) - (a.price - a.cost))[0];

  const insights = [
    {
      title: "Saúde financeira",
      text: income > expense
        ? `Positivo em ${formatMoney(income - expense)}.`
        : income === 0
        ? "Nenhuma entrada registrada ainda."
        : "Saídas acima das entradas."
    },
    {
      title: "Estoque",
      text: lowStock ? `${lowStock} produto(s) precisam de reposição.` : "Todos os produtos com estoque ok."
    },
    {
      title: "Melhor margem",
      text: bestMargin
        ? `${bestMargin.name}: ${formatMoney(bestMargin.price - bestMargin.cost)} por unidade.`
        : "Cadastre produtos para ver a margem."
    }
  ];

  container.innerHTML = insights.map((item) => `
    <article>
      <strong>${item.title}</strong>
      <span>${item.text}</span>
    </article>
  `).join("");
}

function drawChart() {
  const canvas = document.querySelector("#overviewChart");
  if (!canvas || appShell.classList.contains("is-hidden")) return;
  const ctx = canvas.getContext("2d");
  const rect = canvas.getBoundingClientRect();
  const scale = window.devicePixelRatio || 1;
  canvas.width = Math.max(320, rect.width * scale);
  canvas.height = 260 * scale;
  ctx.scale(scale, scale);
  const width = rect.width;
  const height = 260;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#fffdf8";
  ctx.fillRect(0, 0, width, height);
  const values = [
    { label: "Entradas", value: sumByType("income"), color: "#6f9877" },
    { label: "Saídas", value: sumByType("expense"), color: "#c19075" },
    { label: "Lucro", value: Math.max(sumByType("income") - sumByType("expense"), 0), color: "#284737" }
  ];
  const max = Math.max(...values.map((item) => item.value), 1);
  const barWidth = Math.min(120, (width - 90) / values.length - 18);
  const baseY = height - 48;
  values.forEach((item, index) => {
    const x = 34 + index * ((width - 70) / values.length);
    const barHeight = (item.value / max) * 150;
    ctx.fillStyle = item.color;
    roundedRect(ctx, x, baseY - barHeight, barWidth, barHeight, 8);
    ctx.fill();
    ctx.fillStyle = "#172018";
    ctx.font = "700 13px Space Grotesk, Arial";
    ctx.fillText(item.label, x, baseY + 24);
    ctx.fillStyle = "#657064";
    ctx.font = "600 12px Space Grotesk, Arial";
    ctx.fillText(formatMoney(item.value), x, baseY - barHeight - 10);
  });
}

function roundedRect(ctx, x, y, width, height, radius) {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + width, y, x + width, y + height, r);
  ctx.arcTo(x + width, y + height, x, y + height, r);
  ctx.arcTo(x, y + height, x, y, r);
  ctx.arcTo(x, y, x + width, y, r);
  ctx.closePath();
}

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

function sumByType(type) {
  return state.transactions
    .filter((t) => t.type === type)
    .reduce((total, t) => total + Number(t.amount), 0);
}

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

function clone(value) {
  if (typeof structuredClone === "function") return structuredClone(value);
  return JSON.parse(JSON.stringify(value));
}
