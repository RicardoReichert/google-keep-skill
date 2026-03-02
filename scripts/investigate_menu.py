import asyncio
import nodriver as uc
import json
import os

async def investigate_menu():
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
    
    print("Tentando abrir o menu 'Mais'...")
    # Tentar hover + clique
    await tab.evaluate('''
        (() => {
            const toolbar = document.querySelector('div[role="toolbar"]');
            if (!toolbar) return "Toolbar não encontrado";
            const btn = toolbar.querySelector('div[role="button"][data-tooltip-text="Mais"]') ||
                        toolbar.querySelector('div[role="button"][aria-label="Mais"]');
            if (btn) {
                // Simular hover
                btn.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
                btn.dispatchEvent(new MouseEvent('mouseenter', {bubbles: true}));
                // Clique depois de um pequeno delay no JS
                setTimeout(() => btn.click(), 100);
                return "Botão encontrado e clicado";
            }
            return "Botão não encontrado";
        })()
    ''')
    
    await asyncio.sleep(2)
    await tab.save_screenshot("debug_investigate_menu.png")
    
    print("Buscando itens de menu no DOM...")
    dom_dump = await tab.evaluate('''
        (() => {
            const allElements = [...document.querySelectorAll('*')];
            const likelyMenus = allElements.filter(el => {
                const style = window.getComputedStyle(el);
                return style.display !== 'none' && 
                       style.visibility !== 'hidden' && 
                       (el.getAttribute('role') === 'menu' || el.innerText?.includes('Excluir nota'));
            });
            
            return likelyMenus.map(m => ({
                tagName: m.tagName,
                role: m.getAttribute('role'),
                text: m.innerText?.substring(0, 100),
                rect: m.getBoundingClientRect()
            }));
        })()
    ''')
    
    print(json.dumps(dom_dump, indent=2))
    browser.stop()

if __name__ == "__main__":
    asyncio.run(investigate_menu())
