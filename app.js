const storageKey = "wageup-state-v1";

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

const siteShell = document.querySelector(".site-shell");
const appShell = document.querySelector("#app");
const sidebar = document.querySelector(".sidebar");
const title = document.querySelector("#view-title");
const viewTitles = {
  overview: "Bem-vindo de volta.",
  finance: "Financeiro",
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

document.querySelectorAll("[data-open-app]").forEach((button) => {
  button.addEventListener("click", () => {
    siteShell.classList.add("is-hidden");
    appShell.classList.remove("is-hidden");
    window.scrollTo({ top: 0, behavior: "instant" });
    render();
  });
});

document.querySelectorAll("[data-close-app]").forEach((button) => {
  button.addEventListener("click", () => {
    appShell.classList.add("is-hidden");
    siteShell.classList.remove("is-hidden");
    sidebar.classList.remove("open");
    window.scrollTo({ top: 0, behavior: "instant" });
  });
});

document.querySelector(".menu-button").addEventListener("click", () => {
  sidebar.classList.toggle("open");
});

document.querySelectorAll("[data-demo-view]").forEach((button) => {
  button.addEventListener("click", () => setDemoView(button.dataset.demoView));
});

document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => {
    setView(button.dataset.view);
    sidebar.classList.remove("open");
  });
});

document.querySelector("#transactionForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  state.transactions.unshift({
    id: uid(),
    description: form.get("description").trim(),
    type: form.get("type"),
    amount: Number(form.get("amount"))
  });
  event.currentTarget.reset();
  persist();
  render();
});

document.querySelector("#productForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  state.products.unshift({
    id: uid(),
    name: form.get("name").trim(),
    category: form.get("category").trim(),
    cost: Number(form.get("cost")),
    price: Number(form.get("price")),
    stock: Number(form.get("stock"))
  });
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
  output.insertAdjacentHTML("beforeend", `<article class="assistant-message is-loading">Pensando em uma campanha para ${escapeHtml(product.name)}...</article>`);
  output.scrollTop = output.scrollHeight;

  const answer = await askMarketingAi({ product, goal, channel, prompt, margin });
  output.querySelector(".is-loading").remove();
  output.insertAdjacentHTML("beforeend", `<article class="assistant-message">${answer.html}</article>`);

  preview.innerHTML = answer.imageLabel;
  event.currentTarget.reset();
  renderCampaignOptions();
  output.scrollTop = output.scrollHeight;
});

window.addEventListener("resize", () => drawChart());

render();

setDemoView("overview");

function setView(viewName) {
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("active", view.id === viewName);
  });

  document.querySelectorAll(".side-nav button").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === viewName);
  });

  title.textContent = viewTitles[viewName] || "Wage Up";
  if (viewName === "overview") drawChart();
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

  state.transactions.forEach((transaction) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${escapeHtml(transaction.description)}</td>
      <td>${transaction.type === "income" ? "Entrada" : "Saida"}</td>
      <td>${formatMoney(transaction.amount)}</td>
      <td><button class="delete-button" aria-label="Excluir movimentacao" data-delete-transaction="${transaction.id}">x</button></td>
    `;
    rows.appendChild(row);
  });

  rows.querySelectorAll("[data-delete-transaction]").forEach((button) => {
    button.addEventListener("click", () => {
      state.transactions = state.transactions.filter((item) => item.id !== button.dataset.deleteTransaction);
      persist();
      render();
    });
  });
}

function renderProducts() {
  const grid = document.querySelector("#productGrid");
  grid.innerHTML = "";

  state.products.forEach((product) => {
    const margin = product.price - product.cost;
    const marginPercent = product.price ? (margin / product.price) * 100 : 0;
    const card = document.createElement("article");
    card.className = "product-card";
    card.innerHTML = `
      <strong>${escapeHtml(product.name)}</strong>
      <span>${escapeHtml(product.category)}</span>
      <div class="product-meta">
        <span>Preco: ${formatMoney(product.price)}</span>
        <span>Custo: ${formatMoney(product.cost)}</span>
        <span>Margem: ${formatMoney(margin)} (${marginPercent.toFixed(0)}%)</span>
        <span>Estoque: ${product.stock} un.</span>
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

function renderInsights() {
  const container = document.querySelector("#insights");
  const income = sumByType("income");
  const expense = sumByType("expense");
  const lowStock = state.products.filter((product) => product.stock <= 8).length;
  const bestMargin = [...state.products].sort((a, b) => (b.price - b.cost) - (a.price - a.cost))[0];

  const insights = [
    {
      title: "Saude financeira",
      text: income > expense ? `Voce esta positivo em ${formatMoney(income - expense)}.` : "As saidas estao acima das entradas."
    },
    {
      title: "Estoque",
      text: lowStock ? `${lowStock} produto(s) precisam de reposicao.` : "Nenhum produto com estoque baixo."
    },
    {
      title: "Melhor margem",
      text: bestMargin ? `${bestMargin.name} gera ${formatMoney(bestMargin.price - bestMargin.cost)} por unidade.` : "Cadastre produtos para ver margem."
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
    { label: "Saidas", value: sumByType("expense"), color: "#c19075" },
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
    const response = await fetch("/api/marketing/chat/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        product,
        goal,
        channel,
        prompt
      })
    });

    if (response.ok) {
      const data = await response.json();
      return {
        html: escapeHtml(data.message || data.text || "").replaceAll("\n", "<br>"),
        imageLabel: escapeHtml(data.image_label || `${product.name}<br>${channel}`)
      };
    }
  } catch {
    // O endpoint real será criado na migração para Django; até lá, mantemos a experiência local.
  }

  return {
    html:
      `<strong>Campanha para ${escapeHtml(channel)}</strong><br><br>` +
      `<b>Chamada:</b> ${escapeHtml(campaignHeadline(goal, product.name))}<br><br>` +
      `<b>Ideia de imagem:</b> ${escapeHtml(imagePrompt(goal, product.name))}<br><br>` +
      `<b>Legenda:</b> Hoje é um bom dia para garantir ${escapeHtml(product.name)}. Produto com visual caprichado, entrega rápida e preço pensado para vender bem. Margem estimada de ${formatMoney(margin)} por unidade.<br><br>` +
      `<b>CTA:</b> Chame no direct ou finalize pelo PIX.`,
    imageLabel: `${escapeHtml(product.name)}<br>${escapeHtml(channel)}`
  };
}

function sumByType(type) {
  return state.transactions
    .filter((transaction) => transaction.type === type)
    .reduce((total, transaction) => total + transaction.amount, 0);
}

function formatMoney(value) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL"
  }).format(value || 0);
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
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }

  return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function clone(value) {
  if (typeof structuredClone === "function") {
    return structuredClone(value);
  }

  return JSON.parse(JSON.stringify(value));
}
