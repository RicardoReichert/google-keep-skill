---
name: google-keep
description: Integração com Google Keep via nodriver (Chrome não detectável). Cria, lê, atualiza e exclui notas.
version: 0.3.0
author: Ricardo Reichert
read_when:
  - Criar notas no Google Keep
  - Listar notas do Google Keep
  - Atualizar notas no Google Keep
  - Excluir notas do Google Keep
  - Arquivar notas no Google Keep
  - Gerenciar notas
---

# Google Keep Skill

Skill para interagir com o Google Keep via `nodriver` (Chrome real, sem detecção de bot).

## Instalação

**Pré-requisitos**

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (gerenciador de pacotes e ambiente)
- Google Chrome instalado no sistema (ex.: `sudo apt install google-chrome-stable` no Linux)

**Onde a skill fica**

A skill deve estar em `~/.nanobot/workspace/skills/google-keep-skill/` (ou no `workspace/skills` do Nanobot). O Nanobot descobre skills que tenham `SKILL.md` e `_meta.json` nessa árvore.

**Instalar dependências**

Na raiz da skill, o `uv` usa o `pyproject.toml`; não é necessário rodar nada além de `uv run` nos comandos abaixo. Na primeira execução o `uv` cria o ambiente e instala as dependências.

```bash
cd ~/.nanobot/workspace/skills/google-keep-skill
uv run python scripts/keep.py check   # exemplo; na primeira vez o uv instala deps
```

(Opcional: `make check` faz o mesmo se você usar o Makefile.)

## Configuração no Nanobot

1. **Nada no `config.json` do Nanobot** — não é preciso registrar a skill em arquivo de configuração; ela é usada via comandos `exec` quando o usuário pede ações no Google Keep.

2. **Login uma vez** — antes de o bot poder criar/listar/editar notas, é necessário fazer login manual no Chrome (sessão fica salva). O usuário ou o agente deve executar:
   ```bash
   cd ~/.nanobot/workspace/skills/google-keep-skill && uv run python scripts/keep.py login
   ```
   O Chrome abre; fazer login na conta Google, fechar o navegador. A sessão é salva em `config/` e reutilizada nas próximas chamadas.

3. **Como o bot usa a skill** — o agente chama a ferramenta `exec` com o comando completo, por exemplo:
   ```bash
   cd ~/.nanobot/workspace/skills/google-keep-skill && uv run python scripts/keep.py list --limit 5
   ```
   Ou para criar nota: `... keep.py create --title "Título" --content "Texto"`. A saída é JSON; em caso de sessão expirada, o script retorna `"success": false` e mensagem para o usuário rodar `keep.py login` de novo.

4. **Resumo** — Colocar a skill em `workspace/skills/google-keep-skill`, rodar `keep.py login` uma vez, daí o bot usa sempre `exec` com os comandos descritos na seção **Comandos** abaixo.

## Configuração Inicial (login — uma vez)

Este passo é o **login manual** citado em **Configuração no Nanobot** (item 2). Execute uma vez para salvar a sessão.

```bash
cd ~/.nanobot/workspace/skills/google-keep-skill
uv run python scripts/keep.py login
```

O Chrome abrirá com a página do Google Keep. Faça login normalmente. Após detectar o login, o navegador fecha e a sessão é salva.

### Verificar sessão

```bash
cd ~/.nanobot/workspace/skills/google-keep-skill && uv run python scripts/keep.py check
```

### Limpar sessão

```bash
cd ~/.nanobot/workspace/skills/google-keep-skill && uv run python scripts/keep.py logout
```

**Só use `logout` se quiser desvincular a conta.** Após isso será necessário fazer login de novo.

## Preservar autenticação (para o bot usar sempre a mesma sessão)

A sessão fica guardada em dois lugares e é reutilizada em toda execução:

| Onde | Caminho | Uso |
|------|---------|-----|
| **Perfil Chrome** | `config/chrome-profile/` | Cookies, cache e estado do navegador (persistente). |
| **Cópia de cookies** | `config/cookies.json` | Backup dos cookies; restaurado em cada sessão headless. |

**Para não perder a autenticação:**

1. **Não apague** a pasta `config/` nem execute `keep.py logout` a menos que queira deslogar de propósito.
2. **Backup (opcional):** para guardar a sessão noutro lugar (ex.: antes de reinstalar o sistema), copie a pasta `config/` inteira para um backup. Para restaurar, devolva `config/` ao mesmo caminho dentro da skill.
3. **Um Chrome por vez:** não abra outro Chrome usando o mesmo `config/chrome-profile` (ex.: dois `keep.py` em paralelo). O Makefile e o script de teste removem `SingletonLock` antes de rodar para evitar travar o perfil.
4. **Se o Google pedir login de novo** (segurança, troca de senha, etc.), rode de novo `uv run python scripts/keep.py login` e faça o login manual; a nova sessão será salva no mesmo `config/`.
5. **Arquivos sensíveis:** `config/.gitignore` já contém `.env`, `cookies.json` e `chrome-profile/` — não vão para o repositório.

O bot (Nanobot) usa sempre a mesma sessão enquanto esses arquivos existirem e não forem removidos.

## Comandos

Todos via `exec`:

```bash
cd ~/.nanobot/workspace/skills/google-keep-skill && uv run python scripts/keep.py <comando>
```

**Fluxo criar nota normal:** procurar div com texto "Criar uma nota…" e clicar → adicionar texto da nota (conteúdo) → procurar div "Título", clicar e escrever o título → clicar botão Fechar (role=button).

**Fluxo criar nota lista:** procurar div com `data-tooltip-text="Nova lista"` e `aria-label="Nova lista"`, clicar → escrever primeiro item → para cada próximo item: pressionar ENTER (ou clicar div "Item da lista") e escrever → preencher título como na nota normal → botão Fechar.

| Comando | Descrição |
|---------|-----------|
| `list [--limit N] [--filter "texto"]` | Listar notas |
| `create --title "T" --content "C"` | Criar nota (clica em "Criar uma nota…", preenche conteúdo, depois título, Fechar) |
| `create-list --title "T" --items "i1, i2, i3"` | Criar nota tipo lista (Nova lista → itens → título → Fechar) |
| `read --title "T"` | Ler nota pelo título |
| `update --title "T" [--new-title "NT"] [--content "C"]` | Atualizar nota |
| `delete --title "T"` | Mover para lixeira |
| `archive --title "T"` | Arquivar nota |

## Exemplos para o Nanobot

```bash
# Criar nota
cd ~/.nanobot/workspace/skills/google-keep-skill && uv run python scripts/keep.py create --title "Compras" --content "- Leite\n- Pão"

# Criar lista (nota com itens)
cd ~/.nanobot/workspace/skills/google-keep-skill && uv run python scripts/keep.py create-list --title "Compras" --items "Leite, Pão, Café"

# Listar com filtro
cd ~/.nanobot/workspace/skills/google-keep-skill && uv run python scripts/keep.py list --filter "reunião"

# Atualizar
cd ~/.nanobot/workspace/skills/google-keep-skill && uv run python scripts/keep.py update --title "Compras" --content "- Leite\n- Pão\n- Café"
```

## Saída JSON

```json
{
  "success": true,
  "message": "Nota criada com sucesso",
  "data": { "title": "Compras" }
}
```

## Pipeline / Testes

O teste CRUD completo (criar → listar → ler → editar → listar → deletar → verificar) está incorporado ao projeto.

**Requer sessão ativa** (executar `make login` ou `uv run python scripts/keep.py login` antes).

```bash
cd ~/.nanobot/workspace/skills/google-keep-skill
make test
```

Ou sem Makefile:

```bash
cd ~/.nanobot/workspace/skills/google-keep-skill
rm -f config/chrome-profile/SingletonLock 2>/dev/null
uv run python scripts/test_crud.py
```

Outros alvos úteis: `make login`, `make check`, `make clean`.

## Limitações

- Seletores CSS podem quebrar se o Google alterar a UI
- Requer login manual uma vez (sessão persistente); ver **Preservar autenticação** acima
- Se a sessão expirar, orientar o usuário a executar `keep.py login`
