# WageUp — Contexto do Projeto para Claude

## O que é o projeto

Plataforma para microempreendedores brasileiros (TCC). Permite gestão financeira simplificada, geração de cobranças via Pix, análise de desempenho e campanhas de marketing com IA.

Usuário **admin**: acessa módulo financeiro completo (transações, PIX via Abacate Pay).
Usuário **member**: cadastro de produtos, marketing com IA, onboarding.

O escopo completo está em `Escopo TCC.pdf` na raiz do projeto.

---

## Arquitetura

**Backend**: Django 6 + Django REST Framework, autenticação por Token.
**Frontend**: SPA em vanilla JS (sem framework), servido pelo próprio Django via WhiteNoise.
**Pagamentos**: Abacate Pay (PIX). Integração em `backend/apps/payments/services.py`.
**IA**: Anthropic Claude Haiku (`claude-haiku-4-5-20251001`) para geração de campanhas de marketing.
**Deploy**: Railway (backend + PostgreSQL). Frontend já está no Vercel mas pode ser servido pelo Railway também.

### Apps Django

```
backend/apps/
├── accounts/     # Auth (Token), UserProfile com role admin/member
├── businesses/   # Business (criado automaticamente no cadastro do usuário)
├── products/     # Catálogo de produtos por Business
├── finance/      # Transações (entrada/saída) — só admin
├── payments/     # Cobranças PIX via Abacate Pay — só admin
└── marketing/    # Campanhas de marketing com IA (Claude Haiku)
```

### Isolamento de dados

Cada usuário tem um `Business` criado automaticamente no registro (`accounts/serializers.py`).
Todos os ViewSets filtram por `business__owner=request.user`. Nunca use `queryset = Model.objects.all()` sem override de `get_queryset()`.

### Fluxo de permissões

- `IsAdminRole` (em `accounts/permissions.py`): verifica `UserProfile.role == "admin"` ou `is_staff/is_superuser`
- Quem é admin: definido pela env var `WAGEUP_ADMIN_EMAILS` (lista de e-mails separados por vírgula)
- O frontend esconde módulos financeiros via `canAccessFinance()` baseado em `user.can_access_finance`

---

## Variáveis de ambiente

Arquivo `.env` na raiz do projeto (não commitado). Ver `.env.example` para referência.

| Variável | Uso |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DJANGO_DEBUG` | `True` local, `False` produção |
| `DATABASE_URL` | SQLite local (`sqlite:///db.sqlite3`), PostgreSQL no Railway |
| `ABACATE_PAY_API_KEY` | Chave da Abacate Pay para gerar PIX |
| `ABACATE_PAY_WEBHOOK_SECRET` | Segredo do webhook da Abacate Pay |
| `WAGEUP_ADMIN_EMAILS` | E-mails com role admin (ex: `admin@wageup.com`) |
| `ANTHROPIC_API_KEY` | Chave da Anthropic para IA de marketing |
| `CUSTOM_DOMAIN` | Domínio próprio — adicionado automaticamente ao CORS/ALLOWED_HOSTS |
| `RAILWAY_PUBLIC_DOMAIN` | Preenchido automaticamente pelo Railway |

---

## Como rodar localmente

```bash
# A partir da raiz do projeto
.venv\Scripts\python backend\manage.py runserver
# ou
cd backend && ..\.venv\Scripts\python manage.py runserver
```

Acesse `http://localhost:8000`. O frontend é servido na raiz (`/`).

---

## Endpoints principais

```
POST   /api/auth/register/                   # Cria user + UserProfile + Business
POST   /api/auth/login/
GET    /api/auth/me/
PATCH  /api/auth/onboarding/

GET/POST        /api/products/               # Filtrado por business do usuário
GET/POST        /api/transactions/           # Só admin, filtrado por business
GET/POST        /api/payments/              # Só admin, gera PIX via Abacate Pay
POST            /api/payments/webhooks/abacatepay/   # Webhook de confirmação
POST            /api/marketing/chat/         # Gera campanha (Claude Haiku se ANTHROPIC_API_KEY estiver set)
GET/POST        /api/marketing/campaigns/
```

---

## Decisões de arquitetura tomadas

1. **Business criado no registro**: simplificação para TCC — cada user tem exatamente 1 business. Em produção real, suportaria múltiplos.

2. **Frontend servido pelo Django**: WhiteNoise serve `frontend/` como static files. O `index.html` é servido em `/`. Isso simplifica o deploy (tudo num serviço só no Railway).

3. **Marketing AI com fallback**: se `ANTHROPIC_API_KEY` não estiver configurada, o endpoint retorna uma resposta demo local. Não quebra em dev sem chave.

4. **Token auth (não JWT)**: DRF TokenAuthentication. Simples para TCC, suficiente para o escopo.

5. **Admin via env var**: `WAGEUP_ADMIN_EMAILS` define quem é admin no cadastro. Não há promoção de role por interface — é configuração de deploy.

6. **Abacate Pay centralizado**: no TCC, todas as cobranças vão para uma conta única de teste (limitação documentada no escopo). A arquitetura futura usaria subcontas.

---

## Deploy no Railway

O `Procfile` e `railway.json` já estão configurados:
- `release`: roda `migrate` automaticamente
- `web`: gunicorn servindo `config.wsgi:application` do diretório `backend/`

Para domínio próprio: configurar `CUSTOM_DOMAIN=seudominio.com` nas variáveis do Railway.

---

## Arquivos importantes

- [backend/config/settings.py](backend/config/settings.py) — toda a configuração Django
- [backend/apps/accounts/serializers.py](backend/apps/accounts/serializers.py) — registro cria User + UserProfile + Business
- [backend/apps/accounts/permissions.py](backend/apps/accounts/permissions.py) — `IsAdminRole`
- [backend/apps/payments/services.py](backend/apps/payments/services.py) — cliente Abacate Pay
- [backend/apps/marketing/views.py](backend/apps/marketing/views.py) — `_call_claude()` para IA
- [frontend/app.js](frontend/app.js) — toda a lógica do SPA (744 linhas)
- [frontend/styles.css](frontend/styles.css) — CSS atual do SPA
- [frontend/index.html](frontend/index.html) — HTML do SPA
- [design-system.md](design-system.md) — **Design system completo** (cores, tipografia, componentes)
- [.env.example](.env.example) — template de variáveis de ambiente

---

## Regras de Frontend — Design System

**SEMPRE** leia `design-system.md` antes de criar ou modificar qualquer arquivo CSS ou HTML com componentes visuais.

Todas as cores, fontes, espaçamentos e componentes estão definidos lá como CSS custom properties.

**Nunca:**
- Usar cores hardcoded (`#ffffff`, `green`, `rgba(...)`) — use sempre as variáveis do design system
- Usar `font-family: Inter`, `Arial`, `Roboto` ou qualquer fonte fora do design system
- Criar `box-shadow` fora dos tokens (`--shadow-sm`, `--shadow-md`, `--shadow-lg`)
- Usar `border-radius` maior que `--radius-xl` (16px) em cards de dados
- Exibir valores monetários sem `font-family: var(--font-mono)` (DM Mono)

### Regras de CSS
- Mobile-first: CSS base para mobile, `@media (min-width: ...)` para desktop
- Nunca use `!important`
- Animações: apenas `opacity` e `transform` — nunca anime `height`, `width`, `top`, `left`
- Prefira `gap` a `margin` para espaçamento entre filhos de flex/grid

### Nomenclatura BEM simplificado
```css
.bloco {}
.bloco__elemento {}
.bloco--modificador {}
/* ex: .card, .card__header, .card__value, .card--highlighted */
```

### Valores financeiros
Todo valor monetário deve:
1. Usar `font-family: var(--font-mono)` (DM Mono)
2. Estar formatado como `R$ 1.234,56`
3. Usar `var(--color-positive)` para receita/lucro, `var(--color-negative)` para despesa/prejuízo
4. Nunca usar cor como único indicador — incluir ícone ou label textual

### Escopo de alterações
Antes de modificar qualquer arquivo, confirme exatamente o que foi pedido. Alterações cirúrgicas — preserve o que está funcionando.
