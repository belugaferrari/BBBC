.PHONY: up down migrate seed test lint api mobile

up:              ## sobe banco + API
	docker compose up --build

down:
	docker compose down

migrate:
	cd backend && python -m app.cli migrate

seed:            ## cria a familia e clona o catalogo de categorias
	cd backend && python -m app.cli seed-family \
		--name "Familia BBBC" \
		--titular "Felipe" --titular-email felipe@exemplo.com --titular-password trocar \
		--conjuge "Clarissa" --conjuge-email clarissa@exemplo.com --conjuge-password trocar \
		--dependente "Filha 1" --dependente "Filha 2"

test:            ## suite rapida; use BBBC_TEST_DATABASE_URL para incluir a integracao
	cd backend && python -m pytest -q

lint:
	cd backend && python -m ruff check app tests

api:
	cd backend && uvicorn app.main:app --reload

mobile:
	cd mobile && npm start
