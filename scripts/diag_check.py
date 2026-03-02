#!/usr/bin/env python3
import asyncio
import nodriver as uc
from auth import open_keep_session

async def main():
    browser, tab = await open_keep_session(headless=True)
    if not browser: return
    await asyncio.sleep(4)

    # 1. Clicar no título para abrir
    await tab.evaluate("""
        (() => {
            const cards = document.querySelectorAll('div.IZ65Hb-n0tgWb');
            for (const el of cards) {
                const titleEl = el.querySelector('div[role="textbox"]');
                if (titleEl && titleEl.innerText && titleEl.innerText.trim() === "Teste Deletar") {
                    titleEl.click();
                }
            }
        })()
    """)
    await asyncio.sleep(2)

    # 2. Clicar no botão MAIS usando JS
    clicou = await tab.evaluate("""
        (() => {
            const btns = Array.from(document.querySelectorAll('div[role="button"][data-tooltip-text="Mais"][aria-label="Mais"]'));
            const btn = btns.pop(); // Último da lista
            if (btn) {
                btn.click();
                return true;
            }
            return false;
        })()
    """)
    print(f"Clicou no botão MAIS? {clicou}")
    await asyncio.sleep(1.5)
    await tab.save_screenshot("diag_check_menu_items.png")

    # 3. Dump de todos os menuitems na tela
    dump = await tab.evaluate("""
        JSON.stringify((() => {
            const menus = Array.from(document.querySelectorAll('div[role="menu"]'));
            return menus.map((m, i) => {
                return {
                    menu_index: i,
                    visible: m.offsetWidth > 0,
                    items: Array.from(m.querySelectorAll('div[role="menuitem"], div.VIpgJd-j7LFlb-bN97Pc')).map(item => item.innerText || item.textContent)
                };
            });
        })(), null, 2)
    """)
    print("Menus na tela:")
    print(dump)
    
    browser.stop()

if __name__ == "__main__":
    asyncio.run(main())
