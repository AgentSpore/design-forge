# 📋 DESIGN FORGE — СПЕЦИФИКАЦИЯ КАЧЕСТВА ЛЕНДИНГОВ
**Версия:** 1.0 | **Дата:** 2026-03-08

---

## ⛔ ПРОБЛЕМЫ КОТОРЫЕ ПРИВЕЛИ К ЭТОЙ СПЕЦИФИКАЦИИ

- Emoji вместо SVG-иконок → выглядит дёшево
- SMIL-анимации (`<animate>`) → не работают в iOS Safari
- Spinning conic-gradient ("винт") → выглядит как баг
- LLM генерирует шаблонный средний код → не использует design_cluster
- Нет мобильного теста до первого показа → баги с overflow-x

---

## 🔁 ОБЯЗАТЕЛЬНЫЙ РИТУАЛ ПЕРЕД СОЗДАНИЕМ ЛЮБОГО ЛЕНДИНГА

```bash
# ШАГ 1 — Загрузить оперативную память design_cluster
cat /home/v2helper/design_cluster/CLAUDE_BRAIN.json

# ШАГ 2 — Прочитать готовые компоненты
cat /home/v2helper/design_cluster/docs/QUICK_SNIPPETS.md

# ШАГ 3 — Посмотреть визуальные референсы
# Выбрать нужный стиль из demo-файлов:
# demo-glass-world.html      → glassmorphism + floating cards
# demo-motion-universe.html  → deep space + particles
# demo-cyber-grid.html       → cyber/neon + grid
# demo-mobile-glass.html     → glass оптимизирован для мобайла
# demo-mobile-cyber.html     → cyber оптимизирован для мобайла
# demo-mobile-motion.html    → motion оптимизирован для мобайла

# ШАГ 4 — Брать CSS напрямую из design_cluster
# /home/v2helper/design_cluster/templates/glass_utilities.css
# /home/v2helper/design_cluster/styles/scifi_animations.css
# /home/v2helper/design_cluster/templates/scifi_modules/*.css
```

> **КРИТИЧНО:** Не генерировать CSS с нуля через LLM. Брать готовое из design_cluster.

---

## ✅ СТАНДАРТЫ ДИЗАЙНА (ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА)

### 1. ИКОНКИ И ГРАФИКА
```
❌ ЗАПРЕЩЕНО:  🎬 ✨ 🎭 📽️ — любые emoji
✅ ОБЯЗАТЕЛЬНО: inline SVG с animation классами
```

**Минимальный анимированный SVG-объект:**
```html
<svg viewBox="0 0 52 52" width="52" height="52" fill="none">
  <circle cx="26" cy="26" r="22" stroke="rgba(212,134,10,.4)" stroke-width="2"
    style="animation:pulse-glow 2s ease-in-out infinite"/>
  <!-- остальные элементы -->
</svg>
```

### 2. АНИМАЦИИ — ТОЛЬКО CSS KEYFRAMES

```
❌ ЗАПРЕЩЕНО:  <animate attributeName="..."/> — SMIL, не работает в iOS Safari
❌ ЗАПРЕЩЕНО:  conic-gradient + rotate animation ("винт" эффект)
✅ ОБЯЗАТЕЛЬНО: @keyframes + animation: property
✅ ОБЯЗАТЕЛЬНО: CSS keyframes только, никакого SMIL
```

**Список готовых keyframes из design_cluster:**
| Анимация | CSS класс | Эффект |
|---------|-----------|--------|
| `pulse-glow` | scifi_animations.css | Пульс свечения |
| `glitch` | scifi_animations.css | Глитч-эффект |
| `chromatic-shift` | scifi_animations.css | Хроматический сдвиг |
| `ethereal-fade` | scifi_animations.css | Эфирное исчезновение |
| shimmer | встроенный | Блик слева направо |
| float | встроенный | Плавание вверх-вниз |

### 3. GLASSMORPHISM — СТАНДАРТ ИЗ DESIGN CLUSTER

```css
/* Использовать glass_utilities.css классы: */
.glass       /* blur 10px, базовый */
.glass-md    /* blur 12px, medium */
.glass-strong /* blur 16px, сильный */

/* Neon-эффекты: */
.neon-cyan   /* голубой неон */
.neon-pink   /* розовый неон */
.neon-adaptive /* авто-dimming на ярком фоне */
```

### 4. МОБАЙЛ СНАЧАЛА

```css
/* ОБЯЗАТЕЛЬНО в каждом лендинге: */
html { overflow-x: hidden; max-width: 100vw; }
body { overflow-x: hidden; max-width: 100vw; }

/* На каждой секции с горизонтальным контентом: */
.section-with-carousel { overflow: hidden; }
```

### 5. КНОПКИ

```
❌ Простой background-color без анимации
✅ Shimmer (блик): ::after + left: -100% → 160% animation
✅ Pulse (glow): box-shadow 0px → 8px → 0px
✅ Ghost кнопка: -webkit-mask gradient border (не border: 1px solid)
```

### 6. КАРТОЧКИ / БЛОКИ — НЕЛЬЗЯ БЕЗ ГРАФИКИ

```
❌ Карточка только с текстом
✅ Карточка = текст + animated SVG icon + glow orb (::after)
✅ Каждая секция: минимум 1 анимированный SVG-объект
✅ Секция features: иконка 52-72px, анимирована
```

---

## 🎨 ЦВЕТОВАЯ СИСТЕМА

### Тёмная (SovetFilm-стиль, охра):
```css
:root {
  --gold: #D4860A;
  --gold2: #FF6B35;
  --bg: #080810;
  --bg2: #0C0C1A;
  --bg3: #10101E;
  --text: rgba(255,255,255,0.92);
  --muted: rgba(255,255,255,0.42);
}
```

### Кибер/неон (из design_cluster):
```css
:root {
  --cyan: #00D4FF;
  --cyan-glow: rgba(0,212,255,0.6);
  --neon-pink: #FF94E8;
  --neon-green: #7FFF5C;
  --bg-dark: #0a0a0a;
}
```

---

## 🔧 FORGE_INIT — СКРИПТ ИНИЦИАЛИЗАЦИИ

Перед созданием лендинга запускается автоматически:

```bash
/home/v2helper/design_forge/forge_init.sh [тема: dark-gold | cyber | glass | motion]
```

Скрипт:
1. Читает `CLAUDE_BRAIN.json` → выводит краткий контекст
2. Копирует нужные CSS из `design_cluster/` в рабочую папку
3. Генерирует `base.html` с готовыми переменными и keyframes
4. Выводит чеклист для проверки перед публикацией

---

## ✅ ЧЕКЛИСТ ПЕРЕД ПУБЛИКАЦИЕЙ

```
[ ] Нет emoji нигде (grep -r "🎬\|✨\|🎭" index.html)
[ ] Все иконки — inline SVG с CSS animation
[ ] Нет SMIL (<animate>) тегов
[ ] html/body имеют overflow-x: hidden
[ ] Проверено на мобайл (320px и 375px)
[ ] Минимум 3 анимированных объекта на странице
[ ] Кнопки с shimmer или pulse эффектом
[ ] Карточки не "голые" — есть SVG или glow
```

---

## 📂 ФАЙЛОВАЯ СТРУКТУРА ШАБЛОНА

```
design_forge/templates/[название]/
├── index.html          ← Полный лендинг
├── components/
│   ├── hero.html       ← Hero секция с SVG
│   ├── features.html   ← Feature cards с иконками
│   └── stats.html      ← Stats с иконками и анимацией
└── assets/
    ├── glass.css       ← из design_cluster/templates/glass_utilities.css
    └── animations.css  ← из design_cluster/styles/scifi_animations.css
```

---

## 🚫 ANTI-PATTERNS (никогда не делать)

| Плохо | Хорошо |
|-------|--------|
| `<div>🎬 Film Archive</div>` | `<div><svg>...</svg> Film Archive</div>` |
| `animation: rotate 3s infinite` на conic-gradient | shimmer/pulse/float |
| `<animate attributeName="opacity">` | `.element { animation: agFlicker 2s infinite }` |
| Карточка только с заголовком + текстом | Карточка + 72px SVG icon + glow |
| Генерировать всё через LLM | LLM → контент. CSS → из design_cluster |
| Тестировать только на desktop | Всегда 375px mobile first |

---

*Эта спецификация обязательна для всех лендингов в Design Forge.*
*Обновлять при появлении новых паттернов или антипаттернов.*
