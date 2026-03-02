#!/usr/bin/env python3
"""Gerenciamento de sessão para o Google Keep.

Login: Chrome puro (sem automação) para interação normal do usuário.
Operações: nodriver (headless) reutilizando o perfil/cookies.
"""

import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import nodriver as uc

CONFIG_DIR = Path(__file__).parent.parent / "config"
PROFILE_DIR = CONFIG_DIR / "chrome-profile"
COOKIES_FILE = CONFIG_DIR / "cookies.json"
KEEP_URL = "https://keep.google.com/"


def _find_chrome() -> str:
    """Localiza o executável do Chrome no sistema."""
    candidates = [
        "google-chrome",
        "google-chrome-stable",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
    ]
    for c in candidates:
        result = shutil.which(c)
        if result:
            return result
    raise FileNotFoundError("Google Chrome não encontrado. Instale com: sudo apt install google-chrome-stable")


def interactive_login() -> bool:
    """Abre Chrome puro (sem automação) para login manual.

    O usuário interage normalmente — todos os botões funcionam.
    Ao fechar o Chrome, o perfil e cookies são salvos automaticamente.
    """
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    chrome = _find_chrome()

    print("=" * 60, flush=True)
    print("  LOGIN NO GOOGLE KEEP", flush=True)
    print("=" * 60, flush=True)
    print(flush=True)
    print("Chrome será aberto normalmente (sem automação).", flush=True)
    print("1. Faça login na sua conta Google", flush=True)
    print("2. Aguarde o Google Keep carregar", flush=True)
    print("3. FECHE o navegador (clique no X)", flush=True)
    print(flush=True)
    print("A sessão será salva automaticamente ao fechar.", flush=True)
    print(flush=True)

    cmd = [
        chrome,
        f"--user-data-dir={PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-default-apps",
        "--new-window",
        KEEP_URL,
    ]

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("Chrome aberto. Aguardando você fechar o navegador...", flush=True)
        proc.wait()
        print("Chrome fechado.", flush=True)
        print(flush=True)

        # Após fechar, extrair cookies do perfil via nodriver (headless rápido)
        print("Extraindo cookies da sessão...", flush=True)
        ok = uc.loop().run_until_complete(_extract_and_save_cookies())
        if ok:
            print("Sessão salva com sucesso!", flush=True)
        else:
            print("Aviso: não foi possível verificar a sessão.", flush=True)
            print("Tente executar 'check' para confirmar.", flush=True)
        return ok

    except FileNotFoundError:
        print(f"Erro: Chrome não encontrado em {chrome}", flush=True)
        return False
    except Exception as e:
        print(f"Erro: {e}", flush=True)
        return False


async def _extract_and_save_cookies() -> bool:
    """Abre headless com o perfil, navega ao Keep e salva cookies via CDP."""
    browser = await _start_nodriver(headless=True)
    tab = browser.main_tab

    await tab.get(KEEP_URL)
    await asyncio.sleep(4)

    url = tab.target.url
    if "accounts.google" in url:
        browser.stop()
        return False

    await _save_cookies_cdp(tab)
    browser.stop()
    return True


async def _start_nodriver(*, headless: bool = True, use_temp_profile: bool = False) -> uc.Browser:
    """Inicia nodriver. Usa perfil temporário se use_temp_profile=True (dados frescos do servidor)."""
    kwargs = {
        "headless": headless,
        "browser_args": [
            "--no-first-run",
            "--no-default-browser-check",
            "--lang=pt-BR",
            "--window-size=1920,1080",
            "--disable-session-crashed-bubble",
            "--disable-infobars",
        ],
    }
    if not use_temp_profile:
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        kwargs["user_data_dir"] = str(PROFILE_DIR)
    browser = await uc.start(**kwargs)
    return browser


async def _save_cookies_cdp(tab) -> None:
    """Salva cookies via CDP em arquivo JSON."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    cookies = await tab.send(uc.cdp.network.get_all_cookies())
    cookie_list = []
    for c in cookies:
        cookie_list.append({
            "name": c.name,
            "value": c.value,
            "domain": c.domain,
            "path": c.path,
            "secure": c.secure,
            "httpOnly": c.http_only,
            "sameSite": c.same_site.value if c.same_site else "None",
        })
    with open(COOKIES_FILE, "w") as f:
        json.dump(cookie_list, f)
    COOKIES_FILE.chmod(0o600)
    print(f"  {len(cookie_list)} cookies salvos.", flush=True)


async def _restore_cookies_cdp(tab) -> bool:
    """Restaura cookies salvos via CDP."""
    if not COOKIES_FILE.exists():
        return False
    try:
        with open(COOKIES_FILE, "r") as f:
            cookie_list = json.load(f)

        for c in cookie_list:
            same_site = None
            raw = c.get("sameSite", "None")
            if raw == "Strict":
                same_site = uc.cdp.network.CookieSameSite("Strict")
            elif raw == "Lax":
                same_site = uc.cdp.network.CookieSameSite("Lax")
            elif raw == "None":
                same_site = uc.cdp.network.CookieSameSite("None")

            await tab.send(uc.cdp.network.set_cookie(
                name=c["name"],
                value=c["value"],
                domain=c.get("domain", ""),
                path=c.get("path", "/"),
                secure=c.get("secure", False),
                http_only=c.get("httpOnly", False),
                same_site=same_site,
            ))
        return True
    except Exception:
        return False


async def open_keep_session(*, headless: bool = True):
    """Abre Keep com sessão restaurada (perfil persistente + cookies CDP)."""
    browser = await _start_nodriver(headless=headless)
    tab = browser.main_tab

    await _restore_cookies_cdp(tab)

    try:
        await tab.send(uc.cdp.storage.clear_data_for_origin(
            origin="https://keep.google.com",
            storage_types="indexeddb,cache_storage,local_storage",
        ))
    except Exception:
        pass

    await tab.get(KEEP_URL)
    await asyncio.sleep(5)

    url = tab.target.url
    if "accounts.google" in url:
        browser.stop()
        return None, None

    return browser, tab


async def check_session_async() -> bool:
    """Verifica se a sessão está ativa."""
    browser, tab = await open_keep_session(headless=True)
    if not browser:
        return False
    browser.stop()
    return True


def clear_session() -> bool:
    """Remove perfil e cookies."""
    if PROFILE_DIR.exists():
        shutil.rmtree(PROFILE_DIR, ignore_errors=True)
    if COOKIES_FILE.exists():
        COOKIES_FILE.unlink()
    print("Sessão removida.", flush=True)
    return True


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "login"

    if cmd == "login":
        ok = interactive_login()
        sys.exit(0 if ok else 1)
    elif cmd == "check":
        ok = uc.loop().run_until_complete(check_session_async())
        print(f"Sessão ativa: {ok}", flush=True)
        sys.exit(0 if ok else 1)
    elif cmd == "clear":
        clear_session()
    else:
        print("Uso: auth.py [login|check|clear]", flush=True)
