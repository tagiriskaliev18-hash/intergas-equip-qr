#!/usr/bin/env python3
"""
Интерактивный терминальный AI-ассистент для АО «Интергаз Центральная Азия».
Работает через SmartAPI шлюз с моделями Gemini, Claude, DeepSeek.
Автоматически считывает GEMINI.md и обладает полной памятью проекта.

Запуск:
    python scripts/ai_chat.py
    python scripts/ai_chat.py "ваш вопрос"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

# Параметры SmartAPI
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
    """Загружает базу знаний проекта из GEMINI.md"""
    gemini_md = ROOT_DIR / "GEMINI.md"
    if gemini_md.exists():
        try:
            return gemini_md.read_text(encoding="utf-8")
        except Exception:
            pass
    return "Ты — ведущий AI-инженер проекта паспортизации оборудования АО «Интергаз Центральная Азия» (ЛПУ, ГРС, КС)."


def call_smartapi(
    messages: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
    api_key: str = DEFAULT_API_KEY,
    base_url: str = DEFAULT_BASE_URL,
    max_tokens: int = 2048,
    temperature: float = 0.5,
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


def interactive_loop(model: str = DEFAULT_MODEL, api_key: str = DEFAULT_API_KEY):
    system_prompt = load_project_memory()
    conversation: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt}
    ]

    print("=" * 72)
    print(" АО «ИНТЕРГАЗ ЦЕНТРАЛЬНАЯ АЗИЯ» // ТЕРМИНАЛЬНЫЙ AI-ИНЖЕНЕР")
    print(f" Подключено через SmartAPI | Активная модель: {model}")
    print(" База знаний проекта (GEMINI.md) загружена в память.")
    print("=" * 72)
    print("Команды: /model <имя> (сменить модель) | /clear (очистить историю) | exit (выход)\n")

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

        if user_input.startswith("/model"):
            parts = user_input.split(maxsplit=1)
            if len(parts) > 1 and parts[1].strip():
                current_model = parts[1].strip()
                print(f"[+] Модель переключена на: {current_model}\n")
            else:
                print(f"Текущая модель: {current_model}")
                print(f"Доступные модели: {', '.join(AVAILABLE_MODELS)}\n")
            continue

        conversation.append({"role": "user", "content": user_input})
        print(f"\033[1;35mGemini ({current_model}) думает...\033[0m", end="\r")

        answer = call_smartapi(conversation, model=current_model, api_key=api_key)
        # Стираем индикатор
        print(" " * 50, end="\r")
        print(f"\033[1;32mИнженер:\033[0m\n{answer}\n")
        conversation.append({"role": "assistant", "content": answer})


def main():
    parser = argparse.ArgumentParser(description="Терминальный AI-ассистент через SmartAPI")
    parser.add_argument("prompt", nargs="?", default="", help="Одиночный вопрос к модели")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Имя модели (по умолчанию {DEFAULT_MODEL})")
    parser.add_argument("--key", default=DEFAULT_API_KEY, help="SmartAPI ключ")

    args = parser.parse_args()

    if args.prompt:
        # Одиночный быстрый запрос
        system_prompt = load_project_memory()
        msgs = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": args.prompt},
        ]
        res = call_smartapi(msgs, model=args.model, api_key=args.key)
        print(res)
    else:
        # Интерактивный диалог
        interactive_loop(model=args.model, api_key=args.key)


if __name__ == "__main__":
    main()
