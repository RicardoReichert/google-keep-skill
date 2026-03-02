#!/usr/bin/env python3
import asyncio
import json
import nodriver as uc
from auth import open_keep_session

async def main():
    browser, tab = await open_keep_session(headless=True)
    if not browser: return
    await asyncio.sleep(4)
    target = "Minha Nota de Teste"

    # 1. Encontrar a nota apenas no DOM fechado usando o seletor do delete e pegar info com o list
    info_fechado = await tab.evaluate(f"""
        (() => {{
            const target = "{target}";
            const cards = document.querySelectorAll('div.IZ65Hb-n0tgWb');
            for (const el of cards) {{
                const titleEl = el.querySelector('div[role="textbox"][dir="ltr"]') || el.querySelector('div[role="textbox"]');
                if (titleEl && titleEl.innerText && titleEl.innerText.trim() === target) {{
                    const title = titleEl.innerText.trim();
                    const hasCheckboxes = el.querySelector('div[role="checkbox"]') !== null;
                    let content;
                    
                    if (hasCheckboxes) {{
                        const items = [];
                        el.querySelectorAll('div[role="checkbox"]').forEach(cb => {{
                            let row = cb.parentElement;
                            while (row && row !== el) {{
                                const paras = row.querySelectorAll('p[role="presentation"]');
                                if (paras.length === 1 && row.contains(cb)) {{
                                    const span = paras[0].querySelector('span');
                                    const text = (span ? span.innerText : paras[0].innerText).trim();
                                    if (text) items.push(text);
                                    break;
                                }}
                                row = row.parentElement;
                            }}
                        }});
                        content = items;
                    }} else {{
                        const paras = el.querySelectorAll('p[role="presentation"]');
                        const lines = [];
                        paras.forEach(p => {{
                            const span = p.querySelector('span');
                            const line = (span ? span.innerText : p.innerText).trim();
                            if (line) lines.push(line);
                        }});
                        content = lines;
                    }}
                    return JSON.stringify({{ title, content, type: hasCheckboxes ? 'list' : 'text' }});
                }}
            }}
            return null;
        }})()
    """)
    print("EXTRAÇÃO FECHADA:", info_fechado)

    # 2. Clicar e abrir
    clicou = await tab.evaluate(f"""
        (() => {{
            const target = "{target}";
            const cards = document.querySelectorAll('div.IZ65Hb-n0tgWb');
            for (const el of cards) {{
                const titleEl = el.querySelector('div[role="textbox"]');
                if (titleEl && titleEl.innerText && titleEl.innerText.trim() === target) {{
                    titleEl.click();
                    return true;
                }}
            }}
            return false;
        }})()
    """)
    print("Clicou:", clicou)
    await asyncio.sleep(2)

    # 3. Extração com ela aberta (usando o seletor ativo / body completo)
    info_aberto = await tab.evaluate(f"""
        (() => {{
            const target = "{target}";
            // Encontrar o editor atualmente expandido e testar logica do list
            const editor = document.querySelector('div[role="dialog"]') || document.body;
            const titleEl = editor.querySelector('div[role="textbox"][aria-label="Título"]') || 
                            editor.querySelector('div[role="textbox"][aria-label="Title"]');
            
            if (titleEl && titleEl.innerText.trim() === target) {{
                return "Editor encontrado. Precisaria adaptar logica de extração.";
            }}
            return "Editor de nota não pareado de forma simples na raiz.";
        }})()
    """)
    print("EXTRAÇÃO ABERTA:", info_aberto)

    browser.stop()

if __name__ == "__main__":
    asyncio.run(main())
