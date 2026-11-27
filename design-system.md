# Design System — WageUp
> Plataforma de gestão financeira end-to-end para Microempreendedores

A fonte da verdade é o `:root` de [`frontend/styles.css`](frontend/styles.css). Este documento
explica os tokens e os componentes; se os dois divergirem, o CSS vale e este arquivo está
desatualizado.

---

## 1. Identidade Visual

### Tom
Fintech minimalista com calor humano. Séria o suficiente para transmitir confiança financeira,
acessível o suficiente para não intimidar o MEI. Pensa em "Nubank meets Wise" — dados
limpos, linguagem direta, sem jargão, sem frescura.

A identidade atual é a **Broto** (rebrand 2026): verde vivo como acento, verde floresta
profundo para peso e texto, menta para destaques, e neutros levemente puxados para o verde.

### Princípios
- **Clareza acima de tudo** — cada pixel deve ter função. Nada decorativo sem propósito.
- **Confiança pelo espaço** — generoso espaçamento transmite controle, não vazio.
- **Verde como âncora** — a cor carrega o peso da marca; use com intenção, não decoração.
- **Tipografia como hierarquia** — o tamanho e peso do texto organiza a informação, não ícones.

### O que NUNCA fazer
- Gradientes coloridos ou sombras excessivas em cards
- Ícones decorativos em excesso (cada ícone deve ter função)
- Textos em caps lock em contextos de dados
- Border-radius maior que `--radius-xl` (16px) em componentes de dados (parece brinquedo)
- Cores vibrantes demais — o verde É o accent, não precisa de laranja/amarelo por cima
- Backgrounds cinza genérico (`#f5f5f5`) — use os tokens definidos abaixo
- Fontes: Arial, Roboto, Inter, Poppins — proibidas
- `!important` — se precisar dele, a especificidade está errada

---

## 2. Paleta de Cores

```css
:root {
  /* Marca — Broto (verde vivo + floresta profundo + menta) */
  --color-brand-dark:    #07251B;   /* Floresta — hover de botão primário, peso */
  --color-brand-mid:     #14B87A;   /* Verde vivo — FUNDO de botão primário, barras e gráficos. Nunca texto sobre claro */
  --color-brand-light:   #A8F0C6;   /* Menta — bordas de destaque, chips ativos */
  --color-brand-subtle:  #E6F7EF;   /* Verde muito claro — fundos de item ativo e cards positivos */
  --color-brand-ink:     #0A7A50;   /* Verde de TEXTO — links, ícones e itens ativos sobre fundo claro */

  /* Superfícies — neutros enviesados para o verde */
  --color-bg:            #F6F9F6;   /* Background geral (NÃO branco puro) */
  --color-surface:       #FFFFFF;   /* Cards, modais, inputs */
  --color-surface-muted: #EEF3EE;   /* Sidebar, hover de botões, surfaces secundárias */
  --color-border:        #E4EBE5;   /* Bordas suaves */
  --color-border-strong: #CBD8CE;   /* Bordas em hover/foco, separadores fortes */

  /* Texto */
  --color-text-primary:  #0B211A;   /* Headlines, dados */
  --color-text-secondary:#52635A;   /* Labels, metadados */
  --color-text-disabled: #617166;   /* Legendas discretas, estado vazio, placeholders */
  --color-text-inverse:  #F6F9F6;   /* Texto sobre fundos escuros e botão primário */

  /* Semânticas */
  --color-positive:      #0A7A50;   /* Receita, lucro, crescimento */
  --color-negative:      #B53A34;   /* Despesa, prejuízo, erro */
  --color-warning:       #8A5A12;   /* Atenção, pendente, "em breve" */
  --color-negative-subtle: #FBEDED; /* Fundo de badge, aviso e hover de ação negativa */
  --color-warning-subtle:  #FBF3E4; /* Fundo de badge e aviso de atenção */
  --color-neutral:       #52635A;   /* Neutro informativo */

  /* Accent (uso pontual) */
  --color-accent:        #14B87A;   /* Alias de brand-mid para CTAs */
}
```

### Contraste (revisão de 2026-11)
Todo texto passa no AA (4.5:1) sobre `surface`, `bg`, `surface-muted` e os fundos `*-subtle`.
O verde vivo da marca (`brand-mid`) fica em 2.6:1 sobre o branco, então ele é **fundo**,
não texto:

| Situação | Use | Contraste |
|---|---|---|
| Texto sobre `brand-mid` (botão primário, enviar do chat, avatar) | `--color-brand-dark` | 6.3:1 |
| Texto, link ou ícone verde sobre fundo claro | `--color-brand-ink` | 4.8 a 5.4:1 |
| Texto claro | só sobre `brand-dark` (hover do botão primário, faixas escuras) | 15:1 |

Exceções aceitas pela WCAG: o "up" do logotipo e o `brand-mid` sobre o floresta do
fechamento da landing (6.3:1). O modo alto contraste (seção 11) escurece ainda mais texto e
bordas.

---

## 3. Tipografia

### Famílias
Uma família só para texto, mais uma monoespaçada para números. As fontes vêm do Google Fonts
no `<head>` do `index.html`, junto com os ícones (seção 7.12).

```css
:root {
  --font-display: 'Instrument Sans', sans-serif;  /* Títulos */
  --font-body:    'Instrument Sans', sans-serif;  /* Texto e interface */
  --font-mono:    'DM Mono', monospace;           /* Valores financeiros e números alinhados */
}
```

`--font-display` e `--font-body` apontam hoje para a mesma família, mas continuam separados:
use o token pelo papel do texto, não pela fonte. Trocar a fonte de títulos no futuro é mudar
uma linha.

### Escala Tipográfica
```css
:root {
  /* Display */
  --text-display-xl: clamp(2.5rem, 5vw, 4rem);     /* Hero headlines */
  --text-display-lg: clamp(1.75rem, 3vw, 2.5rem);  /* Page titles */
  --text-display-md: clamp(1.25rem, 2vw, 1.75rem); /* Section headers, valor dos cards de métrica */

  /* UI */
  --text-xl:   1.25rem;   /* 20px — subtítulos, título de modal */
  --text-lg:   1.125rem;  /* 18px — título de painel */
  --text-base: 1rem;      /* 16px — body padrão, campo do chat */
  --text-sm:   0.875rem;  /* 14px — labels, botões, mensagens do chat */
  --text-xs:   0.75rem;   /* 12px — badges, chips, captions */

  /* Pesos */
  --weight-regular:  400;
  --weight-medium:   500;
  --weight-semibold: 600;

  /* Line heights */
  --leading-tight:   1.2;
  --leading-normal:  1.5;
  --leading-relaxed: 1.7;

  /* Letter spacing */
  --tracking-tight:  -0.02em;  /* Headlines grandes */
  --tracking-normal:  0em;
  --tracking-wide:    0.04em;  /* Labels em caps, badges */
}
```

### Uso por Contexto
| Elemento | Família | Tamanho | Peso |
|---|---|---|---|
| Hero title | display | display-xl | 400 |
| Page title | display | display-lg | 400 |
| Section header | body | display-md | 600 |
| Título de painel (`.panel-heading h3`) | body | lg | 600 |
| Label de card de métrica | body | xs, caps, tracking-wide | 600 |
| Valor de card de métrica | mono | display-md | 500 |
| Body text | body | base | 400 |
| Botão | body | sm | 500 |
| Badge / chip | body | xs | 500 |
| Caption / meta | body | xs | 400 |

---

## 4. Espaçamento

```css
:root {
  /* Escala base 4px */
  --space-1:  0.25rem;  /*  4px */
  --space-2:  0.5rem;   /*  8px */
  --space-3:  0.75rem;  /* 12px */
  --space-4:  1rem;     /* 16px */
  --space-5:  1.25rem;  /* 20px */
  --space-6:  1.5rem;   /* 24px */
  --space-8:  2rem;     /* 32px */
  --space-10: 2.5rem;   /* 40px */
  --space-12: 3rem;     /* 48px */
  --space-16: 4rem;     /* 64px */
  --space-20: 5rem;     /* 80px */
  --space-24: 6rem;     /* 96px */
}
```

### Regras de Espaçamento
- **Padding interno de painéis e cards:** `--space-6` (24px); cards de métrica `--space-5 --space-6`
- **Gap entre cards no grid:** `--space-4` (16px)
- **Gap entre blocos de uma tela:** `--space-8` (32px), que também é o padding da tela
- **Padding de seção da landing (vertical):** mínimo `--space-16` (64px)
- **Sidebar:** 16.5rem aberta, 5.5rem em trilha de ícones, recuada `--space-3` da borda
- Prefira `gap` a `margin` entre filhos de flex e grid

---

## 5. Border Radius

```css
:root {
  --radius-sm:  4px;     /* Inputs pequenos, kbd, botões de ícone mínimos */
  --radius-md:  8px;     /* Botões, itens de lista, chips de menu */
  --radius-lg:  12px;    /* Cards, composer e sugestões do chat, dropdowns */
  --radius-xl:  16px;    /* Painéis (.work-panel) e modais — teto para componentes de dados */
  --radius-full: 9999px; /* Avatares, chips de filtro, badges, botão de enviar */
}
```

---

## 6. Sombras

```css
:root {
  /* Tom floresta Broto, sutis (minimalismo) */
  --shadow-sm:    0 1px 2px rgba(7, 37, 27, 0.06);    /* Hover de card */
  --shadow-md:    0 4px 12px rgba(7, 37, 27, 0.08);   /* Hover de botão primário */
  --shadow-lg:    0 8px 24px rgba(7, 37, 27, 0.10);   /* Modal, drawer, dropdown — o que flutua */
  --shadow-focus: 0 0 0 2px var(--color-surface), 0 0 0 4px var(--color-brand-ink); /* Ring de foco: sólido, com folga clara */
}
```

Cards e painéis em repouso **não têm sombra**: a separação vem da borda. Sombra é para o que
flutua sobre o conteúdo (modal, drawer, menu) ou para responder ao hover.

---

## 7. Componentes

Nomenclatura BEM simplificada: `.bloco`, `.bloco__elemento`, `.bloco--modificador`. Estado
vai em classe `is-*` (`is-active`, `is-open`, `is-hidden`, `is-collapsed`).

### 7.1 Botões

Todos têm `min-height: 2.5rem`, `display: inline-flex` e `gap: --space-2` para ícone + texto.

| Classe | Uso | Visual |
|---|---|---|
| `.primary-button` | Ação principal da tela (uma por área) | Fundo `brand-mid`, texto `brand-dark`; hover fundo `brand-dark` e texto `text-inverse`, sobe 1px e ganha `shadow-md` |
| `.secondary-button` | Ação alternativa com peso | Borda 1.5px e texto `brand-ink`; hover `brand-subtle` |
| `.ghost-button` | Ações de apoio (Importar, Atualizar) | Borda `border`, texto `text-secondary`; hover `surface-muted` |
| `.ghost-button--danger` | Remover, apagar | Como o ghost, texto `negative` |
| `.icon-btn` | Ação só com ícone (menu, nova conversa) | 2.25rem quadrado, borda `border`, `radius-md`; `--sm` (1.85rem) sem borda |

```css
.primary-button {
  padding: var(--space-3) var(--space-6);
  background: var(--color-brand-mid);
  color: var(--color-brand-dark);
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
}
.primary-button:hover { background: var(--color-brand-dark); color: var(--color-text-inverse); transform: translateY(-1px); box-shadow: var(--shadow-md); }
.primary-button:focus-visible { outline: none; box-shadow: var(--shadow-focus); }
```

Botão só com ícone precisa de `aria-label` e `title`.

### 7.2 Painéis e cards

**Painel de trabalho (`.work-panel`)** — o contêiner padrão de cada bloco das telas internas.

```css
.work-panel {
  display: grid;
  grid-template-columns: minmax(0, 1fr); /* deixa o conteúdo encolher; ver 10. Responsivo */
  gap: var(--space-6);
  padding: var(--space-6);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
}
```

**Cabeçalho de painel (`.panel-heading`)** — título à esquerda, ação ou subtítulo à direita,
com `flex-wrap` para quebrar linha quando não couber.

```html
<div class="panel-heading">
  <h3>Cobrança PIX</h3>
  <span>via Abacate Pay</span>   <!-- subtítulo: filho direto, xs, text-disabled -->
</div>
```

O subtítulo é só o `span` **filho direto** (`.panel-heading > span`). Ícones e selos dentro de
botões do cabeçalho não herdam esse estilo.

**Cabeçalho com fileira de botões (`.panel-heading--toolbar`)** — usado em Movimentações,
com os botões em `.panel-heading__actions`. O arranjo segue a largura do **painel**, não da
janela (container query), porque a mesma janela deixa espaços diferentes com a navegação
aberta ou em trilha:

| Largura do painel | Arranjo |
|---|---|
| até 26rem | Título em cima, um botão por linha, marcas dos bancos escondidas |
| até 40rem | Título em cima, botões em grade de duas colunas (o de banco ocupa a linha) |
| até 52rem | Título em cima, botões numa linha só |
| acima de 52rem | Título e botões na mesma linha, botões à direita |

**Cards de métrica (`.summary-grid`)** — grade `auto-fit` de cards com label e valor.

```
┌─────────────────────────────┐
│ ENTROU NO PERÍODO           │  ← span: xs, semibold, caps, tracking-wide, text-secondary
│                             │
│ R$ 12.450,00                │  ← strong: DM Mono display-md, value-currency
└─────────────────────────────┘
```

Modificadores: `--quad` (os quatro cards do mês na Visão geral: uma coluna no celular, duas a
partir de 30rem, quatro a partir de 64rem) e `--trio` (três cards, máx. 52rem).

Abaixo do valor, `.summary-card__delta` compara com o mês anterior: ícone (`trending_up`,
`trending_down`, `trending_flat`) mais texto, com `--positive` ou `--negative` pelo que é bom
para o negócio. Despesa que subiu é `--negative`. A cor nunca vem sem o texto.

**Barra de progresso (`.goal__bar`, `.method-row__bar`)** — trilho `surface-muted` com
`radius-full`; o preenchimento é um `<i>` com `transform: scaleX(var(--share))`, nunca `width`
(regra de animação). `--share` vai de 0 a 1 no `style` do elemento. A meta usa `brand-mid` e
passa a `positive` quando batida (`.goal__bar--done`); forma de pagamento não informada usa
`border-strong`. A barra da meta leva `role="progressbar"` com `aria-valuenow`.

**Card de produto (`.product-card`)** — foto, nome, preço, tag de margem e custos. Clicável:
no hover a borda vira `brand-light`, ganha `shadow-sm` e sobe 2px.

**Estado vazio (`.empty-state`)** — texto `sm`, `text-disabled`, centralizado, com padding
`--space-10 --space-8`. Sempre diz o que fazer a seguir ("registre a primeira entrada ou saída").

### 7.3 Inputs
```css
.input {
  background: var(--color-surface);
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: var(--space-3) var(--space-4);
  font-family: var(--font-body);
  font-size: var(--text-base);
  color: var(--color-text-primary);
}
.input:focus {
  border-color: var(--color-brand-mid);
  box-shadow: var(--shadow-focus);
  outline: none;
}
```

### 7.4 Chips de filtro (`.chip`)

Pílula para filtrar uma lista (Todas / Entradas / Saídas, status de cobrança, período).
Agrupe em `.charge-filters` (flex com `gap: --space-2`) e marque o ativo com `is-active`.

```css
.chip {
  padding: var(--space-2) var(--space-4);
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: var(--weight-medium);
  color: var(--color-text-secondary);
}
.chip.is-active {
  background: var(--color-brand-subtle);
  border-color: var(--color-brand-light);
  color: var(--color-brand-ink);
}
```

`.chip--action` é o chip que abre um menu (ex.: "Filtros"), com ícone à esquerda.

**Barra de filtros (`.record-filters`)** — chips de tipo à esquerda e navegação de mês à
direita (`.record-filters__month`: seta, mês, seta, "Todo o período", "Filtros"). No celular
vira coluna, e a linha do mês vira grade: o mês entre as setas numa linha, "Todo o período" e
"Filtros" dividindo a de baixo.

### 7.5 Badges de status (`.status-badge`)

Pílula `xs` com fundo claro e texto na cor semântica. Nunca só a cor: o texto diz o estado.

| Modificador | Fundo | Texto | Uso |
|---|---|---|---|
| `--positive` | `brand-subtle` | `positive` | Pago, ativo |
| `--warning` | âmbar claro | `warning` | Pendente, "Em breve" |
| `--negative` | vermelho claro | `negative` | Falhou, expirado |

### 7.6 Modal (`.modal`)

Para formulários curtos que interrompem o fluxo (nova movimentação, importar extrato, produto).

- Overlay escuro translúcido; painel `.modal__panel` centralizado, `min(30rem, 100%)`
  (`--wide`: 52rem), `radius-xl`, `shadow-lg`, máx. 90vh com rolagem interna.
- Entra com opacidade + `translateY(12px)` em `--duration-slow`.
- Cabeçalho `.modal__head` (título `xl` + botão fechar) e corpo `.modal__form` em grade com
  `gap: --space-4`.
- Abre com `is-open`; Esc fecha.

### 7.7 Drawer (`.drawer`)

Painel lateral à direita para detalhes sem sair da tela (dia do calendário, cobrança PIX).
`min(420px, 100%)`, borda à esquerda, `shadow-lg`, entra com `translateX(100%) → 0`. Ações no
rodapé em `.drawer__actions`.

### 7.8 Menu suspenso (`.menu`)

Contêiner `position: relative` com um gatilho (`aria-haspopup`, `aria-expanded`) e um
`.menu__panel` absoluto abaixo, alinhado à direita: `surface`, `radius-lg`, `shadow-lg`.
Usado no filtro de período personalizado (`.menu__panel--wide`).

### 7.9 Chat com IA

Assistente financeiro e Marketing usam a mesma estrutura e o mesmo CSS; o comportamento vem de
`createChat()` em `app.js`. A tela ocupa toda a área útil (`.view--full`) e esconde o título
da página (`.dashboard.is-chat`) no desktop.

```
┌──────────────┬──────────────────────────────────────────────┐
│ CONVERSAS  ✎ │ ☰  Título da conversa                        │ ← .chatbox__bar
│              ├──────────────────────────────────────────────┤
│ Hoje         │  ──                                          │
│  Conversa A  │  Resposta da IA, texto corrido, sem balão    │ ← .msg--bot
│  Conversa B  │                     ┌──────────────────────┐ │
│ Ontem        │                     │ Pergunta do usuário  │ │ ← .msg--user
│  Conversa C  │                     └──────────────────────┘ │
│              ├──────────────────────────────────────────────┤
│ .chat-aside  │  → Sugestão 1                                │ ← .chatbox__suggestions
│              │  ┌────────────────────────────────────────┐  │
│              │  │ Pergunte…                          (↑) │  │ ← .chatbox__composer
│              │  └────────────────────────────────────────┘  │
└──────────────┴──────────────────────────────────────────────┘
```

| Peça | Classe | Regras |
|---|---|---|
| Moldura | `.assistant-shell` | Grade `16rem / 1fr`; `is-collapsed` fecha a lista. No celular a lista vira camada sobre o chat |
| Lista de conversas | `.chat-aside`, `.chat-group`, `.chat-item` | Fundo `bg`, agrupada por data (Hoje, Ontem, Últimos 7 dias…). Item ativo `brand-subtle`; lixeira aparece no hover |
| Conversa | `.chatbox__thread` | Máx. 52rem, centralizada, `gap: --space-6`, `role="log"` |
| Resposta | `.msg--bot` | Texto corrido sem balão, traço `brand-light` acima. Parágrafos como texto, nunca HTML do modelo |
| Pergunta | `.msg--user` | Pílula à direita, `surface-muted`, `radius-lg`, máx. 80% |
| Carregando | `.msg--pending` | Brilho percorrendo o texto (única animação em loop permitida — é estado de carregamento) |
| Erro | `.msg--error` | Fundo vermelho claro, texto `negative` |
| Sugestões | `.chatbox__suggestions`, `.suggestion` | Lista navegável por teclado (↑ ↓ Enter Esc), item com seta `brand-ink` |
| Campo | `.chatbox__composer` | A borda é do conjunto, não do input; foco pinta a borda `brand-mid` + `shadow-focus` |
| Enviar | `.chatbox__send` | Círculo `brand-mid` 2rem, ícone de seta `brand-dark`; desabilitado com opacidade 0.45 |

Peças só do Marketing:
- **Negrito** nos títulos das seções da campanha (`**Chamada principal:**` vira `<strong>`,
  depois de escapar o texto).
- `.msg__image` — a imagem da campanha dentro da resposta, máx. 22rem, `radius-lg`.
- `.msg__actions` / `.msg__action` — "Copiar texto" e "Baixar imagem": pílulas `xs` com
  ícone, borda `border`, hover `surface-muted`.

### 7.10 Navegação (sidebar)

```css
.sidebar {
  background: var(--lp-ink);          /* o floresta dos topos do site */
  color: var(--color-text-inverse);
  margin: var(--space-3) 0 var(--space-3) var(--space-3);
  border-radius: calc(var(--radius-xl) * 1.5);
}
```

- Mesmo floresta do site, recuada e arredondada como os blocos escuros da landing: o app e o
  site se reconhecem. Logo `wageup▲` no alto, conta no pé.
- Itens em `--lp-ink-muted`; hover e ativo em `--lp-ink-raised`. O ativo tem ícone em
  `brand-mid` e um fio de 3px à esquerda. Grupo com submenu (Financeiro) abre com chevron.
- **Aberta ou recolhida é escolha de quem usa** (botão no alto, `data-rail-toggle`), lembrada em
  `localStorage` `wageup:sidebar`. Sem escolha salva, telas abaixo de 1100px começam recolhidas.
  A barra **não** abre no hover: abrir no hover empurrava a tela a cada passagem do mouse.
- A troca passa pela View Transitions API (`app-sidebar` e `app-main`), sem animar largura;
  com "menos movimento" ela é instantânea.
- No celular a barra é uma gaveta escura que abre pelo botão de menu do cabeçalho.

### 7.11 Valores Monetários
```css
/* Regra crítica: SEMPRE usar font-mono para valores financeiros */
.value-currency {
  font-family: var(--font-mono);
  font-weight: var(--weight-medium);
  letter-spacing: -0.01em;
}

.value-positive { color: var(--color-positive); }
.value-negative { color: var(--color-negative); }
```

Formato `R$ 1.234,56`, e nunca a cor sozinha: margem negativa aparece como **Prejuízo**, com
rótulo.

### 7.12 Ícones

**Material Symbols Rounded** (Google Fonts), peso 500, sem preenchimento.

```html
<span class="material-symbols-rounded" aria-hidden="true">upload_file</span>Importar extrato
```

- Sempre `aria-hidden="true"`: quem dá o nome à ação é o texto ou o `aria-label` do botão.
- Tamanho pelo contexto: 1.1rem em botões e navegação, 1.15rem em `.icon-btn`, 0.95rem em
  ações pequenas.

---

## 8. Animações

```css
:root {
  --duration-fast:   100ms;
  --duration-normal: 200ms;
  --duration-slow:   350ms;
  --ease-default:    cubic-bezier(0.4, 0, 0.2, 1);
  --ease-out:        cubic-bezier(0, 0, 0.2, 1);
}

/* Padrão de entrada de elementos */
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
```

### Regras de Animação
- Somente `opacity` + `transform` — nunca animar `height`, `width` ou `top/left`
  (largura de layout muda de uma vez; só a opacidade anima, como na lista de conversas)
- Duração máxima: 400ms para entradas de página
- Hover states: até `--duration-normal`
- Nenhuma animação em loop fora de estados de carregamento (`.msg--pending`)
- Respeitar `prefers-reduced-motion`: movimento decorativo desliga, interações continuam

---

## 9. Módulos e Páginas — Guia Visual

### Site público (home e páginas de módulo)
- Navegação e topos em floresta (`--lp-ink`), com o "▲" do logotipo grande ao fundo; o resto em
  `--color-bg`. Superfícies escuras derivadas dos tokens por `color-mix` (`--lp-ink-raised`,
  `--lp-ink-line`, `--lp-ink-muted`), sem cor nova
- Home: manchete "Receba. Entenda. Decida. Cresça." com foto de MEI e trechos da interface
  flutuando; depois para quem é, os cinco módulos em grade, o caminho do número à ação, a
  calculadora de margem, números do MEI com fonte, acessibilidade, perguntas e fechamento
- Cada módulo tem página própria: topo escuro com a demo, "Como funciona", detalhes em
  texto + interface, regras e o link para o próximo módulo
- O cabeçalho acompanha a seção que passa por baixo dele: floresta sobre as faixas marcadas
  com `data-nav="dark"`, `--color-bg` sobre o resto. Topos terminam em curva e as faixas do meio
  (caminho, números) são recuadas e arredondadas por `--lp-round`
- Perguntas em sanfona: só a pergunta aparece; o hover (ou clique/Enter) abre a resposta, frase
  por frase. A altura muda de uma vez e a rolagem é compensada, para a pergunta não fugir do mouse
- Sem fotos de pessoas nem depoimentos. O topo parte da dor do MEI e mostra a plataforma num
  computador e num celular (`.lp-devices`): desenho em HTML com os números da conta de
  demonstração, não print. O tamanho da letra segue a largura do bloco (`cqi`), então o aparelho
  encolhe inteiro no celular. O PIX do celular passa de "Aguardando" para "Pago" na entrada
- Cabeçalho: ao rolar, o nome da página ou da seção (`data-lockup`) desliza para junto do logo
  ("wageup▲pix"); entre seções, o nome rola para cima. Se não couber antes do primeiro link, não
  aparece (`is-lockup-tight`). Linha de progresso de leitura embaixo
- Login e cadastro: formulário à esquerda, alinhado ao logo, com "Voltar ao site" no alto; painel
  floresta à direita só no desktop, com um único cartão do dia do negócio
- Rolagem nativa do navegador, sem biblioteca de rolagem suave: a Lenis segurava a página
  e soltava aos poucos, o que no trackpad parecia travado
- Nada que dependa da rolagem pode mexer em variável CSS herdada (ela recalcula o estilo de
  todos os filhos a cada quadro) nem medir o layout a cada evento: meça uma vez, ao abrir a
  página e ao redimensionar, e na rolagem só compare números (`medirPagina` no `site.js`).
  Com o app aberto, os gatilhos de rolagem do site ficam desligados
- Páginas de módulo com profundidade: "por dentro" em linha do tempo (`.mp-flow`), contas em
  recibo (`.mp-receipt`), definições com exemplo (`.mp-defs`), regras (`.mp-rules`) e dúvidas
  do módulo na mesma sanfona (`.lp-faq--module`)
- Login e cadastro seguem o site: painel floresta com o título da aba aberta e o formulário claro
  com rótulos visíveis; o indicador das abas desliza (`#auth[data-tab]`, definido em `setAuthTab`)
- Movimento do `site.js`: entrada até 400ms, rolagem ligada (scrub) e mouse; nada em loop

### Dashboard (app)
- Background geral: `--color-bg`; sidebar no floresta do site (ver 7.10)
- Cada tela (`.view`) é uma coluna de `.summary-grid` e `.work-panel`, com `gap: --space-8`
- Header do dashboard: sem background próprio. Em cima, o nome do negócio com o fio verde do
  site; embaixo, o título em semibold com tracking apertado, como os títulos da landing
- Rótulos de cartão sem caixa alta; títulos de painel na fonte de títulos
- Telas de chat (assistente e marketing) no desktop: bloco recuado `--space-3` e arredondado
  como a barra lateral, em vez de ir de ponta a ponta

### Módulo Financeiro
- Métricas em destaque: valor em DM Mono grande, label pequeno em caps acima
- Gráficos: `--color-brand-mid` e `--color-brand-light` como cores primárias
- Positivo/negativo: semânticas (`--color-positive` / `--color-negative`), sempre com rótulo

### Assistente de IA e Marketing
- Tela cheia de chat (seção 7.9). O marketing acrescenta imagem e ações na resposta.

---

## 10. Responsivo

- **Mobile-first:** CSS base para o celular, `@media (min-width: …)` para telas maiores.
  O ponto de corte da navegação é 768px.
- **Colunas que encolhem:** grades de layout usam `minmax(0, 1fr)`, não `1fr` nem a coluna
  implícita. `1fr` não encolhe abaixo do conteúdo mais largo, e a página inteira rola de lado
  no celular. Vale para `.app-shell`, `.view.active` e `.work-panel`.
- **Container query quando o espaço depende do painel:** se o componente pode ficar estreito
  por causa da navegação, e não da janela, use `container-type: inline-size` no pai e
  `@container` nos filhos (exemplo: `.panel-heading--toolbar`).
- Verifique toda tela nova em 390px: nada pode passar da largura da tela.

---

## 11. Acessibilidade
- Contraste mínimo AA: 4.5:1 para texto normal, 3:1 para texto grande
- Todos inputs com `label` explícito (não só placeholder)
- Focus ring sempre visível (`--shadow-focus`)
- Estados hover e active nunca só por cor — incluir mudança de forma/peso ou rótulo
- Botão só com ícone tem `aria-label`; ícone ao lado de texto tem `aria-hidden="true"`
- Listas navegáveis por teclado (sugestões do chat) expõem `role="listbox"`/`option` e
  `aria-selected`
- Item de navegação ativo leva `aria-current="page"`, não só a classe `active`

### Painel de acessibilidade (`a11y.js`)
Botão fixo na lateral direita, acima do botão do VLibras. As preferências viram atributos no
`<html>`, e os tokens são redefinidos por eles no fim do `styles.css`:

| Atributo | Efeito |
|---|---|
| `data-font="115"` / `"130"` | `font-size` da raiz; tudo em `rem` escala junto |
| `data-contrast` | Texto, ícones e bordas a 5.8:1 ou mais; links sublinhados |
| `data-spacing` | Espaço entre letras, palavras e linhas (WCAG 1.4.12); ícones de fora |
| `data-reduce-motion` | Durações zeradas; vem do painel ou do `prefers-reduced-motion` do sistema |

Use sempre os tokens: cor fixa num componente não acompanha o alto contraste.

---

## 12. Exceções conhecidas

Pontos do CSS que hoje fogem das regras acima. Ficam registrados para não virarem padrão:

- **Cores fixas fora dos tokens:** fundos claros de alerta (`#FBEDED` no erro do chat, no badge
  negativo e no botão de perigo; `#FBF3E4` no badge de aviso) e os overlays de modal e drawer
  (`rgba(26, 26, 24, …)`). O caminho é criar tokens `--color-negative-subtle`,
  `--color-warning-subtle` e `--color-overlay`.
- **Logos dos bancos** na tela "Integre com seu banco" usam as cores das próprias marcas.
