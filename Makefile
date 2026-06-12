.PHONY: install bot api frontend

install:
	poetry install
	cd frontend && npm install

bot:
	poetry run python main.py

api:
	poetry run uvicorn bot.api.api:app --host 0.0.0.0 --port 5001 --reload

frontend:
	cd frontend && npm run dev
