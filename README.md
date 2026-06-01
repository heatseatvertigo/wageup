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

## Próximas integrações

- `payments`: criar cobrança na Abacate Pay, salvar `Payment` e processar webhooks com idempotência.
- `marketing`: mover geração de imagens/textos para fila com Redis + Celery.
- `accounts/businesses`: autenticação e isolamento de dados por microempreendedor.
