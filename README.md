# Wage Up

Plataforma para microempreendedores com frontend web, API Django e base preparada para pagamentos, marketing com IA e processamento assíncrono.

## Estrutura

```txt
backend/     API Django + Django REST Framework
frontend/    interface atual em HTML, CSS e JavaScript
```

## Requisitos

- **Python 3.12 ou superior** (o projeto usa Django 6, que não roda em versões anteriores).

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

> O `DJANGO_DEBUG` tem padrão `False` no código — é o modo seguro para quem sobe
> sem configurar nada. O `.env.example` liga `DJANGO_DEBUG=True`, então copiar o
> arquivo (passo acima) já deixa o ambiente de desenvolvimento correto.

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

Antes de publicar, rode a verificação de segurança do Django. Ela precisa de uma
`SECRET_KEY` real: com `DJANGO_DEBUG=False` o projeto se recusa a subir com a
chave de exemplo.

```powershell
$env:DJANGO_DEBUG="False"
$env:SECRET_KEY=(.\.venv\Scripts\python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
.\.venv\Scripts\python backend\manage.py check --deploy
```

## Documentação

| Arquivo | Conteúdo |
|---|---|
| [`FEATURES.md`](FEATURES.md) | O que a plataforma faz hoje, em linguagem de produto |
| [`DOCUMENTACAO-TCC.md`](DOCUMENTACAO-TCC.md) | Documentação completa para o artigo do TCC (arquitetura, IA, PIX, segurança, decisões) |
| [`CLAUDE.md`](CLAUDE.md) | Arquitetura, variáveis de ambiente, endpoints e regras de segurança |
| [`design-system.md`](design-system.md) | Cores, tipografia e componentes do frontend |
| [`DEPLOY-RENDER.md`](DEPLOY-RENDER.md) | Passo a passo do deploy no Render + Neon |
| [`.env.example`](.env.example) | Todas as variáveis de ambiente, comentadas |
