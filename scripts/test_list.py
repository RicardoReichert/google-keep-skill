#!/usr/bin/env python3
"""Teste minimalista: validar login e listar notas."""
import subprocess
import json
import os
import sys

# Raiz da skill
SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEEP_PY = os.path.join(SKILL_ROOT, "scripts", "keep.py")

def run_keep(*args):
    cmd = ["uv", "run", "python", KEEP_PY] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=SKILL_ROOT)

def parse_output(stdout):
    """Extrai o primeiro bloco JSON da saída."""
    stdout = stdout.strip()
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(stdout[start:end+1])
        except:
            return None
    return None

def test_basic():
    print("1. Validando login (check)...", flush=True)
    res = run_keep("check")
    data = parse_output(res.stdout)
    if data and data.get("success"):
        print("   [OK] Sessão ativa.")
    else:
        print("   [FALHOU] Sessão inativa ou erro.")
        return False

    print("\n2. Validando listagem (list)...", flush=True)
    res = run_keep("list", "--limit", "3")
    data = parse_output(res.stdout)
    if data and data.get("success"):
        notes = data.get("data", {}).get("notes", [])
        print(f"   [OK] {len(notes)} notas encontradas.")
        for n in notes:
            print(f"        - ID: {n['id']} | Título: {n['title']}")
        return True
    else:
        print("   [FALHOU] Erro ao listar notas.")
        return False

if __name__ == "__main__":
    if test_basic():
        print("\nTeste concluído com sucesso.")
        sys.exit(0)
    else:
        print("\nO teste falhou.")
        sys.exit(1)
