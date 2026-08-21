#!/usr/bin/env python3
"""
Генератор markdown-файлов по всем категориям моделей OpenRouter.

Что делает:
  1. Тянет актуальный список ВСЕХ моделей с
     https://openrouter.ai/api/v1/models?output_modalities=all
     (включая текстовые, генераторы изображений/видео/аудио, эмбеддеры,
     реранкеры, синтез речи и транскрипцию).
  2. Сырой ответ сохраняет в models_dump.json
  3. Разбивает модели на категории по модальности ВЫХОДА и генерирует
     отдельный README-файл для каждой категории:
       - README.text.md          — Текст (чат / Q&A / работа с документами)
       - README.image.md         — Генерация изображений
       - README.embeddings.md    — Эмбеддинги
       - README.video.md         — Генерация видео
       - README.audio.md         — Генерация музыки
       - README.rerank.md        — Реранкинг
       - README.speech.md        — Синтез речи (TTS)
       - README.transcription.md — Транскрипция (STT)
  4. Ранжирует модели внутри категории по стоимости вывода (completion),
     кроме эмбеддеров и реранкеров (у них иная ценовая модель).

Запуск:  python3 generate.py
"""
import json
import datetime
import urllib.request

from notes import (
    NOTES,
    NOTES_IMAGE,
    NOTES_EMBEDDINGS,
    NOTES_VIDEO,
    NOTES_AUDIO,
    NOTES_RERANK,
    NOTES_SPEECH,
    NOTES_TRANSCRIPTION,
)

API_URL = "https://openrouter.ai/api/v1/models"
OUT_DUMP = "models_dump.json"
UA = {"User-Agent": "openrouter-cast/1.0 (+https://github.com/your/repo)", "Accept": "application/json"}

# ---------------------------------------------------------------------------
# Категории: ключ — имя файла, значение — описание для шапки README.
# Входной признак категории — модальность выхода из architecture.output_modalities.
# ---------------------------------------------------------------------------
CATEGORIES = [
    {
        "key": "text",
        "file": "README.text.md",
        "title": "Текстовые модели OpenRouter",
        "desc": "Чат, ответы на вопросы, работа с документами. Выход — только текст.",
        "modality": "text",
        "rank_by": "completion",
    },
    {
        "key": "image",
        "file": "README.image.md",
        "title": "Генерация изображений OpenRouter",
        "desc": "Модели, которые генерируют и редактируют изображения. Выход — изображение.",
        "modality": "image",
        "rank_by": "completion",
    },
    {
        "key": "embeddings",
        "file": "README.embeddings.md",
        "title": "Эмбеддинги OpenRouter",
        "desc": "Векторные представления текста. Без ранжирования по стоимости вывода.",
        "modality": "embeddings",
        "rank_by": None,
    },
    {
        "key": "video",
        "file": "README.video.md",
        "title": "Генерация видео OpenRouter",
        "desc": "Модели, генерирующие видео из текста/изображений.",
        "modality": "video",
        "rank_by": "completion",
    },
    {
        "key": "audio",
        "file": "README.audio.md",
        "title": "Генерация музыки OpenRouter",
        "desc": "Модели, создающие музыку/звук. Выход — аудио.",
        "modality": "audio",
        "rank_by": "completion",
    },
    {
        "key": "rerank",
        "file": "README.rerank.md",
        "title": "Реранкинг OpenRouter",
        "desc": "Переупорядочивание документов по релевантности. Без ранжирования по стоимости вывода.",
        "modality": "rerank",
        "rank_by": None,
    },
    {
        "key": "speech",
        "file": "README.speech.md",
        "title": "Синтез речи (TTS) OpenRouter",
        "desc": "Преобразование текста в речь. Ранжирование по цене входа (цена токенов текста).",
        "modality": "speech",
        "rank_by": "prompt",
    },
    {
        "key": "transcription",
        "file": "README.transcription.md",
        "title": "Транскрипция (STT) OpenRouter",
        "desc": "Преобразование аудио в текст. Ранжирование по цене входа.",
        "modality": "transcription",
        "rank_by": "prompt",
    },
]


# Словарь описаний моделей по категориям (ключ — ключ категории из CATEGORIES).
CATEGORY_NOTES = {
    "text": NOTES,
    "image": NOTES_IMAGE,
    "embeddings": NOTES_EMBEDDINGS,
    "video": NOTES_VIDEO,
    "audio": NOTES_AUDIO,
    "rerank": NOTES_RERANK,
    "speech": NOTES_SPEECH,
    "transcription": NOTES_TRANSCRIPTION,
}


def default_note(model):
    """Автоматическая эвристика для неизвестных текстовых моделей."""
    mid = (model.get("id") or "").lower()
    name = (model.get("name") or "").lower()
    text = mid + " " + name
    if any(k in text for k in ("coder", "code", "codestral", "apply", "patch", "search", "safeguard", "guard", "moderator", "classif")):
        return "Узкоспециализированная (код/модерация); для общего диалога не предназначена"
    if any(k in text for k in ("translate", "mt2", "voice", "audio", "image", "music")):
        return "Специализированная задача; не для общего диалога"
    if "roleplay" in text or "creative" in name or "story" in text:
        return "Креатив/ролеплей; диалог живой, Q&A слабый"
    if "flash" in text or "lite" in text or "mini" in text or "nano" in text or "small" in text:
        return "Компактная/быстрая; нормальный диалог, лёгкие вопросы"
    if "pro" in text or "max" in text or "large" in text:
        return "Крупная модель; хороший диалог и ответы"
    return "Универсальная; качество диалога/ответов зависит от версии"


def category_fallback_note(model, category_key):
    """Эвристика описания для неизвестных моделей не-текстовых категорий."""
    mid = (model.get("id") or "").lower()
    name = (model.get("name") or "").lower()
    text = mid + " " + name
    if category_key == "image":
        if "free" in mid:
            return "Бесплатная генерация изображений"
        if "mini" in text or "lite" in text or "small" in text or "klein" in text:
            return "Компактная модель генерации изображений"
        if "pro" in text or "max" in text or "large" in text:
            return "Модель генерации изображений высокого качества"
        return "Генерация и редактирование изображений"
    if category_key == "embeddings":
        if "free" in mid:
            return "Бесплатные эмбеддинги"
        if "mini" in text or "small" in text or "base" in text or "lite" in text:
            return "Компактные эмбеддинги"
        return "Векторные представления текста"
    if category_key == "video":
        if "free" in mid:
            return "Бесплатная генерация видео"
        if "mini" in text or "lite" in text or "fast" in text:
            return "Быстрая/лёгкая генерация видео"
        if "pro" in text or "max" in text:
            return "Генерация видео высокого качества"
        return "Генерация видео из текста/изображений"
    if category_key == "audio":
        return "Генерация музыки/звука"
    if category_key == "rerank":
        if "free" in mid:
            return "Бесплатный реранкер"
        return "Реранкинг документов по релевантности"
    if category_key == "speech":
        if "free" in mid:
            return "Бесплатный синтез речи"
        if "mini" in text or "flash" in text or "turbo" in text:
            return "Быстрый синтез речи"
        if "pro" in text or "plus" in text or "hd" in text:
            return "Качественный синтез речи"
        return "Синтез речи (текст → аудио)"
    if category_key == "transcription":
        if "free" in mid:
            return "Бесплатная транскрипция"
        if "mini" in text or "0.6b" in text or "streaming" in text:
            return "Компактное распознавание речи"
        if "pro" in text or "plus" in text:
            return "Качественное распознавание речи"
        return "Транскрипция аудио (аудио → текст)"
    return "Описание отсутствует"


def usd_per_million(x):
    return x * 1_000_000


def fmt_price(x):
    """Цена за 1 млн токенов: на вход — $ за токен."""
    if x < 0:
        return "—"
    return f"{usd_per_million(x):,.2f}"


def fmt_unit_price(x):
    """Цена за единицу вывода (изображение/видео/аудио): на вход — $ за штуку."""
    if x < 0:
        return "—"
    return f"${x:,.4f}"


def fmt_ctx(ctx):
    if not ctx:
        return "—"
    if ctx >= 1_000_000:
        return f"{ctx/1_000_000:.1f}M"
    if ctx < 1000:
        return f"{ctx // 100:.1f}k" if ctx >= 100 else f"{ctx}"
    return f"{ctx//1000}k"


# ---------------------------------------------------------------------------
# Скачивание
# ---------------------------------------------------------------------------
def fetch_and_save_dump():
    """Качает полный список моделей и сохраняет в models_dump.json."""
    url = f"{API_URL}?output_modalities=all"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.load(resp)
    if not isinstance(payload, dict) or "data" not in payload:
        raise RuntimeError(f"Неожиданный ответ API: {payload}")
    with open(OUT_DUMP, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload["data"]


def get_models():
    """Скачивает свежие данные с API и сохраняет их в models_dump.json."""
    return fetch_and_save_dump()


# ---------------------------------------------------------------------------
# Классификация
# ---------------------------------------------------------------------------
def classify(data):
    """Возвращает словарь key -> список моделей для каждой категории."""
    result = {cat["key"]: [] for cat in CATEGORIES}
    for m in data:
        arch = m.get("architecture") or {}
        out_mod = arch.get("output_modalities") or []
        out_set = set(out_mod)
        # Модель может попасть только в одну категорию.
        # Приоритет: спец-модальности > text.
        if out_set & {"transcription", "speech", "embeddings", "rerank", "video"}:
            # Выбираем первую приоритетную спец-модальность
            for spec in ("transcription", "speech", "embeddings", "rerank", "video"):
                if spec in out_set:
                    result[spec].append(m)
                    break
        elif "image" in out_set:
            result["image"].append(m)
        elif "audio" in out_set:
            result["audio"].append(m)
        elif "text" in out_set:
            result["text"].append(m)
    return result


def price_of(m, field):
    pricing = m.get("pricing") or {}
    val = pricing.get(field)
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# Рендер
# ---------------------------------------------------------------------------
def render_text(rows, generated_at):
    lines = [
        "# " + "Текстовые модели OpenRouter: стоимость и оценка диалога\n",
        "> Источник: `https://openrouter.ai/api/v1/models?output_modalities=all`",
        f"> Последняя генерация: `{generated_at}` (UTC)",
        "> Категория: **текст** — чат, ответы на вопросы, работа с документами.",
        "> Цены в **USD за 1 млн токенов**. Таблица отсортирована по цене **output** по возрастанию.\n",
        "| Модель | Input $/M | Output $/M | Контекст | Оценка диалога / Q&A |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        mid = r["id"]
        note = NOTES.get(mid, default_note(r["obj"]))
        lines.append(f"| `{mid}` | {fmt_price(r['prom'])} | {fmt_price(r['comp'])} | {r['ctx']} | {note} |")
    return "\n".join(lines) + "\n"


def render_generic(rows, generated_at, title, desc, rank_field, out_label):
    """Общий рендер для генераторов (image/video/audio) и TTS/STT."""
    lines = [
        f"# {title}\n",
        "> Источник: `https://openrouter.ai/api/v1/models?output_modalities=all`",
        f"> Последняя генерация: `{generated_at}` (UTC)",
        f"> {desc}",
        f"> Цены в **USD за 1 млн токенов**. Ранжирование по **{out_label}** по возрастанию.\n",
        "| Модель | Входная модальность | Цена $/M | Контекст | Описание |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| `{r['id']}` | {r['inmod']} | {fmt_price(r[rank_field])} | {r['ctx']} | {r['note']} |"
        )
    return "\n".join(lines) + "\n"


def render_per_unit(rows, generated_at, title, desc):
    """Рендер для генераторов с ценой за единицу вывода (image/video/audio).

    Два столбца: «Цена за токен $/M» (prompt/completion/<mod>_output) и
    «Цена за единицу $» (pricing.image/video/audio). Оба берутся из JSON как есть.
    """
    lines = [
        f"# {title}\n",
        "> Источник: `https://openrouter.ai/api/v1/models?output_modalities=all`",
        f"> Последняя генерация: `{generated_at}` (UTC)",
        f"> {desc}",
        "> Цены: **Цена за токен $/M** — за 1 млн токенов; **Цена за единицу $** —",
        "> фиксированная цена за единицу вывода (изображение/видео/аудио), если она задана.",
        "> Сортировка по цене вывода по возрастанию.\n",
        "| Модель | Входная модальность | Цена за токен $/M | Цена за единицу $ | Контекст | Описание |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        tok = fmt_price(r["token"]) if r["token"] > 0 else "—"
        unit = fmt_unit_price(r["unit"]) if r["unit"] > 0 else "—"
        lines.append(f"| `{r['id']}` | {r['inmod']} | {tok} | {unit} | {r['ctx']} | {r['note']} |")
    return "\n".join(lines) + "\n"


def render_emb_rerank(rows, generated_at, title, desc, price_label):
    """Рендер для эмбеддингов и реранкеров (без ранжирования по стоимости вывода)."""
    lines = [
        f"# {title}\n",
        "> Источник: `https://openrouter.ai/api/v1/models?output_modalities=all`",
        f"> Последняя генерация: `{generated_at}` (UTC)",
        f"> {desc}",
        f"> Цены в **USD за 1 млн токенов**. {price_label}\n",
        "| Модель | Цена $/M | Контекст | Описание |",
        "|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| `{r['id']}` | {fmt_price(r['prom'])} | {r['ctx']} | {r['note']} |")
    return "\n".join(lines) + "\n"


def build_rows(cat, models):
    """Строит строки для категории с учётом полей сортировки.

    Для генераторов (image/video/audio) у модели может быть либо цена
    за токен (prompt/completion или <mod>_output), либо цена за единицу
    вывода (<mod>, например pricing.image — $ за одно изображение).
    Разделяем их: is_unit — модель берёт за единицу, иначе — за токены.
    """
    key = cat["key"]
    notes_dict = CATEGORY_NOTES.get(key, {})
    unit_mod = cat.get("modality")  # 'image'/'video'/'audio' или иное
    rows = []
    for m in models:
        arch = m.get("architecture") or {}
        in_mod = "+".join(sorted(arch.get("input_modalities") or [])) or "—"
        ctx = fmt_ctx(m.get("context_length") or 0)
        prom = price_of(m, "prompt")
        comp = price_of(m, "completion")
        mid = m.get("id", "")

        # Цена за единицу вывода (например pricing.image — $ за одно изображение)
        unit_price = 0.0
        # Цена за токен (например completion или image_output — $ за токен)
        token_price = 0.0
        if unit_mod in ("image", "video", "audio"):
            unit_price = price_of(m, unit_mod)
            token_price = max(prom, comp, price_of(m, f"{unit_mod}_output"))
        else:
            token_price = max(prom, comp)
        if key == "text":
            note = notes_dict.get(mid, default_note(m))
        else:
            note = notes_dict.get(mid, category_fallback_note(m, key))

        base = {
            "id": mid,
            "ctx": ctx,
            "inmod": in_mod,
            "obj": m,
            "note": note,
            "prom": prom,
            "comp": comp,
            "prompt": prom,          # алиасы для render_generic (rank_field)
            "completion": comp,
            "unit": unit_price,      # $ за единицу вывода (pricing.<mod>)
            "token": token_price,    # $ за токен
        }
        rows.append(base)

    rb = cat["rank_by"]
    if unit_mod in ("image", "video", "audio"):
        # сортируем по фактической цене вывода (большей из двух: за единицу или за токен)
        rows.sort(key=lambda r: (1 if max(r["unit"], r["token"]) <= 0 else 0,
                                 max(r["unit"], r["token"])))
    elif rb == "completion":
        rows.sort(key=lambda r: (1 if r["comp"] < 0 else 0, r["comp"]))
    elif rb == "prompt":
        rows.sort(key=lambda r: r["prom"])
    # для embeddings/rerank сортировка не нужна
    return rows


def generate_all(data, generated_at):
    by_cat = classify(data)

    out_files = []
    for cat in CATEGORIES:
        models = by_cat[cat["key"]]
        rows = build_rows(cat, models)
        key = cat["key"]
        if key == "text":
            md = render_text(rows, generated_at)
        elif key in ("embeddings", "rerank"):
            md = render_emb_rerank(
                rows, generated_at, cat["title"], cat["desc"],
                "Без ранжирования по стоимости вывода (иная ценовая модель).",
            )
        elif cat["modality"] in ("image", "video", "audio"):
            # Столбец «Цена за единицу $» показываем, только если в категории есть
            # хотя бы одна модель с ценой за единицу вывода. Иначе (например video,
            # где цены за единицу в данных нет) — обычный рендер с одним ценовым столбцом.
            if any(r["unit"] > 0 for r in rows):
                md = render_per_unit(rows, generated_at, cat["title"], cat["desc"])
            else:
                md = render_generic(rows, generated_at, cat["title"], cat["desc"], cat["rank_by"], "цене вывода (output)")
        else:
            out_label = "цене вывода (output)" if cat["rank_by"] == "completion" else "цене входа (prompt)"
            md = render_generic(rows, generated_at, cat["title"], cat["desc"], cat["rank_by"], out_label)
        with open(cat["file"], "w", encoding="utf-8") as f:
            f.write(md)
        out_files.append((cat["file"], len(models)))
    return out_files


def main():
    data = get_models()
    generated_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")
    results = generate_all(data, generated_at)
    print("OK. Сгенерированы файлы:")
    for fname, count in results:
        print(f"  {fname:32} моделей: {count}")


if __name__ == "__main__":
    main()