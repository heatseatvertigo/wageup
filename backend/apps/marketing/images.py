"""Geracao da imagem da campanha.

Ultimo item do escopo do TCC. A Anthropic nao gera imagem — le imagem, nao
produz — entao este e o unico ponto do projeto que fala com outro provedor de
IA para isso.

Ordem de tentativa, igual ao resto do projeto: provedor bom quando ha chave,
provedor sem chave depois, nada quando nenhum responde. Campanha sem imagem
continua sendo campanha; a geracao nunca derruba o texto que ja saiu.

1. Cloudflare Workers AI (CF_ACCOUNT_ID + CF_API_TOKEN). Plano free da
   Cloudflare da 10.000 Neurons por dia; o FLUX.1-schnell gasta ~4,8 Neurons
   por ladrilho de 512x512, o que da algo perto de 500 imagens por dia.
2. Pollinations.ai, sem chave nenhuma, quando MARKETING_IMAGE_FALLBACK esta
   ligado. E opt-in porque nao pede chave: ligado por padrao, toda campanha
   esperaria por ele e sairia com marca d'agua. Em troca de nao exigir conta:
   mais ou menos uma imagem a cada 15 segundos, e a marca d'agua.

Sem Cloudflare configurada e sem esse fallback ligado, a campanha sai sem
imagem. E o mesmo principio das chaves de IA do projeto: falta de
configuracao tira a funcionalidade, nao quebra a tela.

O prompt nao e inventado aqui. A campanha ja pede a IA de texto uma "Ideia de
imagem"; esse trecho descreve o que o dono do negocio quer ver e vira o prompt
da imagem. Sem ele, monta-se um prompt do nome do produto e do canal.
"""
import base64
import binascii
import logging
import re
from urllib.parse import quote

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Os dois provedores devolvem os bytes da imagem direto no corpo da resposta.
CLOUDFLARE_MODEL = "@cf/black-forest-labs/flux-1-schnell"
POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"

# O FLUX.1-schnell na Cloudflare nao aceita largura e altura: sai sempre
# 1024x1024, que e o quadrado do feed do Instagram e do WhatsApp sem corte.
# Os dois parametros ficam so para o Pollinations, que aceita.
LARGURA = ALTURA = 1024

TIMEOUT = 45

# Maior que o teto da foto de produto (400 KB) de proposito: a foto chega
# reduzida pelo navegador, esta aqui sai do modelo e um JPEG de 1024x1024 do
# FLUX da por volta de 540 KB. Uma imagem por campanha, entao 1 MB cabe.
MAX_BYTES = 1024 * 1024

# "Ideia de imagem" e um dos quatro blocos que o prompt da campanha pede. O
# titulo pode vir com ou sem os asteriscos do markdown.
IDEIA_DE_IMAGEM = re.compile(
    r"\*{0,2}Ideia de imagem:?\*{0,2}\s*(.+?)(?=\n\s*\*{0,2}[A-ZÀ-Ü][^\n:]{0,40}:|\Z)",
    re.IGNORECASE | re.DOTALL,
)


class ImageGenerationError(Exception):
    pass


def extrair_prompt(texto_da_campanha, product_name, channel):
    """Tira o prompt da imagem do texto que a IA ja escreveu.

    Reaproveitar a "Ideia de imagem" mantem o texto e a imagem falando da
    mesma coisa. Gerar um prompt separado produziria uma imagem que nao
    combina com a legenda.
    """
    achado = IDEIA_DE_IMAGEM.search(texto_da_campanha or "")
    if achado:
        ideia = " ".join(achado.group(1).split()).strip(" .")
        if ideia:
            return ideia

    return f"foto publicitaria de {product_name}, produto em destaque, para {channel}"


def _traduzir_para_o_modelo(prompt):
    """Os modelos de imagem entendem ingles muito melhor que portugues.

    Nao ha traducao aqui: o que se faz e acrescentar o enquadramento em ingles
    ao redor da ideia em portugues, que e o suficiente para o modelo entender
    o tipo de foto esperado.
    """
    return (
        f"product photography, {prompt}, natural light, clean background, "
        f"commercial quality, sharp focus, "
        # O modelo desenha letra embolada quando tenta escrever. O prompt da
        # campanha ja evita pedir texto; isto e a segunda barreira.
        f"no text, no lettering, no logo, no packaging labels, no watermark"
    )


def _cloudflare(prompt):
    account = (settings.CLOUDFLARE_ACCOUNT_ID or "").strip()
    token = (settings.CLOUDFLARE_API_TOKEN or "").strip()
    if not (account and token):
        return None

    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{CLOUDFLARE_MODEL}"
    resposta = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        # So `prompt`: o modelo recusa a requisicao inteira com 400 se receber
        # largura e altura ("Additional or unevaluated properties").
        json={"prompt": prompt},
        timeout=TIMEOUT,
    )
    if not resposta.ok:
        raise ImageGenerationError(
            f"Cloudflare recusou a geracao ({resposta.status_code}): {resposta.text[:200]}"
        )

    # A resposta e JSON, nao os bytes: {"result": {"image": "<base64>"},
    # "success": true}. Cota estourada ou token sem permissao tambem volta em
    # JSON, com success false, entao o campo e conferido antes de decodificar.
    try:
        corpo = resposta.json()
    except ValueError as exc:
        raise ImageGenerationError("Cloudflare devolveu um corpo que nao e JSON.") from exc

    if not corpo.get("success"):
        raise ImageGenerationError(f"Cloudflare respondeu com erro: {corpo.get('errors')}")

    em_base64 = (corpo.get("result") or {}).get("image")
    if not em_base64:
        raise ImageGenerationError("Cloudflare respondeu sem imagem.")

    try:
        conteudo = base64.b64decode(em_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ImageGenerationError("Cloudflare devolveu um base64 invalido.") from exc

    return conteudo, "image/jpeg"


def _pollinations(prompt):
    if not settings.MARKETING_IMAGE_FALLBACK:
        return None

    # `nologo` so vale para conta paga; sem ela a imagem sai com marca d'agua.
    url = POLLINATIONS_URL.format(prompt=quote(prompt, safe=""))
    resposta = requests.get(
        url,
        params={"width": LARGURA, "height": ALTURA, "nologo": "true"},
        timeout=TIMEOUT,
    )
    if not resposta.ok:
        raise ImageGenerationError(
            f"Pollinations recusou a geracao ({resposta.status_code})."
        )

    content_type = resposta.headers.get("Content-Type", "")
    if not content_type.startswith("image/"):
        raise ImageGenerationError(f"Pollinations devolveu {content_type}.")

    return resposta.content, content_type.split(";")[0].strip()


def gerar_imagem(prompt):
    """Devolve (provider, bytes, content_type), ou None se nenhum provedor deu.

    Falha de um provedor nao interrompe: tenta o proximo. Falha de todos
    devolve None e quem chamou segue sem imagem.
    """
    prompt_final = _traduzir_para_o_modelo(prompt)

    for nome, funcao in (("cloudflare", _cloudflare), ("pollinations", _pollinations)):
        try:
            resultado = funcao(prompt_final)
        except (ImageGenerationError, requests.RequestException):
            logger.exception("Falha ao gerar a imagem da campanha em %s.", nome)
            continue

        if resultado is None:
            continue

        conteudo, content_type = resultado
        if len(conteudo) > MAX_BYTES:
            logger.warning(
                "Imagem de %s tem %d bytes, acima do limite de %d. Descartada.",
                nome, len(conteudo), MAX_BYTES,
            )
            continue

        return nome, conteudo, content_type

    return None
