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
**IA**: DeepSeek (`deepseek-chat`) para o assistente financeiro e o chat de marketing, com a Anthropic (Claude Haiku, `claude-haiku-4-5-20251001`) como alternativa e resposta local quando não há nenhuma chave. Os insights do dashboard e as recomendações de marketing usam a Anthropic.
**Deploy**: Render (aplicação) + Neon (PostgreSQL). Produção em https://wageup.onrender.com. Ver [DEPLOY-RENDER.md](DEPLOY-RENDER.md).

### Apps Django

```
backend/apps/
├── accounts/     # Auth (Token), UserProfile com role admin/member
├── businesses/   # Business (criado automaticamente no cadastro do usuário)
├── products/     # Catálogo, cálculo de margem e foto do produto
├── finance/      # Transações, importação de extrato, insights e assistente — só admin
├── payments/     # Cobranças PIX via Abacate Pay — só admin
└── marketing/    # Chat de marketing com IA (DeepSeek, Anthropic como alternativa)
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
| `POST /api/auth/password-reset/` e `/password-reset/confirm/` | Quem perdeu a senha nao tem como fazer login |
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

- O projeto **se recusa a subir** com a `SECRET_KEY` de exemplo, ausente ou com menos de 50 caracteres. O mínimo é o mesmo que o `check --deploy` do Django cobra (`security.W009`): checar só a chave de exemplo deixaria passar um valor curto qualquer, que não protege nada.
- HTTPS obrigatório: `SECURE_SSL_REDIRECT`, cookies com `Secure`, HSTS (ajustável por `SECURE_HSTS_SECONDS`).
- `SECURE_PROXY_SSL_HEADER` é obrigatório atrás do proxy do Render — sem ele o redirect de HTTPS entra em laço.
- A API navegável do DRF (`BrowsableAPIRenderer`) só é carregada com `DEBUG=True`.
- O webhook da Abacate Pay responde `503` se `ABACATE_PAY_WEBHOOK_SECRET` não estiver configurado. Sem segredo, qualquer um poderia postar um evento e marcar uma cobrança como paga. A comparação usa `secrets.compare_digest` (tempo constante).

### Upload de arquivo

A importação de extrato é o único ponto que recebe arquivo. Regras em `settings.py`:

- `FILE_UPLOAD_HANDLERS` tem só o handler de memória, então nada vai para o disco.
- `STATEMENT_MAX_UPLOAD_BYTES` limita em 5 MB, conferido na view antes de ler.
- Arquivo ilegível responde `400` com explicação. Uma exceção inesperada no leitor também vira `400`, com o traceback no log — arquivo corrompido é problema do arquivo, não do servidor.

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
| `ANTHROPIC_API_KEY` | Chave da Anthropic — insights, recomendações e alternativa à DeepSeek nos chats |
| `DEEPSEEK_API_KEY` | Chave da DeepSeek — assistente financeiro e chat de marketing |
| `DEEPSEEK_BASE_URL` | Endpoint da DeepSeek (default `https://api.deepseek.com`) |
| `DEEPSEEK_MODEL` | Modelo da DeepSeek (default `deepseek-chat`) |
| `GOOGLE_CLIENT_ID` | Client ID do Google — habilita o login com Google |
| `CLOUDFLARE_ACCOUNT_ID` / `CLOUDFLARE_API_TOKEN` | Cloudflare Workers AI — gera a imagem da campanha |
| `MARKETING_IMAGE_FALLBACK` | Liga o Pollinations.ai como alternativa sem chave (default `False`) |
| `RESEND_API_KEY` | Chave do Resend — entrega o e-mail de recuperação pela API HTTP |
| `EMAIL_HOST` | Servidor SMTP, alternativa ao Resend — sem nenhum dos dois o e-mail sai no console (dev) |
| `EMAIL_PORT` / `EMAIL_USE_TLS` | Ajuste do SMTP (default 587 / True) |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | Credenciais do SMTP |
| `DEFAULT_FROM_EMAIL` | Remetente dos e-mails |
| `PASSWORD_RESET_TIMEOUT` | Validade do link de recuperação em segundos (default 7200) |
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
POST   /api/auth/password-reset/            # Pede o link de recuperacao por e-mail
POST   /api/auth/password-reset/confirm/    # Troca a senha usando uid + token do link

GET/POST        /api/products/               # Filtrado por business do usuário
GET/POST/DELETE /api/products/<id>/image/    # Foto do produto, guardada no banco
GET/POST        /api/transactions/           # Só admin, filtrado por business
POST            /api/transactions/import/preview/    # Lê o extrato enviado, não grava nada
POST            /api/transactions/import/confirm/    # Grava o que o usuário confirmou
GET             /api/finance/insights/       # Só admin, insights por IA do dashboard
POST            /api/finance/assistant/      # Só admin, pergunta ao assistente financeiro
GET/POST        /api/finance/assistant/conversations/          # Lista ou cria conversa
GET/DELETE      /api/finance/assistant/conversations/<uuid>/   # Mensagens ou remoção
GET/POST        /api/payments/               # Só admin, gera PIX via Abacate Pay
GET             /api/payments/summary/       # Consolidação de recebíveis
POST            /api/payments/<id>/check/    # Sincroniza status com a Abacate Pay
POST            /api/payments/webhooks/abacatepay/   # Webhook de confirmação
POST            /api/marketing/chat/         # Pedido livre ao chat de marketing (DeepSeek; Anthropic como alternativa)
GET/POST        /api/marketing/conversations/          # Lista ou cria conversa de marketing
GET/DELETE      /api/marketing/conversations/<uuid>/   # Mensagens ou remoção
GET             /api/marketing/recommendations/  # O que divulgar em seguida, pela margem real do catálogo
GET             /api/marketing/campaigns/<uuid>/image/   # Imagem da campanha, guardada no banco
GET/POST        /api/marketing/campaigns/
GET             /api/health/                 # Health check (aberto, sem throttle)
```

---

## Decisões de arquitetura tomadas

1. **Business criado no registro**: simplificação para TCC — cada user tem exatamente 1 business. Em produção real, suportaria múltiplos.

2. **Frontend servido pelo Django**: WhiteNoise serve `frontend/` como static files. O `index.html` é servido em `/`. Isso simplifica o deploy (tudo num serviço só no Render).

3. **Marketing AI com fallback**: sem `DEEPSEEK_API_KEY` nem `ANTHROPIC_API_KEY`, ou se as duas falharem, o chat responde com uma campanha local montada a partir do assunto do pedido. Não quebra em dev sem chave.

4. **Token auth (não JWT)**: DRF TokenAuthentication. Simples para TCC, suficiente para o escopo.

5. **Admin via env var**: `WAGEUP_ADMIN_EMAILS` define quem é admin no cadastro. Não há promoção de role por interface — é configuração de deploy.

6. **Abacate Pay centralizado**: no TCC, todas as cobranças vão para uma conta única de teste (limitação documentada no escopo). A arquitetura futura usaria subcontas.

7. **API fechada por padrão**: `DEFAULT_PERMISSION_CLASSES = IsAuthenticated`. O default anterior era `AllowAny`, o que fazia a segurança depender de cada view lembrar de declarar permissão — um esquecimento bastava para expor uma rota. Ver a seção "Segurança".

8. **`DJANGO_DEBUG` default `False`**: quem não configurar nada roda no modo seguro. O `.env.example` liga o modo de desenvolvimento explicitamente.

9. **Importação de extrato em dois passos**: `preview` lê e devolve, `confirm` grava. Nunca criar lançamento direto do arquivo — extrato traz transferência entre contas próprias, que não é receita nem despesa. O usuário confere antes.

10. **O arquivo do extrato não é guardado**: é lido em memória (`FILE_UPLOAD_HANDLERS` só com o handler de memória) e descartado. Ficam os lançamentos e o hash do arquivo. Extrato bancário é dado sensível e a funcionalidade não precisa dele depois.

11. **Foto de produto no banco, não em disco**: o disco do Render no plano free é efêmero — arquivo salvo lá some no próximo deploy. A imagem chega reduzida pelo navegador (lado maior de 800px, JPEG), o servidor recusa acima de 400 KB, e ela vive em `ProductImage`, uma tabela à parte para a listagem de produtos não arrastar os bytes junto. Não escala para milhares de produtos; para o catálogo de um MEI, resolve sem serviço externo.

12. **A rota da foto exige autenticação**, e `<img src>` não manda o token. A tela busca a imagem com `fetch` e monta um object URL. A alternativa seria uma rota pública protegida só pelo UUID, o que troca segurança por conveniência.

13. **Quem consome margem lê do modelo, nunca de preço menos custo**: marketing (`marketing/views.py`, `marketing/recommendations.py`) e insights (`finance/insights.py`) usam `Product.margin_value`. A conta simples ignora embalagem, taxa de cartão e imposto, e com ela a IA recomenda desconto sobre um lucro que não existe. Nas rotas de marketing, os números vêm do banco pelo id do produto — o cliente manda o id, não os valores.

14. **O cálculo de margem mora no modelo `Product`**, em `variable_cost`, `fee_amount`, `margin_value`, `margin_percent` e `markup_percent`. O serializer expõe esses valores prontos. A tela repete a fórmula em `productMargin()` apenas para responder enquanto o usuário digita — mudou a conta no Python, mude no JavaScript.

15. **A imagem da campanha não vem da Anthropic**: a Anthropic lê imagem, não gera. Quem gera é a Cloudflare Workers AI (FLUX.1-schnell), com o Pollinations.ai como alternativa sem chave. O prompt da imagem sai do trecho "Ideia de imagem" que a IA de texto já escreveu — gerar um prompt separado produziria uma imagem que não combina com a legenda. Antes de ir para o FLUX, a mesma IA de texto (DeepSeek/Anthropic) traduz essa ideia para inglês e escolhe um estilo de anúncio que combina com o produto (`prompt_da_imagem` em `marketing/assistant.py`): o FLUX lê ao pé da letra e em português, e "cachorro quente" virava um cachorro. Sem IA de texto, um glossário com os produtos mais comuns de MEI (`images.GLOSSARIO`) faz o mínimo. O Pollinations é **opt-in** (`MARKETING_IMAGE_FALLBACK`) porque não pede chave: ligado por padrão, toda campanha esperaria por ele e sairia com marca d'água.

16. **A imagem da campanha mora no banco**, em `CampaignImage`, pelo mesmo motivo da foto de produto: o disco do Render é efêmero. Tabela à parte para a listagem de campanhas não arrastar os bytes. A rota exige autenticação e filtra por business, então a tela busca com `fetch` e monta um object URL — `<img src>` não manda token.

17. **Deduplicação por `Transaction.external_id`**, com unicidade por business: o FITID do OFX quando existe, senão uma impressão digital do conteúdo. É o que faz reimportar o mesmo extrato não duplicar. Qualquer formato novo (CSV, PDF) precisa devolver um `external_id` estável — sem isso, a importação suja o financeiro em vez de ajudar.

18. **Marketing é um chat, não um formulário**: a tela usa o mesmo componente do assistente financeiro (`createChat()` em `app.js`) e o usuário escreve o pedido livremente. O histórico vive em `MarketingConversation`/`MarketingMessage`, no servidor. Provedores na mesma ordem do assistente financeiro: DeepSeek, depois Anthropic, depois resposta local. A IA recebe o catálogo inteiro com a margem real (`marketing/assistant.py`); o produto e o canal da campanha são deduzidos do nome citado no pedido, ou herdados da campanha anterior da conversa quando o pedido não cita outro assunto. Só a resposta que traz a seção "Ideia de imagem" vira `MarketingCampaign` e ganha imagem — pergunta solta ("que hashtag uso?") não gera imagem nem registro.

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
- [backend/apps/accounts/emails.py](backend/apps/accounts/emails.py) — e-mail de recuperação de senha
- [backend/apps/accounts/email_backends.py](backend/apps/accounts/email_backends.py) — backend de e-mail via API do Resend
- [backend/apps/accounts/tests.py](backend/apps/accounts/tests.py) — testes da recuperação de senha
- [backend/apps/payments/services.py](backend/apps/payments/services.py) — cliente Abacate Pay
- [backend/apps/marketing/views.py](backend/apps/marketing/views.py) — rotas do chat de marketing e das conversas
- [backend/apps/marketing/assistant.py](backend/apps/marketing/assistant.py) — contexto do catálogo, prompt e chamada à IA (DeepSeek/Anthropic) do chat de marketing
- [backend/apps/marketing/recommendations.py](backend/apps/marketing/recommendations.py) — recomendações de ação a partir do catálogo
- [backend/apps/marketing/images.py](backend/apps/marketing/images.py) — geração da imagem da campanha (Cloudflare/Pollinations)
- [backend/apps/finance/assistant.py](backend/apps/finance/assistant.py) — assistente financeiro (DeepSeek/Claude/local)
- [backend/apps/finance/insights.py](backend/apps/finance/insights.py) — insights do dashboard
- [backend/apps/finance/statements/](backend/apps/finance/statements/) — leitura de extrato bancário, um módulo por formato
- [backend/apps/finance/tests.py](backend/apps/finance/tests.py) — testes da leitura de OFX e da importação
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
