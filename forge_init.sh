#!/bin/bash
# forge_init.sh — Инициализация перед созданием лендинга
# Использование: ./forge_init.sh [dark-gold|cyber|glass|motion]

THEME=${1:-"dark-gold"}
CLUSTER="/home/v2helper/design_cluster"

echo "========================================"
echo "  DESIGN FORGE INIT — тема: $THEME"
echo "========================================"

# ШАГ 1: Контекст design_cluster
echo ""
echo "📦 CLAUDE_BRAIN — ключевые переменные:"
python3 -c "
import json
brain = json.load(open('$CLUSTER/CLAUDE_BRAIN.json'))
# Вывести самое важное
keys = list(brain.keys())[:8]
for k in keys:
    v = brain[k]
    if isinstance(v, str) and len(v) < 120:
        print(f'  {k}: {v}')
    elif isinstance(v, dict):
        print(f'  {k}: {list(v.keys())}')
" 2>/dev/null || echo "  (CLAUDE_BRAIN.json не найден)"

# ШАГ 2: Доступные demo-файлы
echo ""
echo "🎨 Доступные визуальные референсы:"
for f in "$CLUSTER"/demo-*.html; do
    name=$(basename "$f")
    size=$(du -k "$f" | cut -f1)
    echo "  ${size}KB — $name"
done

# ШАГ 3: Доступные sci-fi модули
echo ""
echo "✨ Sci-Fi CSS модули (design_cluster):"
for f in "$CLUSTER/templates/scifi_modules"/*.css; do
    echo "  $(basename $f)"
done

# ШАГ 4: Чеклист перед стартом
echo ""
echo "========================================"
echo "  ЧЕКЛИСТ ПЕРЕД СОЗДАНИЕМ ЛЕНДИНГА"
echo "========================================"
echo "  [ ] Определил тему: $THEME"
echo "  [ ] Открыл нужный demo-*.html как референс"
echo "  [ ] Иконки — только inline SVG (не emoji)"
echo "  [ ] Анимации — только CSS keyframes (не SMIL)"
echo "  [ ] html/body overflow-x: hidden запланирован"
echo "  [ ] Каждая карточка имеет SVG + glow"
echo "  [ ] Кнопки с shimmer или pulse"
echo "  [ ] Проверю на 375px после генерации"
echo ""

# ШАГ 5: Выбор CSS файлов для темы
echo "📋 CSS из design_cluster для темы '$THEME':"
case "$THEME" in
  "dark-gold")
    echo "  Цвета: --gold:#D4860A, --gold2:#FF6B35, --bg:#080810"
    echo "  Эффекты: shimmer, pulse-glow, float"
    ;;
  "cyber")
    echo "  Файл: $CLUSTER/templates/scifi_modules/neuro_ui.css"
    echo "  Цвета: --cyan:#00D4FF, --neon-pink:#FF94E8"
    echo "  Эффекты: glitch, chromatic-shift, pulse-glow"
    ;;
  "glass")
    echo "  Файл: $CLUSTER/templates/glass_utilities.css"
    echo "  Классы: .glass, .glass-md, .glass-strong, .neon-cyan"
    echo "  Референс: demo-glass-world.html, demo-mobile-glass.html"
    ;;
  "motion")
    echo "  Файл: $CLUSTER/styles/scifi_animations.css"
    echo "  Референс: demo-motion-universe.html"
    echo "  Эффекты: ethereal-fade, orbital, particle-float"
    ;;
esac

echo ""
echo "✅ Готово. Можно начинать создание лендинга."
echo "   Спецификация: /home/v2helper/design_forge/LANDING_SPEC.md"
echo ""
