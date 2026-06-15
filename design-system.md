# Design System — WageUp
> Plataforma de gestão financeira end-to-end para Microempreendedores

---

## 1. Identidade Visual

### Tom
Fintech minimalista com calor humano. Séria o suficiente para transmitir confiança financeira,
acessível o suficiente para não intimidar o MEI. Pensa em "Nubank meets Wise" — dados
limpos, linguagem direta, sem jargão, sem frescura.

### Princípios
- **Clareza acima de tudo** — cada pixel deve ter função. Nada decorativo sem propósito.
- **Confiança pelo espaço** — generoso espaçamento transmite controle, não vazio.
- **Verde como âncora** — a cor carrega o peso da marca; use com intenção, não decoração.
- **Tipografia como hierarquia** — o tamanho e peso do texto organiza a informação, não ícones.

### O que NUNCA fazer
- Gradientes coloridos ou sombras excessivas em cards
- Ícones decorativos em excesso (cada ícone deve ter função)
- Textos em caps lock em contextos de dados
- Border-radius > 12px em componentes de dados (parece brinquedo)
- Cores vibrantes demais — o verde sage É o accent, não precisa de laranja/amarelo por cima
- Backgrounds cinza genérico (`#f5f5f5`) — use os tokens definidos abaixo
- Fontes: Arial, Roboto, Inter, Poppins — proibidas

---

## 2. Paleta de Cores

```css
:root {
  /* Marca */
  --color-brand-dark:    #2D4A3E;   /* Verde escuro — sidebar, headers, peso */
  --color-brand-mid:     #4A7C65;   /* Verde médio — botões primários, links ativos */
  --color-brand-light:   #7DB896;   /* Verde sage — highlights, badges, ícones */
  --color-brand-subtle:  #EAF2EE;   /* Verde muito claro — backgrounds de cards positivos */

  /* Superfícies */
  --color-bg:            #F8F6F1;   /* Linen quente — background geral (NÃO branco puro) */
  --color-surface:       #FFFFFF;   /* Cards, modais, inputs */
  --color-surface-muted: #F2EFE9;   /* Surface secundária — sidebar, dividers de seção */
  --color-border:        #E2DDD5;   /* Bordas suaves */
  --color-border-strong: #C8C2B8;   /* Bordas em foco ou separadores fortes */

  /* Texto */
  --color-text-primary:  #1A1A18;   /* Quase preto quente — headlines, dados */
  --color-text-secondary:#5A5750;   /* Labels, metadados, placeholders */
  --color-text-disabled: #A8A49E;   /* Estados desabilitados */
  --color-text-inverse:  #F8F6F1;   /* Texto sobre fundos escuros */

  /* Semânticas */
  --color-positive:      #2E7D52;   /* Receita, lucro, crescimento */
  --color-negative:      #B84040;   /* Despesa, queda, alerta */
  --color-warning:       #9B6E28;   /* Atenção, pendente */
  --color-neutral:       #5A5750;   /* Neutro informativo */

  /* Accent (uso pontual) */
  --color-accent:        #4A7C65;   /* Alias de brand-mid para CTAs */
}
```

---

## 3. Tipografia

### Famílias
```css
/* Display / Headings — Questrial (mantida do Figma original) */
@import url('https://fonts.googleapis.com/css2?family=Questrial&display=swap');

/* Body / UI — DM Sans (substitui Space Grotesk — mais legível em tamanhos pequenos) */
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600&display=swap');

/* Dados numéricos — DM Mono (alinhamento de colunas, valores financeiros) */
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&display=swap');

:root {
  --font-display: 'Questrial', sans-serif;
  --font-body:    'DM Sans', sans-serif;
  --font-mono:    'DM Mono', monospace;
}
```

### Escala Tipográfica
```css
:root {
  /* Display */
  --text-display-xl: clamp(2.5rem, 5vw, 4rem);     /* Hero headlines */
  --text-display-lg: clamp(1.75rem, 3vw, 2.5rem);  /* Page titles */
  --text-display-md: clamp(1.25rem, 2vw, 1.75rem); /* Section headers */

  /* UI */
  --text-xl:   1.25rem;   /* 20px — subtítulos */
  --text-lg:   1.125rem;  /* 18px — body destacado */
  --text-base: 1rem;      /* 16px — body padrão */
  --text-sm:   0.875rem;  /* 14px — labels, metadados */
  --text-xs:   0.75rem;   /* 12px — badges, captions */

  /* Pesos */
  --weight-regular: 400;
  --weight-medium:  500;
  --weight-semibold: 600;

  /* Line heights */
  --leading-tight:  1.2;
  --leading-normal: 1.5;
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
| Hero title | Questrial | display-xl | 400 |
| Page title | Questrial | display-lg | 400 |
| Section header | DM Sans | display-md | 600 |
| Card label | DM Sans | sm | 500 |
| Body text | DM Sans | base | 400 |
| Valor monetário | DM Mono | lg/xl | 500 |
| Badge / tag | DM Sans | xs | 500, caps |
| Caption / meta | DM Sans | xs | 400 |

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
- **Padding interno de cards:** `--space-6` (24px)
- **Gap entre cards no grid:** `--space-4` (16px) ou `--space-6` (24px) em layouts maiores
- **Padding de seção (vertical):** mínimo `--space-16` (64px)
- **Sidebar width:** 240px fixo
- **Margem de conteúdo:** máx. 1200px, padding lateral `--space-8`

---

## 5. Border Radius

```css
:root {
  --radius-sm:  4px;   /* Inputs, badges pequenos */
  --radius-md:  8px;   /* Botões, cards compactos */
  --radius-lg:  12px;  /* Cards padrão, modais */
  --radius-xl:  16px;  /* Cards hero, painéis grandes */
  --radius-full: 9999px; /* Avatares, pills */
}
```

---

## 6. Sombras

```css
:root {
  /* Filosofia: sombras quentes, não frias */
  --shadow-sm:  0 1px 3px rgba(45, 74, 62, 0.08);
  --shadow-md:  0 4px 12px rgba(45, 74, 62, 0.10);
  --shadow-lg:  0 8px 24px rgba(45, 74, 62, 0.12);
  --shadow-focus: 0 0 0 3px rgba(74, 124, 101, 0.25); /* Ring de foco */
}
```

---

## 7. Componentes — Regras

### Botões
```css
/* Primário */
.btn-primary {
  background: var(--color-brand-mid);
  color: var(--color-text-inverse);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-6);
  font-family: var(--font-body);
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  letter-spacing: var(--tracking-wide);
  border: none;
  transition: background 150ms ease, transform 100ms ease;
}
.btn-primary:hover { background: var(--color-brand-dark); }

/* Secundário */
.btn-secondary {
  background: transparent;
  color: var(--color-brand-mid);
  border: 1.5px solid var(--color-brand-mid);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-6);
}

/* Ghost */
.btn-ghost {
  background: transparent;
  color: var(--color-text-secondary);
  border: none;
}
```

### Cards
```css
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  /* Sem box-shadow por padrão — use border */
}

.card--metric {
  /* Cards de métricas financeiras */
  padding: var(--space-5) var(--space-6);
}

.card--highlighted {
  /* Card com destaque de marca */
  border-color: var(--color-brand-light);
  background: var(--color-brand-subtle);
}
```

### Inputs
```css
.input {
  background: var(--color-surface);
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: var(--space-3) var(--space-4);
  font-family: var(--font-body);
  font-size: var(--text-base);
  color: var(--color-text-primary);
  transition: border-color 150ms ease, box-shadow 150ms ease;
}
.input:focus {
  border-color: var(--color-brand-mid);
  box-shadow: var(--shadow-focus);
  outline: none;
}
```

### Sidebar (Dashboard)
```css
.sidebar {
  width: 240px;
  background: var(--color-surface-muted);
  border-right: 1px solid var(--color-border);
  padding: var(--space-6) var(--space-4);
  /* NÃO usar background escuro — manter tom claro/linen */
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  color: var(--color-text-secondary);
  text-decoration: none;
  transition: background 150ms, color 150ms;
}
.nav-item:hover  { background: var(--color-border); color: var(--color-text-primary); }
.nav-item.active { background: var(--color-brand-subtle); color: var(--color-brand-mid); }
```

### Valores Monetários
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

/* Use com animation-delay para stagger */
.animate-in {
  animation: fadeUp var(--duration-slow) var(--ease-out) both;
}
```

### Regras de Animação
- Somente `opacity` + `transform` — nunca animar `height`, `width` ou `top/left`
- Duração máxima: 400ms para entradas de página
- Hover states: max 150ms
- Nenhuma animação em loop (sem pulsar, sem girar infinito fora de loading states)

---

## 9. Módulos e Páginas — Guia Visual

### Landing Page
- Background: `--color-bg` (linen)
- Hero: Questrial grande, tracking negativo, sem gradiente
- Nav: fundo `--color-bg`, sem sombra, border-bottom sutil

### Dashboard (app)
- Background geral: `--color-bg`
- Sidebar: `--color-surface-muted`
- Área de conteúdo: grid de cards em `--color-surface`
- Header do dashboard: simples, sem background próprio — funde com o bg

### Módulo Financeiro
- Métricas em destaque: valor em DM Mono grande, label pequeno acima
- Gráficos: usar apenas `--color-brand-mid` e `--color-brand-light` como cores primárias
- Positivo/negativo: semânticas definidas (`--color-positive` / `--color-negative`)

### Cards de Métrica (padrão)
```
┌─────────────────────────────┐
│ FATURAMENTO MENSAL          │  ← label: DM Sans xs, caps, color-text-secondary
│                             │
│ R$ 12.450,00                │  ← valor: DM Mono xl, color-text-primary
│ ↑ 8,3% vs mês anterior     │  ← delta: DM Sans sm, color-positive
└─────────────────────────────┘
```

---

## 10. Acessibilidade
- Contraste mínimo AA: 4.5:1 para texto normal, 3:1 para texto grande
- Todos inputs com `label` explícito (não só placeholder)
- Focus ring sempre visível (`--shadow-focus`)
- Estados hover e active nunca só por cor — incluir mudança de forma/peso
