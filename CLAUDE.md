# WageUp — Contexto do Projeto para Claude

## O que é o projeto

Plataforma para microempreendedores brasileiros (TCC). Permite gestão financeira simplificada, geração de cobranças via Pix, análise de desempenho e campanhas de marketing com IA.

Usuário **admin**: acessa módulo financeiro completo (transações, PIX via Abacate Pay).
Usuário **member**: cadastro de produtos, vendas, marketing com IA, onboarding.

O escopo completo está em `Escopo TCC.pdf`, dentro de `docs/` (pasta local, não versionada).

---

## Arquitetura

**Backend**: Django 6 + Django REST Framework, autenticação por Token.
**Frontend**: SPA em vanilla JS (sem framework), servido pelo próprio Django via WhiteNoise.
**Pagamentos**: Abacate Pay (PIX). Integração em `backend/apps/payments/services.py`.
**IA**: DeepSeek (`deepseek-chat`) para o assistente financeiro, o chat de marketing, os insights do dashboard e as recomendações de marketing, com a Anthropic (Claude Haiku, `claude-haiku-4-5-20251001`) como alternativa e regras locais quando não há nenhuma chave ou as duas falham. Insights e recomendações passam por `consultar_ia` em `finance/insights.py`.
**Deploy**: Render (aplicação) + Neon (PostgreSQL). Produção em https://wageup.onrender.com. Ver [DEPLOY-RENDER.md](DEPLOY-RENDER.md).

### Apps Django

```
backend/apps/
├── accounts/     # Auth (Token), UserProfile com role admin/member
├── businesses/   # Business (criado automaticamente no cadastro do usuário)
├── products/     # Catálogo, cálculo de margem e foto do produto
├── finance/      # Transações, importação de extrato, insights e assistente — só admin
├── payments/     # Cobranças PIX via Abacate Pay — só admin
├── sales/        # Vendas: ligam produto, estoque e financeiro — admin e member
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
| `ANTHROPIC_API_KEY` | Chave da Anthropic — alternativa à DeepSeek em todos os pontos de IA |
| `DEEPSEEK_API_KEY` | Chave da DeepSeek — assistente, chat de marketing, insights e recomendações |
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
# A partir da raiz do projeto, com o ambiente virtual `venv` ativo
source venv/bin/activate            # Windows: .\venv\Scripts\Activate.ps1
python backend/manage.py migrate
python backend/manage.py runserver
```

O `.env` só é lido quando o servidor sobe: depois de mudar uma chave, reinicie o `runserver`.

Conta de demonstração (apresentação do TCC): `python backend/manage.py seed_demo` cria `demo@wageup.local` com dois meses de vendas, despesas, meta, PIX pago e pendente, campanha e um produto em cada situação do marketing. Sem `--password`, gera e imprime uma senha. `--reset` recria; ele só apaga conta com o marcador `DEMO-WAGEUP` em `Business.document`. As datas são relativas ao dia em que o comando roda: rode de novo perto da apresentação. Para produção, rode a partir da sua máquina com `DATABASE_URL` apontando para o Neon.

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
GET    /api/auth/profile/                   # Resumo do perfil: negócio, números do mês, produtos (meta e PIX só admin)
PATCH/DELETE /api/auth/account/             # Nome e e-mail (e-mail pede senha) / apaga a conta (senha + "EXCLUIR")
POST   /api/auth/password/                  # Troca a senha logado; devolve token novo e derruba os outros
GET/PATCH /api/auth/business/               # Perfil do negócio e taxa/imposto padrão dos produtos
GET    /api/auth/connections/               # O que está ligado (PIX, IA, imagens, extrato, Google), sem chaves
GET    /api/auth/export/                    # Arquivo JSON com os dados da conta (LGPD)

GET/POST        /api/products/               # Filtrado por business do usuário
GET/POST/DELETE /api/products/<id>/image/    # Foto do produto, guardada no banco
GET/POST        /api/transactions/           # Só admin, filtrado por business
POST            /api/transactions/import/preview/    # Lê o extrato enviado, não grava nada
POST            /api/transactions/import/confirm/    # Grava o que o usuário confirmou
GET             /api/finance/insights/       # Só admin, insights do mês por IA, com botão de ação no marketing
GET/PUT/DELETE  /api/finance/goal/?month=AAAA-MM   # Só admin, meta de faturamento do mês e quanto falta
POST            /api/finance/assistant/      # Só admin, pergunta ao assistente financeiro
GET/POST        /api/finance/assistant/conversations/          # Lista ou cria conversa
GET/DELETE      /api/finance/assistant/conversations/<uuid>/   # Mensagens ou remoção
GET/POST        /api/payments/               # Só admin, gera PIX via Abacate Pay
GET             /api/payments/summary/       # Consolidação de recebíveis
POST            /api/payments/<id>/check/    # Sincroniza status com a Abacate Pay
POST            /api/payments/webhooks/abacatepay/   # Webhook de confirmação
GET/POST        /api/sales/?month=AAAA-MM    # Vendas do mês / registra venda (admin e member)
POST            /api/sales/<uuid>/cancel/    # Cancela: devolve estoque e tira a entrada do financeiro
GET             /api/sales/summary/?month=AAAA-MM   # Lucro realizado por produto no mês
POST            /api/marketing/chat/         # Pedido livre ao chat de marketing (DeepSeek; Anthropic como alternativa)
GET/POST        /api/marketing/conversations/          # Lista ou cria conversa de marketing
GET/DELETE      /api/marketing/conversations/<uuid>/   # Mensagens ou remoção
GET             /api/marketing/recommendations/  # O que divulgar em seguida, pela margem real do catálogo
POST            /api/marketing/actions/      # Botão da tela: product_id + action (campaign/launch/whatsapp)
GET             /api/marketing/products/     # Situação de cada produto no mês e a ação sugerida
GET             /api/marketing/campaigns/<uuid>/image/   # Imagem da campanha, guardada no banco
GET/POST        /api/marketing/campaigns/
DELETE          /api/marketing/campaigns/<uuid>/   # Exclui a campanha e a imagem; a conversa do chat fica
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

19. **Venda liga produto, estoque e financeiro** (`apps/sales/services.py`): a venda copia preço, custo, taxa e imposto do produto no momento da venda e grava o lucro real — preço e custo mudam depois, o lucro de uma venda antiga não. Estoque insuficiente bloqueia, com `UPDATE ... WHERE stock >= quantidade` para duas vendas simultâneas não deixarem o estoque negativo; produto com unidade serviço não controla estoque. A venda lança a entrada no financeiro com `Transaction.Source.SALE`, e essa entrada não é editada nem apagada em Movimentações: desfaz-se cancelando a venda, que devolve o estoque. Venda não tem editar nem apagar.

20. **PIX de produto vira venda só quando é pago**: o estoque é conferido ao gerar a cobrança, mas a baixa e a venda acontecem na conciliação do pagamento (`record_finance_income`), reaproveitando a entrada do PIX. Como o dinheiro já entrou, ali o estoque não bloqueia: baixa até zero e `Sale.stock_moved` guarda quanto saiu de fato, que é o que volta num estorno.

21. **Member registra venda, mas não vê o financeiro**: cada conta tem o próprio negócio, então a entrada da venda do member cai no financeiro do negócio dele. A visão geral do member mostra só o lucro por produto; cards, calendário e gráfico leem o financeiro e ficam escondidos (`data-admin-only`).

22. **Extrato não conta duas vezes o que já foi lançado na plataforma** (`_ja_lancados_na_plataforma` em `finance/views.py`): venda, PIX e lançamento manual não têm `external_id`, então a deduplicação por FITID (decisão 17) não os pega, mas o banco mostra o mesmo dinheiro no extrato. Na prévia, uma linha com mesmo tipo, mesmo valor e data a até um dia de distância vem desmarcada com `possible_match`. Cada lançamento casa com uma linha só. É sugestão, não bloqueio: o usuário pode marcar e importar. Venda no cartão (cai dias depois, já com a taxa descontada) não é reconhecida.

23. **Marketing abre em ações, não no chat**: a aba Ações mostra o que fazer a partir das vendas, da margem e do estoque, e cada botão leva a um resultado concreto. A ação de cada produto sai de `tipo_de_acao` em `marketing/recommendations.py`, pela situação dele, nunca pelo texto da IA: prejuízo leva ao preço, sem estoque ao estoque, estoque baixo ao aviso de WhatsApp, o resto à campanha. `POST /api/marketing/actions/` monta o pedido no servidor com o nome do produto vindo do banco e passa pelo mesmo `_conversar` do chat, então a campanha sai igual e "Ajustar no chat" continua a conversa. O aviso de WhatsApp abre o WhatsApp do MEI com o texto (`wa.me/?text=`): a plataforma não envia mensagem, porque não tem lista de clientes nem a API paga do WhatsApp Business.


24. **Meta é de faturamento, uma por mês** (`Goal`, `finance/goals.py`): compara com as entradas do mês no financeiro (venda, PIX, manual e extrato), não com o lucro — é o número que o MEI acompanha e o do exemplo do escopo. A conta mora em `progresso_da_meta`, usada pela rota, pelos insights e pelo assistente, para o card e o assistente nunca darem valores diferentes. Só admin, porque lê o financeiro.

25. **Insights falam do mês e levam à ação** (`finance/insights.py`): entradas, saídas e lucro são do mês corrente, como os cards ao lado; o acumulado contradizia o "Lucro do mês". O insight que cita um produto traz `action` com o tipo de `tipo_de_acao` (decisão 23), e o botão abre o Marketing e dispara `POST /api/marketing/actions/`. É o caminho Financeiro → Insight → Recomendação → Marketing do RF12. O produto que a IA cita é resolvido pelo nome contra o catálogo do negócio; um produto ganha botão uma vez só.

26. **Vendas caindo** (`gather_signals` em `marketing/recommendations.py`): unidades dos últimos 7 dias contra os 7 anteriores, com queda de 30% ou mais e pelo menos 3 unidades na semana anterior, para uma venda a menos não virar alarme. Vira a situação "Vendas caindo", recomendação "Recupere as vendas" (antes da estreia de produto nunca divulgado), insight e linha no contexto do assistente. A ação é promoção, não post de lançamento: o produto já é conhecido.

27. **Forma de pagamento no lançamento** (`Transaction.payment_method`, mesmos valores de `Sale.PaymentMethod`): a venda copia a dela, o PIX conciliado é sempre PIX, o lançamento manual escolhe, e o extrato fica "não informado". A migração preencheu o histórico só onde a origem diz a forma; inventar para o resto faria o painel "Como o dinheiro entrou" afirmar algo que ninguém registrou.

28. **Acessibilidade em `frontend/a11y.js`, separada do `app.js`**: carregado no `<head>` sem `defer`, aplica as preferências salvas (`localStorage` `wageup:a11y`) como atributos no `<html>` (`data-font`, `data-contrast`, `data-spacing`, `data-reduce-motion`) antes da primeira pintura; o CSS redefine os tokens por esses atributos, então componente novo acompanha sem regra própria. O mesmo arquivo prende o Tab dentro de `.modal`, `.drawer` e `.pix-screen` abertos e devolve o foco a quem abriu — os modais do `app.js` não precisam fazer isso cada um. Libras é o VLibras do Governo Federal (script de `vlibras.gov.br`, cria o próprio botão); a leitura em voz alta usa a Web Speech API do navegador. Quem usa leitor de tela tem o próprio programa: a plataforma garante rótulos, `aria-current`, `aria-live` e foco corretos. Arquivo novo na raiz do frontend precisa entrar na rota de `config/urls.py` e em `VERSIONED_ASSETS` de `config/views.py`.

29. **Site público com uma página por módulo** (`frontend/site.js`): home em `/` e páginas em `/vendas`, `/financeiro`, `/pix`, `/marketing`, `/assistente`, `/para-quem`, `/acessibilidade` e `/perguntas` — cada item do cabeçalho leva a uma página, não a uma âncora da home. Todas são o mesmo `index.html`, cada uma num `.lp-page`; o `site.js` mostra a do endereço e troca com `history.pushState` (links com `data-route`), sem recarregar. O Django serve o HTML nesses caminhos (`config/urls.py`) e redireciona a versão com barra no fim, porque os assets são relativos à raiz. Página nova: um `.lp-page` no HTML, a rota em `ROUTES` do `site.js` e o caminho no `re_path` de `config/urls.py`. O cabeçalho muda de cor pela seção que passa por baixo dele (`data-nav="dark"` nas faixas escuras). A home não usa foto de pessoa nem depoimento: o topo parte da dor do MEI e mostra a plataforma num computador e num celular, desenhados em HTML com os números da conta de demonstração — a plataforma ainda não foi avaliada com clientes reais, então nada ali pode parecer resultado de cliente. O cabeçalho junta ao logo o nome da página ou da seção ao rolar (`data-lockup`, "wageup▲pix") quando cabe antes do primeiro link. A rolagem é a nativa: a Lenis (rolagem com inércia) foi tirada porque travava a página no trackpad, e a rolagem não mexe em variável CSS nem mede o layout a cada evento (ver design-system.md); a única imagem é a campanha gerada pelo marketing (`frontend/landing/`).

30. **Perfil e configurações moram na conta** (`apps/accounts/conta.py`): o botão da conta, no pé da barra lateral, abre um cartão com o resumo do negócio e leva ao Perfil do negócio e às Configurações (Conta, Negócio, Dinheiro, Conexões, Privacidade e dados). Os números do perfil vêm das vendas, que admin e membro veem; meta e PIX pendente só vão para o admin. Trocar e-mail, trocar senha e apagar a conta pedem a senha atual e usam `PasswordCheckRateThrottle` (o `LoginRateThrottle` é de visitante e não conta quem já está logado). Trocar a senha troca o token, derrubando os outros aparelhos. O CNPJ digitado vai em `Business.cnpj`, validado também no formato alfanumérico de 2026; `Business.document` continua sendo o marcador do `seed_demo`. Taxa e imposto padrão (`Business.default_fee_percent`/`default_tax_percent`) só preenchem o produto novo, e "aplicar aos produtos já cadastrados" é opcional. Conexões mostram o estado de cada integração sem expor chave. Exportar dados devolve um JSON (o membro não recebe o financeiro) e excluir a conta apaga o negócio inteiro.

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
- [backend/apps/accounts/conta.py](backend/apps/accounts/conta.py) — perfil e configurações: conta, senha, negócio, conexões, exportar e excluir
- [backend/apps/accounts/test_conta.py](backend/apps/accounts/test_conta.py) — testes do perfil e das configurações
- [backend/apps/payments/services.py](backend/apps/payments/services.py) — cliente Abacate Pay
- [backend/apps/payments/tests.py](backend/apps/payments/tests.py) — testes do PIX: webhook, conciliação com o financeiro e isolamento
- [backend/apps/sales/services.py](backend/apps/sales/services.py) — regras da venda: estoque, lucro real, lançamento no financeiro, PIX de produto
- [backend/apps/sales/tests.py](backend/apps/sales/tests.py) — testes das vendas
- [backend/apps/marketing/views.py](backend/apps/marketing/views.py) — rotas do chat de marketing e das conversas
- [backend/apps/marketing/assistant.py](backend/apps/marketing/assistant.py) — contexto do catálogo, prompt e chamada à IA (DeepSeek/Anthropic) do chat de marketing
- [backend/apps/marketing/recommendations.py](backend/apps/marketing/recommendations.py) — recomendações de ação a partir do catálogo
- [backend/apps/marketing/images.py](backend/apps/marketing/images.py) — geração da imagem da campanha (Cloudflare/Pollinations)
- [backend/apps/finance/assistant.py](backend/apps/finance/assistant.py) — assistente financeiro (DeepSeek/Claude/local)
- [backend/apps/finance/insights.py](backend/apps/finance/insights.py) — insights do dashboard
- [backend/apps/finance/statements/](backend/apps/finance/statements/) — leitura de extrato bancário, um módulo por formato
- [backend/apps/finance/tests.py](backend/apps/finance/tests.py) — testes da leitura de OFX e da importação
- [backend/apps/accounts/throttles.py](backend/apps/accounts/throttles.py) — limites de requisição por rota
- [backend/apps/businesses/management/commands/seed_demo.py](backend/apps/businesses/management/commands/seed_demo.py) — conta de demonstração com dados realistas
- [frontend/app.js](frontend/app.js) — toda a lógica do SPA
- [frontend/a11y.js](frontend/a11y.js) — painel de acessibilidade, foco nos diálogos e VLibras
- [frontend/site.js](frontend/site.js) — site público: páginas por endereço, calculadora, demo de PIX e animações
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
