#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M I N D // C L I  —  AUTONOMOUS EXECUTIVE TERMINAL
================================================================================
Разработано для Тагира Искалиева // Экосистема Mind
Эстетика: Teenage Engineering • Apple • Anduril Industrial HUD
Движок: SmartAPI (53 модели) • Zero-Dependency • 24-bit TrueColor
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
import time
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any, Optional

# Включение 24-bit TrueColor и ANSI VT100 в Windows Terminal / CMD / PowerShell
os.system("")

# ------------------------------------------------------------------------------
# ФИРМЕННАЯ ПАЛИТРА MIND (24-bit TrueColor RGB)
# ------------------------------------------------------------------------------
C_VIOLET = (123, 47, 247)   # #7B2FF7
C_INDIGO = (75, 59, 255)    # #4B3BFF
C_BLUE   = (30, 144, 255)   # #1E90FF
C_CYAN   = (0, 245, 255)    # #00F5FF (Emissive Accent)
C_WHITE  = (240, 244, 255)  # Crisp White
C_MUTED  = (145, 155, 180)  # Muted Slate
C_DARK   = (40, 45, 65)     # Hairline Border
C_SURF   = (16, 18, 28)     # Dark Surface
C_GREEN  = (0, 230, 153)    # Success Emerald
C_AMBER  = (255, 175, 0)    # Warning Amber
C_RED    = (255, 75, 90)    # Error Crimson


def rgb(r: int, g: int, b: int, text: str) -> str:
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"


def bg_rgb(r: int, g: int, b: int, text: str) -> str:
    return f"\033[48;2;{r};{g};{b}m{text}\033[0m"


def bold(text: str) -> str:
    return f"\033[1m{text}\033[0m"


def dim(text: str) -> str:
    return f"\033[2m{text}\033[0m"


def gradient(text: str, c1: tuple[int, int, int] = C_VIOLET, c2: tuple[int, int, int] = C_CYAN) -> str:
    """Генерирует плавный 24-битный цветовой градиент по тексту."""
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
# СИСТЕМНЫЕ ПУТИ И SSL
# ------------------------------------------------------------------------------
USER_HOME = Path(os.path.expanduser("~"))
DESKTOP_DIR = USER_HOME / "Desktop"
PROJECT_DIR = Path(__file__).resolve().parent.parent

# Обход корпоративного SSL-прокси (SECLEVEL=1)
SSL_CTX = ssl._create_unverified_context()
try:
    SSL_CTX.set_ciphers("DEFAULT:@SECLEVEL=1")
except Exception:
    pass

DEFAULT_API_KEY = os.getenv("SMARTAPI_KEY", "sk-smart-J6NAKcsgKoJ_tfaOrfapSY14L1W8us5GR4ZZ3FwPIO8")
DEFAULT_BASE_URL = os.getenv("SMARTAPI_BASE_URL", "https://smartapi.pro/v1").rstrip("/")
DEFAULT_MODEL = "gemini-3.8-flash"

FALLBACK_MODELS = [
    "claude-fable-5", "claude-fable-5-1", "claude-fable-5-2", "claude-haiku-5-5",
    "claude-opus-4-6", "claude-opus-4-7", "claude-opus-4-8", "claude-opus-5",
    "claude-opus-5-5", "claude-sonnet-4-6", "claude-sonnet-5", "claude-sonnet-5-5",
    "codex-auto-review", "deepseek-v4-flash", "deepseek-v4-flash-uncensored",
    "deepseek-v4-pro", "deepseek-v4.1-flash", "gemini-3.1-pro", "gemini-3.1-pro-preview",
    "gemini-3.8-flash", "gemini-4-argon", "gemini-4-carbon", "glm-5.3",
    "glm-5.3-flash", "gpt-5.6-luna", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-6-astra",
    "gpt-6-luna", "gpt-6-sol", "gpt-6.1-sol", "gpt-6.1-terra", "gpt-6.2-astra",
    "gpt-6.2-sol", "gpt-image-2.6", "grok-4.5", "grok-4.6", "grok-4.7",
    "hy4-preview", "kimi-k2.6", "kimi-k2.7-code", "kimi-k3", "kimi-k3.1-pro",
    "mimo-v2.6-flash", "mimo-v2.6-pro", "minimax-m3", "minimax-m3.1-flash",
    "muse-spark-1.3", "muse-wonder", "nano-banana-2.1-ultra", "qwen-3.8-flash-next",
    "qwen-3.8-max", "qwen-4-max"
]

# Статистика сессии
SESSION_STATS = {
    "total_requests": 0,
    "total_tokens_est": 0,
    "total_tools_executed": 0,
    "loops_intercepted": 0,
    "start_time": time.time()
}


# ------------------------------------------------------------------------------
# UI КОМПОНЕНТЫ И РЕНДЕРЕР ТЕРМИНАЛА
# ------------------------------------------------------------------------------
def get_term_width() -> int:
    try:
        return min(shutil.get_terminal_size((80, 24)).columns, 90)
    except Exception:
        return 80


def render_banner():
    """Выводит флагманский баннер в эстетике Teenage Engineering / Mind."""
    w = get_term_width()
    line = "━" * w
    print(gradient(line, C_VIOLET, C_CYAN))
    print(f"  {gradient('◆ M I N D // C L I', C_VIOLET, C_CYAN)}  {rgb(*C_MUTED, '•  AUTONOMOUS EXECUTIVE TERMINAL')}")
    print(f"  {rgb(*C_MUTED, 'Ecosystem: Mind 2.4')}  {rgb(*C_DARK, '│')}  {rgb(*C_CYAN, 'Tagir Iskaliev')}  {rgb(*C_DARK, '│')}  {rgb(*C_GREEN, '53 Models Ready')}")
    print(gradient(line, C_INDIGO, C_BLUE))


def render_hud(model: str, status: str = "ONLINE", step: int = 0):
    """Выводит компактную статусную строку оборудования и ИИ."""
    w = get_term_width()
    sec_status = rgb(*C_GREEN, "SEC:1")
    stat_color = C_GREEN if status == "ONLINE" else C_AMBER
    status_str = rgb(*stat_color, f"● {status}")
    model_str = rgb(*C_CYAN, model)
    step_str = f"STEP:{step}" if step > 0 else "READY"
    tokens_str = f"TOKENS:~{SESSION_STATS['total_tokens_est']}"
    
    hud_content = f" {status_str}  │  {model_str}  │  {sec_status}  │  {rgb(*C_MUTED, step_str)}  │  {rgb(*C_MUTED, tokens_str)} "
    border = rgb(*C_DARK, "─" * (w - 2))
    print(f"{rgb(*C_DARK, '╭')}{border}{rgb(*C_DARK, '╮')}")
    print(f"{rgb(*C_DARK, '│')}{hud_content:<{w+20}}{rgb(*C_DARK, '│')}")
    print(f"{rgb(*C_DARK, '╰')}{border}{rgb(*C_DARK, '╯')}")


def render_box(title: str, body: str, color: tuple[int, int, int] = C_CYAN):
    """Отрисовывает аккуратный блок с hairline-рамкой."""
    w = get_term_width()
    body_lines = body.strip().split("\n")
    
    header = f" {rgb(*color, '◈ ' + title)} "
    line_len = max(w - len(title) - 6, 4)
    top_line = rgb(*C_DARK, "╭─") + header + rgb(*C_DARK, "─" * line_len + "╮")
    print(top_line)
    
    for l in body_lines:
        print(f"{rgb(*C_DARK, '│')}  {l}")
        
    print(f"{rgb(*C_DARK, '╰' + '─' * (w - 2) + '╯')}")


def render_models_catalog(models: list[str], current: str = DEFAULT_MODEL):
    """Интерактивная витрина всех моделей с категориями."""
    w = get_term_width()
    print(f"\n{rgb(*C_CYAN, '╭─ [КАТАЛОГ ИНТЕЛЛЕКТУАЛЬНЫХ МОДЕЛЕЙ SMARTAPI] ' + '─' * (w - 47) + '╮')}")
    print(f"{rgb(*C_DARK, '│')}  {rgb(*C_AMBER, '🔥 РЕКОМЕНДУЕМЫЕ ДЛЯ БЫСТРОГО СТАРТА:')}")
    print(f"{rgb(*C_DARK, '│')}    {rgb(*C_CYAN, '[20] gemini-3.8-flash')}    — Сверхбыстрый, безлимитный, нулевой оверхед (Default)")
    print(f"{rgb(*C_DARK, '│')}    {rgb(*C_CYAN, '[16] deepseek-v4-pro')}     — Профессионал для PowerShell, кода и отладки")
    print(f"{rgb(*C_DARK, '│')}    {rgb(*C_CYAN, '[11] claude-sonnet-5')}     — Новейший интеллект Claude Sonnet 5")
    print(f"{rgb(*C_DARK, '│')}    {rgb(*C_CYAN, '[ 9] claude-opus-5-5')}     — Архитектурный синтез высокой сложности")
    print(f"{rgb(*C_DARK, '│')}    {rgb(*C_CYAN, '[43] kimi-k3.1-pro')}       — Анализ огромных документов и массивов")
    print(f"{rgb(*C_DARK, '│')}    {rgb(*C_CYAN, '[30] gpt-6-sol')}           — Флагман следующего поколения GPT-6")
    print(f"{rgb(*C_DARK, '├' + '─' * (w - 2) + '┤')}")
    print(f"{rgb(*C_DARK, '│')}  {rgb(*C_WHITE, f'ВСЕ ДОСТУПНЫЕ МОДЕЛИ ({len(models)} шт.):')}")
    
    cols = 3
    for i in range(0, len(models), cols):
        chunk = models[i:i + cols]
        parts = []
        for j, m in enumerate(chunk):
            idx = i + j + 1
            is_active = (m == current)
            badge_color = C_GREEN if is_active else C_AMBER
            idx_str = f"[{idx:2d}]"
            name_str = m[:20]
            if is_active:
                parts.append(f"{rgb(*badge_color, idx_str)} {rgb(*C_GREEN, bold(name_str)):<22}")
            else:
                parts.append(f"{rgb(*badge_color, idx_str)} {rgb(*C_WHITE, name_str):<22}")
        line_str = "    ".join(parts)
        print(f"{rgb(*C_DARK, '│')}  {line_str}")
        
    print(f"{rgb(*C_DARK, '╰' + '─' * (w - 2) + '╯')}\n")


# ------------------------------------------------------------------------------
# АНТИ-ЗАЦИКЛИВАНИЕ И ЗАЩИТА ТОКЕНОВ (LOOP BREAKER & TOKEN GUARDIAN)
# ------------------------------------------------------------------------------
class ExecutionGuardian:
    """
    Защищает от бесконечных циклов, повтора одинаковых ошибок
    и паразитного расхода токенов.
    """
    def __init__(self):
        self.call_history: list[str] = []
        self.output_history: list[str] = []
        self.repeat_counts: dict[str, int] = {}

    def register_call(self, tool_name: str, payload: str) -> tuple[bool, str]:
        """
        Проверяет, не зациклилась ли модель на одном действии.
        Возвращает (is_loop, message).
        """
        sig = hashlib.md5(f"{tool_name}:{payload.strip()}".encode("utf-8")).hexdigest()
        count = self.repeat_counts.get(sig, 0) + 1
        self.repeat_counts[sig] = count

        if count >= 2:
            SESSION_STATS["loops_intercepted"] += 1
            return True, (
                f"[⚡ LOOP BREAKER INTERCEPT]: Обнаружен повторный вызов `{tool_name}` с идентичными параметрами!\n"
                f"Модели ЗАПРЕЩЕНО повторять одно и то же действие. Немедленно смени стратегию, "
                f"используй другой подход или переходи к формированию финального отчёта."
            )
        return False, ""

    def compress_output(self, out: str, max_chars: int = 2400) -> str:
        """
        Умное сжатие вывода: сохраняет начало (контекст) и конец (ошибки/результат),
        отсекая середину, чтобы не раздувать контекст до сотен тысяч токенов.
        """
        clean = out.strip()
        if not clean:
            return "(Успешно выполнено, вывод пуст)"
        if len(clean) <= max_chars:
            return clean

        head = clean[:1200]
        tail = clean[-1200:]
        omitted = len(clean) - 2400
        return f"{head}\n\n... [MIND GUARDIAN: пропущено {omitted} символов повторяющегося вывода] ...\n\n{tail}"


# ------------------------------------------------------------------------------
# ВЫЗОВ SMARTAPI И СЕТЕВОЙ СЛОЙ
# ------------------------------------------------------------------------------
def fetch_smartapi_models(api_key: str = DEFAULT_API_KEY) -> list[str]:
    url = f"{DEFAULT_BASE_URL}/models"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(req, timeout=8, context=SSL_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = sorted([m["id"] for m in data.get("data", []) if "id" in m])
            if models:
                return models
    except Exception:
        pass
    return sorted(FALLBACK_MODELS)


def call_smartapi(messages: list[dict], model: str, api_key: str = DEFAULT_API_KEY) -> str:
    """Выполняет вызов модели с защитой от пустых ответов и таймаутов."""
    url = f"{DEFAULT_BASE_URL}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 16384,  # Полный размер генерации без искусственных лимитов
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
    # Оценка токенов на входе
    in_tokens = sum(len(m.get("content", "")) // 4 for m in messages)
    SESSION_STATS["total_tokens_est"] += in_tokens

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
                ans = f"[MIND ERROR: Модель {model} вернула пустой контент (finish_reason='{finish_reason}'). Переключитесь на /model gemini]"

            SESSION_STATS["total_tokens_est"] += len(ans) // 4
            return ans

    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        return f"[MIND HTTP {e.code}]: {err_body} (Рекомендуется переключиться на /model gemini)"
    except KeyboardInterrupt:
        return "[MIND: Запрос прерван пользователем (Ctrl+C)]"
    except Exception as e:
        return f"[MIND Сбой связи]: {e} (Попробуйте /model gemini)"


# ------------------------------------------------------------------------------
# АВТОНОМНЫЕ ИНСТРУМЕНТЫ (MIND EXECUTOR)
# ------------------------------------------------------------------------------
def execute_mind_tools(text: str, guardian: ExecutionGuardian) -> tuple[bool, str]:
    """Исполняет инструменты, вызванные моделью, с контролем циклов."""
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
            render_box("РЕЗУЛЬТАТ ВЫПОЛНЕНИЯ", compressed[:400] + ("..." if len(compressed) > 400 else ""), C_MUTED)
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
        render_box("ОТКРЫТИЕ ПРОВОДНИКА", str(folder), C_INDIGO)
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
    """
    Автономный ReAct-цикл Mind CLI:
    Решает задачу до 6 автономных шагов. Защищён от зацикливания и раздувания токенов.
    """
    max_steps = 6
    for step in range(1, max_steps + 1):
        # Sliding Window Context Pruning: System Prompt + последние 14 сообщений
        if len(conversation) > 16:
            active_conv = [conversation[0]] + conversation[-14:]
        else:
            active_conv = conversation

        render_hud(model, status=f"THINKING // STEP {step}", step=step)
        reply = call_smartapi(active_conv, model=model, api_key=api_key)

        if not reply or not str(reply).strip():
            return f"[MIND: Пустой ответ модели {model}. Рекомендуется сменить модель через /models]"

        has_tools, tool_out = execute_mind_tools(reply, guardian)
        if has_tools:
            conversation.append({"role": "assistant", "content": reply})
            conversation.append({
                "role": "user",
                "content": (
                    f"{tool_out}\n\n"
                    f"[ИНСТРУКЦИЯ ДЛЯ МОДЕЛИ]: Продолжай автономное решение задачи. "
                    f"Если требуются дальнейшие команды или правка файлов — вызывай их сейчас. "
                    f"Если задача решена — выдай итоговый структурированный отчёт: ЧТО СДЕЛАНО, РЕЗУЛЬТАТ."
                )
            })
        else:
            # Модель закончила инструменты и выдала финальный ответ
            return reply

    return reply


# ------------------------------------------------------------------------------
# СИСТЕМНЫЙ ПРОМПТ В СТИЛЕ MIND EXECUTIVE
# ------------------------------------------------------------------------------
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
   - ⚡ СЛЕДУЮЩИЙ ШАГ (ссылка или готовый статус)

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
# ГЛАВНЫЙ ИНТЕРАКТИВНЫЙ ЦИКЛ (MIND REPL)
# ------------------------------------------------------------------------------
def main():
    render_banner()
    models = fetch_smartapi_models()
    render_models_catalog(models, current=DEFAULT_MODEL)

    try:
        user_choice = input(f"{gradient('◆ ВЫБОР МОДЕЛИ', C_VIOLET, C_CYAN)} [1-{len(models)}] (Enter = {DEFAULT_MODEL}): ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nЗавершение.")
        return

    # Разрешение модели
    current_model = DEFAULT_MODEL
    if user_choice.isdigit():
        idx = int(user_choice) - 1
        if 0 <= idx < len(models):
            current_model = models[idx]
    elif user_choice:
        for m in models:
            if user_choice.lower() in m.lower():
                current_model = m
                break

    print(f"\n{rgb(*C_GREEN, '✔')} Активный интеллект: {gradient(current_model, C_CYAN, C_BLUE)}\n")
    render_hud(current_model, status="ONLINE")

    guardian = ExecutionGuardian()
    conversation = [
        {"role": "system", "content": build_mind_system_prompt()}
    ]

    print(f"{rgb(*C_MUTED, 'Команды:')} {rgb(*C_CYAN, '/models')} {rgb(*C_MUTED, '•')} {rgb(*C_CYAN, '/model <имя/номер>')} {rgb(*C_MUTED, '•')} {rgb(*C_CYAN, '/sys')} {rgb(*C_MUTED, '•')} {rgb(*C_CYAN, '/desktop')} {rgb(*C_MUTED, '•')} {rgb(*C_CYAN, '/clear')} {rgb(*C_MUTED, '•')} {rgb(*C_CYAN, 'exit')}\n")

    while True:
        try:
            prompt_str = f"{gradient('MIND', C_VIOLET, C_CYAN)} [{rgb(*C_MUTED, current_model)}] ❯ "
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
            render_models_catalog(models, current=current_model)
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
            # Быстрый аппаратный срез
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
                arg = parts[1].strip()
                if arg.isdigit():
                    idx = int(arg) - 1
                    if 0 <= idx < len(models):
                        current_model = models[idx]
                else:
                    for m in models:
                        if arg.lower() in m.lower():
                            current_model = m
                            break
                print(f"{rgb(*C_GREEN, '✔ Интеллект переключен на:')} {gradient(current_model, C_CYAN, C_BLUE)}\n")
                render_hud(current_model, status="ONLINE")
            else:
                print(f"Текущая модель: {current_model}. Наберите /models для выбора.\n")
            continue

        # Передача запроса в ReAct цикл
        conversation.append({"role": "user", "content": user_input})
        start_t = time.time()

        try:
            answer = mind_turn(conversation, model=current_model, guardian=guardian)
        except KeyboardInterrupt:
            answer = "[MIND: Выполнение задачи остановлено пользователем (Ctrl+C)]"

        elapsed = time.time() - start_t
        conversation.append({"role": "assistant", "content": answer})

        # Финальный красивый вывод ответа
        print()
        render_box(f"ОТВЕТ АССИСТЕНТА  ({elapsed:.1f}s)", answer, C_VIOLET)
        render_hud(current_model, status="IDLE")
        print()


if __name__ == "__main__":
    main()
