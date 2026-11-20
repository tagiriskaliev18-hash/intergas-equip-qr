#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M I N D // C L I  —  AUTONOMOUS EXECUTIVE TERMINAL v2.5
================================================================================
Разработано для Тагира Искалиева // Экосистема Mind
Эстетика: Teenage Engineering • Apple • Anduril Industrial HUD
Движок: SmartAPI (53 модели) • Структурированный каталог • Живые анимации
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
C_VIOLET = (123, 47, 247)   # #7B2FF7
C_INDIGO = (75, 59, 255)    # #4B3BFF
C_BLUE   = (30, 144, 255)   # #1E90FF
C_CYAN   = (0, 245, 255)    # #00F5FF (Emissive Accent)
C_WHITE  = (240, 244, 255)  # Crisp White
C_MUTED  = (140, 150, 175)  # Muted Slate
C_DARK   = (45, 50, 75)     # Hairline Border
C_GREEN  = (0, 230, 153)    # Success Emerald
C_AMBER  = (255, 184, 0)    # Warning Gold
C_RED    = (255, 75, 90)    # Error Crimson
C_MAGENTA= (217, 70, 239)   # Neon Purple


def rgb(r: int, g: int, b: int, text: str) -> str:
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"


def bold(text: str) -> str:
    return f"\033[1m{text}\033[0m"


def gradient(text: str, c1: tuple[int, int, int] = C_VIOLET, c2: tuple[int, int, int] = C_CYAN) -> str:
    """Генерирует 24-битный плавный градиент по тексту."""
    n = max(len(text), 1)
    out = []
    for i, ch in enumerate(text):
        t = i / float(n)
        r = int(c1[0] * (1 - t) + c2[0] * t)
        g = int(c1[1] * (1 - t) + c2[1] * t)
        b = int(c1[2] * (1 - t) + c2[2] * t)
        out.append(f"\033[38;2;{r};{g};{b}m{ch}\033[0m")
    return "".join(out)


# ------------------------------------------------------------------------------
# РЕЕСТР МОДЕЛЕЙ: СТРУКТУРА, СЕМЕЙСТВА И УНИКАЛЬНЫЕ ИКОНКИ
# ------------------------------------------------------------------------------
# Иконки и цвета семейств:
# ✦ Gemini (Cyan) • ⚡ DeepSeek (Indigo) • ❖ Claude (Violet)
# ⬡ GPT (Amber) • ◐ Kimi (Emerald) • ⌬ Qwen (Magenta)
# ⊛ GLM (Sky Blue) • ✕ Grok (White) • ⋈ MiniMax (Gold) • ⚙ Codex / Other (Muted)

MODEL_METADATA: dict[str, dict[str, Any]] = {
    # 🏆 Топ-6 Флагманов
    "gemini-3.8-flash": {
        "icon": "✦", "color": C_CYAN, "family": "Gemini", "vendor": "Google DeepMind",
        "desc": "Сверхбыстрый, безлимитный, нулевой оверхед (DEFAULT)", "flagship": True
    },
    "deepseek-v4-pro": {
        "icon": "⚡", "color": (50, 130, 255), "family": "DeepSeek", "vendor": "DeepSeek AI",
        "desc": "Лидер по коду, PowerShell, скриптам и системной отладке", "flagship": True
    },
    "claude-opus-5-5": {
        "icon": "❖", "color": C_VIOLET, "family": "Claude", "vendor": "Anthropic",
        "desc": "Архитектурный синтез, глубокие мысли высокой сложности", "flagship": True
    },
    "claude-sonnet-5": {
        "icon": "❖", "color": (190, 110, 255), "family": "Claude", "vendor": "Anthropic",
        "desc": "Новейший интеллектуальный флагман Sonnet 5", "flagship": True
    },
    "kimi-k3.1-pro": {
        "icon": "◐", "color": C_GREEN, "family": "Kimi", "vendor": "Moonshot AI",
        "desc": "Огромный контекст, глубокий анализ документов и файлов", "flagship": True
    },
    "gpt-6-sol": {
        "icon": "⬡", "color": C_AMBER, "family": "GPT", "vendor": "OpenAI",
        "desc": "Флагман следующего поколения линейки GPT-6", "flagship": True
    },

    # ✦ Семейство Google Gemini
    "gemini-3.1-pro": {"icon": "✦", "color": C_CYAN, "family": "Gemini", "vendor": "Google", "desc": "Pro рассуждения v3.1"},
    "gemini-3.1-pro-preview": {"icon": "✦", "color": C_CYAN, "family": "Gemini", "vendor": "Google", "desc": "Экспериментальный Pro 3.1"},
    "gemini-4-carbon": {"icon": "✦", "color": C_BLUE, "family": "Gemini", "vendor": "Google", "desc": "Новое ядро Carbon"},
    "gemini-4-argon": {"icon": "✦", "color": C_BLUE, "family": "Gemini", "vendor": "Google", "desc": "Легковесное ядро Argon"},

    # ⚡ Семейство DeepSeek
    "deepseek-v4.1-flash": {"icon": "⚡", "color": C_CYAN, "family": "DeepSeek", "vendor": "DeepSeek", "desc": "Молниеносный генератор кода"},
    "deepseek-v4-flash": {"icon": "⚡", "color": C_INDIGO, "family": "DeepSeek", "vendor": "DeepSeek", "desc": "Быстрый код V4"},
    "deepseek-v4-flash-uncensored": {"icon": "⚡", "color": C_RED, "family": "DeepSeek", "vendor": "DeepSeek", "desc": "Без фильтрации"},

    # ❖ Семейство Anthropic Claude
    "claude-sonnet-4-6": {"icon": "❖", "color": (175, 120, 255), "family": "Claude", "vendor": "Anthropic", "desc": "Claude Sonnet 4.6"},
    "claude-sonnet-5-5": {"icon": "❖", "color": (195, 130, 255), "family": "Claude", "vendor": "Anthropic", "desc": "Claude Sonnet 5.5"},
    "claude-haiku-5-5": {"icon": "❖", "color": (210, 160, 255), "family": "Claude", "vendor": "Anthropic", "desc": "Компактный и быстрый Haiku 5.5"},
    "claude-opus-5": {"icon": "❖", "color": C_VIOLET, "family": "Claude", "vendor": "Anthropic", "desc": "Claude Opus 5"},
    "claude-opus-4-8": {"icon": "❖", "color": C_VIOLET, "family": "Claude", "vendor": "Anthropic", "desc": "Claude Opus 4.8"},
    "claude-opus-4-7": {"icon": "❖", "color": C_VIOLET, "family": "Claude", "vendor": "Anthropic", "desc": "Claude Opus 4.7"},
    "claude-opus-4-6": {"icon": "❖", "color": C_VIOLET, "family": "Claude", "vendor": "Anthropic", "desc": "Claude Opus 4.6"},
    "claude-fable-5": {"icon": "❖", "color": C_MUTED, "family": "Claude", "vendor": "Anthropic", "desc": "Fable 5"},
    "claude-fable-5-1": {"icon": "❖", "color": C_MUTED, "family": "Claude", "vendor": "Anthropic", "desc": "Fable 5.1"},
    "claude-fable-5-2": {"icon": "❖", "color": C_MUTED, "family": "Claude", "vendor": "Anthropic", "desc": "Fable 5.2"},

    # ⬡ Семейство OpenAI GPT
    "gpt-6-luna": {"icon": "⬡", "color": C_AMBER, "family": "GPT", "vendor": "OpenAI", "desc": "GPT-6 Luna Edition"},
    "gpt-6-astra": {"icon": "⬡", "color": C_AMBER, "family": "GPT", "vendor": "OpenAI", "desc": "GPT-6 Astra Edition"},
    "gpt-6.2-sol": {"icon": "⬡", "color": C_AMBER, "family": "GPT", "vendor": "OpenAI", "desc": "GPT-6.2 Sol"},
    "gpt-6.2-astra": {"icon": "⬡", "color": C_AMBER, "family": "GPT", "vendor": "OpenAI", "desc": "GPT-6.2 Astra"},
    "gpt-6.1-sol": {"icon": "⬡", "color": C_AMBER, "family": "GPT", "vendor": "OpenAI", "desc": "GPT-6.1 Sol"},
    "gpt-6.1-terra": {"icon": "⬡", "color": C_AMBER, "family": "GPT", "vendor": "OpenAI", "desc": "GPT-6.1 Terra"},
    "gpt-5.6-sol": {"icon": "⬡", "color": (230, 160, 20), "family": "GPT", "vendor": "OpenAI", "desc": "GPT-5.6 Sol"},
    "gpt-5.6-luna": {"icon": "⬡", "color": (230, 160, 20), "family": "GPT", "vendor": "OpenAI", "desc": "GPT-5.6 Luna"},
    "gpt-5.6-terra": {"icon": "⬡", "color": (230, 160, 20), "family": "GPT", "vendor": "OpenAI", "desc": "GPT-5.6 Terra"},
    "gpt-image-2.6": {"icon": "⬡", "color": C_MUTED, "family": "GPT", "vendor": "OpenAI", "desc": "Генерация изображений"},

    # ◐ Семейство Moonshot Kimi
    "kimi-k3": {"icon": "◐", "color": C_GREEN, "family": "Kimi", "vendor": "Moonshot", "desc": "Kimi K3"},
    "kimi-k2.7-code": {"icon": "◐", "color": C_GREEN, "family": "Kimi", "vendor": "Moonshot", "desc": "Kimi кодер v2.7"},
    "kimi-k2.6": {"icon": "◐", "color": C_GREEN, "family": "Kimi", "vendor": "Moonshot", "desc": "Kimi K2.6"},

    # ⌬ Семейство Alibaba Qwen
    "qwen-4-max": {"icon": "⌬", "color": C_MAGENTA, "family": "Qwen", "vendor": "Alibaba", "desc": "Флагман Qwen 4 Max"},
    "qwen-3.8-max": {"icon": "⌬", "color": C_MAGENTA, "family": "Qwen", "vendor": "Alibaba", "desc": "Qwen 3.8 Max"},
    "qwen-3.8-flash-next": {"icon": "⌬", "color": C_MAGENTA, "family": "Qwen", "vendor": "Alibaba", "desc": "Qwen 3.8 Flash Next"},

    # ⊛ GLM / Grok / MiniMax / Другие
    "glm-5.3": {"icon": "⊛", "color": (56, 189, 248), "family": "GLM", "vendor": "Zhipu AI", "desc": "GLM 5.3 Аналитик"},
    "glm-5.3-flash": {"icon": "⊛", "color": (56, 189, 248), "family": "GLM", "vendor": "Zhipu AI", "desc": "GLM 5.3 Flash"},
    "grok-4.7": {"icon": "✕", "color": C_WHITE, "family": "Grok", "vendor": "xAI", "desc": "Grok 4.7 xAI"},
    "grok-4.6": {"icon": "✕", "color": C_WHITE, "family": "Grok", "vendor": "xAI", "desc": "Grok 4.6 xAI"},
    "grok-4.5": {"icon": "✕", "color": C_WHITE, "family": "Grok", "vendor": "xAI", "desc": "Grok 4.5 xAI"},
    "minimax-m3": {"icon": "⋈", "color": (245, 158, 11), "family": "MiniMax", "vendor": "MiniMax", "desc": "MiniMax M3 (1M контекст)"},
    "minimax-m3.1-flash": {"icon": "⋈", "color": (245, 158, 11), "family": "MiniMax", "vendor": "MiniMax", "desc": "MiniMax M3.1 Flash"},
    "mimo-v2.6-pro": {"icon": "◈", "color": C_MUTED, "family": "Mimo", "vendor": "Xiaomi", "desc": "Mimo Pro v2.6"},
    "mimo-v2.6-flash": {"icon": "◈", "color": C_MUTED, "family": "Mimo", "vendor": "Xiaomi", "desc": "Mimo Flash v2.6"},
    "muse-spark-1.3": {"icon": "◈", "color": C_MUTED, "family": "Other", "vendor": "Muse", "desc": "Muse Spark 1.3"},
    "muse-wonder": {"icon": "◈", "color": C_MUTED, "family": "Other", "vendor": "Muse", "desc": "Muse Wonder"},
    "nano-banana-2.1-ultra": {"icon": "◈", "color": C_MUTED, "family": "Other", "vendor": "Nano", "desc": "Nano Banana 2.1 Ultra"},
    "hy4-preview": {"icon": "◈", "color": C_MUTED, "family": "Other", "vendor": "HY", "desc": "HY4 Preview"},
    "codex-auto-review": {"icon": "⚙", "color": C_GREEN, "family": "Review", "vendor": "OpenAI", "desc": "Автоматический код-ревьюер"}
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
# АНИМАЦИИ: МНОГОПОТОЧНЫЙ SPINNER И ИЗОМЕТРИЧЕСКИЙ ЛОГОТИП
# ------------------------------------------------------------------------------
class ThinkingAnimation:
    """Плавная анимация мышления с вращением символов Braille и таймером."""
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.meta = MODEL_METADATA.get(model_name, {"icon": "◈", "color": C_CYAN})
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.start_t = time.time()

    def _spin(self):
        # 10 кадров плавной кинематографичной анимации точек Braille
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        idx = 0
        icon = rgb(*self.meta["color"], self.meta["icon"])
        while not self.stop_event.is_set():
            frame = gradient(frames[idx % len(frames)], C_VIOLET, C_CYAN)
            elapsed = time.time() - self.start_t
            status_text = f"\r  {icon} {rgb(*self.meta['color'], self.model_name)}  {frame}  {rgb(*C_MUTED, f'{elapsed:.1f}s')}  {gradient('Анализ задачи и планирование действий...', C_VIOLET, C_CYAN)}"
            sys.stdout.write(status_text)
            sys.stdout.flush()
            idx += 1
            time.sleep(0.08)

        # Очистка строки после завершения
        sys.stdout.write("\r" + " " * 85 + "\r")
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
    """Выводит кинематографический логотип Mind с градиентом."""
    logo = [
        "   ╭━╮╭━╮ ╭━━━╮ ╭━╮   ╭━╮ ╭━━━━╮",
        "   ┃ ┃┃ ┃ ╰╮ ╭╯ ┃  ╰╮ ┃ ┃ ┃ ╭╮ ┃",
        "   ┃ ╰╯ ┃  ┃ ┃  ┃ ╭╮╰╮┃ ┃ ┃ ┃┃ ┃",
        "   ┃ ╭╮ ┃  ┃ ┃  ┃ ┃╰╮ ┃ ┃ ┃ ┃┃ ┃",
        "   ┃ ┃┃ ┃ ╭╯ ╰╮ ┃ ┃ ╰╮  ┃ ┃ ╰╯ ┃",
        "   ╰━╯╰━╯ ╰━━━╯ ╰━╯  ╰━━╯ ╰━━━━╯"
    ]
    w = 80
    border = gradient("━" * w, C_VIOLET, C_CYAN)
    print(f"\n{border}")
    for col, line in enumerate(logo):
        print(gradient(line, C_VIOLET, C_CYAN))
    print(f"   {gradient('◆ M I N D // C L I', C_VIOLET, C_CYAN)}  {rgb(*C_MUTED, '•  AUTONOMOUS EXECUTIVE TERMINAL v2.5')}")
    print(f"   {rgb(*C_MUTED, 'Ecosystem: Mind')}  {rgb(*C_DARK, '│')}  {rgb(*C_CYAN, 'Tagir Iskaliev')}  {rgb(*C_DARK, '│')}  {rgb(*C_GREEN, '53 Structured Models Ready')}")
    print(f"{border}\n")


def render_hud(model: str, status: str = "ONLINE", step: int = 0):
    """Выводит статусную строку в индустриальном стиле."""
    meta = MODEL_METADATA.get(model, {"icon": "◈", "color": C_CYAN})
    icon = rgb(*meta["color"], meta["icon"])
    model_str = f"{icon} {rgb(*meta['color'], model)}"
    status_color = C_GREEN if "ONLINE" in status or "IDLE" in status else C_AMBER
    status_str = rgb(*status_color, f"● {status}")
    tokens_str = f"TOKENS:~{SESSION_STATS['total_tokens_est']}"
    step_str = f"STEP:{step}" if step > 0 else "READY"
    
    line = f" {status_str}  │  {model_str}  │  {rgb(*C_GREEN, 'SEC:1')}  │  {rgb(*C_MUTED, step_str)}  │  {rgb(*C_MUTED, tokens_str)} "
    box_border = rgb(*C_DARK, "─" * 78)
    print(f"{rgb(*C_DARK, '╭')}{box_border}{rgb(*C_DARK, '╮')}")
    print(f"{rgb(*C_DARK, '│')}{line:<96}{rgb(*C_DARK, '│')}")
    print(f"{rgb(*C_DARK, '╰')}{box_border}{rgb(*C_DARK, '╯')}")


def render_box(title: str, body: str, color: tuple[int, int, int] = C_CYAN):
    """Отрисовывает аккуратный блок с hairline-рамкой."""
    lines = body.strip().split("\n")
    header = f" {rgb(*color, '◈ ' + title)} "
    line_len = max(78 - len(title) - 6, 4)
    print(rgb(*C_DARK, "╭─") + header + rgb(*C_DARK, "─" * line_len + "╮"))
    for l in lines:
        print(f"{rgb(*C_DARK, '│')}  {l}")
    print(rgb(*C_DARK, "╰" + "─" * 78 + "╯"))


# ------------------------------------------------------------------------------
# СТРУКТУРИРОВАННЫЙ КАТАЛОГ: БЕЗ ХАОСА, ПО СЕМЕЙСТВАМ И ТИРАМ
# ------------------------------------------------------------------------------
# Упорядоченный список всех 53 моделей (Флагманы -> Семейства)
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

    # Семейство Anthropic Claude (14..22)
    "claude-sonnet-4-6",
    "claude-sonnet-5-5",
    "claude-haiku-5-5",
    "claude-opus-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-fable-5-2",
    "claude-fable-5-1",
    "claude-fable-5",

    # Семейство OpenAI GPT (23..32)
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

    # Семейство Kimi & Qwen (33..38)
    "kimi-k3",
    "kimi-k2.7-code",
    "kimi-k2.6",
    "qwen-4-max",
    "qwen-3.8-max",
    "qwen-3.8-flash-next",

    # Специализированные и другие (39..53)
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
    """Выводит логично сгруппированный каталог моделей с иконками и описаниями."""
    print(f"\n{rgb(*C_CYAN, '╭─ [АРХИТЕКТУРНЫЙ КАТАЛОГ МОДЕЛЕЙ SMARTAPI] ' + '─' * 33 + '╮')}")
    
    # Секция 1: 🏆 ФЛАГМАНЫ
    print(f"{rgb(*C_DARK, '│')}  {gradient('🏆 ТОП-6 ФЛАГМАНОВ ДЛЯ ЕЖЕДНЕВНОЙ РАБОТЫ:', C_VIOLET, C_CYAN)}")
    for i in range(6):
        m = ORDERED_MODEL_LIST[i]
        meta = MODEL_METADATA.get(m, {})
        idx_str = f"[{i+1:2d}]"
        icon_str = rgb(*meta["color"], meta["icon"])
        name_str = rgb(*meta["color"], bold(f"{m:<21}"))
        vendor_str = rgb(*C_MUTED, f"{meta.get('vendor', ''):<16}")
        desc_str = meta.get("desc", "")
        mark = rgb(*C_GREEN, "◀ ACTIVE") if m == current_model else ""
        print(f"{rgb(*C_DARK, '│')}    {rgb(*C_AMBER, idx_str)} {icon_str} {name_str} {vendor_str} {desc_str} {mark}")

    print(f"{rgb(*C_DARK, '├' + '─' * 78 + '┤')}")
    print(f"{rgb(*C_DARK, '│')}  {rgb(*C_WHITE, '📂 СЕМЕЙСТВА МОДЕЛЕЙ (сгруппированы по экосистемам):')}")

    # Семейства для красивого блочного вывода
    families = [
        ("✦ Google Gemini", ORDERED_MODEL_LIST[6:10], C_CYAN),
        ("⚡ DeepSeek AI", ORDERED_MODEL_LIST[10:13], C_INDIGO),
        ("❖ Anthropic Claude", ORDERED_MODEL_LIST[13:23], C_VIOLET),
        ("⬡ OpenAI GPT", ORDERED_MODEL_LIST[23:33], C_AMBER),
        ("◐ Kimi & ⌬ Qwen", ORDERED_MODEL_LIST[33:39], C_GREEN),
        ("⊛ GLM, Grok, MiniMax & Other", ORDERED_MODEL_LIST[39:], C_MUTED),
    ]

    for title, group, fam_color in families:
        print(f"{rgb(*C_DARK, '│')}")
        print(f"{rgb(*C_DARK, '│')}    {rgb(*fam_color, bold(title))}:")
        
        # Выводим в 2 аккуратные колонки с номерами
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
            print(f"{rgb(*C_DARK, '│')}      " + "    ".join(line_parts))

    print(f"{rgb(*C_DARK, '╰' + '─' * 78 + '╯')}\n")


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

            SESSION_STATS["total_tokens_est"] += len(ans) // 4
            return ans

    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        return f"[MIND HTTP {e.code}]: {err_body} (Попробуйте /model gemini)"
    except KeyboardInterrupt:
        return "[MIND: Запрос прерван пользователем (Ctrl+C)]"
    except Exception as e:
        return f"[MIND Ошибка связи]: {e} (Попробуйте /model gemini)"


def execute_mind_tools(text: str, guardian: ExecutionGuardian) -> tuple[bool, str]:
    actions = []

    # 1. PowerShell: ```powershell cmd ```
    for cmd in re.findall(r"```powershell\s*(.*?)\s*```", text, re.DOTALL):
        cmd_clean = cmd.strip()
        if not cmd_clean:
            continue

        is_loop, loop_msg = guardian.register_call("powershell", cmd_clean)
        if is_loop:
            render_box("LOOP BREAKER ВМЕШАТЕЛЬСТВО", loop_msg, C_RED)
            actions.append(loop_msg)
            continue

        render_box("POWERSHELL ВЫПОЛНЕНИЕ", cmd_clean, C_CYAN)
        SESSION_STATS["total_tools_executed"] += 1
        try:
            ps_script = f"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; {cmd_clean}"
            res = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                cwd=str(USER_HOME),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=90
            )
            raw_out = res.stdout
            if res.stderr:
                raw_out += "\n[Ошибки / Stderr]:\n" + res.stderr
            compressed = guardian.compress_output(raw_out)
            render_box("РЕЗУЛЬТАТ", compressed[:350] + ("..." if len(compressed) > 350 else ""), C_MUTED)
            actions.append(f"[Результат команды `{cmd_clean}`]:\n{compressed}")
        except subprocess.TimeoutExpired:
            actions.append(f"[Таймаут]: Команда `{cmd_clean}` выполнялась более 90 секунд.")
        except Exception as e:
            actions.append(f"[Ошибка команды]: {e}")

    # 2. Чтение файла: ```read_file path ```
    for r_path in re.findall(r"```read_file\s*(.*?)\s*```", text, re.DOTALL):
        path_str = r_path.strip().strip('"').strip("'")
        target_path = Path(path_str)
        if not target_path.is_absolute():
            target_path = PROJECT_DIR / target_path

        is_loop, loop_msg = guardian.register_call("read_file", path_str)
        if is_loop:
            actions.append(loop_msg)
            continue

        render_box("ЧТЕНИЕ ФАЙЛА", str(target_path), C_BLUE)
        SESSION_STATS["total_tools_executed"] += 1
        try:
            if target_path.exists():
                content = target_path.read_text(encoding="utf-8", errors="replace")
                compressed = guardian.compress_output(content, max_chars=4000)
                actions.append(f"[Файл {target_path.name}]:\n{compressed}")
            else:
                actions.append(f"[Ошибка]: Файл {target_path} не существует.")
        except Exception as e:
            actions.append(f"[Ошибка чтения {path_str}]: {e}")

    # 3. Запись файла: ```write_file:path ... ```
    for w_path, w_content in re.findall(r"```write_file:([^\n\r]+)[\r\n]+(.*?)```", text, re.DOTALL):
        path_str = w_path.strip().strip('"').strip("'")
        target_path = Path(path_str)
        if not target_path.is_absolute():
            target_path = PROJECT_DIR / target_path

        render_box("ЗАПИСЬ ФАЙЛА", f"{target_path} ({len(w_content)} симв.)", C_GREEN)
        SESSION_STATS["total_tools_executed"] += 1
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(w_content.strip() + "\n", encoding="utf-8")
            actions.append(f"[Успешно]: Файл {target_path} сохранён.")
        except Exception as e:
            actions.append(f"[Ошибка записи файла {path_str}]: {e}")

    # 4. Браузер / Поиск: ```browser url_or_query ```
    for b_item in re.findall(r"```browser\s*(.*?)\s*```", text, re.DOTALL):
        target = b_item.strip()
        if not target.startswith("http://") and not target.startswith("https://"):
            url = f"https://www.google.com/search?q={urllib.parse.quote_plus(target)}"
            render_box("ПОИСК В СЕТИ", target, C_CYAN)
        else:
            url = target
            render_box("ОТКРЫТИЕ ССЫЛКИ", url, C_CYAN)
        try:
            webbrowser.open(url)
            actions.append(f"[Браузер]: Открыта страница {url}")
        except Exception as e:
            actions.append(f"[Ошибка браузера]: {e}")

    # 5. Проводник: ```open_folder path ```
    for f_path in re.findall(r"```open_folder\s*(.*?)\s*```", text, re.DOTALL):
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

    try:
        user_choice = input(f"{gradient('◆ ВЫБОР МОДЕЛИ', C_VIOLET, C_CYAN)} [1-{len(ORDERED_MODEL_LIST)}] (Enter = {DEFAULT_MODEL}): ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nЗавершение.")
        return

    current_model = resolve_model(user_choice, default=DEFAULT_MODEL)
    meta = MODEL_METADATA.get(current_model, {"icon": "◈", "color": C_CYAN})
    icon = rgb(*meta["color"], meta["icon"])

    print(f"\n{rgb(*C_GREEN, '✔')} Интеллект активирован: {icon} {gradient(current_model, meta['color'], C_CYAN)}\n")
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
            prompt_str = f"{gradient('MIND', C_VIOLET, C_CYAN)} [{m_icon} {rgb(*cur_meta['color'], current_model)}] ❯ "
            user_input = input(prompt_str).strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{rgb(*C_MUTED, 'Сессия Mind CLI завершена.')}")
            break

        if not user_input:
            continue

        cmd_lower = user_input.lower()

        if cmd_lower in ("exit", "quit", "q", "/exit"):
            print(f"\n{rgb(*C_CYAN, '◆ До связи, Тагир. Сессия Mind CLI закрыта.')}")
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
                new_meta = MODEL_METADATA.get(current_model, {"icon": "◈", "color": C_CYAN})
                n_icon = rgb(*new_meta["color"], new_meta["icon"])
                print(f"{rgb(*C_GREEN, '✔ Интеллект переключен на:')} {n_icon} {gradient(current_model, new_meta['color'], C_CYAN)}\n")
                render_hud(current_model, status="ONLINE")
            else:
                print(f"Текущая модель: {current_model}. Наберите /models для вывода каталога.\n")
            continue

        # ReAct выполнение задачи
        conversation.append({"role": "user", "content": user_input})
        start_t = time.time()

        try:
            answer = mind_turn(conversation, model=current_model, guardian=guardian)
        except KeyboardInterrupt:
            answer = "[MIND: Выполнение задачи остановлено пользователем (Ctrl+C)]"

        elapsed = time.time() - start_t
        conversation.append({"role": "assistant", "content": answer})

        print()
        render_box(f"ОТВЕТ АССИСТЕНТА  ({elapsed:.1f}s)", answer, C_VIOLET)
        render_hud(current_model, status="IDLE")
        print()


if __name__ == "__main__":
    main()
