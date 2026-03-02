#!/usr/bin/env python3
import asyncio
import nodriver as uc
from auth import open_keep_session

async def main():
    browser, tab = await open_keep_session(headless=True)
    if not browser: return
    await asyncio.sleep(4)

    # Clicar no título da nota "Teste Deletar"
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
    await asyncio.sleep(3)

    # Encontrar todos os botões "Mais" na tela
    dump = await tab.evaluate("""
        JSON.stringify((() => {
            const btns = Array.from(document.querySelectorAll('div[role="button"][data-tooltip-text="Mais"][aria-label="Mais"]'));
            return btns.map((b, i) => {
                let parent = b.parentElement;
                let path = [];
                while (parent && parent !== document.body) {
                    path.push(parent.tagName + (parent.getAttribute('role') ? `[role="${parent.getAttribute('role')}"]` : ''));
                    parent = parent.parentElement;
                }
                return {
                    index: i,
                    visible: b.offsetWidth > 0,
                    x: b.getBoundingClientRect().x,
                    parent_path: path.slice(0, 5).join(' < ')
                };
            });
        })(), null, 2)
    """)
    print("Botões MAIS encontrados:")
    print(dump)
    
    browser.stop()

if __name__ == "__main__":
    asyncio.run(main())
