#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLAUDE OPUS 5.5 — Автономный ИИ-инженер для АО «Интергаз Центральная Азия».
Запуск в 1 клик. Полный доступ к ПК, файлам, PowerShell и браузеру.
"""
import json
import os
import re
import ssl
import subprocess
import sys
import urllib.request
import webbrowser
from pathlib import Path

# Корень проекта
PROJECT_DIR = Path("C:/QRcode")
if not PROJECT_DIR.exists():
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)

API_KEY = "sk-smart-J6NAKcsgKoJ_tfaOrfapSY14L1W8us5GR4ZZ3FwPIO8"
BASE_URL = "https://smartapi.pro/v1"
MODEL = "claude-opus-5-5"

# Корпоративный SSL-контекст (обход проверок прокси и слабых ключей)
SSL_CTX = ssl._create_unverified_context()
try:
    SSL_CTX.set_ciphers('DEFAULT:@SECLEVEL=1')
except Exception:
    pass

# Цвета в консоли
os.system("")
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_MAGENTA = "\033[95m"
CLR_GRAY = "\033[90m"
CLR_WHITE = "\033[97m"
CLR_RED = "\033[91m"
CLR_RESET = "\033[0m"

SYSTEM_PROMPT = f"""Ты — Claude Opus 5.5, ведущий AI-инженер проекта «Паспортизация и ТО оборудования АО Интергаз Центральная Азия» (НК «QazaqGaz»).
У ТЕБЯ ЕСТЬ ПОЛНЫЙ ДОСТУП К КОМПЬЮТЕРУ И БРАУЗЕРУ ПОЛЬЗОВАТЕЛЯ.
Рабочая папка: {PROJECT_DIR}
Файл настроек Active Directory: {PROJECT_DIR / '.env'}

ИНФОРМАЦИЯ О СЕТИ:
- Домен: ica.kz (Base DN: DC=ica,DC=kz)
- Контроллер домена: srv-dc-url1.ica.kz (IP: 192.168.72.22)
- Порты: 389 (LDAP) и 636 (LDAPS) открыты и доступны!
- Сервисная учётка может вводиться как UPN (логин@ica.kz) или ICA\\логин.

ИНСТРУМЕНТЫ (вызывай их прямо в тексте ответа):

1. Выполнить команду в PowerShell:
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

4. Записать файл:
```write_file:путь_к_файлу
содержимое
```

ПРАВИЛА:
- Всегда отвечай на понятном, профессиональном русском языке.
- Никогда не выводи DSML/XML теги или команды Linux (ls, pwd, bash).
- Главное правило предприятия: ПОЛНОЕ ОТСУТСТВИЕ СУММ И ЦЕН В БЮДЖЕТЕ. Никаких тенге и рублей. Только сроки ТО, единицы ЗИП и количество дефектов."""


def call_opus(messages: list[dict]) -> str:
    url = f"{BASE_URL}/chat/completions"
    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": 3500,
        "temperature": 0.2
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json; charset=utf-8"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=90, context=SSL_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[Ошибка связи с Opus]: {e}"


def execute_tools(text: str) -> tuple[bool, str]:
    actions = []

    # 1. Браузер
    for b_url in re.findall(r"```browser\s*(.*?)\s*```", text, re.DOTALL):
        url = b_url.strip()
        if not url.startswith("http"):
            url = "https://" + url
        print(f"\n{CLR_YELLOW}[Инструмент]{CLR_RESET} Открытие браузера: {CLR_CYAN}{url}{CLR_RESET}")
        try:
            webbrowser.open(url)
            actions.append(f"[Браузер]: Открыта страница {url}")
        except Exception as e:
            actions.append(f"[Ошибка браузера]: {e}")

    # 2. Чтение файла
    for r_path in re.findall(r"```read_file\s*(.*?)\s*```", text, re.DOTALL):
        path = Path(r_path.strip().strip('"').strip("'"))
        if not path.is_absolute():
            path = PROJECT_DIR / path
        print(f"\n{CLR_YELLOW}[Инструмент]{CLR_RESET} Чтение файла: {CLR_CYAN}{path}{CLR_RESET}")
        try:
            if path.exists():
                actions.append(f"[Файл {path.name}]:\n{path.read_text(encoding='utf-8', errors='replace')}")
            else:
                actions.append(f"[Ошибка]: Файл {path} не найден.")
        except Exception as e:
            actions.append(f"[Ошибка чтения {path}]: {e}")

    # 3. Запись файла
    for w_path, w_content in re.findall(r"```write_file:([^\n\r]+)[\r\n]+(.*?)```", text, re.DOTALL):
        path = Path(w_path.strip().strip('"').strip("'"))
        if not path.is_absolute():
            path = PROJECT_DIR / path
        print(f"\n{CLR_YELLOW}[Инструмент]{CLR_RESET} Запись файла: {CLR_CYAN}{path}{CLR_RESET}")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(w_content.strip() + "\n", encoding="utf-8")
            actions.append(f"[Успешно]: Файл {path} сохранён.")
        except Exception as e:
            actions.append(f"[Ошибка записи {path}]: {e}")

    # 4. PowerShell
    for cmd in re.findall(r"```powershell\s*(.*?)\s*```", text, re.DOTALL):
        cmd_clean = cmd.strip()
        if not cmd_clean:
            continue
        print(f"\n{CLR_YELLOW}[Инструмент]{CLR_RESET} Выполнение в PowerShell: {CLR_CYAN}{cmd_clean}{CLR_RESET}")
        try:
            ps_script = f"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; {cmd_clean}"
            res = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                cwd=str(PROJECT_DIR),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60
            )
            out = res.stdout
            if res.stderr:
                out += "\n" + res.stderr
            if not out.strip():
                out = "(Команда выполнена успешно)"
            print(f"{CLR_GRAY}[Результат ПК]: {out.strip()[:300]}...{CLR_RESET}")
            actions.append(f"[Результат команды на ПК]:\n{out.strip()}")
        except Exception as e:
            actions.append(f"[Ошибка команды]: {e}")

    if actions:
        return True, "\n\n".join(actions)
    return False, ""


def opus_turn(history: list[dict]) -> str:
    for _ in range(5):
        reply = call_opus(history)
        has_tools, tool_out = execute_tools(reply)
        if has_tools:
            history.append({"role": "assistant", "content": reply})
            history.append({"role": "user", "content": f"{tool_out}\n\nСделай вывод и ответь пользователю на русском."})
        else:
            return reply
    return reply


def main():
    print(f"\n{CLR_CYAN}========================================================================{CLR_RESET}")
    print(f"{CLR_CYAN} CLAUDE OPUS 5.5 // АО «ИНТЕРГАЗ ЦЕНТРАЛЬНАЯ АЗИЯ» // SMARTAPI{CLR_RESET}")
    print(f"{CLR_GREEN} Статус: Прямой доступ к файлам ПК, PowerShell и браузеру АКТИВЕН{CLR_RESET}")
    print(f"{CLR_WHITE} Папка: {PROJECT_DIR} | Модель: {MODEL}{CLR_RESET}")
    print(f"{CLR_CYAN}========================================================================{CLR_RESET}")
    print(f"{CLR_YELLOW}Команды:{CLR_RESET} /env (открыть .env) | /browser (открыть сайт) | /clear | exit\n")

    history = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            user_input = input(f"{CLR_CYAN}Вы > {CLR_RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nСессия завершена.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "q"):
            print("Сессия завершена.")
            break

        if user_input.lower() == "/clear":
            history = [{"role": "system", "content": SYSTEM_PROMPT}]
            print(f"{CLR_GREEN}[+] История очищена.{CLR_RESET}\n")
            continue

        if user_input.lower() == "/browser":
            print(f"{CLR_YELLOW}[*] Открытие https://127.0.0.1:8443 в браузере...{CLR_RESET}")
            webbrowser.open("https://127.0.0.1:8443")
            continue

        if user_input.lower() == "/env":
            env_file = PROJECT_DIR / ".env"
            if not env_file.exists():
                env_file.write_text("AD_ENABLED=true\nAD_SERVER=ldaps://srv-dc-url1.ica.kz:636\nAD_DOMAIN=ica.kz\nAD_BASE_DN=DC=ica,DC=kz\nAD_BIND_DN=\nAD_BIND_PASSWORD=\nAD_USE_SSL=true\n", encoding="utf-8")
            subprocess.Popen(["notepad.exe", str(env_file)])
            print(f"{CLR_GREEN}[+] Открыт {env_file} в Блокноте.{CLR_RESET}\n")
            continue

        history.append({"role": "user", "content": user_input})
        print(f"{CLR_MAGENTA}Opus думает...{CLR_RESET}")

        answer = opus_turn(history)
        history.append({"role": "assistant", "content": answer})

        print(f"\n{CLR_GREEN}Opus:{CLR_RESET}")
        print(f"{CLR_WHITE}{answer}{CLR_RESET}\n")


if __name__ == "__main__":
    main()
