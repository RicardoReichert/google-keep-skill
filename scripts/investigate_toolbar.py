import asyncio
import nodriver as uc
import json
import os

async def investigate_toolbar():
    profile_path = os.path.expanduser("~/.nanobot/workspace/skills/google-keep-skill/config/chrome-profile")
    browser = await uc.start(user_data_dir=profile_path, headless=False)
    tab = await browser.get("https://keep.google.com")
    
    await asyncio.sleep(5)
    
    print("Tentando abrir a nota 'Teste Deletar'...")
    clicked = await tab.evaluate('''
        (() => {
            const titles = [...document.querySelectorAll('div[role="textbox"]')];
            const title = titles.find(el => el.innerText && el.innerText.trim() === 'Teste Deletar');
            if (title) {
                title.closest('div.IZ65Hb-n0tgWb').click();
                return true;
            }
            return false;
        })()
    ''')
    
    if not clicked:
        print("Nota não encontrada")
        browser.stop()
        return
        
    await asyncio.sleep(2)
    
    print("Inspecionando botões da toolbar...")
    buttons = await tab.evaluate('''
        (() => {
            const toolbar = document.querySelector('div[role="toolbar"]');
            if (!toolbar) return "Toolbar não encontrado";
            const btns = [...toolbar.querySelectorAll('div[role="button"]')];
            return btns.map(b => ({
                ariaLabel: b.getAttribute('aria-label'),
                tooltip: b.getAttribute('data-tooltip-text'),
                role: b.getAttribute('role'),
                classes: b.className,
                html: b.outerHTML.substring(0, 200)
            }));
        })()
    ''')
    
    print(json.dumps(buttons, indent=2))
    
    await tab.save_screenshot("debug_toolbar_inspect.png")
    browser.stop()

if __name__ == "__main__":
    asyncio.run(investigate_toolbar())
