# Wage Up

Plataforma para microempreendedores com frontend web, API Django e base preparada para pagamentos, marketing com IA e processamento assíncrono.

## Estrutura

```txt
backend/     API Django + Django REST Framework
frontend/    interface atual em HTML, CSS e JavaScript
```

## Rodando localmente

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python backend\manage.py migrate
.\.venv\Scripts\python backend\manage.py runserver
```

Acesse:

```txt
http://localhost:8000/
http://localhost:8000/api/health/
http://localhost:8000/api/products/
http://localhost:8000/api/transactions/
```

## PostgreSQL e Redis

Para subir os serviços locais:

```powershell
docker compose up -d
```

Depois use o `DATABASE_URL` do `.env.example` e rode as migrations novamente.

## Deploy no Railway

A configuração inicial de deploy está em:

```txt
Procfile
railway.json
requirements.txt
```

Arquitetura recomendada no Railway:

```txt
Service: wageup-web
  Django + DRF + frontend estático

Service: postgres
  Banco principal

Service: redis
  Cache/fila para Celery no próximo passo

Service futuro: wageup-worker
  Celery worker para imagens, webhooks pesados e tarefas assíncronas
```

Variáveis importantes no serviço web:

```txt
SECRET_KEY=
DJANGO_DEBUG=False
ALLOWED_HOSTS=seu-dominio.up.railway.app,seu-dominio.com
CSRF_TRUSTED_ORIGINS=https://seu-dominio.up.railway.app,https://seu-dominio.com
CORS_ALLOWED_ORIGINS=https://seu-dominio.up.railway.app,https://seu-dominio.com
DATABASE_URL=${{Postgres.DATABASE_URL}}
ABACATE_PAY_API_KEY=
ABACATE_PAY_WEBHOOK_SECRET=
```

Fluxo sugerido:

1. Crie um projeto no Railway.
2. Conecte o repositório pelo GitHub.
3. Adicione um serviço PostgreSQL.
4. Configure as variáveis do serviço web.
5. Faça o deploy.
6. Configure o domínio público como URL de webhook no painel da Abacate Pay.

## Próximas integrações

- `payments`: criar cobrança na Abacate Pay, salvar `Payment` e processar webhooks com idempotência.
- `marketing`: mover geração de imagens/textos para fila com Redis + Celery.
- `accounts/businesses`: autenticação e isolamento de dados por microempreendedor.
