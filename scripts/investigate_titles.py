import asyncio
import nodriver as uc
import json
import os

async def investigate_titles():
    profile_path = os.path.expanduser("~/.nanobot/workspace/skills/google-keep-skill/config/chrome-profile")
    browser = await uc.start(user_data_dir=profile_path, headless=False)
    tab = await browser.get("https://keep.google.com")
    
    await asyncio.sleep(5)
    
    print("Listando títulos de todas as notas...")
    notes = await tab.evaluate('''
        (() => {
            const cards = [...document.querySelectorAll('div.IZ65Hb-n0tgWb')];
            return cards.map(el => {
                const titleEl = el.querySelector('div[role="textbox"][dir="ltr"]') || el.querySelector('div[role="textbox"]');
                return {
                    innerText: titleEl ? titleEl.innerText : 'N/A',
                    innerTextTrimmed: titleEl ? titleEl.innerText.trim() : 'N/A',
                    textContent: titleEl ? titleEl.textContent : 'N/A',
                    classes: el.className,
                    id: el.id,
                    isPlaceholder: !!el.querySelector('div[role="combobox"]')
                };
            });
        })()
    ''')
    
    print(json.dumps(notes, indent=2))
    browser.stop()

if __name__ == "__main__":
    asyncio.run(investigate_titles())
