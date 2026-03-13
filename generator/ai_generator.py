"""
Design Forge — AI Content Generator
Calls LLM (Claude by default) to generate landing page content from product description.
"""

import os
import json
import re
import urllib.request
import urllib.error

GROQ_PROXY = "https://alex-groq-proxy.egoriy-konovalov.workers.dev"
_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"

SYSTEM_PROMPT = """You are a world-class landing page copywriter and UX strategist.
Given a product description, generate structured landing page content as JSON.

DESIGN RULES (apply to all copy decisions):
- Install command MUST be short and real (npm install / pip install / cargo install)
- Hero headline: include SPECIFIC numbers ("35 tests in 2 seconds" > "powerful tool")
- Stats: use real-looking impactful numbers (e.g. "87%", "<12ms", "10x", "100%")
- Steps: clear concrete actions, not marketing fluff (max 8 words per step title)
- color_accent: pick per product type — CLI tools: Amber #FF9F0A, AI tools: Purple #BF5AF2, Data tools: Green #30D158, APIs: Cyan #00E5FF
- color_accent2: complementary color, NOT the same as color_accent

ICON RULES (CRITICAL — NO EXCEPTIONS):
- icon field MUST be a name string, NEVER an emoji character
- Valid icon names: rocket, chart, shield, lock, search, code, gear, lightning, eye, heart, globe, star, tv, clock, check, database
- Choose the icon that best matches the feature/step semantically
- Examples: performance → lightning, security → shield, analytics → chart, speed → rocket

VISUAL QUALITY RULES (enforced by design system):
- color_accent + color_accent2 MUST have strong contrast between each other (complementary pair)
- color_accent determines the entire visual feel — choose boldly, not safely
- Stats numbers: make them visceral. "4.2ms" > "fast". "$847K saved" > "saves money". "<1KB" > "tiny"
- Tagline line 1: starts with a VERB ("Kill", "Ship", "Track", "Automate", "Never lose")
- Tagline line 2: the transformation ("the chaos away", "in one command", "every millisecond")
- features: avoid generic titles like "Easy to use", "Powerful" — use specifics ("42 providers in 1 API")
- steps: each step = one clear command/action, no vague "Configure your settings"

COPY RULES:
- Be specific, not generic. Use the product's real value proposition.
- Write as if you know the product deeply.
- Hero tagline: short, punchy, memorable (max 6 words per line)
- Return ONLY valid JSON, no markdown, no explanation.

OUTPUT SCHEMA (fill all fields):
{
  "product_name": "Short product name",
  "tagline_line1": "Punchy first line (verb + noun)",
  "tagline_line2": "Gradient second line (the benefit)",
  "subtitle": "One sentence explaining what it does and for whom (max 20 words)",
  "badge": "Category · Tech · License or similar",
  "stats": [
    {"number": "X%", "label": "Key metric"},
    {"number": "<Xms", "label": "Speed metric"},
    {"number": "100%", "label": "Quality metric"},
    {"number": "X", "label": "Scale metric"}
  ],
  "cta_primary": "Action button text (3-4 words)",
  "cta_secondary": "Secondary button text",
  "problem_title": "Section title about the problem",
  "problem_subtitle": "One sentence expanding on the problem",
  "without_title": "Bad state title (e.g. Slow · Expensive · Noisy)",
  "without_desc": "2 sentences describing the problem without this product",
  "with_title": "Good state title (e.g. Fast · Cheap · Clean)",
  "with_desc": "2 sentences describing the solution with this product",
  "how_title": "How it works section title",
  "how_subtitle": "One sentence",
  "steps": [
    {"title": "Step 1 title", "desc": "Step 1 description (1 sentence)", "icon": "rocket"},
    {"title": "Step 2 title", "desc": "Step 2 description (1 sentence)", "icon": "code"},
    {"title": "Step 3 title", "desc": "Step 3 description (1 sentence)", "icon": "gear"},
    {"title": "Step 4 title", "desc": "Step 4 description (1 sentence)", "icon": "check"}
  ],
  "investor_title": "Market opportunity title",
  "investor_subtitle": "One sentence on market size and opportunity",
  "install_title": "CTA section title",
  "install_subtitle": "One sentence encouraging action",
  "install_command": "pip install product-name or npm install etc",
  "features_title": "Section title for the features bento grid (5-7 words)",
  "features_subtitle": "One sentence expanding on features (max 15 words)",
  "features": [
    {"title": "Feature 1 title", "desc": "Short description (1 sentence)", "icon": "lightning"},
    {"title": "Feature 2 title", "desc": "Short description (1 sentence)", "icon": "shield"},
    {"title": "Feature 3 title", "desc": "Short description (1 sentence)", "icon": "chart"},
    {"title": "Feature 4 title", "desc": "Short description (1 sentence)", "icon": "search"},
    {"title": "Feature 5 title", "desc": "Short description (1 sentence)", "icon": "globe"},
    {"title": "Feature 6 title", "desc": "Short description (1 sentence)", "icon": "star"}
  ],
  "audience": "developers",
  "color_accent": "#6C63FF",
  "color_accent2": "#00D4FF",
  "ru": {
    "badge": "На русском",
    "tagline_line1": "Русский слоган (глагол + существительное)",
    "tagline_line2": "Градиентная строка (польза)",
    "subtitle": "Одно предложение — что делает и для кого (макс 20 слов)",
    "cta_primary": "Текст кнопки (2-3 слова)",
    "cta_secondary": "Текст второй кнопки",
    "problem_title": "Заголовок раздела о проблеме",
    "problem_subtitle": "Одно предложение о проблеме",
    "without_title": "Плохое состояние без продукта",
    "without_desc": "2 предложения описывающих проблему без продукта",
    "with_title": "Хорошее состояние с продуктом",
    "with_desc": "2 предложения описывающих решение с продуктом",
    "how_title": "Заголовок раздела как работает",
    "how_subtitle": "Одно предложение",
    "steps": [
      {"title": "Шаг 1", "desc": "Описание шага 1"},
      {"title": "Шаг 2", "desc": "Описание шага 2"},
      {"title": "Шаг 3", "desc": "Описание шага 3"},
      {"title": "Шаг 4", "desc": "Описание шага 4"}
    ],
    "stats": [
      {"label": "Метрика 1"},
      {"label": "Метрика 2"},
      {"label": "Метрика 3"},
      {"label": "Метрика 4"}
    ],
    "investor_title": "Заголовок о рынке",
    "investor_subtitle": "Одно предложение о размере рынка",
    "install_title": "Заголовок CTA-секции",
    "install_subtitle": "Одно предложение призыва к действию",
    "features_title": "Заголовок секции возможностей (5-7 слов)",
    "features_subtitle": "Одно предложение о возможностях (макс 15 слов)",
    "features": [
      {"title": "Функция 1", "desc": "Краткое описание (1 предложение)"},
      {"title": "Функция 2", "desc": "Краткое описание (1 предложение)"},
      {"title": "Функция 3", "desc": "Краткое описание (1 предложение)"},
      {"title": "Функция 4", "desc": "Краткое описание (1 предложение)"},
      {"title": "Функция 5", "desc": "Краткое описание (1 предложение)"},
      {"title": "Функция 6", "desc": "Краткое описание (1 предложение)"}
    ]
  }
}

IMPORTANT: Fill the "ru" object with REAL Russian translations of all fields above.
Do not leave placeholders — write actual Russian marketing copy.
"""


VALID_ICONS = {
    'rocket', 'chart', 'shield', 'lock', 'search', 'code',
    'gear', 'lightning', 'eye', 'heart', 'globe', 'star',
    'tv', 'clock', 'check', 'database'
}

EMOJI_TO_ICON = {
    '⚡': 'lightning', '🚀': 'rocket', '📊': 'chart', '🔒': 'lock',
    '🔐': 'lock', '🛡': 'shield', '🛡️': 'shield', '🔍': 'search',
    '💻': 'code', '⚙': 'gear', '⚙️': 'gear', '👁': 'eye', '❤': 'heart',
    '🌍': 'globe', '🌐': 'globe', '⭐': 'star', '📺': 'tv', '🕐': 'clock',
    '✅': 'check', '🗄': 'database', '🤖': 'gear', '📦': 'code',
    '🎯': 'check', '💡': 'lightning', '🔧': 'gear', '📈': 'chart',
}


def _fix_icon(icon: str) -> str:
    if icon in VALID_ICONS:
        return icon
    if icon in EMOJI_TO_ICON:
        return EMOJI_TO_ICON[icon]
    # Partial match
    icon_lower = icon.lower()
    for v in VALID_ICONS:
        if v in icon_lower or icon_lower in v:
            return v
    return 'rocket'


def _fix_icons(content: dict) -> dict:
    """Replace emoji/invalid icons with valid icon names."""
    for step in content.get('steps', []):
        step['icon'] = _fix_icon(step.get('icon', ''))
    for feat in content.get('features', []):
        feat['icon'] = _fix_icon(feat.get('icon', ''))
    return content


def validate_content(content: dict) -> list:
    """Returns list of issues. Empty list = valid."""
    issues = []
    required = ['product_name', 'tagline_line1', 'tagline_line2', 'subtitle',
                'color_accent', 'color_accent2', 'stats', 'steps', 'features', 'ru']
    for field in required:
        if not content.get(field):
            issues.append(f"missing_field:{field}")

    if content.get('color_accent') == content.get('color_accent2'):
        issues.append("identical_accent_colors")

    stats = content.get('stats', [])
    if len(stats) < 3:
        issues.append(f"too_few_stats:{len(stats)}")

    for step in content.get('steps', []):
        if step.get('icon', '') not in VALID_ICONS:
            issues.append(f"invalid_step_icon:{step.get('icon')}")

    for feat in content.get('features', []):
        if feat.get('icon', '') not in VALID_ICONS:
            issues.append(f"invalid_feature_icon:{feat.get('icon')}")

    tl1 = content.get('tagline_line1', '')
    if len(tl1) < 3:
        issues.append("tagline_too_short")

    ru = content.get('ru', {})
    if not ru.get('tagline_line1') or not ru.get('subtitle'):
        issues.append("incomplete_ru_translation")

    return issues


def generate_content(description: str, provider: str = "auto", api_key: str = None) -> dict:
    """Generate landing page content from product description using LLM.
    Auto mode: tries Groq → Claude → OpenAI with fallback chain.
    Validates output and auto-fixes icons. Retries once on critical failures.
    """

    if provider != "auto":
        content = _call_provider(description, provider, api_key)
        content = _fix_icons(content)
        return content

    # Auto mode: build fallback chain based on available keys
    chain = []
    if os.environ.get("GROQ_API_KEY") or api_key:
        chain.append(("groq", os.environ.get("GROQ_API_KEY") or api_key))
    if os.environ.get("ANTHROPIC_API_KEY"):
        chain.append(("claude", os.environ.get("ANTHROPIC_API_KEY")))
    if os.environ.get("OPENAI_API_KEY"):
        chain.append(("openai", os.environ.get("OPENAI_API_KEY")))

    if not chain:
        raise ValueError("No API keys found. Set GROQ_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY.")

    last_error = None
    for attempt in range(2):  # max 2 attempts total
        for prov, key in chain:
            try:
                content = _call_provider(description, prov, key)
                content = _fix_icons(content)
                issues = validate_content(content)
                # Only retry on critical issues (missing fields / bad translation)
                critical = [i for i in issues if i.startswith('missing_field') or i == 'incomplete_ru_translation']
                if critical and attempt == 0:
                    last_error = f"Validation issues: {critical}"
                    continue  # retry with next provider
                return content
            except Exception as e:
                last_error = e
                continue

    raise RuntimeError(f"All providers failed. Last error: {last_error}")


def _call_provider(description: str, provider: str, api_key: str = None) -> dict:
    """Call a specific provider."""
    if provider == "claude":
        key = api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
        if not key:
            raise ValueError("No Anthropic API key.")
        return _call_claude(description, key)
    elif provider == "groq":
        key = api_key or os.environ.get("GROQ_API_KEY")
        if not key:
            raise ValueError("No Groq API key.")
        return _call_groq(description, key)
    elif provider == "openai":
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("No OpenAI API key.")
        return _call_openai(description, key)
    else:
        raise ValueError(f"Unknown provider: {provider}. Use claude, groq, or openai.")


def _call_claude(description: str, api_key: str) -> dict:
    """Call Anthropic Claude API."""
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    body = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 2048,
        "system": SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": f"Generate landing page content for: {description}"}
        ]
    }).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    raw = data["content"][0]["text"].strip()
    # Strip markdown code blocks if present
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    return json.loads(raw)


def _call_groq(description: str, api_key: str) -> dict:
    """Call Groq API via proxy (to bypass Cloudflare restrictions)."""
    url = f"{GROQ_PROXY}/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": _UA,
        "Accept": "application/json",
        "Origin": "https://groq.com",
    }
    body = json.dumps({
        "model": "meta-llama/llama-4-maverick-17b-128e-instruct",
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Generate landing page content for: {description}"}
        ]
    }).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    return json.loads(data["choices"][0]["message"]["content"])


def _call_openai(description: str, api_key: str) -> dict:
    """Call OpenAI API."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    body = json.dumps({
        "model": "gpt-4o",
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Generate landing page content for: {description}"}
        ]
    }).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    return json.loads(data["choices"][0]["message"]["content"])


if __name__ == "__main__":
    import sys
    desc = sys.argv[1] if len(sys.argv) > 1 else "CLI tool for optimizing CSS bundle size"
    result = generate_content(desc)
    print(json.dumps(result, ensure_ascii=False, indent=2))
