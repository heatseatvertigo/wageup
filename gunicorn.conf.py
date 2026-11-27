"""Configuracao do gunicorn em producao (Render).

O gunicorn le este arquivo sozinho quando sobe a partir da raiz do projeto,
entao vale tanto para o startCommand do render.yaml quanto para um comando
digitado no painel do Render.

Por que nao o padrao (1 processo sincrono): ele atende uma requisicao por vez.
Enquanto os insights esperavam a IA responder (alguns segundos), login, sair,
os arquivos do site e ate o health check ficavam na fila. Com threads, quem
espera rede (IA, Abacate Pay, banco) libera o processo para os outros.

Memoria: o plano free do Render tem 512 MB. Dois processos do Django cabem com
folga; mais que isso arrisca o servidor ser reiniciado por falta de memoria.
Os limites por requisicao (throttling) vivem no cache de cada processo, entao
o limite efetivo dobra com dois processos (ver CLAUDE.md, secao Seguranca).
"""
import os

workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
worker_class = "gthread"
threads = int(os.environ.get("GUNICORN_THREADS", "8"))
# A IA e a geracao de imagem podem passar de 30 s (o padrao do gunicorn).
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
graceful_timeout = 30
keepalive = 5
# Log de acesso no stdout, que o Render mostra no painel.
accesslog = "-"
