#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Автономный AI-ассистент для АО «Интергаз Центральная Азия» (НК «QazaqGaz»).
Подключение: SmartAPI шлюз (https://smartapi.pro/v1).
Модели: gemini-3.8-flash, claude-opus-5-5, deepseek-v4-pro.

Возможности агента:
1. Работа с файлами ПК: чтение, создание, редактирование, поиск.
2. Работа с браузером: открытие страниц в браузере, тестирование веб-приложения (https://127.0.0.1:8443).
3. Выполнение команд в Windows PowerShell (проверка Active Directory, запуск тестов, запуск сервера).
4. Полная память проекта: GEMINI.md, объекты ЛПУ, ГРС, КС, нулевой бюджет.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

DEFAULT_API_KEY = os.getenv("SMARTAPI_KEY", "sk-smart-J6NAKcsgKoJ_tfaOrfapSY14L1W8us5GR4ZZ3FwPIO8")
DEFAULT_BASE_URL = os.getenv("SMARTAPI_BASE_URL", "https://smartapi.pro/v1").rstrip("/")
DEFAULT_MODEL = "gemini-3.8-flash"

MODELS = {
    "gemini": "gemini-3.8-flash",
    "opus": "claude-opus-5-5",
    "sonnet": "claude-sonnet-4-6",
    "deepseek": "deepseek-v4-pro"
}

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


def load_system_prompt() -> str:
    env_file = ROOT_DIR / ".env"
    prompt = f"""Ты — автономный AI-инженер проекта АО «Интергаз Центральная Азия» (дочерняя компания АО «НК «QazaqGaz»).
У ТЕБЯ ЕСТЬ ПОЛНЫЙ ДОСТУП К КОМПЬЮТЕРУ ПОЛЬЗОВАТЕЛЯ И БРАУЗЕРУ.
Рабочая папка проекта: {ROOT_DIR}
Файл настроек Active Directory: {env_file}

ГЛАВНЫЕ ИНСТРУМЕНТЫ (ты можешь вызывать их прямо в ответе):

1. Выполнить команду на компьютере (PowerShell):
```powershell
твоя команда PowerShell
```

2. Открыть страницу в веб-браузере пользователя:
```browser
https://127.0.0.1:8443
```

3. Прочитать файл с диска:
```read_file
путь_к_файлу
```

4. Записать или изменить файл на диске:
```write_file:путь_к_файлу
содержимое файла
```

ПРАВИЛА ПОВЕДЕНИЯ:
- Отвечай ВСЕГДА на чистом и понятном русском языке.
- Никогда не выводи псевдо-теги вроде <| DSML || calls> или команды bash/pwd/ls.
- Если тебя просят открыть браузер или проверить веб-интерфейс, используй блок ```browser ... ```.
- Если нужно отредактировать .env или запустить тест AD, выполни это через инструменты.
- КЛЮЧЕВОЙ ПРИНЦИП ПРЕДПРИЯТИЯ: ПОЛНОЕ ОТСУТСТВИЕ СУММ И ЦЕН В БЮДЖЕТЕ. Никаких тенге (₸) и рублей (₽). Все расчеты ведутся исключительно в днях/часах ТО, единицах ЗИП (шт., комплекты, литры) и количестве открытых дефектов."""

    gemini_md = ROOT_DIR / "GEMINI.md"
    if gemini_md.exists():
        try:
            prompt += "\n\n" + gemini_md.read_text(encoding="utf-8")
        except Exception:
            pass

    return prompt


def call_smartapi(messages: list[dict], model: str, api_key: str = DEFAULT_API_KEY) -> str:
    url = f"{DEFAULT_BASE_URL}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 3000,
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
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        return f"[SmartAPI HTTP {e.code}]: {err_body}"
    except Exception as e:
        return f"[SmartAPI Error]: {e}"


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
            res = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd_clean],
                cwd=str(ROOT_DIR),
                capture_output=True,
                text=True,
                timeout=60
            )
            out = res.stdout
            if res.stderr:
                out += "\n[Ошибки / Stderr]:\n" + res.stderr
            if not out.strip():
                out = "(Команда выполнена успешно, вывод пуст)"
            print(f"{CLR_GRAY}[Результат с ПК]: {out.strip()[:350]}...{CLR_RESET}")
            actions_taken.append(f"[Результат выполнения команды `{cmd_clean}` на ПК]:\n{out.strip()}")
        except subprocess.TimeoutExpired:
            actions_taken.append(f"[Таймаут]: Команда `{cmd_clean}` выполнялась более 60 секунд.")
        except Exception as e:
            actions_taken.append(f"[Ошибка выполнения команды]: {e}")

    if actions_taken:
        return True, "\n\n".join(actions_taken)
    return False, ""


def agent_turn(conversation: list[dict], model: str, api_key: str = DEFAULT_API_KEY) -> str:
    """Итерационный цикл агента (ReAct loop): модель выдает команду -> скрипт выполняет -> модель анализирует."""
    max_steps = 5
    for _ in range(max_steps):
        reply = call_smartapi(conversation, model=model, api_key=api_key)

        # Проверка и выполнение вызовов инструментов
        has_tools, tool_results = execute_tools(reply)
        if has_tools:
            conversation.append({"role": "assistant", "content": reply})
            conversation.append({
                "role": "user",
                "content": f"{tool_results}\n\nПроанализируй полученный результат и дай итоговый ответ пользователю на русском языке."
            })
        else:
            return reply

    return reply


def main():
    system_prompt = load_system_prompt()
    current_model = DEFAULT_MODEL

    conversation = [
        {"role": "system", "content": system_prompt}
    ]

    print(f"\n{CLR_CYAN}========================================================================{CLR_RESET}")
    print(f"{CLR_CYAN} АВТОНОМНЫЙ AI-ИНЖЕНЕР // АО «ИНТЕРГАЗ ЦЕНТРАЛЬНАЯ АЗИЯ» // SMARTAPI{CLR_RESET}")
    print(f"{CLR_GRAY} Поддерживаемые модели: Gemini 3.8 Flash, Claude Opus 5.5, DeepSeek V4 Pro{CLR_RESET}")
    print(f"{CLR_GREEN} Режим: Доступ к ПК (файлы, PowerShell, веб-браузер) АКТИВЕН{CLR_RESET}")
    print(f"{CLR_CYAN}========================================================================{CLR_RESET}")
    print(f"{CLR_WHITE}Рабочая папка: {ROOT_DIR}{CLR_RESET}")
    print(f"{CLR_YELLOW}Быстрые команды:{CLR_RESET}")
    print(f"  {CLR_CYAN}/model opus{CLR_RESET}     - переключить на Claude Opus 5.5 (глубокие рассуждения)")
    print(f"  {CLR_CYAN}/model gemini{CLR_RESET}   - переключить на Gemini 3.8 Flash (сверхбыстрый)")
    print(f"  {CLR_CYAN}/model deepseek{CLR_RESET} - переключить на DeepSeek V4 Pro (код и скрипты)")
    print(f"  {CLR_CYAN}/browser{CLR_RESET}        - открыть проект в браузере (https://127.0.0.1:8443)")
    print(f"  {CLR_CYAN}/env{CLR_RESET}            - открыть файл настроек .env в Блокноте")
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
                key = parts[1].strip().lower()
                if key in MODELS:
                    current_model = MODELS[key]
                    print(f"{CLR_GREEN}[+] Модель успешно переключена на: {current_model}{CLR_RESET}\n")
                elif key in MODELS.values():
                    current_model = key
                    print(f"{CLR_GREEN}[+] Модель установлена: {current_model}{CLR_RESET}\n")
                else:
                    print(f"{CLR_RED}[!] Неизвестная модель. Доступны: gemini, opus, sonnet, deepseek{CLR_RESET}\n")
            else:
                print(f"Текущая модель: {current_model}. Доступны: gemini, opus, sonnet, deepseek\n")
            continue

        conversation.append({"role": "user", "content": user_input})
        print(f"{CLR_MAGENTA}Инженер анализирует ({current_model})...{CLR_RESET}")

        answer = agent_turn(conversation, model=current_model)
        conversation.append({"role": "assistant", "content": answer})

        print(f"\n{CLR_GREEN}Инженер:{CLR_RESET}")
        print(f"{CLR_WHITE}{answer}{CLR_RESET}\n")


if __name__ == "__main__":
    main()
