#!/usr/bin/env python3
"""Google Keep Manager — CLI para interagir com o Google Keep via nodriver."""

import argparse
import asyncio
import json
import sys
from typing import Optional

import nodriver as uc

from auth import open_keep_session, interactive_login, clear_session

KEEP_URL = "https://keep.google.com/"


def _output(success: bool, message: str, data: Optional[dict] = None) -> None:
    """Imprime resultado em JSON padronizado."""
    result = {"success": success, "message": message}
    if data is not None:
        result["data"] = data
    print(json.dumps(result, ensure_ascii=False, indent=2))


async def _cdp_click(tab, x: int, y: int) -> None:
    """Dispara clique real via CDP Input.dispatchMouseEvent (hover + click)."""
    await tab.send(uc.cdp.input_.dispatch_mouse_event(
        type_="mouseMoved", x=x, y=y,
        button=uc.cdp.input_.MouseButton("none")))
    await asyncio.sleep(0.3)
    await tab.send(uc.cdp.input_.dispatch_mouse_event(
        type_="mousePressed", x=x, y=y,
        button=uc.cdp.input_.MouseButton("left"), click_count=1))
    await asyncio.sleep(0.1)
    await tab.send(uc.cdp.input_.dispatch_mouse_event(
        type_="mouseReleased", x=x, y=y,
        button=uc.cdp.input_.MouseButton("left"), click_count=1))


async def _get_element_center(tab, js_selector: str) -> tuple[int, int] | None:
    """Retorna (x, y) do centro de um elemento via JS. None se não encontrado."""
    result = await tab.evaluate(f"""
        JSON.stringify((() => {{
            {js_selector}
        }})())
    """)
    if isinstance(result, str):
        import json as _json
        data = _json.loads(result)
        if data and isinstance(data, dict) and "x" in data:
            return int(data["x"]), int(data["y"])
    return None


async def _click_button_in_editor(tab, label: str) -> bool:
    """Clica em botão da toolbar da nota aberta via CDP mouse click.

    Localiza o botão dentro do container do editor (próximo ao 'Fechar').
    """
    coords = await _get_element_center(tab, f"""
        const label = "{label}";
        const closeBtn = [...document.querySelectorAll('div[role="button"]')]
            .find(b => b.innerText?.trim() === 'Fechar' && b.offsetParent !== null);
        if (!closeBtn) return null;
        const toolbar = closeBtn.parentElement;
        let btn = toolbar.querySelector('[role="button"][aria-label="' + label + '"]');
        if (!btn || btn.offsetParent === null) {{
            for (const b of toolbar.querySelectorAll('[role="button"]')) {{
                if (b.innerText?.trim() === label && b.offsetParent !== null) {{ btn = b; break; }}
            }}
        }}
        if (!btn || btn.offsetParent === null) return null;
        const r = btn.getBoundingClientRect();
        return {{x: r.x + r.width / 2, y: r.y + r.height / 2}};
    """)
    if not coords:
        return False
    await _cdp_click(tab, *coords)
    return True



async def _open_keep(headless: bool = True) -> tuple:
    """Abre o Keep e verifica se está logado. Retorna (browser, tab) ou (None, None)."""
    browser, tab = await open_keep_session(headless=headless)
    if not browser:
        _output(False, "Sessão expirada. Execute: uv run python scripts/keep.py login")
        return None, None
    return browser, tab


async def _wait_notes(tab) -> None:
    """Aguarda carregamento das notas."""
    for _ in range(10):
        notes = await tab.query_selector_all("div.IZ65Hb-n0tgWb")
        if notes:
            return
        await asyncio.sleep(1)


async def _wait_for_element(tab, selector: str, timeout: int = 10) -> bool:
    """Aguarda um seletor ficar visível e ter offsetParent != null."""
    for _ in range(timeout * 2):
        res = await tab.evaluate(f"document.querySelector('{selector}')?.offsetParent !== null")
        if res:
            return True
        await asyncio.sleep(0.5)
    return False


async def _extract_all_notes(tab) -> list[dict]:
    """Extrai dados de todas as notas visíveis.

    - Título: div[role="textbox"][dir="ltr"] dentro do card.
    - Lista (card com checkbox): presença de div[role="checkbox"] no card → content é array de strings (um por item).
    - Nota normal (só texto): content é string com \\n entre as linhas (cada p[role=presentation] = linha).
    Ignora apenas o placeholder "Criar uma nota…".
    """
    result = await tab.evaluate("""
        JSON.stringify((() => {
            const notes = [];
            document.querySelectorAll('div.IZ65Hb-n0tgWb').forEach((el, i) => {
                if (el.querySelector('div[role="combobox"]')) return;

                const titleEl = el.querySelector('div[role="textbox"][dir="ltr"]') || el.querySelector('div[role="textbox"]');
                const title = titleEl ? titleEl.innerText.trim() : '';
                
                const hasCheckboxes = el.querySelector('div[role="checkbox"]') !== null;
                let content;
                
                if (hasCheckboxes) {
                    const items = [];
                    el.querySelectorAll('div[role="checkbox"]').forEach(cb => {
                        let row = cb.parentElement;
                        while (row && row !== el) {
                            const paras = row.querySelectorAll('p[role="presentation"]');
                            if (paras.length === 1 && row.contains(cb)) {
                                const span = paras[0].querySelector('span');
                                const text = (span ? span.innerText : paras[0].innerText).trim();
                                if (text) items.push(text);
                                break;
                            }
                            row = row.parentElement;
                        }
                    });
                    content = items;
                } else {
                    const paras = el.querySelectorAll('p[role="presentation"]');
                    const lines = [];
                    paras.forEach(p => {
                        const span = p.querySelector('span');
                        const line = (span ? span.innerText : p.innerText).trim();
                        if (line) lines.push(line);
                    });
                    content = lines;
                }
                
                const isEmpty = Array.isArray(content) ? content.length === 0 : !content;
                if (!title && isEmpty) return;
                
                notes.push({
                    id: (notes.length + 1).toString(),
                    title: title,
                    content: content,
                    type: hasCheckboxes ? 'list' : 'text'
                });
            });
            return notes;
        })())
    """)
    if isinstance(result, str):
        return json.loads(result)
    return result if isinstance(result, list) else []


async def _find_and_click_note(tab, title: str) -> bool:
    """Encontra nota pelo título (div[role=textbox] com esse texto) e clica no card."""
    target_js = json.dumps(title)
    found = await tab.evaluate(f"""
        (() => {{
            const target = {target_js};
            const cards = document.querySelectorAll('div.IZ65Hb-n0tgWb');
            for (const el of cards) {{
                const titleEl = el.querySelector('div[role="textbox"][dir="ltr"]') || el.querySelector('div[role="textbox"]');
                if (titleEl && titleEl.innerText.trim() === target) {{
                    el.click();
                    return true;
                }}
            }}
            return false;
        }})()
    """)
    return bool(found)


async def _find_and_click_note_by_title_textbox(tab, title: str) -> bool:
    """Encontra nota por div role=textbox cujo texto é o título e clica nela.

    Ao abrir a nota, o cursor fica no início do texto de descrição.
    """
    target_js = json.dumps(title)
    coords = await _eval_coords(tab, f"""
        const target = {target_js};
        const divs = document.querySelectorAll('div[role="textbox"][dir="ltr"], div[role="textbox"]');
        for (const d of divs) {{
            if (d.offsetParent === null) continue;
            if (d.innerText?.trim() === target) {{
                const r = d.getBoundingClientRect();
                return {{x: r.x + r.width / 2, y: r.y + r.height / 2}};
            }}
        }}
        return null;
    """)
    if not coords:
        return False
    await _cdp_click(tab, *coords)
    return True


# ── Comandos ──────────────────────────────────────────────────

async def cmd_list(args) -> None:
    """Lista notas do Google Keep."""
    browser, tab = await _open_keep(headless=not getattr(args, 'visible', False))
    if not browser:
        return

    try:
        await _wait_notes(tab)
        all_notes = await _extract_all_notes(tab)

        notes = []
        for data in all_notes:
            if len(notes) >= args.limit:
                break
            if args.filter_text:
                term = args.filter_text.lower()
                title = (data.get("title") or "").lower()
                content = data.get("content") or []
                content_str = " ".join(content) if isinstance(content, list) else str(content)
                if term not in title and term not in content_str.lower():
                    continue
            notes.append(data)

        _output(True, f"{len(notes)} nota(s) encontrada(s)", {"notes": notes})
    finally:
        browser.stop()


async def cmd_create(args) -> None:
    """Cria uma nota de texto simples (seguindo o fluxo preciso)."""
    browser, tab = await _open_keep(headless=not getattr(args, 'visible', False))
    if not browser:
        return

    try:
        await _wait_notes(tab)

        # 1. Encontrar o texto "Criar uma nota…" e clicar com o mouse (CDP click)
        if not await _click_div_with_text(tab, "Criar uma nota…"):
            await _click_div_with_text(tab, "Take a note…")
        # Aguardar a expansão do HTML
        await asyncio.sleep(1.5)

        # 2. O conteúdo pode ser multilinhas (um array). Vamos dividir e preencher.
        if args.content:
            try:
                import json
                parsed = json.loads(args.content)
                if isinstance(parsed, list):
                    lines = [str(x) for x in parsed]
                else:
                    lines = args.content.replace('\\n', '\n').splitlines()
            except Exception:
                lines = args.content.replace('\\n', '\n').splitlines()

            for i, line in enumerate(lines):
                escaped = line.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
                await tab.evaluate(f"""
                    (() => {{
                        // Na nota normal, o cursor já está no description box.
                        let target = document.activeElement;
                        if (!target || target.getAttribute('role') === 'button' || target.tagName === 'BODY') {{
                            // Fallback caso tenhamos perdido o foco. Procurar o corpo da nota.
                            const editor = document.querySelector('.IZ65Hb-WsjYwc-nUpftc') || document.body;
                            // Corpo normalmente é o textbox que não é o título
                            const editables = [...editor.querySelectorAll('[role="textbox"]:not([aria-label="Título"]):not([aria-label="Title"])')];
                            if (editables.length > 0) target = editables[0];
                        }}
                        if (target) {{
                            target.focus();
                            document.execCommand('insertText', false, `{escaped}`);
                        }}
                    }})()
                """)
                if i < len(lines) - 1:
                    await _press_enter(tab)
                    await asyncio.sleep(0.3)

        # 3. Preencher Título
        if args.title:
            escaped_title = args.title.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
            await tab.evaluate(f"""
                (() => {{
                    // Procurar explicitamente pelo ari-label Título
                    const titleEl = document.querySelector('div[role="textbox"][aria-label="Título"]') || 
                                    document.querySelector('div[role="textbox"][aria-label="Title"]');
                    if (titleEl) {{
                        // Clicar ativa o cursor
                        titleEl.click();
                        titleEl.focus();
                        document.execCommand('insertText', false, `{escaped_title}`);
                    }}
                }})()
            """)
            await asyncio.sleep(0.5)

        # 4. Fechar procurando pela tag com texto Fechar
        await tab.save_screenshot("debug_create_normal.png")
        await tab.evaluate('''
            (() => {
                const btns = [...document.querySelectorAll('div[role="button"]')];
                const closeBtn = btns.find(e => e.innerText && e.innerText.trim() === 'Fechar');
                if (closeBtn) closeBtn.click();
            })();
        ''')
        await asyncio.sleep(12) # Aguardar sincronização final com a nuvem

        _output(True, "Nota criada com sucesso", {"title": args.title})
    except Exception as e:
        _output(False, f"Erro ao criar nota: {e}")
    finally:
        browser.stop()


async def cmd_create_list(args) -> None:
    """Cria uma nota tipo lista."""
    browser, tab = await _open_keep(headless=not getattr(args, 'visible', False))
    if not browser:
        return

    items = args.items
    if isinstance(items, str):
        items = [s.strip() for s in items.replace(",", "\n").split("\n") if s.strip()]
    if not items:
        _output(False, "Informe ao menos um item (--items)")
        return

    try:
        # 1. Abrir editor de lista clicando no botão 'Nova lista'
        coords = await _eval_coords(tab, '''
            const btn = document.querySelector('div[role="button"][data-tooltip-text="Nova lista"][aria-label="Nova lista"]');
            if (!btn || btn.offsetParent === null) return null;
            const r = btn.getBoundingClientRect();
            return {x: r.x + r.width / 2, y: r.y + r.height / 2};
        ''')
        
        if not coords:
            # Fallback
            await tab.evaluate('document.querySelector(\'div[role="combobox"]\')?.click()')
            await asyncio.sleep(1)
            _output(False, "Botão 'Nova lista' não encontrado visualmente")
            return
            
        await _cdp_click(tab, *coords)
        if not await _wait_for_element(tab, 'div.IZ65Hb-WsjYwc-nUpftc [contenteditable="true"]', timeout=5):
            _output(False, "Editor de lista não abriu após o clique")
            return

        # 2. Preencher itens
        # O Google Keep foca automaticamente no primeiro item da lista ao usar o atalho
        for i, item in enumerate(items):
            escaped = item.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
            if i > 0:
                await _press_enter(tab)
                await asyncio.sleep(0.5)

            await tab.evaluate(f"""
                (() => {{
                    // Escreve diretamente no elemento atualmente focado pelo Keep
                    const target = document.activeElement;
                    if (target && target.getAttribute('contenteditable') === 'true') {{
                        document.execCommand('insertText', false, `{escaped}`);
                    }}
                }})()
            """)
            await asyncio.sleep(0.2)

        # 3. Preencher Título
        if args.title:
            escaped_title = args.title.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
            # Encontrar e clicar na div que contém o texto "Título" (o placeholder)
            coords = await _eval_coords(tab, """
                const divs = document.querySelectorAll('div');
                for (const d of divs) {
                    if (d.innerText && (d.innerText.trim() === 'Título' || d.innerText.trim() === 'Title') && d.children.length === 0) {
                        const r = d.getBoundingClientRect();
                        return {x: r.x + r.width / 2, y: r.y + r.height / 2};
                    }
                }
                return null;
            """)
            if coords:
                await _cdp_click(tab, *coords)
                await asyncio.sleep(0.5)
                # O cursor agora está ativo no campo de título, podemos inserir o texto
                await tab.evaluate(f"""
                    (() => {{
                        document.execCommand('insertText', false, `{escaped_title}`);
                    }})()
                """)
            else:
                _output(False, "Não foi possível encontrar o campo de Título")

        # 4. Fechar
        await tab.save_screenshot("debug_create_list.png")
        await _click_button_in_editor(tab, "Fechar")
        await asyncio.sleep(12) # Aguardar sincronização final com a nuvem

        _output(True, "Lista criada com sucesso", {"title": args.title})
    except Exception as e:
        _output(False, f"Erro ao criar lista: {e}")
    finally:
        browser.stop()


async def cmd_read(args) -> None:
    """Lê uma nota pelo título."""
    browser, tab = await _open_keep(headless=not getattr(args, 'visible', False))
    if not browser:
        return

    try:
        await _wait_notes(tab)
        target_js = json.dumps(args.title)
        
        note_data = await tab.evaluate(f"""
            (() => {{
                const target = {target_js};
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
                        
                        return JSON.stringify({{
                            title: title,
                            content: content,
                            type: hasCheckboxes ? 'list' : 'text'
                        }});
                    }}
                }}
                return null;
            }})()
        """)
        
        if note_data:
            _output(True, "Nota encontrada", json.loads(note_data))
        else:
            _output(False, f"Nota '{args.title}' não encontrada")
    except Exception as e:
        _output(False, f"Erro ao ler nota: {e}")
    finally:
        browser.stop()


async def cmd_update(args) -> None:
    """Atualiza uma nota existente.

    Fluxo: buscar nota por div[role=textbox] com texto = título → clicar → nota abre.
    - Título: div[role=textbox][dir=ltr]; usa insertText.
    - Nota texto: corpo em contenteditable sem role=textbox; --content com \\n.
    - Nota lista: itens em div[aria-label="item da lista"]; --items "A,B,C" ou --content;
      primeiro item no primeiro div, demais no próximo existente ou em novo (clique "Item da lista").
    """
    browser, tab = await _open_keep(headless=not getattr(args, 'visible', False))
    if not browser:
        return

    try:
        await _wait_notes(tab)
        clicked = await _find_and_click_note_by_title_textbox(tab, args.title)
        if not clicked:
            clicked = await _find_and_click_note(tab, args.title)
        if not clicked:
            _output(False, f"Nota '{args.title}' não encontrada")
            return

        await asyncio.sleep(1)

        # Card da nota aberta = ancestral do botão Fechar (evita atingir área "Criar uma nota")
        open_card_js = """
            var btn = Array.from(document.querySelectorAll('div[role="button"]')).find(b => b.innerText && b.innerText.trim() === 'Fechar');
            return btn ? btn.closest('div.IZ65Hb-n0tgWb') : null;
        """

        if args.new_title:
            escaped = args.new_title.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
            await tab.evaluate(f"""
                (() => {{
                    const card = (() => {{ {open_card_js} }})();
                    if (!card) return;
                    const titleEl = card.querySelector('div[role="textbox"][dir="ltr"]') || card.querySelector('div[role="textbox"]');
                    if (!titleEl || titleEl.offsetParent === null) return;
                    titleEl.focus();
                    const sel = document.getSelection();
                    const range = document.createRange();
                    range.selectNodeContents(titleEl);
                    sel.removeAllRanges();
                    sel.addRange(range);
                    document.execCommand('insertText', false, `{escaped}`);
                }})()
            """)
            await asyncio.sleep(0.3)

        # Detectar se a nota aberta é lista (dentro do card aberto)
        is_list = await tab.evaluate(f"""
            (() => {{
                const card = (() => {{ {open_card_js} }})();
                return card ? card.querySelector('div[aria-label="item da lista"]') !== null : false;
            }})();
        """)
        is_list = bool(is_list)

        if is_list and (args.items or args.content):
            items_src = args.items or args.content or ""
            items = [s.strip() for s in items_src.replace(",", "\n").split("\n") if s.strip()]
            if items:
                item_count = 0
                for idx, item in enumerate(items):
                    escaped_item = item.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${}")
                    if idx == 0:
                        coords = await _eval_coords(tab, f"""
                            const card = (() => {{ {open_card_js} }})();
                            if (!card) return null;
                            const el = card.querySelector('div[aria-label="item da lista"]');
                            if (!el || el.offsetParent === null) return null;
                            const r = el.getBoundingClientRect();
                            return {{x: r.x + r.width / 2, y: r.y + r.height / 2}};
                        """)
                    else:
                        item_divs = await tab.evaluate(f"""
                            (() => {{
                                const card = (() => {{ {open_card_js} }})();
                                if (!card) return 0;
                                return card.querySelectorAll('div[aria-label="item da lista"]').length;
                            }})()
                        """)
                        item_count = int(item_divs) if isinstance(item_divs, (int, float)) else 0
                        if idx < item_count:
                            coords = await _eval_coords(tab, f"""
                                const card = (() => {{ {open_card_js} }})();
                                if (!card) return null;
                                const divs = card.querySelectorAll('div[aria-label="item da lista"]');
                                const el = divs[{idx}];
                                if (!el || el.offsetParent === null) return null;
                                const r = el.getBoundingClientRect();
                                return {{x: r.x + r.width / 2, y: r.y + r.height / 2}};
                            """)
                        else:
                            coords = await _eval_coords(tab, f"""
                                const card = (() => {{ {open_card_js} }})();
                                if (!card) return null;
                                const btn = card.querySelector('div[role="button"][aria-label="Adicionar item de lista"]')
                                    || Array.from(card.querySelectorAll('div')).find(d => d.innerText && d.innerText.trim() === 'Item da lista');
                                if (!btn || btn.offsetParent === null) return null;
                                const r = btn.getBoundingClientRect();
                                return {{x: r.x + r.width / 2, y: r.y + r.height / 2}};
                            """)
                    if not coords:
                        if idx == 0:
                            _output(False, "Campo 'item da lista' não encontrado na nota lista")
                        break
                    await _cdp_click(tab, *coords)
                    await asyncio.sleep(0.4 if (idx > 0 and idx >= item_count) else 0.35)
                    await tab.evaluate(f"""
                        (() => {{
                            const card = (() => {{ {open_card_js} }})();
                            if (!card) return false;
                            const divs = card.querySelectorAll('div[aria-label="item da lista"]');
                            const el = divs.length > {idx} ? divs[{idx}] : (divs.length > 0 ? divs[divs.length - 1] : document.activeElement);
                            if (!el) return false;
                            el.focus();
                            const sel = document.getSelection();
                            const range = document.createRange();
                            range.selectNodeContents(el);
                            sel.removeAllRanges();
                            sel.addRange(range);
                            document.execCommand('insertText', false, `{escaped_item}`);
                            return true;
                        }})()
                    """)
                    await asyncio.sleep(0.25)
        elif not is_list and args.content:
            # Mesma estrutura da lista: linhas como array; cada linha = um "slot" (p[role="presentation"] no combobox).
            # Primeiro slot = limpar combobox e insertText; demais = ENTER se preciso, depois clicar no p e insertText.
            content_normalized = args.content.replace("\\n", "\n")
            lines = [s for s in content_normalized.split("\n")]
            if lines:
                for idx, line in enumerate(lines):
                    escaped = line.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${}")
                    if idx == 0:
                        coords = await _eval_coords(tab, f"""
                            const card = (() => {{ {open_card_js} }})();
                            if (!card) return null;
                            const box = card.querySelector('div[role="combobox"]');
                            if (!box || box.offsetParent === null) return null;
                            const r = box.getBoundingClientRect();
                            return {{x: r.x + r.width / 2, y: r.y + r.height / 2}};
                        """)
                        if not coords:
                            _output(False, "Corpo da nota (combobox) não encontrado no card")
                            break
                        await _cdp_click(tab, *coords)
                        await asyncio.sleep(0.35)
                        await tab.evaluate(f"""
                            (() => {{
                                const card = (() => {{ {open_card_js} }})();
                                if (!card) return;
                                const box = card.querySelector('div[role="combobox"]');
                                if (!box) return;
                                box.focus();
                                const sel = document.getSelection();
                                const range = document.createRange();
                                range.selectNodeContents(box);
                                sel.removeAllRanges();
                                sel.addRange(range);
                                document.execCommand('delete', false, null);
                            }})()
                        """)
                        await asyncio.sleep(0.2)
                        await tab.evaluate(f"""
                            (() => {{
                                const card = (() => {{ {open_card_js} }})();
                                if (!card) return;
                                const box = card.querySelector('div[role="combobox"]');
                                if (!box) return;
                                box.focus();
                                const sel = document.getSelection();
                                const range = document.createRange();
                                range.selectNodeContents(box);
                                sel.removeAllRanges();
                                sel.addRange(range);
                                document.execCommand('insertText', false, `{escaped}`);
                            }})()
                        """)
                    else:
                        paras_count = await tab.evaluate(f"""
                            (() => {{
                                const card = (() => {{ {open_card_js} }})();
                                if (!card) return 0;
                                const box = card.querySelector('div[role="combobox"]');
                                return box ? box.querySelectorAll('p[role="presentation"]').length : 0;
                            }})()
                        """)
                        paras_count = int(paras_count) if isinstance(paras_count, (int, float)) else 0
                        if idx >= paras_count:
                            await tab.evaluate(f"""
                                (() => {{
                                    const card = (() => {{ {open_card_js} }})();
                                    if (!card) return;
                                    const box = card.querySelector('div[role="combobox"]');
                                    if (!box) return;
                                    box.focus();
                                    const sel = document.getSelection();
                                    const range = document.createRange();
                                    range.selectNodeContents(box);
                                    range.collapse(false);
                                    sel.removeAllRanges();
                                    sel.addRange(range);
                                }})()
                            """)
                            await asyncio.sleep(0.1)
                            await _press_enter(tab)
                            await asyncio.sleep(0.35)
                        coords = await _eval_coords(tab, f"""
                            const card = (() => {{ {open_card_js} }})();
                            if (!card) return null;
                            const box = card.querySelector('div[role="combobox"]');
                            if (!box) return null;
                            const paras = box.querySelectorAll('p[role="presentation"]');
                            const el = paras.length > {idx} ? paras[{idx}] : paras[paras.length - 1];
                            if (!el || el.offsetParent === null) return null;
                            const r = el.getBoundingClientRect();
                            return {{x: r.x + r.width / 2, y: r.y + r.height / 2}};
                        """)
                        if not coords:
                            break
                        await _cdp_click(tab, *coords)
                        await asyncio.sleep(0.3)
                        await tab.evaluate(f"""
                            (() => {{
                                const card = (() => {{ {open_card_js} }})();
                                if (!card) return;
                                const box = card.querySelector('div[role="combobox"]');
                                if (!box) return;
                                const paras = box.querySelectorAll('p[role="presentation"]');
                                const el = paras.length > {idx} ? paras[{idx}] : paras[paras.length - 1];
                                if (!el) return;
                                el.focus();
                                const sel = document.getSelection();
                                const range = document.createRange();
                                range.selectNodeContents(el);
                                sel.removeAllRanges();
                                sel.addRange(range);
                                document.execCommand('insertText', false, `{escaped}`);
                            }})()
                        """)
                    await asyncio.sleep(0.2)
            await asyncio.sleep(0.2)

        await _click_button_in_editor(tab, "Fechar")
        await asyncio.sleep(12) # Aguardar sincronização final com a nuvem

        _output(True, "Nota atualizada com sucesso")
    except Exception as e:
        _output(False, f"Erro ao atualizar nota: {e}")
    finally:
        browser.stop()


async def _eval_coords(tab, js: str) -> tuple[int, int] | None:
    """Avalia JS que retorna {x, y} e retorna (x, y) inteiros."""
    result = await tab.evaluate(f"JSON.stringify((() => {{ {js} }})())")
    if isinstance(result, str):
        data = json.loads(result)
        if data and isinstance(data, dict) and "x" in data:
            return int(data["x"]), int(data["y"])
    return None


async def _click_div_with_text(tab, text: str) -> bool:
    """Clica em uma div visível cujo texto (trim) seja exatamente o informado."""
    coords = await _eval_coords(tab, f"""
        const target = {json.dumps(text)};
        const divs = document.querySelectorAll('div');
        for (const d of divs) {{
            if (d.offsetParent === null) continue;
            if (d.children.length > 0) continue;
            if (d.innerText?.trim() === target) {{
                const r = d.getBoundingClientRect();
                return {{x: r.x + r.width / 2, y: r.y + r.height / 2}};
            }}
        }}
        return null;
    """)
    if not coords:
        return False
    await _cdp_click(tab, *coords)
    return True


async def _press_enter(tab) -> None:
    """Envia tecla Enter via CDP."""
    await tab.send(uc.cdp.input_.dispatch_key_event(type_="keyDown", key="Enter", code="Enter", windows_virtual_key_code=13))
    await asyncio.sleep(0.05)
    await tab.send(uc.cdp.input_.dispatch_key_event(type_="keyUp", key="Enter", code="Enter", windows_virtual_key_code=13))


async def cmd_delete(args) -> None:
    """Abre a nota e move para lixeira.

    Fluxo:
      1. Localizar o card da nota pelo título e clicar (CDP) para abrir.
      2. Encontrar div[role='button'][data-tooltip-text='Mais'][aria-label='Mais'] e clicar.
      3. Encontrar div com texto 'Excluir nota' e clicar.
    """
    browser, tab = await _open_keep(headless=not getattr(args, 'visible', False))
    if not browser:
        return

async def cmd_delete(args) -> None:
    """Abre a nota e move para lixeira (seguindo o fluxo preciso de clique no título)."""
    browser, tab = await _open_keep(headless=not getattr(args, 'visible', False))
    if not browser:
        return

    try:
        await _wait_notes(tab)
        target_js = json.dumps(args.title)

        # 1. Localizar o título da nota e clicar
        is_opened = await tab.evaluate(f"""
            (() => {{
                const target = {target_js};
                const cards = document.querySelectorAll('div.IZ65Hb-n0tgWb');
                for (const el of cards) {{
                    const titleEl = el.querySelector('div[role="textbox"][dir="ltr"]') || el.querySelector('div[role="textbox"]');
                    if (titleEl && titleEl.innerText && titleEl.innerText.trim() === target) {{
                        titleEl.click();
                        return true;
                    }}
                }}
                return false;
            }})()
        """)
        if not is_opened:
            _output(False, f"Nota '{args.title}' não encontrada para exclusão")
            return

        await asyncio.sleep(2)

        # 2. Procurar div com role="button", data-tooltip-text="Mais" e aria-label="Mais" e clicar via CDP
        mais_c = await _eval_coords(tab, """
            const btns = Array.from(document.querySelectorAll('div[role="button"][data-tooltip-text="Mais"][aria-label="Mais"]'));
            const btn = btns.pop();
            if (btn) {
                const r = btn.getBoundingClientRect();
                return {x: r.x + r.width / 2, y: r.y + r.height / 2};
            }
            return null;
        """)
        if not mais_c:
            _output(False, "Botão 'Mais' não encontrado")
            return

        await _cdp_click(tab, *mais_c)
        await asyncio.sleep(1.5)

        # 3. Procurar div com texto "Excluir nota" e clicar via CDP
        excl_c = await _eval_coords(tab, """
            const divs = Array.from(document.querySelectorAll('div'));
            const btn = divs.reverse().find(d => d.innerText && d.innerText.trim() === 'Excluir nota' && d.offsetWidth > 0);
            if (btn) {
                const r = btn.getBoundingClientRect();
                return {x: r.x + r.width / 2, y: r.y + r.height / 2};
            }
            return null;
        """)
        if not excl_c:
            _output(False, "Opção 'Excluir nota' não encontrada no menu")
            return

        await _cdp_click(tab, *excl_c)        

        await asyncio.sleep(12) # Aguardar sincronização final com a nuvem
        _output(True, "Nota movida para lixeira")
    except Exception as e:
        _output(False, f"Erro ao excluir: {e}")
    finally:
        browser.stop()


async def cmd_archive(args) -> None:
    """Arquiva uma nota abrindo-a primeiro.
    
    Fluxo:
      1. Localizar a nota pelo título e clicar nela.
      2. Encontrar div[role='button'][data-tooltip-text='Arquivar'][aria-label='Arquivar'] e clicar.
    """
    browser, tab = await _open_keep(headless=not getattr(args, 'visible', False))
    if not browser:
        return

    try:
        await _wait_notes(tab)
        target_js = json.dumps(args.title)

        # 1. Localizar o título da nota e clicar
        is_opened = await tab.evaluate(f"""
            (() => {{
                const target = {target_js};
                const cards = document.querySelectorAll('div.IZ65Hb-n0tgWb');
                for (const el of cards) {{
                    const titleEl = el.querySelector('div[role="textbox"][dir="ltr"]') || el.querySelector('div[role="textbox"]');
                    if (titleEl && titleEl.innerText && titleEl.innerText.trim() === target) {{
                        titleEl.click();
                        return true;
                    }}
                }}
                return false;
            }})()
        """)
        if not is_opened:
            _output(False, f"Nota '{args.title}' não encontrada para arquivamento")
            return

        await asyncio.sleep(2)

        # 2. Procurar div com role="button", data-tooltip-text="Arquivar" e aria-label="Arquivar" e clicar via CDP
        arch_c = await _eval_coords(tab, """
            const btns = Array.from(document.querySelectorAll('div[role="button"][data-tooltip-text="Arquivar"][aria-label="Arquivar"]'));
            const btn = btns.pop();
            if (btn) {
                const r = btn.getBoundingClientRect();
                return {x: r.x + r.width / 2, y: r.y + r.height / 2};
            }
            return null;
        """)
        if not arch_c:
            _output(False, "Botão 'Arquivar' não encontrado")
            return

        await _cdp_click(tab, *arch_c)
        await asyncio.sleep(2)

        # 3. Clicar no botão Atualizar para forçar a sincronização
        update_c = await _eval_coords(tab, """
            const btn = document.querySelector('div[role="button"][data-tooltip-text="Atualizar"][aria-label="Atualizar"]');
            if (btn) {
                const r = btn.getBoundingClientRect();
                return {x: r.x + r.width / 2, y: r.y + r.height / 2};
            }
            return null;
        """)
        if update_c:
            await _cdp_click(tab, *update_c)

        await asyncio.sleep(12) # Aguardar sincronização final com a nuvem
        _output(True, "Nota arquivada com sucesso")
    except Exception as e:
        _output(False, f"Erro ao arquivar: {e}")
    finally:
        browser.stop()


# ── CLI ──────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    """Constrói o parser de argumentos CLI."""
    parser = argparse.ArgumentParser(
        description="Google Keep Manager — nodriver (undetected Chrome)"
    )
    parser.add_argument("--visible", action="store_true", help="Mostra o navegador (headful)")
    sub = parser.add_subparsers(dest="command", help="Comando a executar")

    sub.add_parser("login", help="Abrir Chrome para login manual")
    sub.add_parser("logout", help="Limpar sessão salva")
    sub.add_parser("check", help="Verificar se a sessão está ativa")

    sp = sub.add_parser("list", help="Listar notas")
    sp.add_argument("--limit", type=int, default=20, help="Máximo de notas")
    sp.add_argument("--filter", dest="filter_text", help="Filtrar por texto")

    sp = sub.add_parser("create", help="Criar nota")
    sp.add_argument("--title", required=True, help="Título")
    sp.add_argument("--content", required=True, help="Conteúdo")

    sp = sub.add_parser("create-list", help="Criar nota do tipo lista")
    sp.add_argument("--title", default="", help="Título da lista")
    sp.add_argument("--items", required=True, help="Itens separados por vírgula ou quebra de linha (ex: 'Leite, Pão, Café')")

    sp = sub.add_parser("read", help="Ler nota")
    sp.add_argument("--title", required=True, help="Título exato")

    sp = sub.add_parser("update", help="Atualizar nota")
    sp.add_argument("--title", required=True, help="Título atual")
    sp.add_argument("--new-title", help="Novo título")
    sp.add_argument("--content", help="Novo conteúdo (texto com \\n ou, para lista, itens separados por vírgula)")
    sp.add_argument("--items", help="Para nota lista: itens separados por vírgula (ex: 'A, B, C')")

    sp = sub.add_parser("delete", help="Excluir nota")
    sp.add_argument("--title", required=True, help="Título exato")

    sp = sub.add_parser("archive", help="Arquivar nota")
    sp.add_argument("--title", required=True, help="Título exato")

    return parser


def main() -> None:
    """Ponto de entrada CLI."""
    parser = _build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    loop = uc.loop()

    if args.command == "login":
        ok = interactive_login()
        sys.exit(0 if ok else 1)

    if args.command == "logout":
        clear_session()
        return

    if args.command == "check":
        from auth import check_session_async
        ok = loop.run_until_complete(check_session_async())
        _output(ok, f"Sessão {'ativa' if ok else 'inativa'}")
        return

    handlers = {
        "list": cmd_list,
        "create": cmd_create,
        "create-list": cmd_create_list,
        "read": cmd_read,
        "update": cmd_update,
        "delete": cmd_delete,
        "archive": cmd_archive,
    }

    handler = handlers.get(args.command)
    if handler:
        loop.run_until_complete(handler(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
