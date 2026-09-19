"""E-mail de recuperacao de senha.

O link aponta para a raiz do frontend com `uid` e `token` na query string,
porque o SPA e servido pelo proprio Django em `/`. O app.js le esses dois
parametros no boot e abre a tela de nova senha.

A URL base sai de `request.build_absolute_uri`, que respeita o Host validado
por ALLOWED_HOSTS. Isso faz o link funcionar em localhost e no dominio do
Render sem variavel de ambiente nova.
"""
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def build_reset_link(user, request):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    base = request.build_absolute_uri("/").rstrip("/")
    return f"{base}/?uid={uid}&token={token}"


def send_password_reset_email(user, request):
    link = build_reset_link(user, request)
    horas = max(1, settings.PASSWORD_RESET_TIMEOUT // 3600)
    nome = user.first_name or user.email

    assunto = "Recuperacao de senha - WageUp"
    corpo = f"""Ola, {nome}.

Recebemos um pedido para redefinir a senha da sua conta na WageUp.
Abra o endereco abaixo para escolher uma senha nova:

{link}

O link vale por {horas} hora(s) e deixa de funcionar assim que a senha for
trocada. Se voce nao pediu isso, ignore este e-mail: nada muda na sua conta.

Se voce costuma entrar com o Google, pode continuar entrando por la. Definir
uma senha apenas acrescenta uma segunda forma de acesso.

-- 
WageUp
"""
    send_mail(
        assunto,
        corpo,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
