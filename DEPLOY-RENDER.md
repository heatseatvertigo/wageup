# Migração de Deploy: Railway → Render + Neon

> Guia passo a passo para hospedar o WageUp no **Render** (aplicação) + **Neon** (PostgreSQL).
> Custo: R$ 0 nos planos gratuitos. Criado em 2026-07-15.

O código já foi ajustado para o Render (ver seção "Ajustes já feitos no código" no final). Este guia cobre o que **você** precisa clicar nos painéis — a criação de contas e a inserção de chaves secretas precisa ser feita por você.

---

## Visão geral do que vamos fazer

1. Criar o banco PostgreSQL no **Neon** e pegar a string de conexão.
2. Criar o Web Service no **Render** apontando para o seu reppositório do GitHub.
3. Configurar as variáveis de ambiente no Render.
4. Rodar as migrations e criar seu usuário admin.
5. Atualizar as integrações externas (webhook da Abacate Pay + login Google).

---

## Passo 1 — Banco de dados no Neon

1. Acesse [neon.tech](https://neon.tech) e crie uma conta (pode entrar com o GitHub).
2. Clique em **Create Project**. Dê um nome (ex: `wageup`) e escolha a região mais próxima (ex: `AWS São Paulo` ou `US East`).
3. Assim que o projeto for criado, o Neon mostra a **Connection String**. Copie a versão que começa com `postgresql://...` (marque a opção "Pooled connection" se aparecer — é melhor para web apps).
   - Vai ter esta cara: `postgresql://usuario:senha@ep-xxx.aws.neon.tech/wageup?sslmode=require`
4. **Guarde essa string** — ela será a variável `DATABASE_URL` no Render.

> O plano free do Neon **não expira** e inclui backups automáticos (point-in-time recovery). É o motivo de usarmos ele em vez do Postgres do próprio Render, que é apagado após 30 dias.

---

## Passo 2 — Aplicação no Render

1. Acesse [render.com](https://render.com) e crie uma conta (entre com o GitHub para já autorizar o acesso aos repositórios).
2. No dashboard, clique em **New +** → **Web Service**.
3. Conecte e selecione o repositório do **WageUp**.
4. Preencha a configuração:

   | Campo | Valor |
   |---|---|
   | **Name** | `wageup` (vira parte da URL: `wageup.onrender.com`) |
   | **Region** | a mesma/ mais próxima do Neon |
   | **Branch** | `main` |
   | **Runtime** | `Python 3` |
   | **Build Command** | `pip install -r requirements.txt && python backend/manage.py collectstatic --noinput` |
   | **Start Command** | `gunicorn config.wsgi:application --chdir backend --bind 0.0.0.0:$PORT` |
   | **Instance Type** | `Free` |

5. Ainda **não** clique em "Create" — primeiro configure as variáveis de ambiente (próximo passo). Se já tiver criado, tudo bem, é só adicionar depois em **Environment**.

---

## Passo 3 — Variáveis de ambiente no Render

Na aba **Environment** do serviço, adicione (botão "Add Environment Variable"):

| Variável | Valor |
|---|---|
| `DATABASE_URL` | a connection string do Neon (Passo 1) |
| `SECRET_KEY` | um valor secreto aleatório e longo — **ver como gerar abaixo** |
| `DJANGO_DEBUG` | `False` |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,testserver` (o domínio `.onrender.com` é adicionado automaticamente pelo código) |
| `ABACATE_PAY_API_KEY` | sua chave da Abacate Pay |
| `ABACATE_PAY_WEBHOOK_SECRET` | invente um segredo forte (será usado no Passo 5) |
| `WAGEUP_ADMIN_EMAILS` | `guilherme.maiellaroo@gmail.com,discordguigo@gmail.com` |
| `ANTHROPIC_API_KEY` | sua chave da Anthropic (campanhas de marketing e insights) |
| `DEEPSEEK_API_KEY` | sua chave da DeepSeek (assistente financeiro; sem ela o assistente cai na Anthropic) |
| `GOOGLE_CLIENT_ID` | seu Client ID do Google (só se for usar login Google) |

Opcionais, com valores padrão razoáveis no código: `LOG_LEVEL`, `THROTTLE_ANON`,
`THROTTLE_USER`, `THROTTLE_AI`, `THROTTLE_LOGIN`, `SECURE_HSTS_SECONDS`,
`SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD`, `CUSTOM_DOMAIN`. A lista
completa e comentada está em [`.env.example`](.env.example).

> **Duas variáveis são obrigatórias com `DJANGO_DEBUG=False`:**
> - Sem uma `SECRET_KEY` própria, a aplicação **se recusa a subir** (o deploy falha com uma mensagem explicando o que fazer). É proposital: uma chave conhecida permite forjar sessões.
> - Sem `ABACATE_PAY_WEBHOOK_SECRET`, o webhook responde `503` e nenhuma cobrança é confirmada automaticamente. Também é proposital: sem segredo, qualquer um poderia postar um evento e marcar uma cobrança como paga.

**Como gerar o SECRET_KEY** (rode local, no terminal do projeto):
```bash
.venv\Scripts\python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```
Copie a saída e cole como valor de `SECRET_KEY`. **Nunca** use `change-me` em produção.

> ⚠️ As chaves reais (`ABACATE_PAY_API_KEY`, `ANTHROPIC_API_KEY`) que estão no seu `.env` local: coloque-as **só** no painel do Render, nunca commitadas no Git.

---

## Passo 4 — Migrations e usuário admin

O `render.yaml` (já incluído no repo) roda `migrate` automaticamente a cada deploy via **Pre-Deploy Command**. Se você configurou o serviço manualmente pela interface, confirme que o campo **Pre-Deploy Command** está preenchido com:

```
python backend/manage.py migrate --noinput
```

Depois do primeiro deploy bem-sucedido, crie seu usuário admin. No painel do Render, abra a aba **Shell** do serviço e rode:

```bash
python backend/manage.py createsuperuser
```

Informe e-mail `guilherme.maiellaroo@gmail.com` e uma senha. Como esse e-mail está em `WAGEUP_ADMIN_EMAILS`, ele terá acesso ao módulo financeiro/PIX automaticamente.

> O banco do Neon começa **vazio** — os produtos/cobranças que você tem no SQLite local **não** são migrados automaticamente. Para o TCC isso costuma ser irrelevante (dados de teste), mas se quiser levar os dados, dá para exportar/importar com `dumpdata`/`loaddata` — me peça que eu monto esse passo.

---

## Passo 5 — Atualizar integrações externas

O domínio mudou de `*.railway.app` para `*.onrender.com`. Duas integrações apontam para o domínio antigo e **precisam ser atualizadas**:

### 5.1 — Webhook da Abacate Pay
1. Acesse o painel da Abacate Pay → configurações de webhook.
2. Atualize a URL para: `https://wageup.onrender.com/api/payments/webhooks/abacatepay/?webhookSecret=SEU_SEGREDO`
   - `SEU_SEGREDO` = o mesmo valor que você pôs em `ABACATE_PAY_WEBHOOK_SECRET` no Passo 3.

### 5.2 — Login com Google (se usar)
1. Acesse [console.cloud.google.com](https://console.cloud.google.com) → APIs & Services → Credentials.
2. Abra o seu OAuth Client ID.
3. Em **Authorized JavaScript origins**, adicione: `https://wageup.onrender.com`
4. Salve. (Sem isso, o botão do Google falha silenciosamente.)

---

## Pronto! Checklist final

- [ ] Banco criado no Neon, `DATABASE_URL` copiada
- [ ] Web Service criado no Render com build/start commands corretos
- [ ] Todas as env vars configuradas (com `DJANGO_DEBUG=False` e `SECRET_KEY` real)
- [ ] Deploy concluído sem erro (ver aba "Logs" do Render)
- [ ] `createsuperuser` rodado, login funciona em `https://wageup.onrender.com`
- [ ] Módulo financeiro/PIX acessível (confirma que o e-mail é admin)
- [ ] Webhook da Abacate Pay atualizado
- [ ] Origin do Google atualizado (se usar login Google)
- [ ] `python backend/manage.py check --deploy` roda sem avisos (aba **Shell** do Render)

---

## Ajustes já feitos no código (você não precisa fazer nada)

- **`backend/config/settings.py`**: passou a reconhecer o domínio automático do Render (`RENDER_EXTERNAL_HOSTNAME`), além do Railway — adiciona ao `ALLOWED_HOSTS`, CORS e CSRF automaticamente.
- **`frontend/app.js`**: a URL da API deixou de ser `http://localhost:8000` fixo e passou a ser relativa (`/api`), funcionando em qualquer domínio já que o Django serve o próprio frontend.
- **`render.yaml`**: blueprint do Render com build/start/pre-deploy commands já preenchidos (opcional — o Render pode importar isso automaticamente).

## Notas importantes

- **Segurança em produção:** com `DJANGO_DEBUG=False` o código liga sozinho o redirect para HTTPS, o HSTS, os cookies `Secure` e desliga a API navegável do DRF. O HSTS fica gravado no navegador por um ano e **não dá para cancelar antes disso** — se estiver estreando um domínio próprio e ainda em teste, defina `SECURE_HSTS_SECONDS=3600` no início e suba o valor depois. Os detalhes estão na seção "Segurança" do [`CLAUDE.md`](CLAUDE.md).
- **Limite de requisições:** as rotas de IA aceitam 60 chamadas por hora por usuário e as de login 10 por minuto. Se durante a apresentação isso apertar, ajuste `THROTTLE_AI` / `THROTTLE_LOGIN` no painel do Render — a mudança vale no próximo deploy.
- **Hibernação (plano free):** após ~15 min sem acesso, o serviço no Render "dorme" e o próximo acesso demora ~50s para acordar. Para a apresentação do TCC, abra o site alguns minutos antes. Se quiser eliminar isso, o plano pago é US$ 7/mês.
- **Segurança:** com `DJANGO_DEBUG=False`, o Django para de mostrar páginas de erro detalhadas ao público — obrigatório em produção.
