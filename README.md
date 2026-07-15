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

## PostgreSQL local (opcional)

Para desenvolvimento local o projeto usa SQLite por padrão. Se quiser espelhar o
PostgreSQL de produção, suba o serviço via Docker:

```powershell
docker compose up -d
```

Depois aponte o `DATABASE_URL` para o Postgres local e rode as migrations novamente.

## Deploy no Render + Neon

O deploy roda no **Render** (aplicação) com PostgreSQL no **Neon**. A configuração
está em [`render.yaml`](render.yaml) e o passo a passo completo em
[`DEPLOY-RENDER.md`](DEPLOY-RENDER.md).

Produção atual: <https://wageup.onrender.com>
