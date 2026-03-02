import asyncio
import nodriver as uc
import json
import os

async def debug_menu():
    profile_path = os.path.expanduser("~/.nanobot/workspace/skills/google-keep-skill/config/chrome-profile")
    browser = await uc.start(user_data_dir=profile_path, headless=False)
    tab = await browser.get("https://keep.google.com")
    
    print("Aguardando notas...")
    await asyncio.sleep(5)
    
    # Abrir a primeira nota
    print("Abrindo primeira nota...")
    await tab.evaluate('''
        const card = document.querySelector('div.IZ65Hb-n0tgWb');
        if (card) {
            const r = card.getBoundingClientRect();
            const x = r.x + r.width / 2;
            const y = r.y + r.height / 2;
            // Simular clique via JS para simplificar o debug
            card.click();
        }
    ''')
    await asyncio.sleep(2)
    
    # Clicar em "Mais"
    print("Clicando em 'Mais'...")
    await tab.evaluate('''
        const toolbar = document.querySelector('div[role="toolbar"]');
        if (toolbar) {
            const btn = toolbar.querySelector('div[role="button"][data-tooltip-text="Mais"]') ||
                        toolbar.querySelector('div[role="button"][aria-label="Mais"]');
            if (btn) btn.click();
        }
    ''')
    await asyncio.sleep(1)
    
    # Listar itens do menu
    print("Listando itens do menu...")
    menu_items = await tab.evaluate('''
        (() => {
            const menu = document.querySelector('div[role="menu"]');
            if (!menu) return "Menu não encontrado";
            const items = [...menu.querySelectorAll('div')];
            return items.map(i => ({
                text: i.innerText?.trim(),
                role: i.getAttribute('role'),
                children: i.children.length,
                html: i.outerHTML.substring(0, 100)
            })).filter(i => i.text);
        })()
    ''')
    
    print(json.dumps(menu_items, indent=2))
    
    await tab.save_screenshot("debug_menu_items.png")
    browser.stop()

if __name__ == "__main__":
    asyncio.run(debug_menu())
