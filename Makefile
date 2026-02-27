# Google Keep Skill — alvos de build/teste

.PHONY: test login check clean

# Requer sessão ativa (make login antes, se necessário)
test:
	rm -f config/chrome-profile/SingletonLock 2>/dev/null || true
	uv run python scripts/test_crud.py

login:
	uv run python scripts/keep.py login

check:
	uv run python scripts/keep.py check

clean:
	rm -f config/chrome-profile/SingletonLock config/chrome-profile/SingletonSocket config/chrome-profile/SingletonCookie 2>/dev/null || true
