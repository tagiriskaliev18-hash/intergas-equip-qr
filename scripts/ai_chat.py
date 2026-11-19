#!/usr/bin/env python3
"""
Автономный терминальный AI-ассистент с полным доступом к ПК для АО «Интергаз Центральная Азия».
Шлюз: SmartAPI (https://smartapi.pro/v1). Модели: gemini-3.8-flash, claude-opus-5-5, deepseek-v4-pro.

Агент РЕАЛЬНО может выполнять команды на компьютере, читать/изменять файлы (.env, код, тесты)
и диагностировать Active Directory.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

DEFAULT_API_KEY = os.getenv("SMARTAPI_KEY", "sk-smart-J6NAKcsgKoJ_tfaOrfapSY14L1W8us5GR4ZZ3FwPIO8")
DEFAULT_BASE_URL = os.getenv("SMARTAPI_BASE_URL", "https://smartapi.pro/v1").rstrip("/")
DEFAULT_MODEL = os.getenv("SMARTAPI_MODEL", "gemini-3.8-flash")

AVAILABLE_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.1-pro",
    "claude-opus-5-5",
    "claude-sonnet-4-6",
    "deepseek-v4-pro",
    "gpt-4o",
]


def load_project_memory() -> str:
    """Загружает базу знаний проекта из GEMINI.md и добавляет инструкции агента по ПК."""
    env_file = ROOT_DIR / ".env"
    base_instructions = f"""Ты — автономный AI-инженер проекта АО «Интергаз Центральная Азия» (ЛПУ, ГРС, КС).
У ТЕБЯ ЕСТЬ ПОЛНЫЙ ДОСТУП К КОМПЬЮТЕРУ ПОЛЬЗОВАТЕЛЯ.
Рабочая папка проекта: {ROOT_DIR}
Файл настроек Active Directory: {env_file}

Правила выполнения действий на компьютере:
1. Чтобы выполнить команду в терминале (PowerShell/CMD), найти файл, прочитать файл, отредактировать .env, запустить python или проверить Active Directory, напиши блок кода:
```powershell
твоя команда
```
или используй вызов инструмента.
Система выполнит твою команду на ПК и вернёт тебе вывод.
2. Когда результат получен, объясни пользователю всё на чистом русском языке.
3. Главное правило предприятия: ПОЛНОЕ ОТСУТСТВИЕ СУММ И ЦЕН В БЮДЖЕТЕ. Только физические единицы (дни, часы, шт., комплекты, литры) и количество открытых дефектов."""

    gemini_md = ROOT_DIR / "GEMINI.md"
    if gemini_md.exists():
        try:
            return base_instructions + "\n\n" + gemini_md.read_text(encoding="utf-8")
        except Exception:
            pass
    return base_instructions


def call_smartapi(
    messages: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
    api_key: str = DEFAULT_API_KEY,
    base_url: str = DEFAULT_BASE_URL,
    max_tokens: int = 2048,
    temperature: float = 0.3,
) -> str:
    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Intergas-Equip-Agent/1.0",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            choices = body.get("choices", [])
            if choices and "message" in choices[0]:
                return choices[0]["message"].get("content", "")
            return "[-] Получен пустой ответ от SmartAPI."
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        return f"[-] Ошибка SmartAPI HTTP {e.code}: {err_msg}"
    except Exception as e:
        return f"[-] Ошибка соединения со SmartAPI: {e}"


def extract_command(text: str) -> str:
    """Извлекает команду PowerShell/Bash/DSML из ответа модели."""
    # 1. Формат DSML: <| DSML | | parameter name="command"...>CMD</...
    dsml = re.search(r'parameter\s+name=["\']command["\'][^>]*>(.*?)</', text, re.DOTALL)
    if dsml:
        return dsml.group(1).strip()

    # 2. Формат ```powershell или ```bash или ```cmd
    code = re.search(r'```(?:powershell|pwsh|cmd|bash|sh)?\s*\n(.*?)```', text, re.DOTALL)
    if code:
        candidate = code.group(1).strip()
        return candidate

    return ""


def run_host_command(command: str) -> str:
    """Выполняет команду на локальном компьютере и возвращает вывод."""
    # Заменяем linux-специфичные команды на аналоги Windows если нужно
    cmd = command
    if cmd.startswith("ls -a"):
        cmd = "dir -Force"
    elif cmd.startswith("pwd"):
        cmd = "Get-Location"

    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
        )
        out = proc.stdout.strip()
        err = proc.stderr.strip()
        result = []
        if out:
            result.append(out)
        if err:
            result.append(f"[stderr]: {err}")
        return "\n".join(result) if result else "(Команда выполнена успешно, вывод пуст)"
    except subprocess.TimeoutExpired:
        return "[-] Ошибка: Команда превысила таймаут выполнения (30 сек)."
    except Exception as e:
        return f"[-] Ошибка выполнения команды: {e}"


def execute_agent_loop(
    conversation: list[dict[str, str]],
    model: str,
    api_key: str,
    max_steps: int = 4,
) -> str:
    """Автономный цикл Агента: вопрос -> команда на ПК -> результат ПК -> ответ."""
    step = 0
    while step < max_steps:
        step += 1
        reply = call_smartapi(conversation, model=model, api_key=api_key)

        cmd = extract_command(reply)
        if cmd:
            print(f"\n\033[1;33m[AI выполняет на ПК]:\033[0m {cmd}")
            cmd_output = run_host_command(cmd)
            # Показываем превью вывода
            preview = cmd_output[:300] + ("..." if len(cmd_output) > 300 else "")
            print(f"\033[1;30m[Результат ПК]:\033[0m {preview}\n")

            conversation.append({"role": "assistant", "content": reply})
            conversation.append({
                "role": "user",
                "content": f"[Результат выполнения команды на компьютере пользователя]:\n{cmd_output}\n\nПроанализируй вывод и дай ответ пользователю на русском языке."
            })
        else:
            return reply

    return reply


def interactive_loop(model: str = DEFAULT_MODEL, api_key: str = DEFAULT_API_KEY):
    system_prompt = load_project_memory()
    conversation: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt}
    ]

    print("=" * 72)
    print(" АО «ИНТЕРГАЗ ЦЕНТРАЛЬНАЯ АЗИЯ» // АВТОНОМНЫЙ AI-ИНЖЕНЕР")
    print(f" Шлюз: SmartAPI | Активная модель: {model}")
    print(f" Рабочая папка: {ROOT_DIR}")
    print(" Агент имеет ДОСТУП К ПК: может сам читать файлы, менять .env и запускать тесты!")
    print("=" * 72)
    print("Команды: /env (открыть .env) | /model <имя> | /clear | exit\n")

    current_model = model

    while True:
        try:
            user_input = input("\033[1;36mВы > \033[0m").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nСессия завершена.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "q", "/exit", "/quit"):
            print("До свидания!")
            break

        if user_input.lower() == "/clear":
            conversation = [{"role": "system", "content": system_prompt}]
            print("[+] Контекст очищен.\n")
            continue

        if user_input.lower() == "/env":
            env_path = ROOT_DIR / ".env"
            subprocess.Popen(["notepad.exe", str(env_path)])
            print(f"[+] Открыт {env_path} в Блокноте.\n")
            continue

        if user_input.startswith("/model"):
            parts = user_input.split(maxsplit=1)
            if len(parts) > 1 and parts[1].strip():
                current_model = parts[1].strip()
                print(f"[+] Модель переключена на: {current_model}\n")
            else:
                print(f"Текущая модель: {current_model}")
                print(f"Доступные: {', '.join(AVAILABLE_MODELS)}\n")
            continue

        conversation.append({"role": "user", "content": user_input})
        print(f"\033[1;35mИнженер анализирует...\033[0m", end="\r")

        answer = execute_agent_loop(conversation, model=current_model, api_key=api_key)
        print(" " * 50, end="\r")
        print(f"\033[1;32mИнженер:\033[0m\n{answer}\n")
        conversation.append({"role": "assistant", "content": answer})


def main():
    parser = argparse.ArgumentParser(description="Автономный AI-ассистент с доступом к ПК")
    parser.add_argument("prompt", nargs="?", default="", help="Одиночный вопрос к модели")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Имя модели (по умолчанию {DEFAULT_MODEL})")
    parser.add_argument("--key", default=DEFAULT_API_KEY, help="SmartAPI ключ")

    args = parser.parse_args()

    if args.prompt:
        system_prompt = load_project_memory()
        msgs = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": args.prompt},
        ]
        res = execute_agent_loop(msgs, model=args.model, api_key=args.key)
        print(res)
    else:
        interactive_loop(model=args.model, api_key=args.key)


if __name__ == "__main__":
    main()
