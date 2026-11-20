#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MIND UNIVERSAL PC & WINDOWS AI ASSISTANT // АО «ИНТЕРГАЗ ЦЕНТРАЛЬНАЯ АЗИЯ»
Универсальный автономный ИИ-помощник для ПК: управление файлами, автоматизация рутины,
PowerShell-скрипты, системная диагностика, открытие ссылок и решение задач «под ключ».
Подключение: SmartAPI шлюз (53 модели, снятый лимит токенов 16K).
"""
from __future__ import annotations

import json
import os
import re
import ssl
import subprocess
import sys
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

# SSL Context для обхода корпоративных прокси и слабых ключей (EE certificate key too weak)
SSL_CTX = ssl._create_unverified_context()
try:
    SSL_CTX.set_ciphers('DEFAULT:@SECLEVEL=1')
except Exception:
    pass

# Корневые директории системы пользователя
USER_HOME = Path(os.path.expanduser("~"))
DESKTOP_DIR = USER_HOME / "Desktop"
DOCUMENTS_DIR = USER_HOME / "Documents"
DOWNLOADS_DIR = USER_HOME / "Downloads"
PROJECT_DIR = Path(__file__).resolve().parent.parent

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

# ANSI цвета терминала
os.system("")
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_MAGENTA = "\033[95m"
CLR_GRAY = "\033[90m"
CLR_WHITE = "\033[97m"
CLR_RED = "\033[91m"
CLR_BLUE = "\033[94m"
CLR_RESET = "\033[0m"


def fetch_available_models(api_key: str = DEFAULT_API_KEY) -> list[str]:
    """Получает актуальный список моделей со SmartAPI."""
    url = f"{DEFAULT_BASE_URL}/models"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = sorted([m["id"] for m in data.get("data", []) if "id" in m])
            if models:
                return models
    except Exception:
        pass
    return sorted(FALLBACK_MODELS)


def print_models_table(models: list[str], current_model: str = DEFAULT_MODEL):
    """Выводит список моделей с номерами."""
    print(f"\n{CLR_CYAN}------------------------------------------------------------------------{CLR_RESET}")
    print(f"{CLR_GREEN}🔥 РЕКОМЕНДУЕМЫЕ МОДЕЛИ ДЛЯ ЗАДАЧ ПК И WINDOWS:{CLR_RESET}")
    print(f"  {CLR_CYAN}gemini-3.8-flash{CLR_RESET}   — Сверхбыстрый помощник без лимитов токенов (по умолчанию)")
    print(f"  {CLR_CYAN}deepseek-v4-pro{CLR_RESET}    — Лидер по написанию PowerShell-скриптов и сложной логике")
    print(f"  {CLR_CYAN}claude-sonnet-5{CLR_RESET}    — Новейший интеллектуальный аналитик Claude Sonnet 5")
    print(f"  {CLR_CYAN}claude-opus-5-5{CLR_RESET}    — Глубокий анализ сложных системных задач")
    print(f"  {CLR_CYAN}kimi-k3.1-pro{CLR_RESET}      — Обработка огромных файлов и массивов данных")
    print(f"  {CLR_CYAN}gpt-6-sol{CLR_RESET}          — Флагман линейки GPT-6")
    print(f"{CLR_CYAN}------------------------------------------------------------------------{CLR_RESET}")
    print(f"{CLR_WHITE}📋 ВСЕ ДОСТУПНЫЕ МОДЕЛИ SMARTAPI (всего: {len(models)}):{CLR_RESET}")

    cols = 3
    for i in range(0, len(models), cols):
        chunk = models[i:i + cols]
        parts = []
        for j, m in enumerate(chunk):
            idx = i + j + 1
            mark = "*" if m == current_model else " "
            parts.append(f"{CLR_YELLOW}[{idx:2d}]{CLR_RESET}{mark}{CLR_WHITE}{m:<23}{CLR_RESET}")
        print("  " + "  ".join(parts))
    print(f"{CLR_CYAN}------------------------------------------------------------------------{CLR_RESET}\n")


def resolve_model(choice: str, models: list[str], default: str = DEFAULT_MODEL) -> str:
    """Разрешает выбор модели по номеру, псевдониму или подстроке."""
    clean = choice.strip().lower()
    if not clean:
        return default

    if clean.isdigit():
        idx = int(clean) - 1
        if 0 <= idx < len(models):
            return models[idx]

    aliases = {
        "gemini": "gemini-3.8-flash",
        "flash": "gemini-3.8-flash",
        "deepseek": "deepseek-v4-pro",
        "deepseek-flash": "deepseek-v4.1-flash",
        "opus": "claude-opus-5-5",
        "sonnet": "claude-sonnet-5",
        "kimi": "kimi-k3.1-pro",
        "gpt": "gpt-6-sol",
        "qwen": "qwen-4-max"
    }
    if clean in aliases and aliases[clean] in models:
        return aliases[clean]

    for m in models:
        if m.lower() == clean:
            return m

    matches = [m for m in models if clean in m.lower()]
    if matches:
        return matches[0]

    return default


def build_system_prompt() -> str:
    return f"""ТЫ — УНИВЕРСАЛЬНЫЙ АВТОНОМНЫЙ ИИ-АССИСТЕНТ ПК И WINDOWS ДЛЯ ТАГИРА ИСКАЛИЕВА.
ТВОЯ ЗАДАЧА — РЕШАТЬ ЛЮБЫЕ ЗАДАЧИ НА КОМПЬЮТЕРЕ «ПОД КЛЮЧ»:
- Управление файлами и папками (поиск, чтение, создание, сортировка, архивирование, очистка).
- Написание и выполнение скриптов автоматизации рутины (PowerShell, Batch, Python).
- Диагностика системы, дисков, сетей, процессов Windows.
- Поиск информации, открытие веб-страниц, документов и приложений.

ОСНОВНЫЕ ПУТИ В СИСТЕМЕ:
- Домашняя папка пользователя: {USER_HOME}
- Рабочий стол (Desktop): {DESKTOP_DIR}
- Загрузки (Downloads): {DOWNLOADS_DIR}
- Документы (Documents): {DOCUMENTS_DIR}
- Рабочая папка проекта: {PROJECT_DIR}

ЖЕЛЕЗНЫЕ ПРАВИЛА АВТОНОМНОГО ИСПОЛНЕНИЯ (ДЕЙСТВУЙ, А НЕ СПРАШИВАЙ):
1. ПОЛЬЗОВАТЕЛЬ — РУКОВОДИТЕЛЬ. Он ставит задачу и ждёт ГОТОВЫЙ РЕЗУЛЬТАТ, а не промежуточные вопросы.
2. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО писать:
   - «Сказать, чтобы я исправил?», «Жду вашего разрешения», «Напишите мне подтверждение», «Как мне поступить?».
   - Ограничиваться пустыми теоретическими советами вместо реальных действий.
3. ОБЯЗАТЕЛЬНО:
   - Если нужно выполнить системное действие или найти файлы — СРАЗУ выдавай блок ```powershell```.
   - Если нужно создать или отредактировать файл/скрипт — СРАЗУ выдавай блок ```write_file:путь``` с полным содержимым.
   - Если нужно прочитать содержимое файла — СРАЗУ выдавай блок ```read_file```.
   - Если нужно открыть папку в Проводнике — используй ```open_folder``` или ```powershell explorer.exe "путь"```.
   - Если нужно открыть ссылку или найти что-то в сети — используй ```browser```.
   - Если возникла ошибка — САМ проанализируй причину и примени альтернативный путь решения.
4. ФИНАЛЬНЫЙ ОТВЁТ:
   - ✅ ЧТО СДЕЛАНО: список конкретных действий.
   - 📊 РЕЗУЛЬТАТ: статус, созданные файлы, найденная информация.
   - 🚀 СЛЕДУЮЩИЙ ШАГ: как открыть/проверить (если применимо).
   Отвечай на чистом, понятном русском языке без лишней воды.

ИНСТРУМЕНТЫ (вызывай их прямо в тексте ответа):

1. Выполнить команду в PowerShell:
```powershell
команда_powershell
```

2. Прочитать файл:
```read_file
полный_или_относительный_путь
```

3. Записать файл на диск:
```write_file:путь
содержимое
```

4. Открыть страницу в браузере или поисковый запрос:
```browser
https://google.com или поисковый запрос
```

5. Открыть папку в Проводнике Windows:
```open_folder
путь_к_папке
```"""


def call_smartapi(messages: list[dict], model: str, api_key: str = DEFAULT_API_KEY) -> str:
    """Отправляет запрос в SmartAPI без искусственного занижения лимитов."""
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
    try:
        with urllib.request.urlopen(req, timeout=120, context=SSL_CTX) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            choice = res_data.get("choices", [{}])[0]
            message = choice.get("message", {})
            content = message.get("content")
            reasoning = message.get("reasoning_content")

            if content and str(content).strip():
                return str(content).strip()
            if reasoning and str(reasoning).strip():
                return str(reasoning).strip()

            finish_reason = choice.get("finish_reason", "unknown")
            return f"[Внимание: Модель {model} вернула пустой ответ (finish_reason='{finish_reason}'). Переключитесь на /model gemini]"
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        return f"[SmartAPI HTTP {e.code}]: {err_body} (Попробуйте /model gemini)"
    except KeyboardInterrupt:
        return "[Запрос прерван пользователем (Ctrl+C)]"
    except Exception as e:
        return f"[SmartAPI Ошибка]: {e} (Попробуйте /model gemini)"


def execute_tools(text: str) -> tuple[bool, str]:
    """Сканирует ответ модели на вызовы инструментов и исполняет их в Windows."""
    actions = []

    # 1. Браузер / Поиск: ```browser url_or_query ```
    for match in re.findall(r"```browser\s*(.*?)\s*```", text, re.DOTALL):
        target = match.strip()
        if not target.startswith("http://") and not target.startswith("https://"):
            url = f"https://www.google.com/search?q={urllib.parse.quote_plus(target)}"
            print(f"\n{CLR_YELLOW}[Инструмент]{CLR_RESET} Поиск в Google: {CLR_CYAN}{target}{CLR_RESET}")
        else:
            url = target
            print(f"\n{CLR_YELLOW}[Инструмент]{CLR_RESET} Открытие ссылки: {CLR_CYAN}{url}{CLR_RESET}")
        try:
            webbrowser.open(url)
            actions.append(f"[Браузер]: Открыта страница {url}")
        except Exception as e:
            actions.append(f"[Ошибка браузера]: {e}")

    # 2. Открытие папки: ```open_folder path ```
    for match in re.findall(r"```open_folder\s*(.*?)\s*```", text, re.DOTALL):
        folder_str = match.strip().strip('"').strip("'")
        folder_path = Path(folder_str)
        if not folder_path.is_absolute():
            folder_path = USER_HOME / folder_path
        print(f"\n{CLR_YELLOW}[Инструмент]{CLR_RESET} Открытие папки: {CLR_CYAN}{folder_path}{CLR_RESET}")
        try:
            if folder_path.exists():
                subprocess.Popen(["explorer.exe", str(folder_path)])
                actions.append(f"[Проводник]: Открыта папка {folder_path}")
            else:
                actions.append(f"[Ошибка]: Папка {folder_path} не найдена.")
        except Exception as e:
            actions.append(f"[Ошибка открытия папки]: {e}")

    # 3. Чтение файла: ```read_file path ```
    for match in re.findall(r"```read_file\s*(.*?)\s*```", text, re.DOTALL):
        path_str = match.strip().strip('"').strip("'")
        file_path = Path(path_str)
        if not file_path.is_absolute():
            file_path = PROJECT_DIR / file_path
        print(f"\n{CLR_YELLOW}[Инструмент]{CLR_RESET} Чтение файла: {CLR_CYAN}{file_path}{CLR_RESET}")
        try:
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8", errors="replace")
                if len(content) > 5000:
                    content_preview = content[:5000] + f"\n... [файл обрезан для экономии: всего {len(content)} символов]"
                else:
                    content_preview = content
                actions.append(f"[Содержимое файла {file_path.name}]:\n{content_preview}")
            else:
                actions.append(f"[Ошибка]: Файл {file_path} не существует.")
        except Exception as e:
            actions.append(f"[Ошибка чтения файла {path_str}]: {e}")

    # 4. Запись файла: ```write_file:path ... ```
    for w_path, w_content in re.findall(r"```write_file:([^\n\r]+)[\r\n]+(.*?)```", text, re.DOTALL):
        path_str = w_path.strip().strip('"').strip("'")
        target_path = Path(path_str)
        if not target_path.is_absolute():
            target_path = PROJECT_DIR / target_path
        print(f"\n{CLR_YELLOW}[Инструмент]{CLR_RESET} Запись файла: {CLR_CYAN}{target_path}{CLR_RESET}")
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(w_content.strip() + "\n", encoding="utf-8")
            actions.append(f"[Успешно]: Файл {target_path} записан ({len(w_content)} символов).")
        except Exception as e:
            actions.append(f"[Ошибка записи файла {path_str}]: {e}")

    # 5. PowerShell: ```powershell cmd ```
    for cmd in re.findall(r"```powershell\s*(.*?)\s*```", text, re.DOTALL):
        cmd_clean = cmd.strip()
        if not cmd_clean:
            continue
        print(f"\n{CLR_YELLOW}[Инструмент]{CLR_RESET} PowerShell: {CLR_CYAN}{cmd_clean}{CLR_RESET}")
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
            out = res.stdout
            if res.stderr:
                out += "\n[Ошибки / Stderr]:\n" + res.stderr
            clean_out = out.strip()
            if not clean_out:
                clean_out = "(Команда выполнена успешно, вывод пуст)"
            if len(clean_out) > 3000:
                clean_out = clean_out[:3000] + f"\n... [вывод сокращен: всего {len(out)} символов]"
            print(f"{CLR_GRAY}[Результат]: {clean_out[:300]}...{CLR_RESET}")
            actions.append(f"[Результат команды `{cmd_clean}`]:\n{clean_out}")
        except subprocess.TimeoutExpired:
            actions.append(f"[Таймаут]: Команда `{cmd_clean}` выполнялась более 90 секунд.")
        except Exception as e:
            actions.append(f"[Ошибка команды]: {e}")

    if actions:
        return True, "\n\n".join(actions)
    return False, ""


def agent_turn(conversation: list[dict], model: str, api_key: str = DEFAULT_API_KEY) -> str:
    """Автономный цикл решения задачи до полного завершения (до 10 шагов)."""
    max_steps = 10
    for _ in range(max_steps):
        if len(conversation) > 20:
            active_conv = [conversation[0]] + conversation[-16:]
        else:
            active_conv = conversation

        reply = call_smartapi(active_conv, model=model, api_key=api_key)
        if not reply or not str(reply).strip():
            return f"[Ответ от {model} пуст. Попробуйте переключиться на /model gemini]"

        has_tools, tool_results = execute_tools(reply)
        if has_tools:
            conversation.append({"role": "assistant", "content": reply})
            conversation.append({
                "role": "user",
                "content": f"{tool_results}\n\nПродолжай автономно решать задачу. Если нужны ещё команды или файлы — делай их в блоках инструментов прямо сейчас. Если задача решена — выдай итоговый структурированный отчёт руководителю."
            })
        else:
            return reply

    return reply


def main():
    system_prompt = build_system_prompt()

    print(f"\n{CLR_BLUE}========================================================================{CLR_RESET}")
    print(f"{CLR_CYAN} MIND UNIVERSAL PC & WINDOWS AI ASSISTANT // ТАГИР ИСКАЛИЕВ{CLR_RESET}")
    print(f"{CLR_GREEN} Задачи: Автоматизация Windows, управление файлами, скрипты, диагностика{CLR_RESET}")
    print(f"{CLR_WHITE} Лимиты токенов: СНЯТЫ (16K) | Режим: Полная автономность «под ключ»{CLR_RESET}")
    print(f"{CLR_GRAY} Домашняя папка: {USER_HOME} | Рабочий стол: {DESKTOP_DIR}{CLR_RESET}")
    print(f"{CLR_BLUE}========================================================================{CLR_RESET}")

    print(f"{CLR_YELLOW}[*] Получение каталога моделей со SmartAPI...{CLR_RESET}")
    available_models = fetch_available_models()
    print_models_table(available_models, current_model=DEFAULT_MODEL)

    try:
        user_choice = input(f"{CLR_CYAN}Выберите модель [1-{len(available_models)}] или нажмите Enter для [{DEFAULT_MODEL}]: {CLR_RESET}").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nЗапуск отменён.")
        return

    current_model = resolve_model(user_choice, available_models, default=DEFAULT_MODEL)
    print(f"{CLR_GREEN}[+] Активная модель: {current_model}{CLR_RESET}\n")

    conversation = [
        {"role": "system", "content": system_prompt}
    ]

    print(f"{CLR_YELLOW}Быстрые команды:{CLR_RESET}")
    print(f"  {CLR_CYAN}/models{CLR_RESET}          - показать полный каталог всех 53 моделей SmartAPI")
    print(f"  {CLR_CYAN}/model <номер/имя>{CLR_RESET} - переключить модель (например: /model 16 или /model opus)")
    print(f"  {CLR_CYAN}/desktop{CLR_RESET}        - открыть Рабочий стол в Проводнике")
    print(f"  {CLR_CYAN}/downloads{CLR_RESET}      - открыть папку Загрузки")
    print(f"  {CLR_CYAN}/clear{CLR_RESET}          - очистить историю диалога")
    print(f"  {CLR_CYAN}exit{CLR_RESET}            - выход\n")

    while True:
        try:
            user_input = input(f"{CLR_CYAN}Вы [{current_model}] > {CLR_RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nСессия завершена.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "q", "/exit", "/quit"):
            print("Сессия завершена.")
            break

        if user_input.lower() == "/clear":
            conversation = [{"role": "system", "content": system_prompt}]
            print(f"{CLR_GREEN}[+] История диалога очищена.{CLR_RESET}\n")
            continue

        if user_input.lower() == "/models":
            print_models_table(available_models, current_model=current_model)
            continue

        if user_input.lower() == "/desktop":
            subprocess.Popen(["explorer.exe", str(DESKTOP_DIR)])
            print(f"{CLR_GREEN}[+] Рабочий стол открыт в Проводнике.{CLR_RESET}\n")
            continue

        if user_input.lower() == "/downloads":
            subprocess.Popen(["explorer.exe", str(DOWNLOADS_DIR)])
            print(f"{CLR_GREEN}[+] Папка Загрузки открыта в Проводнике.{CLR_RESET}\n")
            continue

        if user_input.startswith("/model"):
            parts = user_input.split(maxsplit=1)
            if len(parts) > 1:
                target = resolve_model(parts[1], available_models, default=current_model)
                current_model = target
                print(f"{CLR_GREEN}[+] Модель успешно переключена на: {current_model}{CLR_RESET}\n")
            else:
                print(f"Текущая модель: {current_model}. Наберите /models для вывода каталога.\n")
            continue

        conversation.append({"role": "user", "content": user_input})
        print(f"{CLR_MAGENTA}Ассистент выполняет задачу ({current_model})...{CLR_RESET}")

        try:
            answer = agent_turn(conversation, model=current_model)
        except KeyboardInterrupt:
            answer = "[Выполнение прервано пользователем (Ctrl+C)]"

        conversation.append({"role": "assistant", "content": answer})

        print(f"\n{CLR_GREEN}Ассистент:{CLR_RESET}")
        print(f"{CLR_WHITE}{answer}{CLR_RESET}\n")


if __name__ == "__main__":
    main()
