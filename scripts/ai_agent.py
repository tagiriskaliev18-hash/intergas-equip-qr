#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
АВТОНОМНЫЙ AI-ИНЖЕНЕР // АО «ИНТЕРГАЗ ЦЕНТРАЛЬНАЯ АЗИЯ» (НК «QazaqGaz»)
Подключение: SmartAPI шлюз (https://smartapi.pro/v1).
Поддержка всех 53 моделей SmartAPI, снятые лимиты на генерацию, автономное решение задач.
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

# SSL Context для обхода проверок корпоративных прокси и слабых ключей (EE certificate key too weak)
SSL_CTX = ssl._create_unverified_context()
try:
    SSL_CTX.set_ciphers('DEFAULT:@SECLEVEL=1')
except Exception:
    pass

ROOT_DIR = Path(__file__).resolve().parent.parent

DEFAULT_API_KEY = os.getenv("SMARTAPI_KEY", "sk-smart-J6NAKcsgKoJ_tfaOrfapSY14L1W8us5GR4ZZ3FwPIO8")
DEFAULT_BASE_URL = os.getenv("SMARTAPI_BASE_URL", "https://smartapi.pro/v1").rstrip("/")
DEFAULT_MODEL = "gemini-3.8-flash"

# Полный список моделей (fallback на случай отсутствия сети при старте)
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

# Включение ANSI цветов в Windows консоли
os.system("")

CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_MAGENTA = "\033[95m"
CLR_GRAY = "\033[90m"
CLR_WHITE = "\033[97m"
CLR_RED = "\033[91m"
CLR_RESET = "\033[0m"


def fetch_available_models(api_key: str = DEFAULT_API_KEY) -> list[str]:
    """Запрашивает актуальный список доступных моделей с сервера SmartAPI."""
    url = f"{DEFAULT_BASE_URL}/models"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {api_key}"}
    )
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
    """Выводит красивый, структурированный список моделей с номерами."""
    print(f"\n{CLR_CYAN}------------------------------------------------------------------------{CLR_RESET}")
    print(f"{CLR_GREEN}🔥 РЕКОМЕНДУЕМЫЕ МОДЕЛИ ДЛЯ РАБОТЫ:{CLR_RESET}")
    print(f"  {CLR_CYAN}gemini-3.8-flash{CLR_RESET}   — Сверхбыстрый, стабильный, без лимитов токенов (по умолчанию)")
    print(f"  {CLR_CYAN}deepseek-v4-pro{CLR_RESET}    — Лучший для кода, скриптов, PowerShell и отладки")
    print(f"  {CLR_CYAN}claude-opus-5-5{CLR_RESET}    — Глубокие рассуждения и сложная архитектура")
    print(f"  {CLR_CYAN}claude-sonnet-5{CLR_RESET}    — Быстрый и умный Claude Sonnet 5")
    print(f"  {CLR_CYAN}kimi-k3.1-pro{CLR_RESET}      — Большой контекст, глубокий анализ")
    print(f"  {CLR_CYAN}gpt-6-sol{CLR_RESET}          — Флагман линейки GPT-6")
    print(f"{CLR_CYAN}------------------------------------------------------------------------{CLR_RESET}")
    print(f"{CLR_WHITE}📋 ВСЕ ДОСТУПНЫЕ МОДЕЛИ SMARTAPI (всего: {len(models)}):{CLR_RESET}")

    cols = 3
    for i in range(0, len(models), cols):
        chunk = models[i:i + cols]
        line_parts = []
        for j, m in enumerate(chunk):
            idx = i + j + 1
            mark = "*" if m == current_model else " "
            line_parts.append(f"{CLR_YELLOW}[{idx:2d}]{CLR_RESET}{mark}{CLR_WHITE}{m:<23}{CLR_RESET}")
        print("  " + "  ".join(line_parts))
    print(f"{CLR_CYAN}------------------------------------------------------------------------{CLR_RESET}\n")


def resolve_model_selection(choice: str, models: list[str], default: str = DEFAULT_MODEL) -> str:
    """Определяет модель по номеру, короткому псевдониму или точному имени."""
    clean = choice.strip().lower()
    if not clean:
        return default

    # 1. Выбор по номеру: '1', '16', '20'
    if clean.isdigit():
        idx = int(clean) - 1
        if 0 <= idx < len(models):
            return models[idx]

    # 2. Быстрые псевдонимы
    aliases = {
        "gemini": "gemini-3.8-flash",
        "flash": "gemini-3.8-flash",
        "opus": "claude-opus-5-5",
        "sonnet": "claude-sonnet-5",
        "sonnet4": "claude-sonnet-4-6",
        "deepseek": "deepseek-v4-pro",
        "deepseek-flash": "deepseek-v4.1-flash",
        "kimi": "kimi-k3.1-pro",
        "gpt": "gpt-6-sol",
        "gpt6": "gpt-6-sol",
        "qwen": "qwen-4-max"
    }
    if clean in aliases and aliases[clean] in models:
        return aliases[clean]

    # 3. Точное совпадение
    for m in models:
        if m.lower() == clean:
            return m

    # 4. Частичное совпадение (подстрока)
    matches = [m for m in models if clean in m.lower()]
    if matches:
        return matches[0]

    return default


def load_system_prompt() -> str:
    env_file = ROOT_DIR / ".env"
    prompt = f"""ТЫ — ВЕДУЩИЙ АВТОНОМНЫЙ ИИ-ИНЖЕНЕР АО «ИНТЕРГАЗ ЦЕНТРАЛЬНАЯ АЗИЯ» (АО «НК «QazaqGaz»).
У ТЕБЯ ЕСТЬ ПОЛНЫЙ ПРЯМОЙ ДОСТУП К КОМПЬЮТЕРУ ПОЛЬЗОВАТЕЛЯ, ФАЙЛОВОЙ СИСТЕМЕ, POWERSHELL И БРАУЗЕРУ.
Рабочая папка проекта: {ROOT_DIR}
Файл настроек Active Directory: {env_file}

КЛЮЧЕВОЙ ПРИНЦИП РАБОТЫ: АВТОНОМНОЕ РЕШЕНИЕ ЗАДАЧ «ПОД КЛЮЧ»
1. НЕ СПРАШИВАЙ — ДЕЛАЙ!
   - Руководитель даёт задачу и ждёт ГОТОВЫЙ РЕЗУЛЬТАТ, а не встречные вопросы.
   - КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО писать: «Сказать, чтобы я исправил?», «Жду вашего подтверждения», «Напишите <правь ad_auth>», «Как мне поступить?».
   - Если нужно изменить файл — СРАЗУ выдавай блок ```write_file:путь``` с полным содержимым.
   - Если нужно проверить сеть, запустить процесс или протестировать AD — СРАЗУ выдавай блок ```powershell```.
   - Если команда выдала ошибку — САМ анализируй причину и пробуй исправление, пока задача не будет решена.

2. СТРУКТУРА ФИНАЛЬНОГО ОТВЕТА:
   Когда задача полностью решена, выдай краткий, чёткий и ёмкий отчёт руководителю:
   - ✅ ЧТО СДЕЛАНО: список конкретных действий (исправленные файлы, запущенные процессы).
   - 📊 РЕЗУЛЬТАТ: статус работоспособности, найденные данные, статус порта 8443 / AD.
   - 🚀 ДАЛЬНЕЙШИЙ ШАГ: ссылка для входа или статус.
   Никакой лишней воды и философии.

3. ПРАВИЛО БЮДЖЕТА ПРЕДПРИЯТИЯ:
   - ПОЛНОЕ ОТСУТСТВИЕ СУММ И ЦЕН В БЮДЖЕТЕ. Никаких тенге (₸) и рублей (₽).
   - Все расчеты ведутся исключительно в днях/часах ТО, единицах ЗИП (шт., комплекты, литры) и количестве открытых дефектов.

ИНСТРУМЕНТЫ (вызывай их прямо в тексте ответа):

1. Выполнить команду на компьютере (PowerShell):
```powershell
твоя команда
```

2. Открыть страницу в браузере:
```browser
https://127.0.0.1:8443
```

3. Прочитать файл:
```read_file
путь_к_файлу
```

4. Записать или изменить файл на диске:
```write_file:путь_к_файлу
содержимое файла
```"""

    gemini_md = ROOT_DIR / "GEMINI.md"
    if gemini_md.exists():
        try:
            prompt += "\n\n" + gemini_md.read_text(encoding="utf-8")
        except Exception:
            pass

    return prompt


def call_smartapi(messages: list[dict], model: str, api_key: str = DEFAULT_API_KEY) -> str:
    """Выполняет вызов SmartAPI без искусственного занижения лимитов токенов."""
    url = f"{DEFAULT_BASE_URL}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 16384,  # Полный размер генерации без обрезки кода и решений
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
        return f"[SmartAPI HTTP {e.code}]: {err_body} (Попробуйте переключиться на /model gemini)"
    except KeyboardInterrupt:
        return "[Запрос прерван пользователем (Ctrl+C)]"
    except Exception as e:
        return f"[SmartAPI Ошибка]: {e} (Попробуйте переключиться на /model gemini)"


def execute_tools(text: str) -> tuple[bool, str]:
    """Сканирует ответ модели на наличие вызовов инструментов и выполняет их на ПК."""
    actions_taken = []

    # 1. Открытие браузера: ```browser https://... ```
    browser_matches = re.findall(r"```browser\s*(.*?)\s*```", text, re.DOTALL)
    for b_url in browser_matches:
        url = b_url.strip()
        if not url.startswith("http"):
            url = "https://" + url
        print(f"\n{CLR_YELLOW}[Инструмент]{CLR_RESET} Открытие в браузере: {CLR_CYAN}{url}{CLR_RESET}")
        try:
            webbrowser.open(url)
            actions_taken.append(f"[Браузер]: Успешно открыта страница {url}")
        except Exception as e:
            actions_taken.append(f"[Ошибка браузера]: {e}")

    # 2. Чтение файла: ```read_file путь ```
    read_matches = re.findall(r"```read_file\s*(.*?)\s*```", text, re.DOTALL)
    for r_path in read_matches:
        path_str = r_path.strip().strip('"').strip("'")
        target_path = Path(path_str)
        if not target_path.is_absolute():
            target_path = ROOT_DIR / target_path
        print(f"\n{CLR_YELLOW}[Инструмент]{CLR_RESET} Чтение файла: {CLR_CYAN}{target_path}{CLR_RESET}")
        try:
            if target_path.exists():
                content = target_path.read_text(encoding="utf-8", errors="replace")
                actions_taken.append(f"[Содержимое файла {target_path.name}]:\n{content}")
            else:
                actions_taken.append(f"[Ошибка]: Файл {target_path} не найден.")
        except Exception as e:
            actions_taken.append(f"[Ошибка чтения файла {path_str}]: {e}")

    # 3. Запись файла: ```write_file:путь ... ```
    write_matches = re.findall(r"```write_file:([^\n\r]+)[\r\n]+(.*?)```", text, re.DOTALL)
    for w_path, w_content in write_matches:
        path_str = w_path.strip().strip('"').strip("'")
        target_path = Path(path_str)
        if not target_path.is_absolute():
            target_path = ROOT_DIR / target_path
        print(f"\n{CLR_YELLOW}[Инструмент]{CLR_RESET} Запись файла: {CLR_CYAN}{target_path}{CLR_RESET}")
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(w_content.strip() + "\n", encoding="utf-8")
            actions_taken.append(f"[Успешно]: Файл {target_path} сохранён ({len(w_content)} символов).")
        except Exception as e:
            actions_taken.append(f"[Ошибка записи файла {path_str}]: {e}")

    # 4. Команда PowerShell: ```powershell ... ```
    ps_matches = re.findall(r"```powershell\s*(.*?)\s*```", text, re.DOTALL)
    for cmd in ps_matches:
        cmd_clean = cmd.strip()
        if not cmd_clean:
            continue
        print(f"\n{CLR_YELLOW}[Инструмент]{CLR_RESET} Выполнение PowerShell на ПК: {CLR_CYAN}{cmd_clean}{CLR_RESET}")
        try:
            ps_script = f"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; {cmd_clean}"
            res = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                cwd=str(ROOT_DIR),
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
            print(f"{CLR_GRAY}[Результат с ПК]: {clean_out[:350]}...{CLR_RESET}")
            actions_taken.append(f"[Результат выполнения команды `{cmd_clean}` на ПК]:\n{clean_out}")
        except subprocess.TimeoutExpired:
            actions_taken.append(f"[Таймаут]: Команда `{cmd_clean}` выполнялась более 90 секунд.")
        except Exception as e:
            actions_taken.append(f"[Ошибка выполнения команды]: {e}")

    if actions_taken:
        return True, "\n\n".join(actions_taken)
    return False, ""


def agent_turn(conversation: list[dict], model: str, api_key: str = DEFAULT_API_KEY) -> str:
    """
    Автономный исполнительный цикл (ReAct):
    Модель выполняет команды и правит файлы до полного завершения задачи, не задавая встречных вопросов.
    """
    max_steps = 10  # До 10 автономных шагов для решения сложных задач без остановок
    for _ in range(max_steps):
        if len(conversation) > 20:
            active_conv = [conversation[0]] + conversation[-16:]
        else:
            active_conv = conversation

        reply = call_smartapi(active_conv, model=model, api_key=api_key)
        if not reply or not str(reply).strip():
            return f"[Ответ от {model} пуст. Попробуйте сменить модель через /models]"

        has_tools, tool_results = execute_tools(reply)
        if has_tools:
            conversation.append({"role": "assistant", "content": reply})
            conversation.append({
                "role": "user",
                "content": f"{tool_results}\n\nПродолжай автономно решать задачу. Если требуются дополнительные действия (правка файлов, запуск команд) — выполняй их прямо сейчас в блоках инструментов. Если всё готово — выдай финальный чёткий отчёт руководителю."
            })
        else:
            return reply

    return reply


def main():
    system_prompt = load_system_prompt()

    print(f"\n{CLR_CYAN}========================================================================{CLR_RESET}")
    print(f"{CLR_CYAN} АВТОНОМНЫЙ AI-ИНЖЕНЕР // АО «ИНТЕРГАЗ ЦЕНТРАЛЬНАЯ АЗИЯ» // SMARTAPI{CLR_RESET}")
    print(f"{CLR_GREEN} Режим: Полная автономность (действует без переспрашивания){CLR_RESET}")
    print(f"{CLR_WHITE} Лимиты на токены: СНЯТЫ (max_tokens = 16384){CLR_RESET}")
    print(f"{CLR_WHITE} Рабочая папка: {ROOT_DIR}{CLR_RESET}")
    print(f"{CLR_CYAN}========================================================================{CLR_RESET}")

    # Загрузка и показ всех моделей SmartAPI
    print(f"{CLR_YELLOW}[*] Получение каталога моделей со SmartAPI...{CLR_RESET}")
    available_models = fetch_available_models()
    print_models_table(available_models, current_model=DEFAULT_MODEL)

    # Интерактивный выбор модели при входе
    try:
        user_choice = input(f"{CLR_CYAN}Выберите модель [1-{len(available_models)}] или нажмите Enter для [{DEFAULT_MODEL}]: {CLR_RESET}").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nЗапуск отменён.")
        return

    current_model = resolve_model_selection(user_choice, available_models, default=DEFAULT_MODEL)
    print(f"{CLR_GREEN}[+] Активная модель: {current_model}{CLR_RESET}\n")

    conversation = [
        {"role": "system", "content": system_prompt}
    ]

    print(f"{CLR_YELLOW}Команды управления:{CLR_RESET}")
    print(f"  {CLR_CYAN}/models{CLR_RESET}          - показать полный каталог всех 53 моделей SmartAPI")
    print(f"  {CLR_CYAN}/model <номер/имя>{CLR_RESET} - быстро переключить модель (например: /model 16 или /model opus)")
    print(f"  {CLR_CYAN}/browser{CLR_RESET}         - открыть проект в браузере (https://127.0.0.1:8443)")
    print(f"  {CLR_CYAN}/env{CLR_RESET}             - открыть .env в Блокноте")
    print(f"  {CLR_CYAN}/clear{CLR_RESET}           - очистить историю диалога")
    print(f"  {CLR_CYAN}exit{CLR_RESET}             - выход из агента\n")

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

        if user_input.lower() == "/browser":
            url = "https://127.0.0.1:8443"
            print(f"{CLR_YELLOW}[*] Открытие веб-приложения в браузере: {url}{CLR_RESET}")
            webbrowser.open(url)
            continue

        if user_input.lower() == "/env":
            env_path = ROOT_DIR / ".env"
            subprocess.Popen(["notepad.exe", str(env_path)])
            print(f"{CLR_GREEN}[+] Открыт {env_path} в Блокноте.{CLR_RESET}\n")
            continue

        if user_input.startswith("/model"):
            parts = user_input.split(maxsplit=1)
            if len(parts) > 1:
                target = resolve_model_selection(parts[1], available_models, default=current_model)
                current_model = target
                print(f"{CLR_GREEN}[+] Модель успешно переключена на: {current_model}{CLR_RESET}\n")
            else:
                print(f"Текущая модель: {current_model}. Наберите /models для вывода списка.\n")
            continue

        conversation.append({"role": "user", "content": user_input})
        print(f"{CLR_MAGENTA}Инженер выполняет задачу ({current_model})...{CLR_RESET}")

        try:
            answer = agent_turn(conversation, model=current_model)
        except KeyboardInterrupt:
            answer = "[Выполнение прервано пользователем (Ctrl+C)]"

        conversation.append({"role": "assistant", "content": answer})

        print(f"\n{CLR_GREEN}Инженер:{CLR_RESET}")
        print(f"{CLR_WHITE}{answer}{CLR_RESET}\n")


if __name__ == "__main__":
    main()
