#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M I N D // C L I  —  AUTONOMOUS EXECUTIVE TERMINAL v2.5
================================================================================
Разработано для Тагира Искалиева // Экосистема Mind
Эстетика: Teenage Engineering • Apple • Anduril Industrial HUD
Движок: SmartAPI (53 модели) • Архитектурный каталог • Живой осциллограф
Иконки: Персональный глиф и фирменный цвет для каждой модели
Защита: Loop Breaker (Анти-зацикливание) • Token Economy • Auto-Fallback
================================================================================
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any, Optional

# Включение 24-bit TrueColor и ANSI VT100
os.system("")

# ------------------------------------------------------------------------------
# ФИРМЕННАЯ ПАЛИТРА MIND (24-bit TrueColor RGB)
# ------------------------------------------------------------------------------
C_VIOLET = (123, 47, 247)   # #7B2FF7 (Mind Primary)
C_INDIGO = (75, 59, 255)    # #4B3BFF (Mind Secondary)
C_BLUE   = (30, 144, 255)   # #1E90FF (Mind Light Blue)
C_CYAN   = (0, 245, 255)    # #00F5FF (Mind Emissive Accent)
C_WHITE  = (240, 244, 255)  # Crisp White
C_MUTED  = (140, 150, 175)  # Muted Slate
C_DARK   = (45, 50, 75)     # Hairline Slate
C_GREEN  = (0, 230, 153)    # Success Emerald
C_AMBER  = (255, 184, 0)    # Warning Gold
C_RED    = (255, 75, 90)    # Error Crimson
C_MAGENTA= (217, 70, 239)   # Neon Purple


def rgb(r: int, g: int, b: int, text: str) -> str:
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"


def bold(text: str) -> str:
    return f"\033[1m{text}\033[0m"


def multi_gradient(text: str, stops: list[tuple[int, int, int]] = None) -> str:
    """Генерирует 24-битный TrueColor градиент по ключевым цветам бренда Mind."""
    if stops is None:
        stops = [C_VIOLET, C_INDIGO, C_BLUE, C_CYAN]
    n = len(text)
    if n <= 1:
        r, g, b = stops[0]
        return f"\033[38;2;{r};{g};{b}m{text}\033[0m"
    res = []
    num_segments = len(stops) - 1
    for i, ch in enumerate(text):
        global_t = i / float(n - 1)
        seg_idx = min(int(global_t * num_segments), num_segments - 1)
        local_t = (global_t - seg_idx / num_segments) * num_segments
        c1 = stops[seg_idx]
        c2 = stops[seg_idx + 1]
        r = int(c1[0] + (c2[0] - c1[0]) * local_t)
        g = int(c1[1] + (c2[1] - c1[1]) * local_t)
        b = int(c1[2] + (c2[2] - c1[2]) * local_t)
        res.append(f"\033[38;2;{r};{g};{b}m{ch}\033[0m")
    return "".join(res)


def gradient(text: str, c1: tuple[int, int, int] = C_VIOLET, c2: tuple[int, int, int] = C_CYAN) -> str:
    return multi_gradient(text, [c1, c2])


# ------------------------------------------------------------------------------
# РЕЕСТР ВСЕХ 53 МОДЕЛЕЙ: УНИКАЛЬНЫЙ ИКОНОСТАС И МЕТАДАННЫЕ
# ------------------------------------------------------------------------------
MODEL_METADATA: dict[str, dict[str, Any]] = {
    # 🏆 Топ-6 Флагманов (Dedicated Hardware Cores)
    "gemini-3.8-flash": {
        "icon": "✦", "color": C_CYAN, "family": "Gemini", "vendor": "Google DeepMind",
        "meter": "[■■■■■■■■■■] 10/10",
        "desc": "Сверхбыстрый автономный агент, безлимитный контекст (DEFAULT)", "flagship": True
    },
    "deepseek-v4-pro": {
        "icon": "⚡", "color": (50, 130, 255), "family": "DeepSeek", "vendor": "DeepSeek AI",
        "meter": "[■■■■■■■■■□]  9.8",
        "desc": "Лидер по коду, PowerShell, скриптам и системной отладке", "flagship": True
    },
    "claude-opus-5-5": {
        "icon": "❖", "color": C_VIOLET, "family": "Claude", "vendor": "Anthropic",
        "meter": "[■■■■■■■■■■] 10/10",
        "desc": "Архитектурный синтез, глубокие мысли высокой сложности", "flagship": True
    },
    "claude-sonnet-5": {
        "icon": "★", "color": (190, 110, 255), "family": "Claude", "vendor": "Anthropic",
        "meter": "[■■■■■■■■■□]  9.5",
        "desc": "Новейший интеллектуальный флагман Sonnet 5", "flagship": True
    },
    "kimi-k3.1-pro": {
        "icon": "◐", "color": C_GREEN, "family": "Kimi", "vendor": "Moonshot AI",
        "meter": "[■■■■■■■■■□]  9.2",
        "desc": "Огромный контекст, глубокий анализ документов и файлов", "flagship": True
    },
    "gpt-6-sol": {
        "icon": "⬡", "color": C_AMBER, "family": "GPT", "vendor": "OpenAI",
        "meter": "[■■■■■■■■■□]  9.0",
        "desc": "Флагман следующего поколения линейки GPT-6", "flagship": True
    },

    # ✦ Семейство Google Gemini
    "gemini-3.1-pro": {"icon": "◈", "color": C_CYAN, "family": "Gemini", "vendor": "Google", "desc": "Pro рассуждения v3.1"},
    "gemini-3.1-pro-preview": {"icon": "✧", "color": C_CYAN, "family": "Gemini", "vendor": "Google", "desc": "Экспериментальный Pro 3.1"},
    "gemini-4-carbon": {"icon": "◆", "color": C_BLUE, "family": "Gemini", "vendor": "Google", "desc": "Новое ядро Carbon"},
    "gemini-4-argon": {"icon": "◇", "color": C_BLUE, "family": "Gemini", "vendor": "Google", "desc": "Легковесное ядро Argon"},

    # ⚡ Семейство DeepSeek
    "deepseek-v4.1-flash": {"icon": "ϟ", "color": C_CYAN, "family": "DeepSeek", "vendor": "DeepSeek", "desc": "Молниеносный код V4.1"},
    "deepseek-v4-flash": {"icon": "☇", "color": C_INDIGO, "family": "DeepSeek", "vendor": "DeepSeek", "desc": "Быстрый код V4"},
    "deepseek-v4-flash-uncensored": {"icon": "☣", "color": C_RED, "family": "DeepSeek", "vendor": "DeepSeek", "desc": "Без фильтрации"},

    # ❖ Семейство Anthropic Claude
    "claude-sonnet-5-5": {"icon": "✷", "color": (195, 130, 255), "family": "Claude", "vendor": "Anthropic", "desc": "Claude Sonnet 5.5"},
    "claude-sonnet-4-6": {"icon": "✦", "color": (175, 120, 255), "family": "Claude", "vendor": "Anthropic", "desc": "Claude Sonnet 4.6"},
    "claude-haiku-5-5": {"icon": "≋", "color": (210, 160, 255), "family": "Claude", "vendor": "Anthropic", "desc": "Компактный Haiku 5.5"},
    "claude-opus-5": {"icon": "☩", "color": C_VIOLET, "family": "Claude", "vendor": "Anthropic", "desc": "Claude Opus 5"},
    "claude-opus-4-8": {"icon": "✤", "color": C_VIOLET, "family": "Claude", "vendor": "Anthropic", "desc": "Claude Opus 4.8"},
    "claude-opus-4-7": {"icon": "✥", "color": C_VIOLET, "family": "Claude", "vendor": "Anthropic", "desc": "Claude Opus 4.7"},
    "claude-opus-4-6": {"icon": "✣", "color": C_VIOLET, "family": "Claude", "vendor": "Anthropic", "desc": "Claude Opus 4.6"},
    "claude-fable-5-2": {"icon": "§", "color": C_MUTED, "family": "Claude", "vendor": "Anthropic", "desc": "Fable 5.2"},
    "claude-fable-5-1": {"icon": "¶", "color": C_MUTED, "family": "Claude", "vendor": "Anthropic", "desc": "Fable 5.1"},
    "claude-fable-5": {"icon": "†", "color": C_MUTED, "family": "Claude", "vendor": "Anthropic", "desc": "Fable 5"},

    # ⬡ Семейство OpenAI GPT
    "gpt-6-luna": {"icon": "☽", "color": C_AMBER, "family": "GPT", "vendor": "OpenAI", "desc": "GPT-6 Luna Edition"},
    "gpt-6-astra": {"icon": "✵", "color": C_AMBER, "family": "GPT", "vendor": "OpenAI", "desc": "GPT-6 Astra Edition"},
    "gpt-6.2-sol": {"icon": "☼", "color": C_AMBER, "family": "GPT", "vendor": "OpenAI", "desc": "GPT-6.2 Sol"},
    "gpt-6.2-astra": {"icon": "✶", "color": C_AMBER, "family": "GPT", "vendor": "OpenAI", "desc": "GPT-6.2 Astra"},
    "gpt-6.1-sol": {"icon": "☀", "color": C_AMBER, "family": "GPT", "vendor": "OpenAI", "desc": "GPT-6.1 Sol"},
    "gpt-6.1-terra": {"icon": "♁", "color": C_AMBER, "family": "GPT", "vendor": "OpenAI", "desc": "GPT-6.1 Terra"},
    "gpt-5.6-sol": {"icon": "☉", "color": (230, 160, 20), "family": "GPT", "vendor": "OpenAI", "desc": "GPT-5.6 Sol"},
    "gpt-5.6-luna": {"icon": "☾", "color": (230, 160, 20), "family": "GPT", "vendor": "OpenAI", "desc": "GPT-5.6 Luna"},
    "gpt-5.6-terra": {"icon": "⊕", "color": (230, 160, 20), "family": "GPT", "vendor": "OpenAI", "desc": "GPT-5.6 Terra"},
    "gpt-image-2.6": {"icon": "▣", "color": C_MUTED, "family": "GPT", "vendor": "OpenAI", "desc": "Генерация изображений"},

    # ◐ Семейство Moonshot Kimi
    "kimi-k3": {"icon": "◑", "color": C_GREEN, "family": "Kimi", "vendor": "Moonshot", "desc": "Kimi K3"},
    "kimi-k2.7-code": {"icon": "⌨", "color": C_GREEN, "family": "Kimi", "vendor": "Moonshot", "desc": "Kimi кодер v2.7"},
    "kimi-k2.6": {"icon": "○", "color": C_GREEN, "family": "Kimi", "vendor": "Moonshot", "desc": "Kimi K2.6"},

    # ⌬ Семейство Alibaba Qwen
    "qwen-4-max": {"icon": "⌬", "color": C_MAGENTA, "family": "Qwen", "vendor": "Alibaba", "desc": "Флагман Qwen 4 Max"},
    "qwen-3.8-max": {"icon": "⌖", "color": C_MAGENTA, "family": "Qwen", "vendor": "Alibaba", "desc": "Qwen 3.8 Max"},
    "qwen-3.8-flash-next": {"icon": "»", "color": C_MAGENTA, "family": "Qwen", "vendor": "Alibaba", "desc": "Qwen 3.8 Flash Next"},

    # ⊛ GLM / Grok / MiniMax / Другие
    "glm-5.3": {"icon": "⊛", "color": (56, 189, 248), "family": "GLM", "vendor": "Zhipu AI", "desc": "GLM 5.3 Аналитик"},
    "glm-5.3-flash": {"icon": "※", "color": (56, 189, 248), "family": "GLM", "vendor": "Zhipu AI", "desc": "GLM 5.3 Flash"},
    "grok-4.7": {"icon": "✕", "color": C_WHITE, "family": "Grok", "vendor": "xAI", "desc": "Grok 4.7 xAI"},
    "grok-4.6": {"icon": "✖", "color": C_WHITE, "family": "Grok", "vendor": "xAI", "desc": "Grok 4.6 xAI"},
    "grok-4.5": {"icon": "✗", "color": C_WHITE, "family": "Grok", "vendor": "xAI", "desc": "Grok 4.5 xAI"},
    "minimax-m3": {"icon": "⋈", "color": (245, 158, 11), "family": "MiniMax", "vendor": "MiniMax", "desc": "MiniMax M3 (1M контекст)"},
    "minimax-m3.1-flash": {"icon": "∞", "color": (245, 158, 11), "family": "MiniMax", "vendor": "MiniMax", "desc": "MiniMax M3.1 Flash"},
    "mimo-v2.6-pro": {"icon": "⚙", "color": C_MUTED, "family": "Mimo", "vendor": "Xiaomi", "desc": "Mimo Pro v2.6"},
    "mimo-v2.6-flash": {"icon": "⌁", "color": C_MUTED, "family": "Mimo", "vendor": "Xiaomi", "desc": "Mimo Flash v2.6"},
    "muse-spark-1.3": {"icon": "❇", "color": C_MUTED, "family": "Other", "vendor": "Muse", "desc": "Muse Spark 1.3"},
    "muse-wonder": {"icon": "◎", "color": C_MUTED, "family": "Other", "vendor": "Muse", "desc": "Muse Wonder"},
    "nano-banana-2.1-ultra": {"icon": "◬", "color": C_MUTED, "family": "Other", "vendor": "Nano", "desc": "Nano Banana 2.1 Ultra"},
    "hy4-preview": {"icon": "◭", "color": C_MUTED, "family": "Other", "vendor": "HY", "desc": "HY4 Preview"},
    "codex-auto-review": {"icon": "🛡", "color": C_GREEN, "family": "Review", "vendor": "OpenAI", "desc": "Автоматический код-ревьюер"}
}

# ------------------------------------------------------------------------------
# СИСТЕМНЫЕ ПАРАМЕТРЫ И СЕТЬ
# ------------------------------------------------------------------------------
USER_HOME = Path(os.path.expanduser("~"))
DESKTOP_DIR = USER_HOME / "Desktop"
PROJECT_DIR = Path(__file__).resolve().parent.parent

SSL_CTX = ssl._create_unverified_context()
try:
    SSL_CTX.set_ciphers("DEFAULT:@SECLEVEL=1")
except Exception:
    pass

DEFAULT_API_KEY = os.getenv("SMARTAPI_KEY", "sk-smart-J6NAKcsgKoJ_tfaOrfapSY14L1W8us5GR4ZZ3FwPIO8")
DEFAULT_BASE_URL = os.getenv("SMARTAPI_BASE_URL", "https://smartapi.pro/v1").rstrip("/")
DEFAULT_MODEL = "gemini-3.8-flash"

SESSION_STATS = {
    "total_requests": 0,
    "total_tokens_est": 0,
    "total_tools_executed": 0,
    "loops_intercepted": 0,
    "start_time": time.time()
}


# ------------------------------------------------------------------------------
# АНИМАЦИИ: МНОГОПОТОЧНЫЙ SPINNER + ОСЦИЛЛОГРАФ И БАННЕР MIND
# ------------------------------------------------------------------------------
class ThinkingAnimation:
    """Плавная кинематографичная анимация мышления с Braille, осциллографом и таймером."""
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.meta = MODEL_METADATA.get(model_name, {"icon": "◈", "color": C_CYAN})
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.start_t = time.time()

    def _spin(self):
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        waves = [
            "∿∿∿∿∿∿∿∿",
            " ▂▃▅▆▇▆▅",
            "∿∿∿∿∿∿∿∿",
            "▅▆▇█▇▆▅▃",
            "∿∿∿∿∿∿∿∿",
            "▃▅▆▇▆▅▃ ",
        ]
        idx = 0
        icon = rgb(*self.meta["color"], self.meta["icon"])
        m_name = rgb(*self.meta["color"], self.model_name)
        while not self.stop_event.is_set():
            frame = multi_gradient(frames[idx % len(frames)])
            wave = multi_gradient(waves[idx % len(waves)])
            elapsed = time.time() - self.start_t
            timer_str = rgb(*C_MUTED, f"[{elapsed:.1f}s]")
            msg = multi_gradient("Нейронный синтез и выполнение действий...")
            status_text = f"\r  {icon} {m_name}  {frame}  {wave}  {timer_str}  {msg}"
            sys.stdout.write(status_text)
            sys.stdout.flush()
            idx += 1
            time.sleep(0.08)

        sys.stdout.write("\r" + " " * 95 + "\r")
        sys.stdout.flush()

    def __enter__(self):
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=0.5)


def render_banner():
    """Выводит монументальный архитектурный логотип Mind, бейдж «M» и телеметрию."""
    w = 84
    border = multi_gradient("━" * w)
    print(f"\n{border}")
    emblem_and_logo = [
        "   ╭── «M» ──╮   ███╗   ███╗  ██╗  ███╗   ██╗  ██████╗ ",
        "   │  ╱╲  ╱╲ │   ████╗ ████║  ██║  ████╗  ██║  ██╔══██╗",
        "   │ ╱  ╲╱  ╲│   ██╔████╔██║  ██║  ██╔██╗ ██║  ██║  ██║",
        "   │ ▏ ╱╲╱╲ ▕│   ██║╚██╔╝██║  ██║  ██║╚██╗██║  ██║  ██║",
        "   │ ▀▀    ▀▀│   ██║ ╚═╝ ██║  ██║  ██║ ╚████║  ██████╔╝",
        "   ╰─────────╯   ╚═╝     ╚═╝  ╚═╝  ╚═╝  ╚═══╝  ╚═════╝ "
    ]
    for line in emblem_and_logo:
        print(multi_gradient(line))

    hud_lines = [
        "   [ M I N D // C L I ]  •  AUTONOMOUS EXECUTIVE TERMINAL v2.5",
        "   Ecosystem: Mind       •  Architect: Tagir Iskaliev  •  Style: Teenage Eng / Apple",
        "   Status: ONLINE [SECLEVEL=1]  •  53 Neural Cores Synchronized  •  Anti-Loop Active"
    ]
    for h in hud_lines:
        print(multi_gradient(h, [C_CYAN, C_BLUE, C_VIOLET]))

    print(multi_gradient("   [ ░▒▓████████████████████████████████████████████████████████████████████▒░ ] 100% LINK"))
    print(f"{border}\n")


def render_hud(model: str, status: str = "ONLINE", step: int = 0):
    """Выводит статусную строку в индустриальном стиле с TrueColor градиентной рамкой."""
    meta = MODEL_METADATA.get(model, {"icon": "◈", "color": C_CYAN})
    icon = rgb(*meta["color"], meta["icon"])
    model_str = f"{icon} {rgb(*meta['color'], model)}"
    status_color = C_GREEN if "ONLINE" in status or "IDLE" in status else C_AMBER
    status_str = rgb(*status_color, f"● {status}")
    tokens_str = f"TOKENS:~{SESSION_STATS['total_tokens_est']}"
    step_str = f"STEP:{step}" if step > 0 else "READY"
    
    line = f" {status_str}  │  {model_str}  │  {rgb(*C_GREEN, 'SEC:1')}  │  {rgb(*C_MUTED, step_str)}  │  {rgb(*C_MUTED, tokens_str)} "
    w = 84
    top = multi_gradient("╭─ [ АППАРАТНЫЙ ТЕЛЕМЕТРИЧЕСКИЙ СТАТУС ] " + "─" * (w - 44) + "╮")
    bot = multi_gradient("╰" + "─" * (w - 2) + "╯")
    v = multi_gradient("│")
    print(top)
    print(f"{v}{line:<100}{v}")
    print(bot)


def render_box(title: str, body: str, color: tuple[int, int, int] = C_CYAN):
    """Отрисовывает аккуратный блок с hairline-рамкой и полным градиентом."""
    lines = body.strip().split("\n")
    w = 84
    top = multi_gradient("╭─ [ " + title + " ] " + "─" * max(w - len(title) - 8, 4) + "╮")
    bot = multi_gradient("╰" + "─" * (w - 2) + "╯")
    v = multi_gradient("│")
    print(top)
    for l in lines:
        print(f"{v}  {l}")
    print(bot)


# ------------------------------------------------------------------------------
# СТРУКТУРИРОВАННЫЙ КАТАЛОГ: БЕЗ ХАОСА, ПО СЕМЕЙСТВАМ И ТИРАМ
# ------------------------------------------------------------------------------
ORDERED_MODEL_LIST: list[str] = [
    # Топ-6 Флагманов (1..6)
    "gemini-3.8-flash",
    "deepseek-v4-pro",
    "claude-opus-5-5",
    "claude-sonnet-5",
    "kimi-k3.1-pro",
    "gpt-6-sol",

    # Семейство Google Gemini (7..10)
    "gemini-3.1-pro",
    "gemini-3.1-pro-preview",
    "gemini-4-carbon",
    "gemini-4-argon",

    # Семейство DeepSeek (11..13)
    "deepseek-v4.1-flash",
    "deepseek-v4-flash",
    "deepseek-v4-flash-uncensored",

    # Семейство Anthropic Claude (14..23)
    "claude-sonnet-5-5",
    "claude-sonnet-4-6",
    "claude-haiku-5-5",
    "claude-opus-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-fable-5-2",
    "claude-fable-5-1",
    "claude-fable-5",

    # Семейство OpenAI GPT (24..33)
    "gpt-6-luna",
    "gpt-6-astra",
    "gpt-6.2-sol",
    "gpt-6.2-astra",
    "gpt-6.1-sol",
    "gpt-6.1-terra",
    "gpt-5.6-sol",
    "gpt-5.6-luna",
    "gpt-5.6-terra",
    "gpt-image-2.6",

    # Семейство Kimi & Qwen (34..39)
    "kimi-k3",
    "kimi-k2.7-code",
    "kimi-k2.6",
    "qwen-4-max",
    "qwen-3.8-max",
    "qwen-3.8-flash-next",

    # Специализированные и другие (40..53)
    "glm-5.3",
    "glm-5.3-flash",
    "grok-4.7",
    "grok-4.6",
    "grok-4.5",
    "minimax-m3",
    "minimax-m3.1-flash",
    "mimo-v2.6-pro",
    "mimo-v2.6-flash",
    "muse-spark-1.3",
    "muse-wonder",
    "nano-banana-2.1-ultra",
    "hy4-preview",
    "codex-auto-review"
]


def render_structured_catalog(current_model: str = DEFAULT_MODEL):
    """Выводит логично сгруппированный каталог моделей с иконками, карточками и градиентом."""
    w = 84
    top_border = multi_gradient("╭─ [ АРХИТЕКТУРНЫЙ КАТАЛОГ 53 МОДЕЛЕЙ SMARTAPI ] " + "─" * (w - 51) + "╮")
    div_border = multi_gradient("├" + "─" * (w - 2) + "┤")
    bot_border = multi_gradient("╰" + "─" * (w - 2) + "╯")
    v_edge = multi_gradient("│")

    print(f"\n{top_border}")
    print(f"{v_edge}  {multi_gradient('🏆 ТОП-6 ФЛАГМАНОВ ДЛЯ ЕЖЕДНЕВНОЙ РАБОТЫ (HARDWARE CORES):')}")
    
    for i in range(6):
        m = ORDERED_MODEL_LIST[i]
        meta = MODEL_METADATA.get(m, {})
        idx_str = f"[{i+1:2d}]"
        icon_str = rgb(*meta["color"], meta["icon"])
        name_str = rgb(*meta["color"], bold(f"{m:<20}"))
        vendor_str = rgb(*C_MUTED, f"{meta.get('vendor', ''):<15}")
        meter_str = rgb(*C_GREEN if m == current_model else C_CYAN, meta.get("meter", "[■■■■■■■■■■]"))
        desc_str = meta.get("desc", "")
        mark = rgb(*C_GREEN, " ◀ ACTIVE") if m == current_model else ""
        print(f"{v_edge}    {rgb(*C_AMBER, idx_str)} {icon_str} {name_str} {vendor_str} {meter_str} {desc_str}{mark}")

    print(div_border)
    print(f"{v_edge}  {multi_gradient('📂 СЕМЕЙСТВА МОДЕЛЕЙ (сгруппированы по экосистемам):')}")

    families = [
        ("✦ Google Gemini", ORDERED_MODEL_LIST[6:10], C_CYAN),
        ("⚡ DeepSeek AI", ORDERED_MODEL_LIST[10:13], C_INDIGO),
        ("❖ Anthropic Claude", ORDERED_MODEL_LIST[13:23], C_VIOLET),
        ("⬡ OpenAI GPT", ORDERED_MODEL_LIST[23:33], C_AMBER),
        ("◐ Kimi & ⌬ Qwen", ORDERED_MODEL_LIST[33:39], C_GREEN),
        ("⊛ GLM, Grok, MiniMax & Other", ORDERED_MODEL_LIST[39:], C_MUTED),
    ]

    for title, group, fam_color in families:
        print(f"{v_edge}")
        print(f"{v_edge}    {multi_gradient('■ ' + title, [fam_color, C_CYAN])}:")
        
        cols = 2
        for r in range(0, len(group), cols):
            row_items = group[r:r+cols]
            line_parts = []
            for item in row_items:
                idx = ORDERED_MODEL_LIST.index(item) + 1
                meta = MODEL_METADATA.get(item, {})
                icon_str = rgb(*meta.get("color", fam_color), meta.get("icon", "◈"))
                is_curr = (item == current_model)
                name_fmt = rgb(*C_GREEN, bold(f"{item:<25}")) if is_curr else f"{item:<25}"
                line_parts.append(f"{rgb(*C_AMBER, f'[{idx:2d}]')} {icon_str} {name_fmt}")
            print(f"{v_edge}      " + "    ".join(line_parts))

    print(f"{bot_border}\n")


def render_model_prompt_box(default_model: str):
    """Выводит графический блок приглашения ввода модели."""
    w = 84
    top = multi_gradient("╭─ [ ВЫБОР НЕЙРОННОГО ЯДРА SMARTAPI ] " + "─" * (w - 40) + "╮")
    bot = multi_gradient("╰" + "─" * (w - 2) + "╯")
    v = multi_gradient("│")
    print(top)
    print(f"{v}  Введите номер модели [1-53], псевдоним (flash, deepseek, opus) или Enter:{' ' * 6}{v}")
    print(f"{v}  По умолчанию: {rgb(*C_GREEN, '✦ ' + default_model)} (нулевой оверхед, максимальная скорость){' ' * 6}{v}")
    print(bot)


def resolve_model(choice: str, default: str = DEFAULT_MODEL) -> str:
    """Разрешает выбор модели по номеру 1..53, псевдониму или имени."""
    clean = choice.strip().lower()
    if not clean:
        return default

    # 1. По номеру в упорядоченном каталоге
    if clean.isdigit():
        idx = int(clean) - 1
        if 0 <= idx < len(ORDERED_MODEL_LIST):
            return ORDERED_MODEL_LIST[idx]

    # 2. Псевдонимы
    aliases = {
        "gemini": "gemini-3.8-flash",
        "flash": "gemini-3.8-flash",
        "deepseek": "deepseek-v4-pro",
        "deepseek-flash": "deepseek-v4.1-flash",
        "opus": "claude-opus-5-5",
        "sonnet": "claude-sonnet-5",
        "kimi": "kimi-k3.1-pro",
        "gpt": "gpt-6-sol",
        "qwen": "qwen-4-max",
        "grok": "grok-4.7"
    }
    if clean in aliases:
        return aliases[clean]

    # 3. Точное или частичное совпадение
    for m in ORDERED_MODEL_LIST:
        if m.lower() == clean:
            return m
    for m in ORDERED_MODEL_LIST:
        if clean in m.lower():
            return m

    return default


# ------------------------------------------------------------------------------
# АНТИ-ЗАЦИКЛИВАНИЕ И ЗАЩИТА ТОКЕНОВ (LOOP BREAKER & TOKEN GUARDIAN)
# ------------------------------------------------------------------------------
class ExecutionGuardian:
    def __init__(self):
        self.repeat_counts: dict[str, int] = {}

    def register_call(self, tool_name: str, payload: str) -> tuple[bool, str]:
        sig = hashlib.md5(f"{tool_name}:{payload.strip()}".encode("utf-8")).hexdigest()
        count = self.repeat_counts.get(sig, 0) + 1
        self.repeat_counts[sig] = count

        if count >= 2:
            SESSION_STATS["loops_intercepted"] += 1
            return True, (
                f"[⚡ LOOP BREAKER INTERCEPT]: Обнаружен повторный вызов `{tool_name}`!\n"
                f"Модели ЗАПРЕЩЕНО повторять одно и то же действие. Смени стратегию решения "
                f"или сформируй итоговый отчёт руководителю."
            )
        return False, ""

    def compress_output(self, out: str, max_chars: int = 2400) -> str:
        clean = out.strip()
        if not clean:
            return "(Успешно выполнено, вывод пуст)"
        if len(clean) <= max_chars:
            return clean

        head = clean[:1200]
        tail = clean[-1200:]
        omitted = len(clean) - 2400
        return f"{head}\n\n... [MIND GUARDIAN: пропущено {omitted} символов вывода] ...\n\n{tail}"


# ------------------------------------------------------------------------------
# ВЫЗОВ SMARTAPI И ВЫПОЛНЕНИЕ ИНСТРУМЕНТОВ
# ------------------------------------------------------------------------------
def call_smartapi(messages: list[dict], model: str, api_key: str = DEFAULT_API_KEY) -> str:
    url = f"{DEFAULT_BASE_URL}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 16384,
        "temperature": 0.2
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json; charset=utf-8"
        }
    )

    SESSION_STATS["total_requests"] += 1
    SESSION_STATS["total_tokens_est"] += sum(len(m.get("content", "")) // 4 for m in messages)

    try:
        with urllib.request.urlopen(req, timeout=45, context=SSL_CTX) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            choice = res_data.get("choices", [{}])[0]
            message = choice.get("message", {})
            content = message.get("content")
            reasoning = message.get("reasoning_content")

            ans = ""
            if content and str(content).strip():
                ans = str(content).strip()
            elif reasoning and str(reasoning).strip():
                ans = str(reasoning).strip()
            else:
                finish_reason = choice.get("finish_reason", "unknown")
                ans = f"[MIND: Пустой контент от {model} (finish_reason='{finish_reason}'). Переключитесь на /model gemini]"
            return ans
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        return f"[MIND ERROR HTTP {e.code}]: {e.reason} — {err_body}"
    except Exception as e:
        return f"[MIND ERROR]: {e}"


def execute_mind_tools(text: str, guardian: ExecutionGuardian) -> tuple[bool, str]:
    """Парсит и выполняет блоки инструментов из ответа модели."""
    actions = []

    # 1. PowerShell
    ps_pattern = re.compile(r"```(?:powershell|pwsh|ps1)\s*\n([\s\S]*?)```", re.IGNORECASE)
    for match in ps_pattern.finditer(text):
        script = match.group(1).strip()
        if not script:
            continue

        loop, warn = guardian.register_call("powershell", script)
        if loop:
            actions.append(warn)
            continue

        render_box("ВЫПОЛНЕНИЕ POWERSHELL", script, C_CYAN)
        SESSION_STATS["total_tools_executed"] += 1

        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=90
            )
            raw_out = (res.stdout or "") + (("\n[STDERR]:\n" + res.stderr) if res.stderr else "")
            out = guardian.compress_output(raw_out)
            status_tag = "[PowerShell Успех]" if res.returncode == 0 else f"[PowerShell Ошибка {res.returncode}]"
            actions.append(f"{status_tag}:\n```\n{out}\n```")
        except subprocess.TimeoutExpired:
            actions.append("[PowerShell Ошибка]: Превышен таймаут выполнения (90 сек).")
        except Exception as e:
            actions.append(f"[PowerShell Исключение]: {e}")

    # 2. Запись файлов: write_file:путь
    wf_pattern = re.compile(r"```write_file:([^\n]+)\s*\n([\s\S]*?)```", re.IGNORECASE)
    for match in wf_pattern.finditer(text):
        f_path = match.group(1).strip().strip('"').strip("'")
        f_content = match.group(2)

        loop, warn = guardian.register_call("write_file", f_path)
        if loop:
            actions.append(warn)
            continue

        target = Path(f_path)
        if not target.is_absolute():
            target = PROJECT_DIR / target

        render_box("СОЗДАНИЕ/ЗАПИСЬ ФАЙЛА", str(target), C_GREEN)
        SESSION_STATS["total_tools_executed"] += 1
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(f_content)
            actions.append(f"[Запись файла]: Успешно записан {target} ({len(f_content)} байт)")
        except Exception as e:
            actions.append(f"[Ошибка записи файла {target}]: {e}")

    # 3. Чтение файлов: read_file
    rf_pattern = re.compile(r"```read_file\s*\n([^\n]+)\s*```", re.IGNORECASE)
    for match in rf_pattern.finditer(text):
        f_path = match.group(1).strip().strip('"').strip("'")
        target = Path(f_path)
        if not target.is_absolute():
            target = PROJECT_DIR / target

        render_box("ЧТЕНИЕ ФАЙЛА", str(target), C_AMBER)
        SESSION_STATS["total_tools_executed"] += 1
        try:
            if target.exists() and target.is_file():
                with open(target, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                compressed = guardian.compress_output(content)
                actions.append(f"[Файл {target}]:\n```\n{compressed}\n```")
            else:
                actions.append(f"[Ошибка]: Файл {target} не найден.")
        except Exception as e:
            actions.append(f"[Ошибка чтения файла {target}]: {e}")

    # 4. Браузер: browser
    br_pattern = re.compile(r"```browser\s*\n([^\n]+)\s*```", re.IGNORECASE)
    for match in br_pattern.finditer(text):
        target_url = match.group(1).strip()
        if not target_url.startswith("http://") and not target_url.startswith("https://"):
            target_url = "https://www.google.com/search?q=" + urllib.parse.quote(target_url)
        render_box("БРАУЗЕР", target_url, C_BLUE)
        try:
            webbrowser.open(target_url)
            actions.append(f"[Браузер]: Открыта страница {target_url}")
        except Exception as e:
            actions.append(f"[Ошибка запуска браузера]: {e}")

    # 5. Проводник: open_folder
    of_pattern = re.compile(r"```open_folder\s*\n([^\n]+)\s*```", re.IGNORECASE)
    for match in of_pattern.finditer(text):
        f_path = match.group(1).strip()
        folder_str = f_path.strip().strip('"').strip("'")
        folder = Path(folder_str)
        if not folder.is_absolute():
            folder = USER_HOME / folder
        render_box("ПРОВОДНИК", str(folder), C_INDIGO)
        try:
            if folder.exists():
                subprocess.Popen(["explorer.exe", str(folder)])
                actions.append(f"[Проводник]: Открыта папка {folder}")
            else:
                actions.append(f"[Ошибка]: Папка {folder} не найдена.")
        except Exception as e:
            actions.append(f"[Ошибка открытия папки]: {e}")

    if actions:
        return True, "\n\n".join(actions)
    return False, ""


def mind_turn(conversation: list[dict], model: str, guardian: ExecutionGuardian, api_key: str = DEFAULT_API_KEY) -> str:
    """Автономный цикл с живой анимацией мышления и защитой токенов."""
    max_steps = 6
    for step in range(1, max_steps + 1):
        if len(conversation) > 16:
            active_conv = [conversation[0]] + conversation[-14:]
        else:
            active_conv = conversation

        render_hud(model, status=f"THINKING // STEP {step}", step=step)

        # Запуск живой плавной анимации мышления
        with ThinkingAnimation(model):
            reply = call_smartapi(active_conv, model=model, api_key=api_key)

        if not reply or not str(reply).strip():
            return f"[MIND: Модель {model} не вернула контент. Рекомендуется сменить модель через /models]"

        has_tools, tool_out = execute_mind_tools(reply, guardian)
        if has_tools:
            conversation.append({"role": "assistant", "content": reply})
            conversation.append({
                "role": "user",
                "content": (
                    f"{tool_out}\n\n"
                    f"[ИНСТРУКЦИЯ]: Продолжай автономное решение задачи. "
                    f"Если требуются действия — вызывай инструменты. "
                    f"Если задача решена — выдай финальный чёткий отчёт: ЧТО СДЕЛАНО, РЕЗУЛЬТАТ."
                )
            })
        else:
            return reply

    return reply


def build_mind_system_prompt() -> str:
    return f"""ТЫ — АВТОНОМНЫЙ ИИ-ИНЖЕНЕР СИСТЕМЫ MIND ДЛЯ ТАГИРА ИСКАЛИЕВА (ЭКОСИСТЕМА MIND).
ТВОЙ УРОВЕНЬ — АБСОЛЮТНАЯ АВТОНОМНОСТЬ, ВЫСОКАЯ ТОЧНОСТЬ, СТАНДАРТЫ TEENAGE ENGINEERING / ANDURIL.

ДОСТУПНЫЕ ПУТИ:
- Пользователь: {USER_HOME}
- Рабочий стол: {DESKTOP_DIR}
- Проект: {PROJECT_DIR}

ЖЕЛЕЗНЫЕ ПРАВИЛА:
1. НЕ СПРАШИВАЙ — ДЕЛАЙ!
   - Руководитель ставит задачу и ждёт ГОТОВЫЙ РЕЗУЛЬТАТ.
   - Запрещено писать: «Сказать, чтобы я исправил?», «Жду вашего разрешения», «Напишите подтверждение», «Как мне поступить?».
   - Если нужно выполнить команду — СРАЗУ выдавай блок ```powershell```.
   - Если нужно изменить файл — СРАЗУ выдавай блок ```write_file:путь``` с полным кодом.
   - Если возникла ошибка — САМ диагностируй и исправляй без лишних разговоров.

2. СТРУКТУРА ОТВЕТА:
   - ✅ ЧТО СДЕЛАНО
   - 📊 РЕЗУЛЬТАТ
   - ⚡ СЛЕДУЮЩИЙ ШАГ

ИНСТРУМЕНТЫ:
```powershell
твоя команда
```
```read_file
путь
```
```write_file:путь
содержимое
```
```browser
ссылка_или_поиск
```
```open_folder
путь
```"""


# ------------------------------------------------------------------------------
# ГЛАВНЫЙ ИНТЕРАКТИВНЫЙ РЕЖИМ (REPL)
# ------------------------------------------------------------------------------
def main():
    render_banner()
    render_structured_catalog(current_model=DEFAULT_MODEL)
    render_model_prompt_box(default_model=DEFAULT_MODEL)

    try:
        user_choice = input(f"\n{multi_gradient('MIND')} ❯ ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nЗавершение.")
        return

    current_model = resolve_model(user_choice, default=DEFAULT_MODEL)
    meta = MODEL_METADATA.get(current_model, {"icon": "◈", "color": C_CYAN})
    icon = rgb(*meta["color"], meta["icon"])

    print(f"\n{rgb(*C_GREEN, '✔')} Интеллект активирован: {icon} {multi_gradient(current_model, [meta['color'], C_CYAN])}\n")
    render_hud(current_model, status="ONLINE")

    guardian = ExecutionGuardian()
    conversation = [
        {"role": "system", "content": build_mind_system_prompt()}
    ]

    print(f"{rgb(*C_MUTED, 'Команды:')} {rgb(*C_CYAN, '/models')} {rgb(*C_MUTED, '•')} {rgb(*C_CYAN, '/model <номер/имя>')} {rgb(*C_MUTED, '•')} {rgb(*C_CYAN, '/sys')} {rgb(*C_MUTED, '•')} {rgb(*C_CYAN, '/desktop')} {rgb(*C_MUTED, '•')} {rgb(*C_CYAN, '/clear')} {rgb(*C_MUTED, '•')} {rgb(*C_CYAN, 'exit')}\n")

    while True:
        try:
            cur_meta = MODEL_METADATA.get(current_model, {"icon": "◈", "color": C_CYAN})
            m_icon = rgb(*cur_meta["color"], cur_meta["icon"])
            prompt_str = f"{multi_gradient('MIND')} [{m_icon} {rgb(*cur_meta['color'], current_model)}] ❯ "
            user_input = input(prompt_str).strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{rgb(*C_MUTED, 'Сессия Mind CLI завершена.')}")
            break

        if not user_input:
            continue

        cmd_lower = user_input.lower()

        if cmd_lower in ("exit", "quit", "q", "/exit"):
            print(f"\n{multi_gradient('◆ До связи, Тагир. Сессия Mind CLI закрыта.')}")
            break

        if cmd_lower == "/models":
            render_structured_catalog(current_model=current_model)
            continue

        if cmd_lower == "/clear":
            conversation = [{"role": "system", "content": build_mind_system_prompt()}]
            guardian = ExecutionGuardian()
            os.system("cls" if os.name == "nt" else "clear")
            render_banner()
            render_hud(current_model, status="RESET")
            print(f"{rgb(*C_GREEN, '✔ Контекст очищен.')}\n")
            continue

        if cmd_lower == "/sys":
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory; Get-PSDrive C | Select-Object Used,Free"],
                capture_output=True, text=True, encoding="utf-8"
            )
            render_box("СИСТЕМНЫЙ ДАШБОРД WINDOWS", res.stdout.strip(), C_BLUE)
            continue

        if cmd_lower == "/desktop":
            subprocess.Popen(["explorer.exe", str(DESKTOP_DIR)])
            print(f"{rgb(*C_GREEN, '✔ Рабочий стол открыт в Проводнике.')}\n")
            continue

        if user_input.startswith("/model"):
            parts = user_input.split(maxsplit=1)
            if len(parts) > 1:
                target = resolve_model(parts[1], default=current_model)
                current_model = target
                cur_meta = MODEL_METADATA.get(current_model, {"icon": "◈", "color": C_CYAN})
                m_icon = rgb(*cur_meta["color"], cur_meta["icon"])
                print(f"\n{rgb(*C_GREEN, '✔')} Модель переключена: {m_icon} {multi_gradient(current_model, [cur_meta['color'], C_CYAN])}\n")
                render_hud(current_model, status="ONLINE")
            else:
                render_structured_catalog(current_model=current_model)
            continue

        # Обычный запрос пользователя
        conversation.append({"role": "user", "content": user_input})
        ans = mind_turn(conversation, model=current_model, guardian=guardian)
        conversation.append({"role": "assistant", "content": ans})

        print(f"\n{multi_gradient('─' * 84)}\n")
        print(ans)
        print(f"\n{multi_gradient('─' * 84)}\n")


if __name__ == "__main__":
    main()
