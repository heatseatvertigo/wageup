# WageUp — Contexto do Projeto para Claude

## O que é o projeto

Plataforma para microempreendedores brasileiros (TCC). Permite gestão financeira simplificada, geração de cobranças via Pix, análise de desempenho e campanhas de marketing com IA.

Usuário **admin**: acessa módulo financeiro completo (transações, PIX via Abacate Pay).
Usuário **member**: cadastro de produtos, marketing com IA, onboarding.

O escopo completo está em `Escopo TCC.pdf`, dentro de `docs/` (pasta local, não versionada).

---

## Arquitetura

**Backend**: Django 6 + Django REST Framework, autenticação por Token.
**Frontend**: SPA em vanilla JS (sem framework), servido pelo próprio Django via WhiteNoise.
**Pagamentos**: Abacate Pay (PIX). Integração em `backend/apps/payments/services.py`.
**IA**: Anthropic Claude Haiku (`claude-haiku-4-5-20251001`) para campanhas de marketing e insights do dashboard. DeepSeek (`deepseek-chat`) para o assistente financeiro, com a Anthropic como alternativa e resposta local quando não há nenhuma chave.
**Deploy**: Render (aplicação) + Neon (PostgreSQL). Produção em https://wageup.onrender.com. Ver [DEPLOY-RENDER.md](DEPLOY-RENDER.md).

### Apps Django

```
backend/apps/
├── accounts/     # Auth (Token), UserProfile com role admin/member
├── businesses/   # Business (criado automaticamente no cadastro do usuário)
├── products/     # Catálogo de produtos por Business
├── finance/      # Transações, insights e assistente financeiro — só admin
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

## Segurança

Regras que valem para qualquer código novo. Todas estão implementadas em `backend/config/settings.py` e nas views.

### Permissão é fechada por padrão

`DEFAULT_PERMISSION_CLASSES` é `IsAuthenticated`. Uma view que esquecer de declarar permissão fica **inacessível**, não pública. As únicas rotas abertas declaram `AllowAny` de forma explícita:

| Rota | Por que é aberta |
|---|---|
| `POST /api/auth/register/` | Cria a conta — não há como exigir login |
| `POST /api/auth/login/` e `/api/auth/google/` | Autenticam |
| `POST /api/payments/webhooks/abacatepay/` | Quem chama é a Abacate Pay; autentica pelo segredo compartilhado |
| `GET /api/health/` | Health check do Render |

Ao criar uma view nova, **não** adicione `AllowAny` sem um motivo desta tabela.

### Limites de requisição (throttling)

Definidos em `backend/apps/accounts/throttles.py` e aplicados com `@throttle_classes`:

- `AIRateThrottle` (escopo `ai`, default 60/hora) — em toda rota que chama modelo de linguagem. Cada chamada custa dinheiro; sem limite, uma conta comprometida esvazia o crédito da API.
- `LoginRateThrottle` (escopo `login`, default 10/min) — em registro, login e login com Google. Segura tentativa de descobrir senha por força bruta.
- Padrão global: 30/min para visitante, 120/min para usuário autenticado.

O health check e o webhook rodam com `@throttle_classes([])`: um 429 no health check derruba o deploy, e no webhook faria a Abacate Pay reentregar o evento à toa.

O contador do throttle vive no cache do Django, que hoje é `LocMemCache` — ou seja, por processo. Com mais de um worker do gunicorn o limite efetivo é multiplicado pelo número de workers. Para um limite exato seria preciso um cache compartilhado (Redis).

### Produção (`DJANGO_DEBUG=False`)

- O projeto **se recusa a subir** com a `SECRET_KEY` de exemplo.
- HTTPS obrigatório: `SECURE_SSL_REDIRECT`, cookies com `Secure`, HSTS (ajustável por `SECURE_HSTS_SECONDS`).
- `SECURE_PROXY_SSL_HEADER` é obrigatório atrás do proxy do Render — sem ele o redirect de HTTPS entra em laço.
- A API navegável do DRF (`BrowsableAPIRenderer`) só é carregada com `DEBUG=True`.
- O webhook da Abacate Pay responde `503` se `ABACATE_PAY_WEBHOOK_SECRET` não estiver configurado. Sem segredo, qualquer um poderia postar um evento e marcar uma cobrança como paga. A comparação usa `secrets.compare_digest` (tempo constante).

### Isolamento continua sendo responsabilidade da view

Throttle e permissão não substituem o filtro por `business`. Todo `get_queryset()` filtra pelo negócio do usuário — ver a seção "Isolamento de dados".

---

## Variáveis de ambiente

Arquivo `.env` na raiz do projeto (não commitado). Ver `.env.example` para referência.

| Variável | Uso |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DJANGO_DEBUG` | `True` local, `False` produção |
| `DATABASE_URL` | SQLite local (default `backend/db.sqlite3`), PostgreSQL (Neon) em produção |
| `ABACATE_PAY_API_KEY` | Chave da Abacate Pay para gerar PIX |
| `ABACATE_PAY_WEBHOOK_SECRET` | Segredo do webhook da Abacate Pay |
| `WAGEUP_ADMIN_EMAILS` | E-mails com role admin (ex: `admin@wageup.com`) |
| `ANTHROPIC_API_KEY` | Chave da Anthropic — campanhas de marketing e insights |
| `DEEPSEEK_API_KEY` | Chave da DeepSeek — assistente financeiro |
| `DEEPSEEK_BASE_URL` | Endpoint da DeepSeek (default `https://api.deepseek.com`) |
| `DEEPSEEK_MODEL` | Modelo da DeepSeek (default `deepseek-chat`) |
| `GOOGLE_CLIENT_ID` | Client ID do Google — habilita o login com Google |
| `LOG_LEVEL` | Nível dos logs de `apps.*` (default `INFO`) |
| `THROTTLE_ANON` / `THROTTLE_USER` | Limite de requisições por visitante / por usuário |
| `THROTTLE_AI` / `THROTTLE_LOGIN` | Limite das rotas de IA / das rotas de login e registro |
| `SECURE_HSTS_SECONDS` | Duração do HSTS em produção (default 31536000) |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` / `SECURE_HSTS_PRELOAD` | Ajuste fino do HSTS |
| `CUSTOM_DOMAIN` | Domínio próprio — adicionado automaticamente ao CORS/ALLOWED_HOSTS |
| `RENDER_EXTERNAL_HOSTNAME` | Preenchido automaticamente pelo Render — adicionado ao ALLOWED_HOSTS/CORS/CSRF |

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
GET             /api/finance/insights/       # Só admin, insights por IA do dashboard
POST            /api/finance/assistant/      # Só admin, pergunta ao assistente financeiro
GET/POST        /api/finance/assistant/conversations/          # Lista ou cria conversa
GET/DELETE      /api/finance/assistant/conversations/<uuid>/   # Mensagens ou remoção
GET/POST        /api/payments/               # Só admin, gera PIX via Abacate Pay
GET             /api/payments/summary/       # Consolidação de recebíveis
POST            /api/payments/<id>/check/    # Sincroniza status com a Abacate Pay
POST            /api/payments/webhooks/abacatepay/   # Webhook de confirmação
POST            /api/marketing/chat/         # Gera campanha (Claude Haiku se ANTHROPIC_API_KEY estiver set)
GET/POST        /api/marketing/campaigns/
GET             /api/health/                 # Health check (aberto, sem throttle)
```

---

## Decisões de arquitetura tomadas

1. **Business criado no registro**: simplificação para TCC — cada user tem exatamente 1 business. Em produção real, suportaria múltiplos.

2. **Frontend servido pelo Django**: WhiteNoise serve `frontend/` como static files. O `index.html` é servido em `/`. Isso simplifica o deploy (tudo num serviço só no Render).

3. **Marketing AI com fallback**: se `ANTHROPIC_API_KEY` não estiver configurada, o endpoint retorna uma resposta demo local. Não quebra em dev sem chave.

4. **Token auth (não JWT)**: DRF TokenAuthentication. Simples para TCC, suficiente para o escopo.

5. **Admin via env var**: `WAGEUP_ADMIN_EMAILS` define quem é admin no cadastro. Não há promoção de role por interface — é configuração de deploy.

6. **Abacate Pay centralizado**: no TCC, todas as cobranças vão para uma conta única de teste (limitação documentada no escopo). A arquitetura futura usaria subcontas.

7. **API fechada por padrão**: `DEFAULT_PERMISSION_CLASSES = IsAuthenticated`. O default anterior era `AllowAny`, o que fazia a segurança depender de cada view lembrar de declarar permissão — um esquecimento bastava para expor uma rota. Ver a seção "Segurança".

8. **`DJANGO_DEBUG` default `False`**: quem não configurar nada roda no modo seguro. O `.env.example` liga o modo de desenvolvimento explicitamente.

---

## Deploy no Render + Neon

O `render.yaml` já está configurado:
- `buildCommand`: instala deps e roda `collectstatic`
- `preDeployCommand`: roda `migrate` automaticamente
- `startCommand`: gunicorn servindo `config.wsgi:application` do diretório `backend/`

Banco PostgreSQL no Neon (não expira; backups automáticos). Passo a passo completo em [DEPLOY-RENDER.md](DEPLOY-RENDER.md).

Para domínio próprio: configurar `CUSTOM_DOMAIN=seudominio.com` nas variáveis do Render.

---

## Arquivos importantes

- [backend/config/settings.py](backend/config/settings.py) — toda a configuração Django
- [backend/apps/accounts/serializers.py](backend/apps/accounts/serializers.py) — registro cria User + UserProfile + Business
- [backend/apps/accounts/permissions.py](backend/apps/accounts/permissions.py) — `IsAdminRole`
- [backend/apps/payments/services.py](backend/apps/payments/services.py) — cliente Abacate Pay
- [backend/apps/marketing/views.py](backend/apps/marketing/views.py) — `_call_claude()` para IA
- [backend/apps/finance/assistant.py](backend/apps/finance/assistant.py) — assistente financeiro (DeepSeek/Claude/local)
- [backend/apps/finance/insights.py](backend/apps/finance/insights.py) — insights do dashboard
- [backend/apps/accounts/throttles.py](backend/apps/accounts/throttles.py) — limites de requisição por rota
- [frontend/app.js](frontend/app.js) — toda a lógica do SPA
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
