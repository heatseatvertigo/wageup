"""IA de marketing em formato de conversa.

Antes a tela era um formulario — produto, objetivo, canal e uma frase — e a IA
sempre devolvia os mesmos quatro blocos. Agora o usuario escreve o que quiser:
"cria um post do bolo para o Instagram", "me da cinco ideias de reels",
"reescreve essa legenda mais curta". A conversa segue o desenho do assistente
financeiro (apps/finance/assistant.py): historico no banco, contexto do negocio
montado aqui, e resposta local quando nao ha chave.

O que nao mudou: os numeros do catalogo saem do `Product` — `margin_value`,
nao preco menos custo — e vao prontos para o modelo. A IA recebe o catalogo e
escolhe o produto pelo nome que o usuario usou; nunca recebe numero do cliente.
"""
import logging
import re
import unicodedata

import anthropic as anthropic_sdk
from django.conf import settings

from apps.finance.assistant import _call_deepseek
from apps.finance.insights import brl
from apps.products.models import Product
from .images import IDEIA_DE_IMAGEM

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"
MAX_HISTORY = 12          # mensagens da conversa enviadas ao modelo
MAX_MESSAGE_CHARS = 2000  # tamanho maximo de cada mensagem do usuario
MAX_PRODUTOS = 20         # produtos do catalogo que entram no contexto

CANAIS = {
    "instagram": "Instagram",
    "whatsapp": "WhatsApp",
    "tiktok": "TikTok",
    "facebook": "Facebook",
}

SYSTEM_PROMPT = (
    "Você é a IA de marketing do WageUp. Ajuda donos de negócios pequenos — "
    "confeiteiras, barbeiros, quem vende marmita, quem faz unha — a divulgar o "
    "que vendem. O usuário escreve livremente: pode pedir uma campanha, um post, "
    "uma legenda, ideias de conteúdo, hashtags, um roteiro de vídeo, uma "
    "mensagem para clientes, ou ajustar algo que você já escreveu.\n\n"
    "COMO RESPONDER:\n"
    "- Faça exatamente o que foi pedido. Pergunta curta, resposta curta.\n"
    "- Linguagem informal, direta, focada em vender. Nada de jargão "
    "corporativo nem introduções como 'Ótima ideia!'.\n"
    "- Adapte o tom ao canal (Instagram, WhatsApp, TikTok...). Se o canal não "
    "foi dito, escolha o que fizer mais sentido e diga qual.\n"
    "- Use **negrito** só para os títulos das seções. Nada de títulos com #.\n\n"
    "QUANDO O PEDIDO FOR UMA CAMPANHA OU UM POST PRONTO, use esta estrutura:\n"
    "**Chamada principal:** headline curta e impactante\n"
    "**Ideia de imagem:** descreva só a cena — o produto, o cenário e a luz. "
    "Nada de texto, logo, selo ou embalagem escrita: quem gera a imagem desenha "
    "letra embolada e estraga a foto.\n"
    "**Legenda:** texto para postar, com emojis se fizer sentido\n"
    "**CTA:** chamada para ação direta\n"
    "Para qualquer outro pedido, NÃO escreva a seção 'Ideia de imagem': ela é "
    "o que dispara a geração de uma imagem.\n\n"
    "REGRAS QUE NÃO SE QUEBRAM:\n"
    "- Use apenas os produtos e números do catálogo abaixo. Nunca invente "
    "preço, produto ou promoção que o negócio não informou.\n"
    "- A margem do catálogo já desconta custo, embalagem, frete, taxa de "
    "cartão/PIX e imposto. Se sugerir desconto, ele tem que caber nela: um "
    "desconto maior faz o negócio vender no prejuízo.\n"
    "- Produto com margem negativa não se divulga: diga que o preço precisa "
    "ser revisto antes.\n"
    "- Responda sempre em português brasileiro.\n"
)


def _sem_acento(texto):
    normalizado = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in normalizado if not unicodedata.combining(c)).lower()


def catalogo(business):
    """Produtos ativos, da melhor para a pior margem real."""
    ativos = [p for p in Product.objects.filter(business=business) if p.is_active]
    return sorted(ativos, key=lambda p: p.margin_value, reverse=True)


def format_context(business, produtos):
    linhas = [f"NEGÓCIO: {business.name or 'microempreendedor'}", ""]
    if not produtos:
        linhas.append(
            "CATÁLOGO: nenhum produto cadastrado. Se o usuário pedir campanha de "
            "um produto, escreva sem inventar preço e sugira cadastrar o produto "
            "na tela Produtos para a próxima campanha usar os números reais."
        )
        return "\n".join(linhas)

    linhas.append("CATÁLOGO (da melhor para a pior margem real):")
    for p in produtos[:MAX_PRODUTOS]:
        marcas = []
        if p.is_low_stock:
            marcas.append("estoque baixo")
        if p.margin_value < 0:
            marcas.append("PREJUÍZO por unidade")
        sufixo = f" [{', '.join(marcas)}]" if marcas else ""
        descricao = f" — {p.description.strip()[:160]}" if p.description.strip() else ""
        linhas.append(
            f"- {p.name}: preço {brl(p.price)}, margem real {brl(p.margin_value)} "
            f"({float(p.margin_percent):.0f}% do preço), estoque {p.stock}{sufixo}{descricao}"
        )
    return "\n".join(linhas)


def produto_citado(texto, produtos):
    """O produto do catalogo que o usuario citou pelo nome, se houver.

    Com dois nomes batendo ("Bolo" e "Bolo de cenoura"), vale o mais longo:
    e o mais especifico.
    """
    alvo = _sem_acento(texto)
    citados = [p for p in produtos if _sem_acento(p.name).strip() and _sem_acento(p.name) in alvo]
    return max(citados, key=lambda p: len(p.name), default=None)


def canal_citado(texto):
    alvo = _sem_acento(texto)
    for chave, nome in CANAIS.items():
        if chave in alvo or (chave == "whatsapp" and re.search(r"\bzap\b", alvo)):
            return nome
    return None


def objetivo_citado(texto):
    alvo = _sem_acento(texto)
    if re.search(r"lanc", alvo):
        return "lancamento"
    if re.search(r"relacion|fideli|agradec", alvo):
        return "relacionamento"
    if re.search(r"promo|oferta|desconto|liquida", alvo):
        return "promocao"
    return "livre"


def e_campanha(texto):
    """Resposta com "Ideia de imagem" e campanha: vira registro e ganha imagem."""
    return bool(IDEIA_DE_IMAGEM.search(texto or ""))


def sanitize_history(messages):
    clean = []
    for item in messages or []:
        role = item.get("role")
        content = str(item.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        clean.append({"role": role, "content": content[:MAX_MESSAGE_CHARS]})
    clean = clean[-MAX_HISTORY:]
    # A API da Anthropic exige que a conversa comece pelo usuario.
    while clean and clean[0]["role"] != "user":
        clean.pop(0)
    return clean


def responder(business, historico, produto=None, canal=None):
    """Devolve (provider, resposta) para a conversa.

    Falha do provedor nao vira erro: o usuario fica com a resposta local, como
    antes, em vez de ficar sem campanha por um problema de configuracao.
    """
    history = sanitize_history(historico)
    produtos = catalogo(business)

    # Mesma ordem do assistente financeiro: DeepSeek, depois Anthropic. Se o
    # primeiro falhar, tenta o segundo antes de cair na resposta local.
    provedores = []
    if settings.DEEPSEEK_API_KEY:
        provedores.append(("deepseek", _call_deepseek_marketing))
    if settings.ANTHROPIC_API_KEY:
        provedores.append(("anthropic", _call_claude))

    falhou = False
    if history and provedores:
        system_prompt = f"{SYSTEM_PROMPT}\n{format_context(business, produtos)}"
        for nome, chamar in provedores:
            try:
                return nome, chamar(system_prompt, history)
            except Exception:
                falhou = True
                logger.exception("Falha ao responder no chat de marketing com %s.", nome)

    ultimo = history[-1]["content"] if history else ""
    # Sem produto citado, o assunto vem do proprio pedido ("anuncio de
    # pudim"): ir direto ao catalogo faria a campanha falar de outra coisa. So
    # quando o pedido nao diz nada reconhecivel entra o produto de melhor
    # margem.
    assunto = (
        (produto.name if produto else None)
        or assunto_do_pedido(ultimo)
        or (produtos[0].name if produtos else None)
    )
    return "local-demo", resposta_local(assunto, ultimo, canal, falhou=falhou)


def _call_deepseek_marketing(system_prompt, history):
    # Temperatura maior que a do assistente financeiro: aqui se quer texto
    # criativo, nao leitura de numeros.
    return _call_deepseek(system_prompt, history, max_tokens=900, temperature=0.8)


def _call_claude(system_prompt, history):
    client = anthropic_sdk.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=MODEL,
        max_tokens=900,
        system=system_prompt,
        messages=history,
    )
    return message.content[0].text.strip()


# Onde o assunto costuma aparecer num pedido livre, do mais especifico para o
# mais solto: "divulgando o bolo", "anuncio de pudim", "post sobre brownie".
_PECAS = r"(?:an[uú]ncio|post|postagem|campanha|foto|propaganda|legenda|v[ií]deo|reels?|lan[cç]amento|promo[cç][aã]o|oferta)"
_PADROES_DE_ASSUNTO = [
    r"\b(?:divulgando|divulgar|promovendo|promover|anunciando|anunciar|vender|vendendo|oferecendo|oferecer|lan[cç]ando|lan[cç]ar)\s+(.+)",
    r"\b" + _PECAS + r"\s+(?:de|do|da|dos|das|sobre|pro|pra|para o|para a)\s+(.+)",
    r"\bsobre\s+(.+)",
]
# O que sobra na frente do assunto e nao e assunto: artigo, possessivo e o
# proprio tipo de peca ("meu novo anuncio de pudim" -> "pudim").
_PREFIXOS = (
    r"^(?:(?:o|a|os|as|meu|minha|meus|minhas|nosso|nossa|um|uma|novo|nova)\s+"
    r"|" + _PECAS + r"\s+(?:de|do|da|dos|das)\s+)"
)
_CORTES = r"\s+(?:para|pra|pro|no|na|nos|nas|com|em|que|e)\s+|[,.;:!?]"


def assunto_do_pedido(pedido):
    """O que o usuario quer divulgar, tirado do texto do pedido.

    Heuristica simples, usada so na resposta local — com a IA ligada, quem le
    o pedido e o modelo. Sem nada reconhecivel, devolve None.
    """
    texto = " ".join(str(pedido or "").split())
    for padrao in _PADROES_DE_ASSUNTO:
        achado = re.search(padrao, texto, re.IGNORECASE)
        if not achado:
            continue
        trecho = re.split(_CORTES, achado.group(1), maxsplit=1, flags=re.IGNORECASE)[0]
        while True:
            sem_artigo = re.sub(_PREFIXOS, "", trecho, flags=re.IGNORECASE)
            if sem_artigo == trecho:
                break
            trecho = sem_artigo
        palavras = trecho.split()[:5]
        if palavras and canal_citado(" ".join(palavras)) is None:
            return " ".join(palavras)
    return None


def resposta_local(assunto, pedido, canal=None, falhou=False):
    """Sem IA: uma campanha montada por regra.

    Nao finge ter entendido o pedido livre — so a IA entende —, mas fala do
    que foi pedido. A margem fica fora da legenda: e numero do dono, nao do
    cliente.
    """
    canal = canal or "Instagram"
    nome = assunto or "seu produto"
    objetivo = objetivo_citado(pedido)
    headlines = {
        "lancamento": f"Chegou {nome}: feito para encantar no primeiro pedido",
        "relacionamento": f"Seu dia fica melhor com {nome}",
    }
    headline = headlines.get(objetivo, f"{nome} com oferta especial por tempo limitado")
    headline = headline[:1].upper() + headline[1:]
    # Os dois casos tem solucao diferente, entao a mensagem tambem: um e
    # configuracao que falta, o outro e chave ou provedor com problema.
    if falhou:
        aviso = (
            "(Resposta automática: a IA de marketing não respondeu agora — "
            "confira a chave da DeepSeek e o log do servidor. Tente de novo em instantes.)"
        )
    else:
        aviso = (
            "(Resposta automática: a IA de marketing não está configurada neste "
            "ambiente — falta a DEEPSEEK_API_KEY —, então o pedido não foi lido por inteiro.)"
        )
    return (
        f"Campanha para {canal}\n\n"
        f"**Chamada principal:** {headline}\n\n"
        f"**Ideia de imagem:** foto clara de {nome} sobre uma mesa, "
        f"luz natural, produto em destaque.\n\n"
        f"**Legenda:** Hoje é um bom dia para garantir {nome}. Feito com carinho, entrega rápida.\n\n"
        f"**CTA:** Chame no direct ou finalize pelo PIX.\n\n"
        f"{aviso}"
    )
