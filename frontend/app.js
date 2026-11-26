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
  manual: { label: "Lançamento manual", tone: "neutral" },
  sale: { label: "Venda", tone: "positive" }
};
// Forma de pagamento do lançamento. Vazio é "não informada": extrato e
// lançamento antigo não dizem como o dinheiro entrou.
const PAYMENT_METHOD_LABEL = { pix: "PIX", dinheiro: "Dinheiro", cartao: "Cartão", outro: "Outro" };
const PAYMENT_METHOD_ORDER = ["pix", "dinheiro", "cartao", "outro", ""];
// Meta do mês na visão geral: a última resposta da API e a chave
// mês|versão dos dados, para não buscar de novo sem mudança.
let ovGoal = null;
let ovGoalKey = "";
// Mesmo motivo: renderProducts() lê este mapa, e render() roda no topo.

const PRODUCT_UNITS = {
  un: "un", kg: "kg", g: "g", l: "L", ml: "mL", m: "m", pct: "pct", srv: "serviço"
};

let txFilter = "all";
let txMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
let txAllPeriods = false;
let txEditingId = null;
let txRange = { start: null, end: null };

// Tela de Vendas e painéis da visão geral. Declarados aqui pelo mesmo motivo
// do estado de Movimentações: o boot roda antes do resto do arquivo.
let salesMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
let currentSales = [];
// Versão dos dados na tela: render() sobe a cada mudança, e os insights só
// são pedidos de novo à IA quando ela mudou desde a última leitura.
let dataVersion = 0;
let insightsVersion = -1;
// Recomendações de marketing: também chamam a IA, então seguem a mesma regra.
let marketingRecommendations = [];
let marketingRecsVersion = -1;
// Aba da tela de marketing: "actions" (o que fazer agora) ou "chat".
let marketingTab = "actions";

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
  sales: "Vendas",
  help: "Ajuda"
};

// Views que vivem dentro do grupo "Financeiro" na navegação lateral.
const FINANCE_VIEWS = ["finance", "payments", "finance-assistant"];
const CHAT_VIEWS = ["finance-assistant", "app-marketing"];

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
  button.addEventListener("click", () => openEntryFlow(button.dataset.openApp === "register" ? "register" : "login"));
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

document.querySelectorAll("[data-auth-tab]").forEach((button) => {
  button.addEventListener("click", () => setAuthTab(button.dataset.authTab));
});

document.querySelector("[data-logout]").addEventListener("click", async () => {
  await logout();
});

document.querySelector(".menu-button").addEventListener("click", (event) => {
  const open = sidebar.classList.toggle("open");
  event.currentTarget.setAttribute("aria-expanded", String(open));
  event.currentTarget.setAttribute("aria-label", open ? "Fechar menu" : "Abrir menu");
});

document.querySelectorAll("[data-demo-view]").forEach((button) => {
  button.addEventListener("click", () => setDemoView(button.dataset.demoView));
});

document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", (event) => {
    if (button.dataset.adminOnly !== undefined && !canAccessFinance()) return;
    setView(button.dataset.view);
    sidebar.classList.remove("open");
    const menu = document.querySelector(".menu-button");
    menu?.setAttribute("aria-expanded", "false");
    menu?.setAttribute("aria-label", "Abrir menu");
    // Quem usa leitor de tela não vê o conteúdo trocar: avisa qual tela abriu.
    window.a11yAnnounce?.(`${title.textContent}. Tela aberta.`);
    // Clique de mouse (detail > 0) solta o foco: com o foco preso, a barra
    // lateral ficava expandida e recolhia no primeiro clique no conteúdo,
    // deslocando a tela embaixo do cursor e perdendo o clique. Pelo teclado
    // (detail 0) o foco fica, para a navegação continuar de onde estava.
    if (event.detail > 0) button.blur();
  });
});

// ─── Grupo "Financeiro" na navegação lateral ────────────────────────────────
// O item não abre view nenhuma: passar o mouse revela os módulos financeiros
// em cascata e o clique apenas abre/recolhe essa cascata.

// Hover e foco abrem o grupo, e o clique vem logo em seguida: sem esta marca,
// o clique fecharia o que o mouse (ou o toque, que também foca) acabou de abrir.
const NAV_GROUP_CLICK_GRACE_MS = 500;

function setNavGroupOpen(group, open, { byHover = false } = {}) {
  if (open && byHover && !group.classList.contains("is-open")) {
    group.dataset.openedAt = String(performance.now());
  }
  group.classList.toggle("is-open", open);
  group.querySelector(".nav-group__toggle")?.setAttribute("aria-expanded", String(open));
}

document.querySelectorAll("[data-nav-group]").forEach((group) => {
  const toggle = group.querySelector(".nav-group__toggle");

  toggle?.addEventListener("click", () => {
    const openedAt = Number(group.dataset.openedAt || 0);
    if (performance.now() - openedAt < NAV_GROUP_CLICK_GRACE_MS) return;
    setNavGroupOpen(group, !group.classList.contains("is-open"));
  });

  // Hover abre; ao sair, só recolhe se nenhuma view do grupo estiver ativa.
  group.addEventListener("mouseenter", () => setNavGroupOpen(group, true, { byHover: true }));
  group.addEventListener("mouseleave", () => {
    if (!group.classList.contains("has-active")) setNavGroupOpen(group, false);
  });

  // Teclado: abre ao focar qualquer item e recolhe ao sair do grupo.
  group.addEventListener("focusin", () => setNavGroupOpen(group, true, { byHover: true }));
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

document.querySelector("#txType")?.addEventListener("change", () => updateTxSaleHint());

document.querySelector("#txGoToSale")?.addEventListener("click", () => {
  closeTxModal();
  setView("sales");
  openSaleModal();
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
    amount: centavos / 100,
    payment_method: form.get("payment_method") || ""
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

// ─── Produtos: cadastro, foto e cálculo de margem ───────────────────────────

// Lado maior da foto depois da redução, e qualidade do JPEG. A imagem vai para
// o banco, então encolher no navegador é o que mantém a linha pequena — o
// servidor recusa acima de 400 KB.
const PHOTO_MAX_SIDE = 800;
const PHOTO_QUALITY = 0.8;

let productEditingId = null;
let productPhotoPending = null;   // Blob escolhido e ainda não enviado
let productPhotoCleared = false;  // usuário pediu para remover a foto atual

document.querySelector("#openProductModal")?.addEventListener("click", () => openProductModal(null));

document.querySelectorAll("[data-close-product]").forEach((el) =>
  el.addEventListener("click", closeProductModal)
);

["#productPrice", "#productCost", "#productOtherCosts"].forEach((seletor) => {
  document.querySelector(seletor)?.addEventListener("input", (event) => {
    const input = event.target;
    input.value = centsFromMasked(input.value) ? maskMoney(input.value) : "";
    updateProductCalc();
  });
});

["#productFee", "#productTax", "#calcTarget"].forEach((seletor) => {
  document.querySelector(seletor)?.addEventListener("input", updateProductCalc);
});

document.querySelector("#productPhoto")?.addEventListener("change", async (event) => {
  const arquivo = event.target.files?.[0];
  if (!arquivo) return;

  const erro = document.querySelector("#productFormError");
  try {
    productPhotoPending = await shrinkImage(arquivo);
    productPhotoCleared = false;
    showProductPhoto(URL.createObjectURL(productPhotoPending));
    erro.hidden = true;
  } catch (falha) {
    erro.textContent = falha.message;
    erro.hidden = false;
  }
});

document.querySelector("#productPhotoRemove")?.addEventListener("click", () => {
  productPhotoPending = null;
  productPhotoCleared = true;
  document.querySelector("#productPhoto").value = "";
  showProductPhoto(null);
});

document.querySelector("#productDelete")?.addEventListener("click", async () => {
  const produto = state.products.find((item) => String(item.id) === String(productEditingId));
  if (!produto) return;

  const erro = document.querySelector("#productFormError");
  try {
    await apiRequest(`/products/${produto.id}/`, { method: "DELETE" });
  } catch (falha) {
    erro.textContent = falha.message;
    erro.hidden = false;
    return;
  }

  state.products = state.products.filter((item) => String(item.id) !== String(produto.id));
  closeProductModal();
  persist();
  render();
});

document.querySelector("#productForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const erro = document.querySelector("#productFormError");
  const submit = document.querySelector("#productSubmit");

  const payload = {
    name: document.querySelector("#productName").value.trim(),
    category: document.querySelector("#productCategory").value.trim(),
    sku: document.querySelector("#productSku").value.trim(),
    description: document.querySelector("#productDescription").value.trim(),
    unit: document.querySelector("#productUnit").value,
    price: reaisFromField("#productPrice"),
    cost: reaisFromField("#productCost"),
    other_costs: reaisFromField("#productOtherCosts"),
    fee_percent: Number(document.querySelector("#productFee").value) || 0,
    tax_percent: Number(document.querySelector("#productTax").value) || 0,
    stock: Number(document.querySelector("#productStock").value) || 0,
    min_stock: Number(document.querySelector("#productMinStock").value) || 0,
    is_active: document.querySelector("#productActive").checked
  };

  if (!payload.name) {
    erro.textContent = "Informe o nome do produto.";
    erro.hidden = false;
    return;
  }

  erro.hidden = true;
  submit.disabled = true;
  const rotulo = submit.textContent;
  submit.textContent = "Salvando...";

  try {
    let produto = productEditingId
      ? await apiRequest(`/products/${productEditingId}/`, { method: "PATCH", body: JSON.stringify(payload) })
      : await apiRequest("/products/", { method: "POST", body: JSON.stringify(payload) });

    // A foto vai numa chamada separada: ela só pode ser enviada depois que o
    // produto existe e tem id.
    if (productPhotoPending) {
      const dados = new FormData();
      dados.append("file", productPhotoPending, "foto.jpg");
      produto = await apiRequest(`/products/${produto.id}/image/`, { method: "POST", body: dados });
    } else if (productPhotoCleared && productEditingId) {
      await apiRequest(`/products/${produto.id}/image/`, { method: "DELETE" });
      produto = { ...produto, has_image: false, image_updated_at: null };
    }

    const posicao = state.products.findIndex((item) => String(item.id) === String(produto.id));
    if (posicao === -1) state.products.unshift(produto);
    else state.products[posicao] = produto;
  } catch (falha) {
    erro.textContent = falha.message;
    erro.hidden = false;
    return;
  } finally {
    submit.disabled = false;
    submit.textContent = rotulo;
  }

  closeProductModal();
  persist();
  render();
});

function openProductModal(produto) {
  const modal = document.querySelector("#productModal");
  if (!modal) return;

  productEditingId = produto ? produto.id : null;
  productPhotoPending = null;
  productPhotoCleared = false;

  document.querySelector("#productModalTitle").textContent = produto ? "Editar produto" : "Novo produto";
  document.querySelector("#productSubmit").textContent = produto ? "Salvar" : "Cadastrar";
  document.querySelector("#productDelete").hidden = !produto;

  document.querySelector("#productName").value = produto?.name || "";
  document.querySelector("#productCategory").value = produto?.category || "";
  document.querySelector("#productSku").value = produto?.sku || "";
  document.querySelector("#productDescription").value = produto?.description || "";
  document.querySelector("#productUnit").value = produto?.unit || "un";
  document.querySelector("#productPrice").value = produto ? formatMoney(produto.price) : "";
  document.querySelector("#productCost").value = produto ? formatMoney(produto.cost) : "";
  document.querySelector("#productOtherCosts").value = produto ? formatMoney(produto.other_costs || 0) : "";
  document.querySelector("#productFee").value = produto?.fee_percent ? Number(produto.fee_percent) : "";
  document.querySelector("#productTax").value = produto?.tax_percent ? Number(produto.tax_percent) : "";
  document.querySelector("#productStock").value = produto?.stock ?? "";
  document.querySelector("#productMinStock").value = produto?.min_stock ?? "";
  document.querySelector("#productActive").checked = produto ? produto.is_active !== false : true;
  document.querySelector("#productPhoto").value = "";

  showProductPhoto(null);
  if (produto?.has_image) {
    productImageUrl(produto).then((url) => {
      // Só aplica se o usuário ainda estiver editando este produto: numa
      // conexão lenta ele pode ter fechado ou trocado de item antes de chegar.
      if (url && String(productEditingId) === String(produto.id) && !productPhotoPending) showProductPhoto(url);
    });
  }

  const erro = document.querySelector("#productFormError");
  erro.hidden = true;
  erro.textContent = "";

  updateProductCalc();
  modal.hidden = false;
  requestAnimationFrame(() => modal.classList.add("is-open"));
  document.addEventListener("keydown", productModalEscHandler);
  document.querySelector("#productName")?.focus();
}

function closeProductModal() {
  const modal = document.querySelector("#productModal");
  if (!modal) return;
  modal.classList.remove("is-open");
  productEditingId = null;
  productPhotoPending = null;
  productPhotoCleared = false;
  document.removeEventListener("keydown", productModalEscHandler);
  window.setTimeout(() => { modal.hidden = true; }, 300);
}

function productModalEscHandler(event) {
  if (event.key === "Escape") closeProductModal();
}

function showProductPhoto(url) {
  const preview = document.querySelector("#productPhotoPreview");
  const remover = document.querySelector("#productPhotoRemove");
  if (!preview) return;

  if (url) {
    preview.innerHTML = `<img src="${url}" alt="Pré-visualização da foto do produto" />`;
    preview.classList.add("photo-field__preview--filled");
    remover.hidden = false;
  } else {
    preview.innerHTML = `<span class="material-symbols-rounded" aria-hidden="true">photo_camera</span>`;
    preview.classList.remove("photo-field__preview--filled");
    remover.hidden = true;
  }
}

function reaisFromField(seletor) {
  return centsFromMasked(document.querySelector(seletor).value) / 100;
}

// Espelho da conta que vive em Product, no backend. Existe só para o usuário
// ver o resultado enquanto digita; o valor gravado é sempre o que o servidor
// calcula. Mudou a fórmula lá, muda aqui.
function productMargin({ price, cost, otherCosts, feePercent, taxPercent }) {
  const custoTotal = cost + otherCosts;
  const taxas = price * (feePercent + taxPercent) / 100;
  const margem = price - custoTotal - taxas;
  return {
    custoTotal,
    taxas,
    margem,
    margemPercent: price ? (margem / price) * 100 : 0,
    markupPercent: custoTotal ? ((price - custoTotal) / custoTotal) * 100 : 0
  };
}

function updateProductCalc() {
  const entrada = {
    price: reaisFromField("#productPrice"),
    cost: reaisFromField("#productCost"),
    otherCosts: reaisFromField("#productOtherCosts"),
    feePercent: Number(document.querySelector("#productFee").value) || 0,
    taxPercent: Number(document.querySelector("#productTax").value) || 0
  };
  const conta = productMargin(entrada);

  const hero = document.querySelector(".calc-panel__hero");
  hero.classList.toggle("calc-panel__hero--negative", conta.margem < 0);
  document.querySelector("#calcMarginValue").textContent = formatMoney(conta.margem);
  document.querySelector("#calcMarginPercent").textContent = conta.margem < 0
    ? `Prejuízo de ${Math.abs(conta.margemPercent).toFixed(1)}% sobre o preço`
    : `${conta.margemPercent.toFixed(1)}% do preço de venda`;

  document.querySelector("#calcPrice").textContent = formatMoney(entrada.price);
  document.querySelector("#calcCost").textContent = formatMoney(conta.custoTotal);
  document.querySelector("#calcFees").textContent = formatMoney(conta.taxas);
  document.querySelector("#calcMarkup").textContent = `${conta.markupPercent.toFixed(0)}%`;

  const alvo = Number(document.querySelector("#calcTarget").value) || 0;
  const divisor = 1 - (entrada.feePercent + entrada.taxPercent + alvo) / 100;
  const sugestao = document.querySelector("#calcSuggestion");
  if (!conta.custoTotal) {
    sugestao.textContent = "Informe o custo para ver o preço sugerido.";
  } else if (divisor <= 0) {
    sugestao.textContent = "Taxas e margem somam 100% ou mais — nenhum preço fecha essa conta.";
  } else {
    sugestao.textContent = `Cobre ${formatMoney(conta.custoTotal / divisor)}`;
  }
}

// Reduz a foto no navegador antes de subir. Sem isto, a foto de um celular
// moderno tem vários megabytes e o servidor recusa.
async function shrinkImage(arquivo) {
  if (!arquivo.type.startsWith("image/")) throw new Error("Escolha um arquivo de imagem.");

  const bitmap = await createImageBitmap(arquivo);
  const escala = Math.min(1, PHOTO_MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * escala);
  canvas.height = Math.round(bitmap.height * escala);
  canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close?.();

  const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", PHOTO_QUALITY));
  if (!blob) throw new Error("Não foi possível preparar esta imagem.");
  if (blob.size > 400 * 1024) throw new Error("Mesmo reduzida a foto ficou grande demais. Tente outra.");
  return blob;
}

// A rota da foto exige autenticação como qualquer outra, e <img src> não manda
// o token. Por isso a imagem é buscada e vira um object URL.
const productPhotoCache = new Map();

async function productImageUrl(produto) {
  const chave = `${produto.id}:${produto.image_updated_at || ""}`;
  if (productPhotoCache.has(chave)) return productPhotoCache.get(chave);

  try {
    const resposta = await fetch(`${apiBaseUrl}/products/${produto.id}/image/`, {
      headers: authToken ? { Authorization: `Token ${authToken}` } : {}
    });
    if (!resposta.ok) return null;
    const url = URL.createObjectURL(await resposta.blob());
    productPhotoCache.set(chave, url);
    return url;
  } catch {
    return null;
  }
}

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
  document.querySelector("#chargeQuantity").value = 1;
  applyProductToCharge(event.target.value);
});

document.querySelector("#chargeQuantity")?.addEventListener("input", () => {
  applyProductToCharge(document.querySelector("#chargeProduct").value);
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
        customer_cellphone: (form.get("customer_cellphone") || "").trim(),
        // Cobrança de produto: paga, vira venda e baixa o estoque.
        ...(form.get("product")
          ? { product_id: form.get("product"), quantity: parseInt(form.get("quantity"), 10) || 1 }
          : {})
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

function openEntryFlow(tab = "login") {
  if (authToken && currentUser) {
    openApp();
    return;
  }
  siteShell.classList.add("is-hidden");
  authShell.classList.remove("is-hidden");
  appShell.classList.add("is-hidden");
  onboardingShell.classList.add("is-hidden");
  setAuthTab(tab);
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
  // O painel da marca troca o título e o indicador das abas desliza por aqui.
  authShell.dataset.tab = tabName;
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
    const ativo = button.dataset.view === viewName;
    button.classList.toggle("active", ativo);
    // A classe é só visual: aria-current diz ao leitor de tela onde se está.
    if (ativo) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
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
  // As telas de chat escondem o título da página: a barra do chat basta.
  // O marketing só vira tela de chat na aba Conversa; na aba Ações é uma
  // tela comum, com título e rolagem.
  const emChat = CHAT_VIEWS.includes(viewName) && !(viewName === "app-marketing" && marketingTab === "actions");
  document.querySelector(".dashboard")?.classList.toggle("is-chat", emChat);
  // A navegação fica recolhida em trilha de ícones em toda a plataforma e se
  // abre ao passar o mouse ou receber foco pelo teclado.
  appShell.classList.add("is-rail");
  if (viewName === "overview") {
    renderSummary(); renderCalendar(); renderSemesterChart();
    loadProfitTable();
    loadInsights();
  }
  if (viewName === "payments") loadPayments();
  if (viewName === "sales") loadSales();
  // A conversa vive no servidor: ao abrir a tela, restaura o histórico.
  if (viewName === "finance-assistant") financeChat.ensureStarted();
  if (viewName === "app-marketing") {
    setMarketingTab(marketingTab, { fromView: true });
    loadMarketingRecommendations();
    if (marketingTab === "actions") loadMarketingActions();
  }
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
  dataVersion += 1;
  renderSummary();
  renderTransactions();
  renderProducts();
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

// `ateDia` limita ao mesmo período: no dia 15, o mês anterior conta do 1 ao
// 15. Comparar meio mês com o mês inteiro diria "50% abaixo" todo dia 15.
function monthTotals(year, month, ateDia = 31) {
  const totais = { income: 0, expense: 0, methods: {} };
  state.transactions.forEach((transaction) => {
    const date = transactionDate(transaction);
    if (date.getFullYear() !== year || date.getMonth() !== month || date.getDate() > ateDia) return;
    const amount = Number(transaction.amount) || 0;
    if (transaction.type === "income") {
      totais.income += amount;
      const forma = PAYMENT_METHOD_LABEL[transaction.payment_method] ? transaction.payment_method : "";
      totais.methods[forma] = (totais.methods[forma] || 0) + amount;
    } else {
      totais.expense += amount;
    }
  });
  return totais;
}

// Comparação com o mês anterior: ícone e texto, nunca só a cor.
function renderDelta(el, { text = "", icon = "", tone = "neutral" } = {}) {
  if (!el) return;
  el.className = `summary-card__delta summary-card__delta--${tone}`;
  el.innerHTML = text
    ? `${icon ? `<span class="material-symbols-rounded" aria-hidden="true">${icon}</span>` : ""}${escapeHtml(text)}`
    : "";
}

function percentDelta(atual, anterior, ref, maiorEhMelhor = true) {
  if (!anterior) return {};
  const diferenca = ((atual - anterior) / anterior) * 100;
  if (Math.abs(diferenca) < 1) return { text: ref.igual, icon: "trending_flat" };
  const subiu = diferenca > 0;
  return {
    text: `${Math.abs(diferenca).toFixed(0)}% ${subiu ? "acima" : "abaixo"} ${ref.de}`,
    icon: subiu ? "trending_up" : "trending_down",
    tone: subiu === maiorEhMelhor ? "positive" : "negative"
  };
}

function renderSummary() {
  const year = calendarCursor.getFullYear();
  const month = calendarCursor.getMonth();
  const atual = monthTotals(year, month);
  const anteriorData = new Date(year, month - 1, 1);
  const hoje = new Date();
  const mesCorrente = year === hoje.getFullYear() && month === hoje.getMonth();
  const anterior = monthTotals(anteriorData.getFullYear(), anteriorData.getMonth(), mesCorrente ? hoje.getDate() : 31);
  const mesAnterior = CAL_MONTHS[anteriorData.getMonth()].toLowerCase();
  // Como cada frase cita o mês anterior: inteiro, ou só o mesmo período.
  const ref = mesCorrente
    ? { de: `do mesmo período de ${mesAnterior}`, que: `que no mesmo período de ${mesAnterior}`, igual: `Igual ao mesmo período de ${mesAnterior}` }
    : { de: `de ${mesAnterior}`, que: `que ${mesAnterior}`, igual: `Igual a ${mesAnterior}` };
  const temAnterior = anterior.income > 0 || anterior.expense > 0;

  const income = atual.income;
  const expense = atual.expense;
  const profit = income - expense;
  const lucroAnterior = anterior.income - anterior.expense;

  const incomeEl = document.querySelector("#ov-income");
  if (incomeEl) incomeEl.textContent = formatMoney(income);
  renderDelta(document.querySelector("#ov-income-delta"), percentDelta(income, anterior.income, ref));

  const expenseEl = document.querySelector("#ov-expenses");
  if (expenseEl) expenseEl.textContent = formatMoney(expense);
  renderDelta(document.querySelector("#ov-expenses-delta"), percentDelta(expense, anterior.expense, ref, false));

  const profitEl = document.querySelector("#ov-profit");
  if (profitEl) {
    profitEl.textContent = formatMoney(profit);
    profitEl.classList.toggle("value-positive", profit >= 0);
    profitEl.classList.toggle("value-negative", profit < 0);
  }
  // Lucro pode ser negativo nos dois meses: a diferença em reais diz mais
  // que um percentual sobre base negativa.
  const diferencaLucro = profit - lucroAnterior;
  renderDelta(document.querySelector("#ov-profit-delta"), !temAnterior ? {} : Math.abs(diferencaLucro) < 0.01
    ? { text: ref.igual, icon: "trending_flat" }
    : {
        text: `${formatMoney(Math.abs(diferencaLucro))} ${diferencaLucro > 0 ? "a mais" : "a menos"} ${ref.que}`,
        icon: diferencaLucro > 0 ? "trending_up" : "trending_down",
        tone: diferencaLucro > 0 ? "positive" : "negative"
      });

  const marginEl = document.querySelector("#ov-margin");
  if (marginEl) {
    const margem = income > 0 ? (profit / income) * 100 : null;
    marginEl.textContent = margem === null ? "—" : `${margem.toFixed(0)}%`;
    marginEl.classList.toggle("value-positive", margem !== null && margem >= 0);
    marginEl.classList.toggle("value-negative", margem !== null && margem < 0);
    renderDelta(document.querySelector("#ov-margin-note"), margem === null
      ? { text: "Sem entradas no mês" }
      : margem >= 0
      ? { text: `Sobram ${formatMoney(margem)} de cada R$ 100 que entram`, icon: "savings", tone: "positive" }
      : { text: "Saiu mais do que entrou", icon: "warning", tone: "negative" });
  }

  renderMethods(atual);
  loadGoal();
}

function renderMethods(totais) {
  const container = document.querySelector("#ovMethods");
  if (!container) return;
  if (!totais.income) {
    container.innerHTML = `<p class="empty-state">Nenhuma entrada neste mês. As vendas e os PIX pagos aparecem aqui separados por forma de pagamento.</p>`;
    return;
  }
  const linhas = PAYMENT_METHOD_ORDER.filter((forma) => totais.methods[forma] > 0).map((forma) => {
    const valor = totais.methods[forma];
    const parte = valor / totais.income;
    return `
      <div class="method-row">
        <span class="method-row__label">${escapeHtml(PAYMENT_METHOD_LABEL[forma] || "Não informada")}</span>
        <span class="method-row__share">${(parte * 100).toFixed(0)}%</span>
        <span class="method-row__value value-currency value-positive">${formatMoney(valor)}</span>
        <span class="method-row__bar${forma ? "" : " method-row__bar--unknown"}" aria-hidden="true"><i style="--share: ${parte.toFixed(4)}"></i></span>
      </div>`;
  }).join("");
  const semForma = totais.methods[""] > 0
    ? `<p class="method-list__note">Entradas do extrato e lançamentos sem forma de pagamento ficam em "Não informada". Ao lançar uma entrada manual, escolha a forma.</p>`
    : "";
  container.innerHTML = linhas + semForma;
}

function monthKeyOf(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function cursorMonthKey() {
  return monthKeyOf(calendarCursor);
}

async function loadGoal(force = false) {
  if (!canAccessFinance() || !apiAvailable || !authToken) return;
  const mes = cursorMonthKey();
  const chave = `${mes}|${dataVersion}`;
  if (!force && chave === ovGoalKey) return;
  ovGoalKey = chave;
  try {
    const dados = await apiRequest(`/finance/goal/?month=${mes}`);
    // O usuário pode ter trocado de mês enquanto a resposta vinha.
    if (dados.month !== cursorMonthKey()) return;
    ovGoal = dados;
    renderGoal();
  } catch (requestError) {
    ovGoalKey = "";
    ovGoal = null;
    renderGoal(requestError.message);
  }
}

function renderGoal(erro) {
  const container = document.querySelector("#ovGoal");
  if (!container) return;
  const nomeMes = CAL_MONTHS[calendarCursor.getMonth()];
  const rotulo = document.querySelector("#ovGoalMonth");
  if (rotulo) rotulo.textContent = `${nomeMes} de ${calendarCursor.getFullYear()}`;

  if (erro || !ovGoal) {
    container.innerHTML = `<p class="empty-state">${escapeHtml(erro || "Carregando a meta...")}</p>`;
    return;
  }

  if (ovGoal.target === null) {
    container.innerHTML = `
      <p class="goal__lead">Defina quanto quer faturar em ${escapeHtml(nomeMes.toLowerCase())}. A plataforma mostra quanto falta e quanto precisa entrar por dia.</p>
      <p class="goal__so-far">${ovGoal.month < monthKeyOf(new Date()) ? "Entrou no mês" : "Entrou até agora"} <strong class="value-currency value-positive">${formatMoney(Number(ovGoal.achieved))}</strong></p>
      <div><button class="primary-button" type="button" data-goal-edit>Definir meta</button></div>`;
  } else {
    const alvo = Number(ovGoal.target);
    const feito = Number(ovGoal.achieved);
    const falta = Number(ovGoal.remaining);
    const parte = Math.min(feito / alvo, 1);
    let status;
    if (ovGoal.reached) {
      const sobra = feito - alvo;
      status = { tone: "positive", icon: "check_circle", text: sobra > 0
        ? `Meta batida! Entrou ${formatMoney(sobra)} a mais que o planejado.`
        : "Meta batida!" };
    } else if (ovGoal.days_left > 0) {
      status = { tone: "neutral", icon: "flag", text:
        `Você está a ${formatMoney(falta)} da meta. Faltam ${ovGoal.days_left} dia${ovGoal.days_left === 1 ? "" : "s"}: ${formatMoney(Number(ovGoal.needed_per_day))} por dia.` };
    } else {
      status = { tone: "negative", icon: "flag", text: `O mês fechou a ${formatMoney(falta)} da meta.` };
    }
    container.innerHTML = `
      <div class="goal__numbers">
        <strong class="value-currency">${formatMoney(feito)}</strong>
        <span>de <span class="value-currency">${formatMoney(alvo)}</span> · ${Math.floor(ovGoal.percent)}%</span>
      </div>
      <div class="goal__bar${ovGoal.reached ? " goal__bar--done" : ""}" role="progressbar" aria-label="Progresso da meta"
           aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.min(Math.floor(ovGoal.percent), 100)}">
        <i style="--share: ${parte.toFixed(4)}"></i>
      </div>
      <p class="goal__status goal__status--${status.tone}">
        <span class="material-symbols-rounded" aria-hidden="true">${status.icon}</span>${escapeHtml(status.text)}
      </p>
      <div><button class="ghost-button" type="button" data-goal-edit>Alterar meta</button></div>`;
  }
  container.querySelector("[data-goal-edit]")?.addEventListener("click", openGoalForm);
}

function openGoalForm() {
  const form = document.querySelector("#ovGoalForm");
  if (!form || !ovGoal) return;
  const input = document.querySelector("#ovGoalInput");
  input.value = ovGoal.target !== null ? formatMoney(Number(ovGoal.target)) : "";
  document.querySelector("#ovGoalFormLabel").textContent =
    `Quanto você quer faturar em ${CAL_MONTHS[calendarCursor.getMonth()].toLowerCase()}?`;
  document.querySelector("#ovGoalRemove").hidden = ovGoal.target === null;
  document.querySelector("#ovGoalError").hidden = true;
  form.hidden = false;
  input.focus();
}

function closeGoalForm() {
  const form = document.querySelector("#ovGoalForm");
  if (form) form.hidden = true;
}

async function saveGoal(method, body) {
  const erro = document.querySelector("#ovGoalError");
  try {
    const mes = cursorMonthKey();
    ovGoal = await apiRequest(method === "DELETE" ? `/finance/goal/?month=${mes}` : "/finance/goal/", {
      method,
      body: body ? JSON.stringify({ ...body, month: mes }) : undefined
    });
    ovGoalKey = `${mes}|${dataVersion}`;
    closeGoalForm();
    renderGoal();
    // O insight da meta muda junto.
    loadInsights(true);
  } catch (requestError) {
    erro.textContent = requestError.message;
    erro.hidden = false;
  }
}

document.querySelector("#ovGoalInput")?.addEventListener("input", (event) => {
  const input = event.target;
  input.value = centsFromMasked(input.value) ? maskMoney(input.value) : "";
});

document.querySelector("#ovGoalForm")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const centavos = centsFromMasked(document.querySelector("#ovGoalInput").value);
  if (centavos <= 0) {
    const erro = document.querySelector("#ovGoalError");
    erro.textContent = "Informe um valor maior que zero.";
    erro.hidden = false;
    return;
  }
  const botao = document.querySelector("#ovGoalSave");
  botao.disabled = true;
  await saveGoal("PUT", { target_amount: (centavos / 100).toFixed(2) });
  botao.disabled = false;
});

document.querySelector("#ovGoalCancel")?.addEventListener("click", closeGoalForm);
document.querySelector("#ovGoalRemove")?.addEventListener("click", () => saveGoal("DELETE"));

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
  loadProfitTable();
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
const CHART_MONTH_SHORT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

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
          <small>${escapeHtml(quando)} · ${escapeHtml(origem.label)}${PAYMENT_METHOD_LABEL[item.payment_method] ? ` · ${escapeHtml(PAYMENT_METHOD_LABEL[item.payment_method])}` : ""}</small>
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
  const daVenda = item.source === "sale";
  const somenteLeitura = doPix || daVenda;

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
      ["Forma de pagamento", PAYMENT_METHOD_LABEL[item.payment_method] || "Não informada"],
      ["Registrada em", formatDateTime(item.created_at)]
    ])}
    ${doPix
      ? `<p class="drawer__note">Esta entrada foi criada automaticamente quando a cobrança PIX foi paga. Editar aqui faria o financeiro divergir da cobrança, então ela é somente leitura.</p>`
      : daVenda
      ? `<p class="drawer__note">Esta entrada veio de uma venda. Para desfazer, cancele a venda na tela de Vendas: o estoque volta junto.</p>`
      : `<div class="drawer__actions">
           <button class="ghost-button" type="button" id="txEdit">Editar</button>
           <button class="ghost-button ghost-button--danger" type="button" id="txDelete">Excluir</button>
         </div>`}
  `;

  if (!somenteLeitura) {
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
    // Já importado (mesmo FITID) ou parecido com algo lançado na plataforma
    // (venda, PIX, lançamento manual): nos dois casos a linha vem desmarcada.
    const parecido = linha.possible_match;
    const desmarcada = linha.duplicate || Boolean(parecido);
    const etiqueta = linha.duplicate
      ? `<span class="import-row__tag status-badge status-badge--neutral">Já importado</span>`
      : parecido
      ? `<span class="import-row__tag status-badge status-badge--warning"
               title="${escapeHtml(`${parecido.description} · ${new Date(parecido.occurred_at).toLocaleDateString("pt-BR")}`)}">
           Já lançado: ${escapeHtml(txSourceInfo(parecido.source).label)}
         </span>`
      : `<span class="import-row__tag"></span>`;
    return `
      <div class="import-row ${desmarcada ? "import-row--duplicate" : ""}" data-import-row
           data-external-id="${escapeHtml(linha.external_id)}"
           data-occurred-at="${escapeHtml(linha.occurred_at)}"
           data-amount="${escapeHtml(linha.amount)}">
        <input class="import-row__check" type="checkbox" id="${id}" data-import-check
               ${desmarcada ? "" : "checked"} />
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
        ${etiqueta}
        ${parecido ? `<p class="import-row__match">Parece ${escapeHtml(parecido.description)}, de ${escapeHtml(new Date(parecido.occurred_at).toLocaleDateString("pt-BR"))}. Importar contaria o mesmo dinheiro duas vezes.</p>` : ""}
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
  const parecidos = importPreview?.possible_matches || 0;

  const partes = [`${marcados} de ${total} lançamentos selecionados`];
  if (duplicados) {
    partes.push(`${duplicados} já ${duplicados === 1 ? "existe" : "existem"} no financeiro e ${duplicados === 1 ? "veio desmarcado" : "vieram desmarcados"}`);
  }
  if (parecidos) {
    partes.push(`${parecidos} ${parecidos === 1 ? "parece já ter sido lançado" : "parecem já ter sido lançados"} na plataforma e ${parecidos === 1 ? "veio desmarcado" : "vieram desmarcados"}`);
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
  updateTxSaleHint();
  document.querySelector("#txDescription").value = item ? item.description : "";
  document.querySelector("#txAmount").value = item ? formatMoney(item.amount) : "";
  document.querySelector("#txMethod").value = item ? item.payment_method || "" : "";
  document.querySelector("#txDate").value = item ? dateKey(transactionDate(item)) : dateKey(new Date());

  const erro = document.querySelector("#txFormError");
  erro.hidden = true;
  erro.textContent = "";

  modal.hidden = false;
  requestAnimationFrame(() => modal.classList.add("is-open"));
  document.addEventListener("keydown", txModalEscHandler);
  document.querySelector("#txDescription")?.focus();
}

// Entrada nova pode ser a venda de um produto, que tem tela própria: lá o
// estoque baixa e o lucro é calculado. Lançada aqui, nada disso acontece.
function updateTxSaleHint() {
  const dica = document.querySelector("#txSaleHint");
  if (!dica) return;
  dica.hidden = Boolean(txEditingId) || document.querySelector("#txType").value !== "income";
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
  if (!grid) return;

  if (!state.products.length) {
    grid.innerHTML = `<p class="empty-state">Seu catálogo está vazio — cadastre o primeiro produto para a plataforma calcular a margem de cada um.</p>`;
    return;
  }

  grid.innerHTML = state.products.map((product) => {
    // Produto salvo antes destes campos existirem não traz os calculados; a
    // conta local cobre esse caso sem quebrar a tela.
    const conta = productMargin({
      price: Number(product.price) || 0,
      cost: Number(product.cost) || 0,
      otherCosts: Number(product.other_costs) || 0,
      feePercent: Number(product.fee_percent) || 0,
      taxPercent: Number(product.tax_percent) || 0
    });
    const margem = product.margin_value !== undefined ? Number(product.margin_value) : conta.margem;
    const margemPercent = product.margin_percent !== undefined
      ? Number(product.margin_percent)
      : conta.margemPercent;
    const unidade = PRODUCT_UNITS[product.unit] || "un";
    const estoqueBaixo = product.is_low_stock ?? (product.min_stock > 0 && product.stock <= product.min_stock);
    const inativo = product.is_active === false;

    return `
      <article class="product-card ${inativo ? "product-card--inactive" : ""}" tabindex="0"
               role="button" data-product="${escapeHtml(product.id)}">
        <div class="product-card__photo" data-product-photo="${escapeHtml(product.id)}">
          <span class="material-symbols-rounded" aria-hidden="true">photo_camera</span>
        </div>
        <div class="product-card__head">
          <h4>${escapeHtml(product.name)}</h4>
          <span class="value-currency">${formatMoney(product.price)}</span>
        </div>
        <p>${escapeHtml(product.category || "Sem categoria")}${product.sku ? ` · ${escapeHtml(product.sku)}` : ""}</p>
        <div class="product-card__tags">
          <span class="status-badge status-badge--${margem < 0 ? "negative" : "positive"}">
            ${margem < 0 ? "Prejuízo" : "Margem"} ${formatMoney(Math.abs(margem))} · ${margemPercent.toFixed(0)}%
          </span>
          ${estoqueBaixo ? `<span class="status-badge status-badge--warning">Estoque baixo</span>` : ""}
          ${inativo ? `<span class="status-badge status-badge--neutral">Inativo</span>` : ""}
        </div>
        <div class="product-meta">
          <span><b>Custo total</b><em>${formatMoney(conta.custoTotal)}</em></span>
          <span><b>Taxas</b><em>${formatMoney(conta.taxas)}</em></span>
          <span><b>Estoque</b><em>${product.stock ?? 0} ${escapeHtml(unidade)}</em></span>
        </div>
      </article>`;
  }).join("");

  grid.querySelectorAll("[data-product]").forEach((card) => {
    const abrir = () => {
      const produto = state.products.find((item) => String(item.id) === String(card.dataset.product));
      if (produto) openProductModal(produto);
    };
    card.addEventListener("click", abrir);
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        abrir();
      }
    });
  });

  // As fotos chegam depois: cada uma é uma requisição autenticada, e segurar a
  // grade até todas voltarem deixaria a tela vazia à toa.
  state.products.filter((product) => product.has_image).forEach(async (product) => {
    const url = await productImageUrl(product);
    const alvo = grid.querySelector(`[data-product-photo="${CSS.escape(String(product.id))}"]`);
    if (url && alvo) alvo.innerHTML = `<img src="${url}" alt="Foto de ${escapeHtml(product.name)}" />`;
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
  document.querySelector("#chargeQuantityField").hidden = true;
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
  const quantityField = document.querySelector("#chargeQuantityField");
  if (quantityField) quantityField.hidden = !product;
  if (!product) return;
  const quantidade = Math.max(1, parseInt(document.querySelector("#chargeQuantity").value, 10) || 1);
  document.querySelector("#chargeDescription").value = quantidade > 1 ? `${quantidade}x ${product.name}` : product.name;
  const cents = Math.round(Number(product.price) * 100) * quantidade;
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

// ─── Chat com IA (assistente financeiro e marketing) ─────────────────────────

// As duas telas de IA têm o mesmo formato: histórico de conversas à esquerda,
// thread no centro, sugestões e campo livre embaixo. O que muda é a rota, a
// saudação, as sugestões e como a resposta é desenhada — por isso um
// controlador só, configurado por tela.

const ASSISTANT_GREETING =
  "Oi! Eu leio os números do seu negócio e explico em português claro. " +
  "Posso dizer quanto sobrou no mês, comparar com os anteriores, apontar " +
  "qual produto rende mais e quais cobranças ainda não foram pagas.";

const MARKETING_GREETING =
  "Oi! Me diga o que você quer divulgar e do jeito que preferir: um post, uma " +
  "campanha, uma legenda, ideias de vídeo, uma mensagem para os clientes. " +
  "Eu já conheço os produtos do seu catálogo e a margem real de cada um.";

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

// Parágrafos entram como texto, nunca como HTML.
function renderPlainParagraphs(article, text) {
  String(text).split(/\n{2,}/).forEach((paragraph) => {
    const p = document.createElement("p");
    p.textContent = paragraph.replace(/\n/g, " ").trim();
    article.appendChild(p);
  });
}

function createChat(cfg) {
  const $ = (id) => document.getElementById(id);
  let currentId = null;
  let busy = false;
  let suggestionIndex = -1;

  function thread() {
    return $(cfg.ids.thread);
  }

  function appendMessage(role, text, variant, extra) {
    const el = thread();
    if (!el) return null;

    const article = document.createElement("article");
    article.className = `msg msg--${role === "user" ? "user" : "bot"}`;
    if (variant) article.classList.add(`msg--${variant}`);

    if (role !== "user" && !variant && cfg.renderBot) cfg.renderBot(article, text, extra || {});
    else renderPlainParagraphs(article, text);

    el.appendChild(article);
    el.scrollTop = el.scrollHeight;
    return article;
  }

  function suggestionButtons() {
    return [...document.querySelectorAll(`#${cfg.ids.suggestionList} .suggestion`)];
  }

  function setSuggestionsVisible(visible) {
    $(cfg.ids.suggestions)?.classList.toggle("is-hidden", !visible || !suggestionButtons().length);
    if (!visible) highlightSuggestion(-1);
  }

  function highlightSuggestion(index) {
    suggestionIndex = index;
    suggestionButtons().forEach((item, i) => {
      const active = i === index;
      item.classList.toggle("is-active", active);
      item.setAttribute("aria-selected", String(active));
      if (active) item.scrollIntoView({ block: "nearest" });
    });
  }

  // Sugestões dinâmicas (as do marketing citam produtos do catálogo) são
  // redesenhadas a cada conversa nova; as fixas vêm prontas no HTML.
  function renderSuggestions() {
    if (!cfg.suggestions) return;
    const list = $(cfg.ids.suggestionList);
    if (!list) return;
    list.innerHTML = cfg.suggestions().map((item) => `
      <button class="suggestion" type="button" role="option" aria-selected="false" data-ask="${escapeHtml(item.ask)}">
        <span class="suggestion__arrow" aria-hidden="true">→</span>${escapeHtml(item.label || item.ask)}
      </button>`).join("");
  }

  function setBusy(value) {
    busy = value;
    const send = $(cfg.ids.send);
    const input = $(cfg.ids.input);
    if (send) send.disabled = value;
    if (input) input.disabled = value;
  }

  function setTitle(texto) {
    const el = $(cfg.ids.title);
    if (el) el.textContent = texto || "Nova conversa";
  }

  function setAsideOpen(open) {
    const shell = $(cfg.ids.shell);
    if (!shell) return;
    shell.classList.toggle("is-collapsed", !open);
    $(cfg.ids.toggle)?.setAttribute("aria-expanded", String(open));
  }

  async function loadConversations() {
    const list = $(cfg.ids.list);
    if (!list) return;

    let conversas = [];
    try {
      conversas = await apiRequest(cfg.conversationsPath);
    } catch {
      list.innerHTML = `<p class="chat-aside__empty">Não foi possível carregar as conversas.</p>`;
      return;
    }

    if (!conversas.length) {
      list.innerHTML = `<p class="chat-aside__empty">${escapeHtml(cfg.emptyHistory)}</p>`;
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
          <div class="chat-item${conversa.id === currentId ? " is-active" : ""}">
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

  async function openConversation(id) {
    const el = thread();
    if (!el) return;

    try {
      const conversa = await apiRequest(`${cfg.conversationsPath}${id}/`);
      currentId = conversa.id;
      setTitle(conversa.title);
      el.innerHTML = "";
      conversa.messages.forEach((m) => appendMessage(m.role, m.content, null, m));
      setSuggestionsVisible(conversa.messages.length === 0);
      loadConversations();
    } catch {
      appendMessage("bot", "Não foi possível abrir essa conversa.", "error");
    }
  }

  async function deleteConversation(id) {
    try {
      await apiRequest(`${cfg.conversationsPath}${id}/`, { method: "DELETE" });
    } catch {
      return;
    }
    if (id === currentId) startNew();
    else loadConversations();
  }

  function startNew() {
    const el = thread();
    if (!el) return;
    currentId = null;
    setTitle(null);
    el.innerHTML = "";
    appendMessage("bot", cfg.greeting, "greeting");
    renderSuggestions();
    setSuggestionsVisible(true);
    highlightSuggestion(-1);
    loadConversations();
    $(cfg.ids.input)?.focus();
  }

  async function ask(question) {
    const text = String(question || "").trim();
    if (!text || busy) return;

    setSuggestionsVisible(false);
    appendMessage("user", text);

    const pending = appendMessage("bot", cfg.pendingText, "pending");
    setBusy(true);

    try {
      const data = await apiRequest(cfg.askPath, {
        method: "POST",
        body: JSON.stringify({ message: text, conversation_id: currentId })
      });
      pending?.remove();
      appendMessage("bot", data.message, null, data);
      currentId = data.conversation.id;
      setTitle(data.conversation.title);
      loadConversations();
    } catch (error) {
      pending?.remove();
      appendMessage("bot", error.message, "error");
    } finally {
      setBusy(false);
      $(cfg.ids.input)?.focus();
    }
  }

  $(cfg.ids.form)?.addEventListener("submit", (event) => {
    event.preventDefault();
    const input = $(cfg.ids.input);
    const question = input.value;
    input.value = "";
    ask(question);
  });

  $(cfg.ids.newButton)?.addEventListener("click", () => {
    startNew();
    if (window.matchMedia("(max-width: 768px)").matches) setAsideOpen(false);
  });

  $(cfg.ids.toggle)?.addEventListener("click", () => {
    setAsideOpen($(cfg.ids.shell)?.classList.contains("is-collapsed"));
  });

  // Delegado na lista: as sugestões do marketing são recriadas a cada conversa.
  $(cfg.ids.suggestionList)?.addEventListener("click", (event) => {
    const item = event.target.closest(".suggestion");
    if (item) ask(item.dataset.ask);
  });

  // Teclado no campo: setas navegam as sugestões, Enter escolhe a destacada
  // (ou envia o que foi digitado) e Esc fecha a lista.
  $(cfg.ids.input)?.addEventListener("keydown", (event) => {
    const items = suggestionButtons();
    const visible = !$(cfg.ids.suggestions)?.classList.contains("is-hidden");

    if (event.key === "ArrowDown" && visible && items.length) {
      event.preventDefault();
      highlightSuggestion((suggestionIndex + 1) % items.length);
    } else if (event.key === "ArrowUp" && visible && items.length) {
      event.preventDefault();
      highlightSuggestion(suggestionIndex <= 0 ? items.length - 1 : suggestionIndex - 1);
    } else if (event.key === "Enter" && visible && suggestionIndex >= 0) {
      event.preventDefault();
      ask(items[suggestionIndex].dataset.ask);
    } else if (event.key === "Escape" && visible) {
      setSuggestionsVisible(false);
    }
  });

  // Ao abrir a tela sem conversa em andamento, recomeça e recarrega o
  // histórico — a conversa vive no servidor.
  function ensureStarted() {
    if (currentId === null) startNew();
  }

  // No celular a lista cobre o chat: a tela abre com ela recolhida.
  if (window.matchMedia("(max-width: 768px)").matches) setAsideOpen(false);

  return { startNew, ensureStarted, openConversation, refreshSuggestions: renderSuggestions };
}

// ─── Assistente financeiro ──────────────────────────────────────────────────

const financeChat = createChat({
  ids: {
    shell: "assistantShell",
    toggle: "asideToggle",
    list: "chatHistoryList",
    newButton: "assistantNew",
    title: "assistantTitle",
    thread: "assistantThread",
    suggestions: "assistantSuggestions",
    suggestionList: "assistantSuggestionList",
    form: "assistantForm",
    input: "assistantInput",
    send: "assistantSend"
  },
  askPath: "/finance/assistant/",
  conversationsPath: "/finance/assistant/conversations/",
  greeting: ASSISTANT_GREETING,
  pendingText: "Analisando seus números…",
  emptyHistory: "Suas conversas aparecem aqui depois da primeira pergunta."
});

// ─── Marketing com IA ───────────────────────────────────────────────────────

// O texto da IA vem com **negrito** no estilo markdown. O escape vem antes de
// qualquer tag, para o texto do modelo nunca virar HTML; so depois os pares de
// ** viram <strong>. Trocar cada ** por <strong> abriria a tag e nunca a
// fecharia.
function formatCampaignText(rawText) {
  return escapeHtml(rawText)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replaceAll("\n", "<br>");
}

function renderMarketingReply(article, text, extra) {
  String(text).split(/\n{2,}/).forEach((paragraph) => {
    const p = document.createElement("p");
    p.innerHTML = formatCampaignText(paragraph.trim());
    article.appendChild(p);
  });

  const actions = document.createElement("div");
  actions.className = "msg__actions";
  const copy = document.createElement("button");
  copy.type = "button";
  copy.className = "msg__action";
  copy.innerHTML = `<span class="material-symbols-rounded" aria-hidden="true">content_copy</span>Copiar texto`;
  copy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(String(text).replace(/\*\*/g, ""));
      copy.lastChild.textContent = "Copiado";
    } catch {
      copy.lastChild.textContent = "Não foi possível copiar";
    }
  });
  actions.appendChild(copy);
  article.appendChild(actions);

  if (extra.has_image && extra.campaign_id) showCampaignImage(article, actions, extra.campaign_id);
}

// A rota da imagem exige o token, e <img src> não manda cabeçalho. Mesma
// solução da foto de produto: busca com fetch e monta um object URL.
async function showCampaignImage(article, actions, campaignId) {
  try {
    const response = await fetch(`${apiBaseUrl}/marketing/campaigns/${campaignId}/image/`, {
      headers: { Authorization: `Token ${authToken}` }
    });
    if (!response.ok) return;

    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const img = new Image();
    img.className = "msg__image";
    img.alt = "Imagem gerada para a campanha";
    img.onload = () => {
      article.insertBefore(img, actions);
      const download = document.createElement("a");
      download.className = "msg__action";
      download.href = objectUrl;
      download.download = `campanha-${campaignId.slice(0, 8)}.${blob.type.includes("png") ? "png" : "jpg"}`;
      download.innerHTML = `<span class="material-symbols-rounded" aria-hidden="true">download</span>Baixar imagem`;
      actions.appendChild(download);
    };
    img.onerror = () => URL.revokeObjectURL(objectUrl);
    img.src = objectUrl;
  } catch {
    // Sem imagem o texto da campanha continua servindo.
  }
}

// Sugestões que citam o catálogo de verdade: o produto de melhor margem é o
// que mais vale divulgar. Sem produto, ficam as genéricas.
const MARKETING_GOALS = {
  promocao: "promoção",
  lancamento: "lançamento",
  relacionamento: "relacionamento com os clientes"
};

async function loadMarketingRecommendations() {
  if (marketingRecsVersion === dataVersion) return;
  marketingRecsVersion = dataVersion;
  try {
    const data = await apiRequest("/marketing/recommendations/");
    marketingRecommendations = data.recommendations || [];
  } catch {
    return;
  }
  marketingChat.refreshSuggestions();
  renderMarketingCards();
}

// Cada recomendação vira um pedido pronto para o chat. O pedido muda com a
// situação do produto: em prejuízo a conversa é sobre preço, com estoque
// baixo é sobre avisar quem já compra, e só no resto é campanha.
function recommendationSuggestion(rec) {
  const produto = (state.products || []).find((item) => String(item.id) === String(rec.product_id));
  if (!produto) return null;
  const label = `${rec.title}: ${rec.text}`;
  if (Number(produto.margin_value) < 0) {
    return { label, ask: `${produto.name} está dando prejuízo. Como posso ajustar o preço sem perder clientes?` };
  }
  if (produto.is_low_stock) {
    return { label, ask: `Escreva uma mensagem de WhatsApp avisando meus clientes que restam poucas unidades de ${produto.name}` };
  }
  const objetivo = MARKETING_GOALS[rec.goal] || "promoção";
  return { label, ask: `Crie uma campanha de ${objetivo} para o ${rec.channel || "Instagram"} divulgando ${produto.name}` };
}

function marketingSuggestions() {
  const recomendadas = marketingRecommendations.map(recommendationSuggestion).filter(Boolean).slice(0, 3);
  if (recomendadas.length) {
    return [...recomendadas, { ask: "Me dê 5 ideias de vídeos curtos para o TikTok" }];
  }
  const ativos = (state.products || []).filter((p) => p.is_active !== false);
  const melhor = [...ativos].sort((a, b) => Number(b.margin_value ?? 0) - Number(a.margin_value ?? 0))[0];
  const itens = [];
  if (melhor) {
    itens.push({ ask: `Crie um post para o Instagram divulgando ${melhor.name}` });
    itens.push({ ask: `Escreva uma mensagem de WhatsApp oferecendo ${melhor.name} para meus clientes` });
  }
  itens.push({ ask: "Qual produto eu deveria divulgar essa semana e por quê?" });
  itens.push({ ask: "Me dê 5 ideias de vídeos curtos para o TikTok" });
  return itens;
}

const marketingChat = createChat({
  ids: {
    shell: "marketingShell",
    toggle: "marketingAsideToggle",
    list: "marketingHistoryList",
    newButton: "marketingNew",
    title: "marketingTitle",
    thread: "marketingThread",
    suggestions: "marketingSuggestions",
    suggestionList: "marketingSuggestionList",
    form: "marketingForm",
    input: "marketingInput",
    send: "marketingSend"
  },
  askPath: "/marketing/chat/",
  conversationsPath: "/marketing/conversations/",
  greeting: MARKETING_GREETING,
  pendingText: "Criando…",
  emptyHistory: "Suas campanhas e conversas aparecem aqui depois do primeiro pedido.",
  suggestions: marketingSuggestions,
  renderBot: renderMarketingReply
});


// ─── Marketing: aba Ações ───────────────────────────────────────────────────
// A tela abre mostrando o que fazer, a partir das vendas, da margem e do
// estoque. Cada botão leva a um resultado concreto: a campanha pronta, o
// aviso para o WhatsApp ou o campo do produto que precisa de ajuste. O chat
// continua na aba Conversa, para o pedido livre e para ajustar o que o botão
// gerou.

let marketingProducts = [];
let marketingCards = [];
let marketingGallery = [];
let marketingResult = null;

// Rótulo do botão por ação. "Avisar clientes" prometeria um envio que a
// plataforma não faz: ela prepara a mensagem e o envio é no WhatsApp do MEI.
const MKT_ACTION_LABEL = {
  campaign: "Criar promoção",
  launch: "Criar post de lançamento",
  whatsapp: "Criar aviso para WhatsApp",
  price: "Ajustar preço",
  stock: "Atualizar estoque"
};
const MKT_TONE = { positive: "positive", warning: "warning", negative: "negative", neutral: "neutral" };
const MKT_GENERATES = ["campaign", "launch", "whatsapp"];

function setMarketingTab(tab, { fromView = false } = {}) {
  marketingTab = tab;
  const acoes = tab === "actions";
  document.querySelector("#mktActions").hidden = !acoes;
  document.querySelector("#marketingShell").hidden = acoes;
  document.querySelectorAll("[data-mkt-tab]").forEach((botao) => {
    const ativo = botao.dataset.mktTab === tab;
    botao.classList.toggle("is-active", ativo);
    botao.setAttribute("aria-selected", String(ativo));
  });
  document.querySelector(".dashboard")?.classList.toggle("is-chat", !acoes);
  document.querySelector("#app-marketing").classList.toggle("view--full", !acoes);
  if (acoes) {
    if (!fromView) loadMarketingActions();
  } else {
    marketingChat.ensureStarted();
  }
}

function marketingProduct(id) {
  return (state.products || []).find((item) => String(item.id) === String(id));
}

async function loadMarketingActions() {
  await Promise.all([loadMarketingProducts(), loadMarketingGallery()]);
  renderMarketingCards();
}

async function loadMarketingProducts() {
  try {
    marketingProducts = await apiRequest("/marketing/products/");
  } catch {
    marketingProducts = [];
  }
  renderMarketingProducts();
}

function renderMarketingCards() {
  const container = document.querySelector("#mktCards");
  if (!container) return;

  // Um cartão por produto: duas recomendações do mesmo produto dividiriam a
  // atenção sem dizer nada novo.
  const vistos = new Set();
  const cards = marketingRecommendations.filter((rec) => {
    if (!rec.product_id || !rec.action || vistos.has(rec.product_id)) return false;
    vistos.add(rec.product_id);
    return true;
  }).slice(0, 4);
  marketingCards = cards;
  if (!cards.length) {
    container.innerHTML = (state.products || []).length
      ? `<p class="empty-state">Lendo os números do negócio...</p>`
      : `<div class="empty-state">Cadastre seus produtos para receber recomendações.
           <button class="ghost-button" type="button" data-goto-view="products">Ir para Produtos</button></div>`;
    return;
  }

  container.innerHTML = cards.map((rec, indice) => {
    const produto = marketingProduct(rec.product_id) || {};
    const linha = marketingProducts.find((item) => String(item.product_id) === String(rec.product_id));
    const tom = MKT_TONE[linha?.tone] || (rec.action === "price" ? "negative" : "positive");
    const margem = Number(produto.margin_value ?? linha?.margin ?? 0);
    const gera = MKT_GENERATES.includes(rec.action);
    const rotulo = rec.action === "campaign" ? `Criar promoção no ${rec.channel || "Instagram"}` : MKT_ACTION_LABEL[rec.action];
    return `
      <article class="mkt-card">
        <span class="status-badge status-badge--${tom}">${escapeHtml(rec.title)}</span>
        <h4 class="mkt-card__product">${escapeHtml(rec.product_name)}</h4>
        <p class="mkt-card__reason">${escapeHtml(rec.text)}</p>
        <dl class="mkt-card__numbers">
          <div><dt>${margem < 0 ? "Prejuízo/un" : "Lucro/un"}</dt>
               <dd class="value-currency ${margem < 0 ? "value-negative" : "value-positive"}">${margem < 0 ? "− " : ""}${formatMoney(Math.abs(margem))}</dd></div>
          <div><dt>Estoque</dt><dd class="value-currency">${linha && !linha.controls_stock ? "serviço" : `${produto.stock ?? linha?.stock ?? 0} un`}</dd></div>
        </dl>
        <button class="${gera ? "primary-button" : "ghost-button"}" type="button" data-mkt-card="${indice}">${escapeHtml(rotulo)}</button>
        ${gera ? `<button class="mkt-card__alt" type="button" data-mkt-card-chat="${indice}">Ajustar o pedido no chat</button>` : ""}
      </article>`;
  }).join("");

}

function renderMarketingProducts() {
  const container = document.querySelector("#mktProducts");
  if (!container) return;
  if (!marketingProducts.length) {
    container.innerHTML = `<p class="empty-state">Nenhum produto ativo no catálogo.</p>`;
    return;
  }

  container.innerHTML = `
    <div class="mkt-row mkt-row--head" aria-hidden="true">
      <span>Produto</span><span>Vendidos</span><span>Lucro real</span><span>Estoque</span><span>Situação</span><span></span>
    </div>` + marketingProducts.map((linha, indice) => {
    const lucro = Number(linha.profit_month) || 0;
    return `
      <div class="mkt-row">
        <span class="mkt-row__name">${escapeHtml(linha.name)}</span>
        <span class="mkt-row__cell" data-label="Vendidos">${linha.quantity_month}</span>
        <span class="mkt-row__cell value-currency ${lucro < 0 ? "value-negative" : lucro > 0 ? "value-positive" : ""}" data-label="Lucro real">${lucro < 0 ? "− " : ""}${formatMoney(Math.abs(lucro))}</span>
        <span class="mkt-row__cell" data-label="Estoque">${linha.controls_stock ? linha.stock : "serviço"}</span>
        <span class="mkt-row__status"><span class="status-badge status-badge--${MKT_TONE[linha.tone] || "neutral"}">${escapeHtml(linha.status)}</span></span>
        <span class="mkt-row__action"><button class="ghost-button" type="button" data-mkt-product="${indice}">${escapeHtml(MKT_ACTION_LABEL[linha.action] || "Criar promoção")}</button></span>
      </div>`;
  }).join("");

}

// Primeira linha útil da campanha, para o título do card da galeria.
function campaignHeadline(texto, reserva) {
  const chamada = String(texto || "").match(/\*\*Chamada principal:\*\*\s*(.+)/i);
  return (chamada ? chamada[1] : reserva || "Campanha").replace(/\*\*/g, "").trim();
}

async function loadMarketingGallery() {
  const container = document.querySelector("#mktGallery");
  if (!container) return;
  let campanhas = [];
  try {
    const data = await apiRequest("/marketing/campaigns/");
    campanhas = (Array.isArray(data) ? data : data.results || []).filter((c) => c.generated_text).slice(0, 6);
  } catch {
    // A galeria vazia não impede as ações.
  }
  marketingGallery = campanhas;
  if (!campanhas.length) {
    container.innerHTML = `<p class="empty-state">As campanhas que você gerar aparecem aqui, com o texto e a imagem para baixar.</p>`;
    return;
  }

  container.innerHTML = campanhas.map((c, indice) => `
    <article class="mkt-shot">
      <div class="mkt-shot__image" data-mkt-shot-image="${escapeHtml(c.id)}">
        <span class="material-symbols-rounded" aria-hidden="true">image</span>
      </div>
      <div class="mkt-shot__body">
        <span class="mkt-shot__meta">${escapeHtml(c.channel || "Instagram")} · ${escapeHtml(new Date(c.created_at).toLocaleDateString("pt-BR"))}${c.product_name ? ` · ${escapeHtml(c.product_name)}` : ""}</span>
        <h4>${escapeHtml(campaignHeadline(c.generated_text, c.product_name))}</h4>
        <button class="ghost-button" type="button" data-mkt-shot="${indice}">Ver campanha</button>
      </div>
    </article>`).join("");


  campanhas.filter((c) => c.has_image).forEach(async (c) => {
    const url = await campaignImageUrl(c.id);
    const alvo = container.querySelector(`[data-mkt-shot-image="${CSS.escape(String(c.id))}"]`);
    if (url && alvo) alvo.innerHTML = `<img src="${url}" alt="Imagem da campanha" />`;
  });
}

// A rota da imagem exige o token: busca com fetch e guarda o object URL.
const campaignImageCache = new Map();
async function campaignImageUrl(id) {
  if (campaignImageCache.has(id)) return campaignImageCache.get(id);
  try {
    const response = await fetch(`${apiBaseUrl}/marketing/campaigns/${id}/image/`, {
      headers: { Authorization: `Token ${authToken}` }
    });
    if (!response.ok) return null;
    const url = URL.createObjectURL(await response.blob());
    campaignImageCache.set(id, url);
    return url;
  } catch {
    return null;
  }
}

async function runMarketingAction(productId, action, channel) {
  // Preço e estoque se resolvem no cadastro do produto, não com campanha:
  // divulgar produto em prejuízo é vender no vermelho.
  if (action === "price" || action === "stock") {
    const produto = marketingProduct(productId);
    setView("products");
    if (produto) {
      openProductModal(produto);
      window.setTimeout(() => document.querySelector(action === "price" ? "#productPrice" : "#productStock")?.focus(), 350);
    }
    return;
  }

  const produto = marketingProduct(productId);
  const titulo = action === "whatsapp" ? "Aviso para WhatsApp" : action === "launch" ? "Post de lançamento" : "Promoção";
  openMarketingResult({ loading: true, title: `${titulo}: ${produto?.name || "produto"}` });

  try {
    const resultado = await apiRequest("/marketing/actions/", {
      method: "POST",
      body: JSON.stringify({ product_id: productId, action, channel: channel || "Instagram" })
    });
    openMarketingResult({ ...resultado, title: `${titulo}: ${produto?.name || "produto"}`, productId, channel });
  } catch (erro) {
    openMarketingResult({ error: erro.message || "Não foi possível gerar agora.", title: titulo, action, productId, channel });
    return;
  }
  // A campanha nova muda a galeria, a situação dos produtos e as recomendações.
  marketingRecsVersion = -1;
  loadMarketingActions();
  loadMarketingRecommendations();
}

function openMarketingResult(resultado) {
  marketingResult = resultado;
  const modal = document.querySelector("#mktResultModal");
  const corpo = document.querySelector("#mktResultBody");
  document.querySelector("#mktResultTitle").textContent = resultado.title || "Campanha";

  if (resultado.loading) {
    corpo.innerHTML = `<p class="mkt-result__loading">Criando com a sua margem e o seu estoque... pode levar alguns segundos.</p>`;
  } else if (resultado.error) {
    corpo.innerHTML = `<p class="modal__error">${escapeHtml(resultado.error)}</p>
      <div class="modal__actions"><button class="primary-button" type="button" data-mkt-again>Tentar de novo</button></div>`;
  } else {
    const whatsapp = resultado.action === "whatsapp";
    const textoLimpo = String(resultado.message || "").replace(/\*\*/g, "");
    corpo.innerHTML = `
      <div class="mkt-result__text">${String(resultado.message || "").split(/\n{2,}/).map((p) => `<p>${formatCampaignText(p.trim())}</p>`).join("")}</div>
      <div class="mkt-result__image" id="mktResultImage" hidden></div>
      ${whatsapp ? `<p class="mkt-result__note">A mensagem abre no seu WhatsApp já escrita. Você escolhe para quem mandar: um contato, um grupo ou uma lista de transmissão.</p>` : ""}
      ${whatsapp && resultado.provider === "local-demo" ? `<p class="mkt-result__note">Mensagem padrão: a IA de marketing não respondeu, então o texto não foi personalizado.</p>` : ""}
      <div class="mkt-result__actions">
        ${whatsapp ? `<a class="primary-button" href="https://wa.me/?text=${encodeURIComponent(textoLimpo)}" target="_blank" rel="noopener">Abrir no WhatsApp</a>` : ""}
        <button class="${whatsapp ? "ghost-button" : "primary-button"}" type="button" data-mkt-copy>Copiar texto</button>
        <a class="ghost-button" id="mktResultDownload" hidden>Baixar imagem</a>
        ${resultado.productId ? `<button class="ghost-button" type="button" data-mkt-again>Gerar de novo</button>` : ""}
        ${resultado.conversation?.id ? `<button class="ghost-button" type="button" data-mkt-chat>Ajustar no chat</button>` : ""}
        ${resultado.campaign_id ? `<button class="ghost-button ghost-button--danger mkt-result__delete" type="button" data-mkt-delete>
          <span class="material-symbols-rounded" aria-hidden="true">delete</span>Excluir campanha
        </button>` : ""}
      </div>
      <p class="modal__error" id="mktResultError" role="alert" hidden></p>`;

    corpo.querySelector("[data-mkt-copy]").addEventListener("click", async (event) => {
      try {
        await navigator.clipboard.writeText(textoLimpo);
        event.currentTarget.textContent = "Copiado";
      } catch {
        event.currentTarget.textContent = "Não foi possível copiar";
      }
    });
    corpo.querySelector("[data-mkt-delete]")?.addEventListener("click", (event) =>
      deleteMarketingCampaign(resultado, event.currentTarget)
    );
    corpo.querySelector("[data-mkt-chat]")?.addEventListener("click", () => {
      closeMarketingResult();
      setMarketingTab("chat");
      marketingChat.openConversation(resultado.conversation.id);
    });
    if (resultado.has_image && resultado.campaign_id) {
      campaignImageUrl(resultado.campaign_id).then((url) => {
        if (!url || marketingResult !== resultado) return;
        const caixa = document.querySelector("#mktResultImage");
        caixa.innerHTML = `<img src="${url}" alt="Imagem gerada para a campanha" />`;
        caixa.hidden = false;
        const baixar = document.querySelector("#mktResultDownload");
        baixar.href = url;
        baixar.download = `campanha-${String(resultado.campaign_id).slice(0, 8)}.jpg`;
        baixar.hidden = false;
      });
    }
  }

  corpo.querySelector("[data-mkt-again]")?.addEventListener("click", () =>
    runMarketingAction(resultado.productId, resultado.action, resultado.channel)
  );

  if (modal.hidden) {
    modal.hidden = false;
    requestAnimationFrame(() => modal.classList.add("is-open"));
    document.addEventListener("keydown", marketingResultEscHandler);
  }
}

// Excluir pede um segundo clique: apagar some com texto e imagem de vez.
async function deleteMarketingCampaign(resultado, botao) {
  if (!botao.classList.contains("is-confirming")) {
    botao.classList.add("is-confirming");
    botao.innerHTML = `<span class="material-symbols-rounded" aria-hidden="true">delete</span>Confirmar exclusão`;
    return;
  }
  const erro = document.querySelector("#mktResultError");
  botao.disabled = true;
  try {
    await apiRequest(`/marketing/campaigns/${resultado.campaign_id}/`, { method: "DELETE" });
  } catch (requestError) {
    botao.disabled = false;
    erro.textContent = requestError.message || "Não foi possível excluir agora.";
    erro.hidden = false;
    return;
  }
  const url = campaignImageCache.get(resultado.campaign_id);
  if (url) URL.revokeObjectURL(url);
  campaignImageCache.delete(resultado.campaign_id);
  closeMarketingResult();
  // Sem a campanha, o produto pode voltar a "Nunca divulgado".
  marketingRecsVersion = -1;
  loadMarketingActions();
  loadMarketingRecommendations();
}

function closeMarketingResult() {
  const modal = document.querySelector("#mktResultModal");
  if (!modal) return;
  modal.classList.remove("is-open");
  marketingResult = null;
  document.removeEventListener("keydown", marketingResultEscHandler);
  window.setTimeout(() => { modal.hidden = true; }, 300);
}

function marketingResultEscHandler(event) {
  if (event.key === "Escape") closeMarketingResult();
}

document.querySelectorAll("[data-close-mkt-result]").forEach((el) => el.addEventListener("click", closeMarketingResult));

// Cliques delegados: as listas são redesenhadas quando chegam os dados, e
// um ouvinte preso ao botão antigo perderia o clique de quem foi rápido.
document.querySelector("#mktCards")?.addEventListener("click", (event) => {
  const acao = event.target.closest("[data-mkt-card]");
  const chat = event.target.closest("[data-mkt-card-chat]");
  if (acao) {
    const rec = marketingCards[Number(acao.dataset.mktCard)];
    if (rec) runMarketingAction(rec.product_id, rec.action, rec.channel);
  } else if (chat) {
    const rec = marketingCards[Number(chat.dataset.mktCardChat)];
    const sugestao = rec && recommendationSuggestion(rec);
    setMarketingTab("chat");
    const campo = document.querySelector("#marketingInput");
    if (campo && sugestao) {
      campo.value = sugestao.ask;
      campo.focus();
    }
  } else if (event.target.closest("[data-goto-view]")) {
    setView("products");
  }
});

document.querySelector("#mktProducts")?.addEventListener("click", (event) => {
  const botao = event.target.closest("[data-mkt-product]");
  const linha = botao && marketingProducts[Number(botao.dataset.mktProduct)];
  if (linha) runMarketingAction(linha.product_id, linha.action);
});

document.querySelector("#mktGallery")?.addEventListener("click", (event) => {
  const botao = event.target.closest("[data-mkt-shot]");
  const c = botao && marketingGallery[Number(botao.dataset.mktShot)];
  if (!c) return;
  openMarketingResult({
    action: "campaign",
    title: campaignHeadline(c.generated_text, c.product_name),
    message: c.generated_text,
    campaign_id: c.id,
    has_image: c.has_image,
    conversation: c.metadata?.conversation_id ? { id: c.metadata.conversation_id } : null
  });
});
document.querySelectorAll("[data-mkt-tab]").forEach((botao) =>
  botao.addEventListener("click", () => setMarketingTab(botao.dataset.mktTab))
);

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

// ─── Vendas ─────────────────────────────────────────────────────────────────
// A venda liga o catálogo ao estoque e ao financeiro. Admin e membro
// registram; quem calcula custo, taxa e lucro é o servidor, a partir do
// produto no banco. A tela só repete a conta para mostrar a prévia.

const SALE_METHODS = { dinheiro: "Dinheiro", pix: "PIX", cartao: "Cartão", outro: "Outro" };

function monthParam(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function controlsStock(product) {
  return product.unit !== "srv";
}

async function loadSales() {
  const label = document.querySelector("#salesMonthLabel");
  if (label) label.textContent = `${CAL_MONTHS[salesMonth.getMonth()]} de ${salesMonth.getFullYear()}`;
  try {
    currentSales = await apiRequest(`/sales/?month=${monthParam(salesMonth)}`);
  } catch {
    currentSales = [];
  }
  renderSales();
}

function shiftSalesMonth(delta) {
  salesMonth = new Date(salesMonth.getFullYear(), salesMonth.getMonth() + delta, 1);
  loadSales();
}

function profitBadge(lucro) {
  const valor = Number(lucro) || 0;
  return valor < 0
    ? `<span class="status-badge status-badge--negative">Prejuízo ${formatMoney(Math.abs(valor))}</span>`
    : `<span class="status-badge status-badge--positive">Lucro ${formatMoney(valor)}</span>`;
}

function renderSales() {
  const container = document.querySelector("#salesRows");
  if (!container) return;

  const concluidas = currentSales.filter((venda) => venda.status === "concluida");
  const somar = (campo) => concluidas.reduce((total, venda) => total + (Number(venda[campo]) || 0), 0);
  const lucro = somar("profit");
  document.querySelector("#salesTotal").textContent = formatMoney(somar("total"));
  const lucroEl = document.querySelector("#salesProfit");
  lucroEl.textContent = formatMoney(lucro);
  lucroEl.classList.toggle("value-positive", lucro >= 0);
  lucroEl.classList.toggle("value-negative", lucro < 0);
  document.querySelector("#salesUnits").textContent = String(somar("quantity"));

  if (!currentSales.length) {
    container.innerHTML = `<p class="empty-state">${
      state.products.length
        ? "Nenhuma venda neste mês. Registre uma venda para o estoque e o lucro andarem juntos."
        : "Cadastre um produto em Produtos para registrar a primeira venda."
    }</p>`;
    return;
  }

  container.innerHTML = currentSales.map((venda) => {
    const cancelada = venda.status === "cancelada";
    const quando = new Date(venda.occurred_at).toLocaleDateString("pt-BR");
    const origem = venda.source === "pix" ? " · Cobrança PIX" : "";
    return `
      <button class="charge-row" type="button" data-sale="${escapeHtml(venda.id)}">
        <span class="charge-row__main">
          <strong>${escapeHtml(`${venda.quantity}x ${venda.product_name}`)}</strong>
          <small>${escapeHtml(`${quando} · ${SALE_METHODS[venda.payment_method] || "Outro"}${origem}`)}</small>
        </span>
        <span class="charge-row__side">
          <span class="value-currency charge-row__amount ${cancelada ? "" : "value-positive"}">
            ${cancelada ? "" : "+ "}${formatMoney(venda.total)}
          </span>
          ${cancelada
            ? `<span class="status-badge status-badge--neutral">Cancelada</span>`
            : profitBadge(venda.profit)}
        </span>
        <span class="charge-row__chevron material-symbols-rounded" aria-hidden="true">chevron_right</span>
      </button>`;
  }).join("");

  container.querySelectorAll("[data-sale]").forEach((linha) => {
    linha.addEventListener("click", () => openSaleDrawer(linha.dataset.sale));
  });
}

function openSaleDrawer(id) {
  const drawer = document.querySelector("#saleDrawer");
  const venda = currentSales.find((item) => String(item.id) === String(id));
  if (!drawer || !venda) return;

  const cancelada = venda.status === "cancelada";
  const doPix = venda.source === "pix";
  const lucro = Number(venda.profit) || 0;

  document.querySelector("#saleDrawerTitle").textContent = `${venda.quantity}x ${venda.product_name}`;
  const kind = document.querySelector("#saleDrawerKind");
  kind.textContent = cancelada ? "Cancelada" : "Concluída";
  kind.className = `drawer__weekday ${cancelada ? "" : "status-text--positive"}`;

  document.querySelector("#saleDrawerBody").innerHTML = `
    <div class="drawer__amount">
      <span>${lucro < 0 ? "Prejuízo" : "Lucro real"}</span>
      <strong class="value-currency ${lucro < 0 ? "status-text--negative" : "status-text--positive"}">${formatMoney(Math.abs(lucro))}</strong>
    </div>
    ${drawerRows("Venda", [
      ["Produto", venda.product_name],
      ["Quantidade", String(venda.quantity)],
      ["Preço por unidade", formatMoney(venda.unit_price)],
      ["Total", formatMoney(venda.total)],
      ["Pagamento", SALE_METHODS[venda.payment_method] || "Outro"],
      ["Data", new Date(venda.occurred_at).toLocaleDateString("pt-BR")],
      ["Origem", doPix ? "Cobrança PIX paga" : "Registrada na tela de vendas"]
    ])}
    ${drawerRows("De onde sai o lucro", [
      ["Total vendido", formatMoney(venda.total)],
      ["Custo dos produtos", `− ${formatMoney(venda.cost_total)}`],
      ["Taxa e imposto", `− ${formatMoney(venda.fees)}`],
      [lucro < 0 ? "Prejuízo" : "Lucro real", formatMoney(lucro)]
    ])}
    ${cancelada
      ? `<p class="drawer__note">Venda cancelada${venda.canceled_at ? ` em ${formatDateTime(venda.canceled_at)}` : ""}. O estoque voltou e a entrada saiu do financeiro.</p>`
      : doPix
      ? `<p class="drawer__note">Esta venda veio de uma cobrança PIX paga. Para desfazer, estorne a cobrança: a venda é cancelada e o estoque volta.</p>`
      : `<p class="modal__error" id="saleCancelError" role="alert" hidden></p>
         <div class="drawer__actions">
           <button class="ghost-button ghost-button--danger" type="button" id="saleCancel">Cancelar venda</button>
         </div>`}
  `;

  // Cancelar pede um segundo clique: devolve estoque e mexe no financeiro.
  document.querySelector("#saleCancel")?.addEventListener("click", async (event) => {
    const botao = event.currentTarget;
    if (botao.dataset.confirm !== "1") {
      botao.dataset.confirm = "1";
      botao.textContent = "Confirmar cancelamento";
      return;
    }
    botao.disabled = true;
    try {
      await apiRequest(`/sales/${venda.id}/cancel/`, { method: "POST" });
    } catch (requestError) {
      const erro = document.querySelector("#saleCancelError");
      erro.textContent = requestError.message;
      erro.hidden = false;
      botao.disabled = false;
      return;
    }
    closeSaleDrawer();
    await refreshAfterSale();
  });

  drawer.hidden = false;
  requestAnimationFrame(() => drawer.classList.add("is-open"));
  document.addEventListener("keydown", saleDrawerEscHandler);
}

function closeSaleDrawer() {
  const drawer = document.querySelector("#saleDrawer");
  if (!drawer) return;
  drawer.classList.remove("is-open");
  document.removeEventListener("keydown", saleDrawerEscHandler);
  window.setTimeout(() => { drawer.hidden = true; }, 300);
}

function saleDrawerEscHandler(event) {
  if (event.key === "Escape") closeSaleDrawer();
}

function saleSelectedProduct() {
  const id = document.querySelector("#saleProduct")?.value;
  return state.products.find((item) => String(item.id) === String(id));
}

function openSaleModal() {
  const modal = document.querySelector("#saleModal");
  if (!modal) return;

  const select = document.querySelector("#saleProduct");
  const ativos = state.products.filter((product) => product.is_active !== false);
  select.innerHTML = ativos.map((product) => {
    const semEstoque = controlsStock(product) && !(Number(product.stock) > 0);
    const estoque = controlsStock(product) ? `${product.stock ?? 0} em estoque` : "serviço";
    return `<option value="${escapeHtml(product.id)}" ${semEstoque ? "disabled" : ""}>
      ${escapeHtml(product.name)} — ${formatMoney(product.price)} · ${semEstoque ? "sem estoque" : estoque}
    </option>`;
  }).join("");
  const primeiroDisponivel = select.querySelector("option:not([disabled])");
  if (primeiroDisponivel) select.value = primeiroDisponivel.value;

  document.querySelector("#saleQuantity").value = 1;
  document.querySelector("#saleMethod").value = "dinheiro";
  document.querySelector("#saleDate").value = dateKey(new Date());
  applyProductToSale();

  const erro = document.querySelector("#saleFormError");
  erro.hidden = !(ativos.length === 0 || !primeiroDisponivel);
  erro.textContent = ativos.length === 0
    ? "Cadastre um produto ativo em Produtos antes de registrar uma venda."
    : !primeiroDisponivel ? "Todos os produtos estão sem estoque. Atualize o estoque em Produtos." : "";
  document.querySelector("#saleSubmit").disabled = !primeiroDisponivel;

  modal.hidden = false;
  requestAnimationFrame(() => modal.classList.add("is-open"));
  document.addEventListener("keydown", saleModalEscHandler);
  select.focus();
}

function closeSaleModal() {
  const modal = document.querySelector("#saleModal");
  if (!modal) return;
  modal.classList.remove("is-open");
  document.removeEventListener("keydown", saleModalEscHandler);
  window.setTimeout(() => { modal.hidden = true; }, 300);
}

function saleModalEscHandler(event) {
  if (event.key === "Escape") closeSaleModal();
}

function applyProductToSale() {
  const product = saleSelectedProduct();
  document.querySelector("#salePrice").value = product ? formatMoney(Number(product.price) || 0) : "";
  updateSalePreview();
}

// Mesma conta do servidor (apps/sales/services.py): taxa por unidade
// arredondada ao centavo. Mudou lá, mude aqui.
function updateSalePreview() {
  const product = saleSelectedProduct();
  const quantidade = Math.max(0, parseInt(document.querySelector("#saleQuantity").value, 10) || 0);
  const precoCentavos = centsFromMasked(document.querySelector("#salePrice").value);
  const preview = document.querySelector("#salePreview");
  if (!preview) return;

  let totalCentavos = 0;
  let lucroCentavos = 0;
  if (product) {
    const custoCentavos = Math.round((Number(product.cost) || 0) * 100) + Math.round((Number(product.other_costs) || 0) * 100);
    const percentual = (Number(product.fee_percent) || 0) + (Number(product.tax_percent) || 0);
    const taxaCentavos = Math.round(precoCentavos * percentual / 100);
    totalCentavos = precoCentavos * quantidade;
    lucroCentavos = (precoCentavos - custoCentavos - taxaCentavos) * quantidade;
  }
  const prejuizo = lucroCentavos < 0;
  preview.innerHTML = `
    <span>Total <strong class="value-currency">${formatMoney(totalCentavos / 100)}</strong></span>
    <span>${prejuizo ? "Prejuízo" : "Lucro real"} <strong class="value-currency ${prejuizo ? "value-negative" : "value-positive"}">${formatMoney(Math.abs(lucroCentavos) / 100)}</strong></span>`;
}

// Venda mexe no estoque (produtos) e no financeiro (movimentações): as três
// telas são recarregadas do servidor, que é quem fez a conta.
async function refreshAfterSale() {
  try {
    state = await loadRemoteState();
    render();
  } catch {
    // A lista de vendas abaixo ainda mostra o que mudou.
  }
  await loadSales();
  loadProfitTable();
}

document.querySelector("#openSaleModal")?.addEventListener("click", () => openSaleModal());
document.querySelectorAll("[data-close-sale-modal]").forEach((el) => el.addEventListener("click", closeSaleModal));
document.querySelectorAll("[data-close-sale]").forEach((el) => el.addEventListener("click", closeSaleDrawer));
document.querySelector("#salesPrevMonth")?.addEventListener("click", () => shiftSalesMonth(-1));
document.querySelector("#salesNextMonth")?.addEventListener("click", () => shiftSalesMonth(1));
document.querySelector("#saleProduct")?.addEventListener("change", () => applyProductToSale());
document.querySelector("#saleQuantity")?.addEventListener("input", () => updateSalePreview());
document.querySelector("#salePrice")?.addEventListener("input", (event) => {
  const input = event.target;
  input.value = centsFromMasked(input.value) ? maskMoney(input.value) : "";
  updateSalePreview();
});

document.querySelector("#saleForm")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const erro = document.querySelector("#saleFormError");
  const submit = document.querySelector("#saleSubmit");

  const quantidade = parseInt(form.get("quantity"), 10) || 0;
  if (quantidade < 1) {
    erro.textContent = "Informe uma quantidade maior que zero.";
    erro.hidden = false;
    return;
  }

  const payload = {
    product_id: form.get("product_id"),
    quantity: quantidade,
    unit_price: centsFromMasked(form.get("unit_price")) / 100,
    payment_method: form.get("payment_method")
  };
  const data = form.get("occurred_at");
  if (data && data !== dateKey(new Date())) payload.occurred_at = `${data}T12:00:00`;

  erro.hidden = true;
  submit.disabled = true;
  submit.textContent = "Registrando...";
  try {
    await apiRequest("/sales/", { method: "POST", body: JSON.stringify(payload) });
  } catch (requestError) {
    erro.textContent = requestError.message;
    erro.hidden = false;
    return;
  } finally {
    submit.disabled = false;
    submit.textContent = "Registrar";
  }

  closeSaleModal();
  // Venda registrada em outro mês: a lista acompanha o mês da venda.
  const quando = data ? new Date(`${data}T12:00:00`) : new Date();
  salesMonth = new Date(quando.getFullYear(), quando.getMonth(), 1);
  await refreshAfterSale();
});

// ─── Visão geral: lucro por produto e insights ──────────────────────────────

async function loadProfitTable() {
  const container = document.querySelector("#ovProfitTable");
  if (!container || !currentUser) return;
  const mes = `${CAL_MONTHS[calendarCursor.getMonth()]} de ${calendarCursor.getFullYear()}`;

  let resumo;
  try {
    resumo = await apiRequest(`/sales/summary/?month=${monthParam(calendarCursor)}`);
  } catch {
    container.innerHTML = `<p class="empty-state">Não foi possível carregar as vendas agora.</p>`;
    return;
  }

  if (!resumo.products?.length) {
    container.innerHTML = `<p class="empty-state">Nenhuma venda em ${escapeHtml(mes.toLowerCase())}. Registre vendas para ver quanto cada produto rende de verdade.</p>`;
    return;
  }

  const linha = (nome, meta, lucro, extraClass = "") => `
    <div class="profit-row ${extraClass}">
      <span class="profit-row__name">${escapeHtml(nome)}</span>
      <span class="profit-row__meta">${escapeHtml(meta)}</span>
      <span class="profit-row__value">${profitBadge(lucro)}</span>
    </div>`;

  const totais = resumo.totals;
  container.innerHTML = resumo.products.map((item) => linha(
    item.product_name,
    `${item.quantity} ${item.quantity === 1 ? "unidade" : "unidades"} · faturou ${formatMoney(item.total)}`,
    item.profit
  )).join("") + linha(
    `Total de ${mes.toLowerCase()}`,
    `${totais.count} ${totais.count === 1 ? "venda" : "vendas"} · faturou ${formatMoney(totais.total)}`,
    totais.profit,
    "profit-row--total"
  );
}

// Os insights chamam a IA, que custa por chamada: só são pedidos de novo
// quando os dados mudaram desde a última leitura, ou pelo botão Atualizar.
const INSIGHT_ACTION_ICON = { campaign: "campaign", launch: "campaign", whatsapp: "chat", price: "sell", stock: "inventory_2" };

async function loadInsights(force = false) {
  const container = document.querySelector("#ovInsights");
  if (!container || !canAccessFinance()) return;
  if (insightsVersion === dataVersion && !force) return;
  insightsVersion = dataVersion;

  container.innerHTML = `<p class="empty-state">Lendo os números do negócio...</p>`;
  let data;
  try {
    data = await apiRequest("/finance/insights/");
  } catch (requestError) {
    insightsVersion = -1;
    container.innerHTML = `<p class="empty-state">${escapeHtml(requestError.message || "Não foi possível gerar os insights agora.")}</p>`;
    return;
  }
  const lista = data.insights || [];
  container.innerHTML = lista.length
    ? lista.map((item, indice) => `
        <article class="insight-item">
          <strong>${escapeHtml(item.title)}</strong>
          <p>${escapeHtml(item.text)}</p>
          ${item.action && MKT_ACTION_LABEL[item.action.type] ? `
            <button class="ghost-button insight-item__action" type="button" data-insight-action="${indice}">
              <span class="material-symbols-rounded" aria-hidden="true">${INSIGHT_ACTION_ICON[item.action.type] || "campaign"}</span>${escapeHtml(MKT_ACTION_LABEL[item.action.type])}: ${escapeHtml(item.action.product_name)}
            </button>` : ""}
        </article>`).join("")
    : `<p class="empty-state">Sem insights por enquanto.</p>`;

  // O insight leva à ação: abre o Marketing e já gera a campanha, o aviso
  // ou abre o cadastro do produto, como o botão do cartão de lá.
  container.querySelectorAll("[data-insight-action]").forEach((botao) => {
    botao.addEventListener("click", () => {
      const acao = lista[Number(botao.dataset.insightAction)].action;
      setView("app-marketing");
      setMarketingTab("actions");
      runMarketingAction(acao.product_id, acao.type);
    });
  });
}

document.querySelector("#ovInsightsRefresh")?.addEventListener("click", () => loadInsights(true));

document.querySelectorAll("[data-goto-view]").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.gotoView));
});

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
