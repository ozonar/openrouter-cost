#!/usr/bin/env python3
"""
Генератор markdown-таблицы текстовых моделей OpenRouter.

Что делает:
  1. Тянет актуальный список моделей с https://openrouter.ai/api/v1/models
  2. Отбирает модели, у которых выход КАК МИНИМУМ содержит текст
     (в output_modalities есть "text") — включая мультимодальные
  3. Форматирует цены input/output в USD за 1 млн токенов
  4. Сортирует по цене OUTPUT по возрастанию
  5. Пишет результат в openrouter_models.md

Запуск:  python3 generate.py
"""
import json
import urllib.request

API_URL = "https://openrouter.ai/api/v1/models"
OUT_FILE = "openrouter_models.md"
UA = {"User-Agent": "openrouter-cast/1.0 (+https://github.com/your/repo)", "Accept": "application/json"}


# ---------------------------------------------------------------------------
# Краткие оценки пригодности модели для «диалог + ответы на вопросы».
# Ключ — id модели из API. Если модели нет в словаре, применяется
# автоматическая эвристика (default_note).
# ---------------------------------------------------------------------------
NOTES = {
    # Anthropic
    "anthropic/claude-opus-5": "Максимальное качество диалога и ответов на сложные вопросы",
    "anthropic/claude-opus-5-fast": "Быстрый Opus 5; то же качество, вдвое дороже",
    "anthropic/claude-opus-4.8": "Сильнейший диалог и агентная работа",
    "anthropic/claude-opus-4.7": "Сильнейший диалог и кодинг",
    "anthropic/claude-opus-4.6": "Сильнейший диалог и агентная работа",
    "anthropic/claude-opus-4.5": "Сильнейший диалог, длинный контекст",
    "anthropic/claude-opus-4.1": "Максимальное качество, дорого",
    "anthropic/claude-opus-4": "Максимальное качество, дорого",
    "anthropic/claude-sonnet-5": "Превосходный диалог, сильнейшие ответы на вопросы",
    "anthropic/claude-sonnet-4.6": "Отличный диалог, агентный фокус",
    "anthropic/claude-sonnet-4.5": "Отличный диалог и ответы",
    "anthropic/claude-sonnet-4": "Отличный диалог и кодинг",
    "anthropic/claude-haiku-4.5": "Быстрый и дешёвый; хороший диалог, надёжные ответы",
    "anthropic/claude-3-haiku": "Быстрый Claude; хороший диалог, знания до 2023",
    "anthropic/claude-fable-5": "Mythos-класс; автономная работа, дорого",
    "~anthropic/claude-sonnet-latest": "Алиас Sonnet; превосходный диалог",
    "~anthropic/claude-haiku-latest": "Алиас Haiku; хороший диалог",
    "~anthropic/claude-opus-latest": "Алиас Opus; максимальное качество",

    # OpenAI
    "openai/gpt-5.6-sol": "Флагман GPT-5.6; топовый диалог и сложные вопросы",
    "openai/gpt-5.6-sol-pro": "Sol с pro-reasoning; топовый диалог",
    "openai/gpt-5.6-terra": "Сбалансированный GPT-5.6; сильный диалог",
    "openai/gpt-5.6-luna": "Бюджетный GPT-5.6; отличный чат и Q&A, оптимален",
    "openai/gpt-5.6-luna-pro": "Luna с pro-reasoning; отличный чат и Q&A",
    "openai/gpt-5.5-pro": "Самая мощная reasoning-модель OpenAI; глубочайшие ответы, дорого",
    "openai/gpt-5.5": "GPT-5.5; отличный диалог и рассуждения",
    "openai/gpt-5.4-pro": "GPT-5.4 Pro; максимальное качество, дорого",
    "openai/gpt-5.4": "GPT-5.4; сильный диалог и рассуждения",
    "openai/gpt-5.4-mini": "GPT-5.4 Mini; хороший диалог и Q&A",
    "openai/gpt-5.4-nano": "GPT-5.4 Nano; быстрый, простые диалоги",
    "openai/gpt-5.2": "GPT-5.2; сильный диалог и рассуждения",
    "openai/gpt-5.2-chat": "Быстрый GPT-5.2; хороший диалог",
    "openai/gpt-5.2-pro": "Максимальный GPT-5.2; очень дорого",
    "openai/gpt-5.1": "GPT-5.1; сильный диалог, естественный стиль",
    "openai/gpt-5": "GPT-5; сильный диалог и рассуждения",
    "openai/gpt-5-pro": "GPT-5 Pro; максимальное качество, дорого",
    "openai/gpt-5-mini": "Компактный GPT-5; хороший диалог и лёгкие рассуждения",
    "openai/gpt-5-nano": "Самый быстрый GPT-5; простые диалоги",
    "openai/gpt-4.1": "GPT-4.1; сильный диалог и фактические ответы",
    "openai/gpt-4.1-mini": "GPT-4.1 Mini; хороший диалог, сильные ответы",
    "openai/gpt-4.1-nano": "GPT-4.1 Nano; простые диалоги",
    "openai/gpt-4o": "Проверенный GPT-4o; отличный диалог и Q&A",
    "openai/gpt-4o-2024-11-20": "GPT-4o; отличный диалог, лучшее письмо",
    "openai/gpt-4o-mini": "Бюджетный GPT-4o; хороший диалог и Q&A",
    "openai/gpt-4-turbo": "GPT-4 Turbo; хороший диалог, знания до 2023",
    "openai/o3": "Мощный reasoning; глубокие ответы, диалог сдержанный",
    "openai/o3-pro": "Топовый reasoning; максимально глубокие ответы",
    "openai/o3-mini": "Reasoning о3-mini; хорош в STEM, диалог суше",
    "openai/o3-mini-high": "Reasoning high; глубокие рассуждения",
    "openai/o4-mini": "Reasoning o4-mini; хорош в STEM и кодинге",
    "openai/o4-mini-high": "Reasoning high; глубокие рассуждения",
    "openai/o1": "Reasoning o1; глубокие рассуждения, сдержанный диалог",
    "openai/o1-pro": "Максимальный reasoning; очень дорого",
    "openai/gpt-chat-latest": "Алиас ChatGPT; хороший диалог",
    "~openai/gpt-latest": "Алиас GPT; сильный диалог",
    "~openai/gpt-mini-latest": "Алиас GPT Mini; хороший диалог",
    "openai/gpt-oss-120b": "Открытая 117B; хороший диалог, сильные ответы",
    "openai/gpt-oss-20b": "Открытая OpenAI; неплохой диалог, средние ответы",
    "openai/gpt-oss-20b:free": "Открытая OpenAI; неплохой диалог, средние ответы",

    # Google / Gemini
    "google/gemini-3.7-flash": "Gemini 3.7 Flash; отличный диалог и Q&A, оптимальный выбор",
    "google/gemini-3.6-flash": "Gemini 3.6 Flash; отличный универсальный диалог",
    "google/gemini-3.5-flash": "Gemini 3.5 Flash; сильный диалог и Q&A",
    "google/gemini-3.5-flash-lite": "Лёгкая Gemini; нормальный диалог",
    "google/gemini-3.1-flash-lite": "Лёгкая; нормальный диалог, лёгкие вопросы",
    "google/gemini-3-flash-preview": "Предпросмотр; хороший диалог, быстрый",
    "google/gemini-3.1-pro-preview": "Pro-предпросмотр; сильный диалог и рассуждения",
    "google/gemini-2.5-pro": "Прошлый флагман; сильный диалог и рассуждения",
    "google/gemini-2.5-flash": "Прошлый workhorse; хороший диалог и рассуждения",
    "google/gemini-2.5-flash-lite": "Лёгкая сверхбыстрая; нормальный диалог, лёгкие Q&A",
    "google/gemma-4-31b-it": "Открытая 31B; живой диалог, достойные ответы",
    "google/gemma-4-26b-a4b-it": "Эффективная MoE; среднее качество",
    "google/gemma-3-27b-it": "Открытая 27B; приятный диалог, средние ответы",
    "google/gemma-3-12b-it": "Открытая 12B; нормальный диалог",
    "google/gemma-3-4b-it": "Открытая 4B; простые диалоги",
    "google/gemma-3n-e4b-it": "Мобильная 4B; очень простые диалоги",
    "~google/gemini-flash-latest": "Алиас актуального Flash; отличный диалог",
    "~google/gemini-pro-latest": "Алиас Pro; сильный диалог и рассуждения",

    # DeepSeek
    "deepseek/deepseek-v4-flash-0731": "Актуальный Flash; отличный диалог и Q&A, лучшее соотношение цена/качество",
    "deepseek/deepseek-v4-flash": "Быстрая V4 Flash; сильный диалог и рассуждения",
    "~deepseek/deepseek-v4-flash-latest": "Алиас V4 Flash; отличный диалог",
    "deepseek/deepseek-v4-pro": "Мощная V4 Pro; отличный диалог и рассуждения",
    "deepseek/deepseek-v4-pro-0813": "GA V4 Pro; сильный универсал",
    "deepseek/deepseek-r1-0528": "Знаменитая R1; превосходные рассуждения, формальный диалог",
    "deepseek/deepseek-r1": "R1; сильные рассуждения, сдержанный диалог",
    "deepseek/deepseek-r1-distill-llama-70b": "Дистилляция R1; средний диалог",
    "deepseek/deepseek-v3.2": "V3.2; сильный диалог и Q&A",
    "deepseek/deepseek-chat-v3.1": "Гибридная; отличный диалог и рассуждения",
    "deepseek/deepseek-chat-v3-0324": "Улучшенный V3; хороший диалог и Q&A",
    "deepseek/deepseek-chat": "Классический V3; надёжный диалог",

    # Qwen
    "qwen/qwen3.8-max": "Qwen3.8 Max; отличный универсальный диалог и Q&A",
    "qwen/qwen3.8-2.4t-a95b": "Гигантская открытая MoE (95B активных); очень сильный диалог",
    "qwen/qwen3.7-max": "Qwen3.7 Max; хороший диалог, офисный фокус",
    "qwen/qwen3.7-plus": "Qwen3.7 Plus; хороший диалог и Q&A",
    "qwen/qwen3.7-flash": "Быстрая Qwen; отличный диалог и Q&A за копейки",
    "qwen/qwen3.6-plus": "Qwen3.6 Plus; хороший диалог и Q&A",
    "qwen/qwen3.6-flash": "Быстрая Qwen3.6; хороший диалог и Q&A",
    "qwen/qwen3.6-max-preview": "Qwen3.6 Max Preview; сильный диалог",
    "qwen/qwen3.5-plus-20260420": "Qwen3.5 Plus; хороший диалог и Q&A",
    "qwen/qwen3-max": "Qwen3 Max; хороший диалог и рассуждения",
    "qwen/qwen3-max-thinking": "Reasoning Qwen3 Max; глубокие рассуждения",
    "qwen/qwen3-235b-a22b": "Крупная MoE; сильные ответы и рассуждения",
    "qwen/qwen3-32b": "Dense 32B; хороший диалог, достойные ответы",
    "qwen/qwen3-30b-a3b-instruct-2507": "Эффективная MoE; хороший диалог и ответы",
    "qwen/qwen3-14b": "Dense 14.8B; нормальный чат, средние ответы",
    "qwen/qwen3-8b": "Компактная; неплохой диалог, лёгкие вопросы",
    "qwen/qwen-plus": "Qwen-Plus; хороший универсальный диалог и Q&A",
    "qwen/qwen2.5-72b-instruct": "Проверенная 72B; хороший диалог, надёжные ответы",
    "qwen/qwen-2.5-7b-instruct": "Компактная; простые диалоги",
    "qwen/qwen3.5-397b-a17b": "Крупная MoE; сильные ответы",
    "qwen/qwen3.5-122b-a10b": "Крупная MoE; хороший диалог и ответы",

    # xAI / Grok
    "x-ai/grok-4.6": "Grok 4.6 флагман; топовый диалог, отличный Q&A",
    "x-ai/grok-4.5": "Grok 4.5; живой диалог, сильные фактические ответы",
    "x-ai/grok-4.3": "Grok 4.3; хороший диалог, высокая фактичность",
    "x-ai/grok-4.20": "Grok 4.20; низкая галлюцинация, строгое следование",
    "~x-ai/grok-latest": "Алиас Grok; топовый диалог",
    "x-ai/grok-build-0.1": "Быстрый кодинг; не для общего диалога",

    # Meta / Llama
    "meta-llama/llama-3.3-70b-instruct": "Проверенная 70B; отличный многоязычный диалог",
    "meta-llama/llama-3.1-70b-instruct": "Надёжная 70B; хороший диалог, сильные ответы",
    "meta-llama/llama-3.1-8b-instruct": "Классика Llama 8B; нормальный диалог, средние ответы",
    "meta-llama/llama-3.2-3b-instruct": "Компактная 3B; простые диалоги",
    "meta-llama/llama-3.2-1b-instruct": "Мини 1B; очень простые диалоги",
    "meta-llama/llama-4-maverick": "Новая Llama 4; средний диалог",
    "meta-llama/llama-4-scout": "Llama 4 Scout; средний диалог",
    "meta-llama/llama-guard-4-12b": "Safety-классификатор; не для диалога",

    # Mistral
    "mistralai/mistral-large-2512": "Mistral Large 3; хороший диалог, сильные ответы",
    "mistralai/mistral-medium-3-5": "Mistral Medium 3.5; хороший диалог, достойные ответы",
    "mistralai/mistral-medium-3": "Mistral Medium 3; приятный диалог",
    "mistralai/mistral-medium-3.1": "Mistral Medium 3.1; приятный диалог",
    "mistralai/mistral-small-2603": "Mistral Small 4; хороший диалог, средние ответы",
    "mistralai/mistral-small-24b-instruct-2501": "Быстрая 24B; живой диалог, адекватные ответы, дёшево",
    "mistralai/mistral-small-3.2-24b-instruct": "Быстрая 24B; хороший диалог, достойные ответы",
    "mistralai/mistral-small-3.1-24b-instruct": "24B; хороший диалог, средние ответы",
    "mistralai/mistral-nemo": "Многоязычная 12B; приятный естественный диалог, хороший Q&A",
    "mistralai/mixtral-8x22b-instruct": "Крупная открытая MoE; хороший диалог",
    "mistralai/codestral-2508": "Кодинг-модель; не для общего диалога",
    "mistralai/mistral-large-2407": "Mistral Large 2; хороший диалог и ответы",
    "mistralai/mistral-large": "Mistral Large 2; хороший диалог и ответы",
    "mistralai/mistral-saba": "Для Ближнего Востока; нишевый диалог",

    # Moonshot / Kimi
    "moonshotai/kimi-k3": "Флагман Kimi; отличный диалог и глубокие рассуждения",
    "moonshotai/kimi-k2.7-code": "Кодинг-модель; для общих вопросов ограниченно",
    "moonshotai/kimi-k2.6": "Kimi K2.6; хороший диалог, длинные задачи",
    "moonshotai/kimi-k2.5": "Kimi K2.5; хороший диалог, визуальный кодинг",
    "moonshotai/kimi-k2-thinking": "Открытый reasoning; хороший диалог, глубокие ответы",
    "moonshotai/kimi-k2-0905": "Kimi K2; хороший диалог и рассуждения",
    "moonshotai/kimi-k2": "Kimi K2; хороший диалог и рассуждения",
    "~moonshotai/kimi-latest": "Алиас Kimi; хороший диалог",

    # Z.ai / GLM
    "z-ai/glm-5.3": "Новейший reasoning GLM; топовый диалог и сложные вопросы",
    "z-ai/glm-5.2": "Флагман GLM 5.2; превосходный диалог, глубокие ответы",
    "z-ai/glm-5.2:free": "Флагман бесплатно — отличный универсальный диалог и Q&A",
    "z-ai/glm-5.2:batch": "GLM 5.2 batch; превосходный диалог",
    "z-ai/glm-5.1": "GLM 5.1; сильный диалог, отличный кодинг",
    "z-ai/glm-5": "Флагман GLM 5; отличный диалог и рассуждения",
    "z-ai/glm-5-turbo": "Быстрый GLM; хороший диалог",
    "z-ai/glm-4.7": "Флагман GLM 4.7; отличный диалог, многошаговые рассуждения",
    "z-ai/glm-4.7-flash": "Быстрая 30B-класс; хороший диалог, хорош для агентов",
    "z-ai/glm-4.6": "GLM 4.6; хороший диалог и рассуждения",
    "z-ai/glm-4.5": "GLM 4.5; хороший диалог, агентный фокус",
    "z-ai/glm-4.5-air": "Лёгкий GLM; нормальный диалог, средние ответы",
    "~z-ai/glm-latest": "Алиас GLM; превосходный диалог",

    # MiniMax
    "minimax/minimax-m3": "MiniMax M3; хороший диалог, длинный контекст",
    "minimax/minimax-m2.7": "MiniMax M2.7; хороший диалог и рассуждения",
    "minimax/minimax-m2.5": "MiniMax M2.5; хороший диалог и ответы",
    "minimax/minimax-m2.1": "MiniMax M2.1; хороший диалог и ответы",
    "minimax/minimax-m2-her": "Специально для диалога/ролеплея; лучший тон разговора",
    "minimax/minimax-m2": "MiniMax M2; хороший диалог и ответы",
    "minimax/minimax-m1": "MiniMax M1; хороший диалог, длинный контекст",
    "minimax/minimax-01": "MiniMax-01; хороший диалог, длинный контекст",

    # Прочие
    "inclusionai/ling-3.0-flash": "Эффективная MoE; средний диалог",
    "inclusionai/ling-2.6-flash": "Мгновенная; быстрый простой чат, низкий интеллект",
    "inclusionai/ling-2.6-1t": "Trillion-параметров; хороший диалог, эффективный",
    "inclusionai/ring-2.6-1t": "Reasoning 1T; глубокие рассуждения",
    "bytedance-seed/seed-2.1-turbo": "Seed 2.1 Turbo; хороший диалог, силён в кодинге",
    "bytedance-seed/seed-2.0-lite": "Seed 2.0 Lite; хороший диалог, средние ответы",
    "bytedance-seed/seed-1.6-flash": "Seed 1.6 Flash; быстрый, средний диалог",
    "nousresearch/hermes-4-405b": "Крупный Hermes 4; сильный диалог и рассуждения",
    "nousresearch/hermes-4-70b": "Гибрид reasoning; хороший диалог, сильные ответы",
    "nousresearch/hermes-3-llama-3.1-405b": "Крупный Hermes 3; сильный диалог и рассуждения",
    "nousresearch/hermes-3-llama-3.1-70b": "Отличный открытый универсал; хороший диалог и ролеплей",
    "amazon/nova-premier-v1": "Nova Premier; хороший диалог и рассуждения",
    "amazon/nova-pro-v1": "Старшая Nova; хороший диалог, достойные ответы",
    "amazon/nova-lite-v1": "Недорогая Nova; нормальный диалог, средние ответы",
    "amazon/nova-micro-v1": "Самая быстрая Nova; простые диалоги и лёгкие вопросы",
    "cohere/command-a": "Cohere Command A; RAG/инструменты, нормальный диалог",
    "cohere/command-r-08-2024": "Cohere Command R; нормальный диалог, RAG-фокус",
    "cohere/command-r7b-12-2024": "Компактная Cohere; средний диалог, RAG-фокус",
    "upstage/solar-pro4": "Дешёвая, длинный контекст; нормальный диалог, средние ответы",
    "upstage/solar-pro-3": "Upstage Solar Pro 3; средний диалог",
    "writer/palmyra-x5": "Корпоративные агенты; нормальный диалог, enterprise-фокус",
    "perplexity/sonar": "Поисковый Q&A с цитатами; лучший для вопросов с поиском",
    "perplexity/sonar-pro": "Расширенный поисковый Q&A; глубокие ответы с источниками",
    "perplexity/sonar-reasoning-pro": "Поиск + reasoning; сильные аналитические ответы",
    "perplexity/sonar-deep-research": "Глубокий поиск; многошаговое исследование",
    "sakana/sakana-namazu": "Японский специалист; диалог на японском отличный",
    "sakana/fugu-ultra": "Мультиагентная система; сильный диалог, дорого",
    "thinkingmachines/inkling": "Открытая MoE; хороший диалог и рассуждения",
    "thinkingmachines/inkling-small": "Открытая MoE; средний диалог",
    "meituan/longcat-2.0": "Meituan; средний диалог, кодинг-фокус",
    "tencent/hy3": "Tencent Hy3; хороший диалог, сильные рассуждения",
    "tencent/hunyuan-a13b-instruct": "Tencent; нормальный диалог, средние ответы",
    "xiaomi/mimo-v2.5-pro": "Xiaomi флагман; хороший диалог и рассуждения",
    "xiaomi/mimo-v2.5": "Xiaomi; хороший диалог, длинный контекст",
    "stepfun/step-3.5-flash": "Эффективная MoE; нормальный диалог, средние ответы",
    "deepcogito/cogito-v2.1-671b": "Открытый 671B; отличные рассуждения, хороший диалог",
    "allenai/olmo-3-32b-think": "Open reasoning; логика сильная, диалог суше",
    "liquid/lfm-2.5-2.6b:free": "Маленькая reasoning-модель; только лёгкие задачи",
    "nvidia/nemotron-3-ultra-550b-a55b:free": "Сильная MoE (55B активных); хорош в рассуждениях",
    "nvidia/nemotron-3-super-120b-a12b": "Сбалансированная; нормальный диалог и Q&A",
    "nvidia/nemotron-3-nano-30b-a3b": "Компактная; простые диалоги",
    "openrouter/free": "Роутер случайных бесплатных моделей — качество непредсказуемо",
    "openrouter/auto": "Роутер по задачам; качество зависит от выбора",
    "openrouter/auto-beta": "Бета-роутер; качество зависит от выбора",
    "openrouter/fusion": "Мультимодельное обсуждение; хороший Q&A",
}


def default_note(model):
    """Автоматическая эвристика для неизвестных моделей."""
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


def usd_per_million(x):
    return x * 1_000_000


def fmt_price(x):
    if x < 0:
        return "—"
    return f"{usd_per_million(x):,.2f}"


def fetch_models():
    req = urllib.request.Request(API_URL, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.load(resp)
    if not isinstance(payload, dict) or "data" not in payload:
        raise RuntimeError(f"Неожиданный ответ API: {payload}")
    return payload["data"]


def build_rows(data):
    rows = []
    for m in data:
        arch = m.get("architecture") or {}
        out_mod = arch.get("output_modalities") or []
        # Отбираем модели, у которых выход КАК МИНИМУМ содержит текст
        # (чисто текстовые, а также мультимодальные с текстовым выводом).
        if "text" not in out_mod:
            continue
        pricing = m.get("pricing") or {}
        comp = float(pricing.get("completion", 0) or 0)
        prom = float(pricing.get("prompt", 0) or 0)
        ctx = m.get("context_length") or 0
        ctx_str = (f"{ctx/1_000_000:.1f}M" if ctx >= 1_000_000 else f"{ctx//1000}k") if ctx else "—"
        mid = m.get("id", "")
        note = NOTES.get(mid, default_note(m))
        rows.append({"id": mid, "prom": prom, "comp": comp, "ctx": ctx_str, "note": note})
    # Сортировка по цене OUTPUT по возрастанию (роутеры с отрицательной ценой — в конец)
    rows.sort(key=lambda r: (1 if r["comp"] < 0 else 0, r["comp"]))
    return rows


def render(rows, generated_at):
    lines = [
        "# Текстовые модели OpenRouter: стоимость input/output и оценка диалога\n",
        "> Источник: `https://openrouter.ai/api/v1/models`",
        f"> Последняя генерация: `{generated_at}` (UTC)",
        "> Отобраны **текстовые** модели (выход — только текст).",
        "> Цены приведены в **USD за 1 млн токенов**. Таблица отсортирована по цене **output** по возрастанию.\n",
        "| Модель | Input $/M | Output $/M | Контекст | Оценка диалога / Q&A |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| `{r['id']}` | {fmt_price(r['prom'])} | {fmt_price(r['comp'])} | {r['ctx']} | {r['note']} |")

    lines.append("""

---

## 🏆 Краткие выводы по функции «диалог + ответы на вопросы»

- **Лучшее качество (без ограничения бюджета):** `anthropic/claude-opus-5`, `openai/gpt-5.6-sol`, `openai/gpt-5.5-pro`.
- **Оптимальный баланс цена/качество:** `google/gemini-3.7-flash`, `deepseek/deepseek-v4-flash`, `openai/gpt-5.6-luna`, `z-ai/glm-5.2`.
- **Лучшее среди бесплатных:** `z-ai/glm-5.2:free`.
- **Для живого/характерного диалога (ролеплей):** `minimax/minimax-m2-her`, `nousresearch/hermes-3`.
- **Для вопросов с поиском и источниками:** `perplexity/sonar*`.
""")
    return "\n".join(lines) + "\n"


def main():
    import datetime
    data = fetch_models()
    rows = build_rows(data)
    generated_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")
    md = render(rows, generated_at)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"OK: записано моделей {len(rows)} -> {OUT_FILE}")


if __name__ == "__main__":
    main()