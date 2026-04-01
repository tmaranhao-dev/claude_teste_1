"""Use Claude API to curate and summarize the final digest stories."""

import json
import logging
from dataclasses import dataclass

import anthropic

from src.config import Settings
from src.fetcher import RawArticle

logger = logging.getLogger(__name__)


@dataclass
class StoryAnalysis:
    title: str
    source: str
    date: str
    link: str
    what_happened: str
    why_it_matters: str
    brazilian_angle: str
    content_angle: str
    focus_area: str


@dataclass
class DigestResult:
    date: str
    stories: list[StoryAnalysis]
    editorial_note: str


SYSTEM_PROMPT_PTBR = """\
Você é um editor-chefe sênior de um boletim diário para profissionais brasileiros \
de comunicação, mídia, conteúdo e criatividade. Seu tom é direto, opinativo e \
analítico — como um editor veterano conversando com colegas de profissão. \
Sem floreios, sem linguagem corporativa vazia, sem voz passiva desnecessária.

Seu público são profissionais criativos no Brasil com visão global: publicitários, \
jornalistas, produtores audiovisuais, criadores de conteúdo, profissionais de \
comunicação corporativa e RP."""

SYSTEM_PROMPT_EN = """\
You are a senior editor-in-chief of a daily digest for Brazilian professionals \
in communication, media, content, and creativity. Your tone is direct, opinionated, \
and analytical — like a veteran editor talking to peers. No fluff, no corporate \
language, no unnecessary passive voice.

Your audience is creative professionals in Brazil with a global outlook: advertisers, \
journalists, audiovisual producers, content creators, corporate communication and PR \
professionals."""


def _build_user_prompt(
    candidates: list[RawArticle], settings: Settings, language: str
) -> str:
    """Build the user prompt with candidate articles and instructions."""
    # Serialize candidates
    articles_text = ""
    for i, article in enumerate(candidates, 1):
        pub_str = (
            article.published.strftime("%Y-%m-%d")
            if article.published
            else "data desconhecida"
        )
        articles_text += (
            f"\n--- Artigo {i} ---\n"
            f"Título: {article.title}\n"
            f"Fonte: {article.source_name} ({article.source_region})\n"
            f"Data: {pub_str}\n"
            f"Link: {article.link}\n"
            f"Idioma: {article.language}\n"
            f"Resumo: {article.summary}\n"
        )

    focus_names = ", ".join(fa.name for fa in settings.focus_areas)

    if language == "pt-br":
        return f"""\
Aqui estão {len(candidates)} artigos candidatos coletados hoje de fontes nacionais e internacionais.

Selecione exatamente {settings.num_stories} histórias que formem o digest mais relevante \
para profissionais brasileiros de comunicação, criatividade e produção audiovisual.

REGRAS OBRIGATÓRIAS:
- Pelo menos {settings.min_brazil_stories} histórias devem ter relevância direta para o mercado brasileiro
- Cubra o máximo de áreas de foco possível: {focus_names}
- Quando cobrir uma história global, sempre adicione um ângulo brasileiro
- Escreva como editor sênior: direto, opinativo, sem linguagem corporativa
- Se a história é global mas tem impacto atrasado no Brasil, estime quando chegará

Para CADA história selecionada, retorne um objeto JSON com estes campos:
- "title": título editado da história (pode reformular para maior impacto)
- "source": nome da publicação original
- "date": data no formato YYYY-MM-DD
- "link": URL original do artigo
- "what_happened": 2-3 frases factuais e objetivas sobre o que aconteceu
- "why_it_matters": 2-3 frases analíticas e opinativas — para quem trabalha com conteúdo, comunicação ou produção audiovisual no Brasil
- "brazilian_angle": 1-2 frases sobre como isso se conecta, impacta ou já está acontecendo no mercado brasileiro
- "content_angle": 1 frase sugerindo um ângulo para transformar isso em conteúdo de newsletter, post no LinkedIn ou legenda no Instagram
- "focus_area": a área de foco principal (uma das seguintes: {focus_names})

Também inclua um campo "editorial_note" com 2-3 frases de abertura do digest, \
resumindo o tom do dia — o que dominou as notícias e por que importa.

CANDIDATOS:
{articles_text}

Responda APENAS com JSON válido neste formato exato:
{{
  "editorial_note": "...",
  "stories": [
    {{
      "title": "...",
      "source": "...",
      "date": "YYYY-MM-DD",
      "link": "...",
      "what_happened": "...",
      "why_it_matters": "...",
      "brazilian_angle": "...",
      "content_angle": "...",
      "focus_area": "..."
    }}
  ]
}}"""
    else:
        return f"""\
Here are {len(candidates)} candidate articles collected today from national and international sources.

Select exactly {settings.num_stories} stories that form the most relevant digest \
for Brazilian professionals in communication, creativity, and audiovisual production.

MANDATORY RULES:
- At least {settings.min_brazil_stories} stories must have direct relevance to the Brazilian market
- Cover as many focus areas as possible: {focus_names}
- When covering a global story, always add a Brazilian angle
- Write as a senior editor: direct, opinionated, no corporate language
- If a story is global but has delayed impact in Brazil, estimate when it will arrive

For EACH selected story, return a JSON object with these fields:
- "title": edited story title (you may rephrase for greater impact)
- "source": original publication name
- "date": date in YYYY-MM-DD format
- "link": original article URL
- "what_happened": 2-3 factual, objective sentences about what happened
- "why_it_matters": 2-3 analytical, opinionated sentences — for someone working in content, communication or audiovisual production in Brazil
- "brazilian_angle": 1-2 sentences about how this connects to, impacts, or is already happening in the Brazilian market
- "content_angle": 1 sentence suggesting an angle to turn this into newsletter content, a LinkedIn post, or an Instagram caption
- "focus_area": the primary focus area (one of: {focus_names})

Also include an "editorial_note" field with 2-3 opening sentences for the digest, \
summarizing the day's tone — what dominated the news and why it matters.

CANDIDATES:
{articles_text}

Respond ONLY with valid JSON in this exact format:
{{
  "editorial_note": "...",
  "stories": [
    {{
      "title": "...",
      "source": "...",
      "date": "YYYY-MM-DD",
      "link": "...",
      "what_happened": "...",
      "why_it_matters": "...",
      "brazilian_angle": "...",
      "content_angle": "...",
      "focus_area": "..."
    }}
  ]
}}"""


def _parse_response(raw: str) -> dict:
    """Parse JSON from Claude's response, handling markdown code blocks."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (```json and ```)
        lines = [l for l in lines[1:] if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


def generate_digest(
    candidates: list[RawArticle], settings: Settings, date_str: str
) -> DigestResult:
    """Call Claude API to generate the final digest from candidates."""
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    language = settings.language
    system_prompt = SYSTEM_PROMPT_PTBR if language == "pt-br" else SYSTEM_PROMPT_EN
    user_prompt = _build_user_prompt(candidates, settings, language)

    logger.info(
        "Sending %d candidates to Claude (%s) for digest generation",
        len(candidates), settings.claude_model,
    )

    # First attempt
    response = client.messages.create(
        model=settings.claude_model,
        max_tokens=4096,
        temperature=0.3,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = response.content[0].text

    try:
        data = _parse_response(raw_text)
    except json.JSONDecodeError as e:
        logger.warning("First JSON parse failed (%s). Retrying with fix prompt.", e)
        # Retry: ask Claude to fix the JSON
        retry_response = client.messages.create(
            model=settings.claude_model,
            max_tokens=4096,
            temperature=0.1,
            system="You fix invalid JSON. Return ONLY valid JSON, nothing else.",
            messages=[
                {"role": "user", "content": f"Fix this JSON:\n\n{raw_text}"},
            ],
        )
        raw_text = retry_response.content[0].text
        try:
            data = _parse_response(raw_text)
        except json.JSONDecodeError:
            logger.error("Failed to parse JSON after retry. Raw response saved.")
            raise RuntimeError(
                "Claude returned invalid JSON after retry. "
                "Check logs for the raw response."
            )

    # Build result
    stories = []
    for s in data.get("stories", []):
        stories.append(
            StoryAnalysis(
                title=s.get("title", ""),
                source=s.get("source", ""),
                date=s.get("date", ""),
                link=s.get("link", ""),
                what_happened=s.get("what_happened", ""),
                why_it_matters=s.get("why_it_matters", ""),
                brazilian_angle=s.get("brazilian_angle", ""),
                content_angle=s.get("content_angle", ""),
                focus_area=s.get("focus_area", ""),
            )
        )

    logger.info("Digest generated: %d stories", len(stories))

    return DigestResult(
        date=date_str,
        stories=stories,
        editorial_note=data.get("editorial_note", ""),
    )
