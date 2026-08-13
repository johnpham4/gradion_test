ROOT := $(abspath .)
VENV := $(ROOT)/backend/venv

ifeq ($(OS),Windows_NT)
  BIN := $(VENV)/Scripts
else
  BIN := $(VENV)/bin
endif

.PHONY: setup install-backend install-frontend dev dev-backend dev-frontend test test-backend test-frontend clean

setup: install-backend install-frontend

install-backend:
	python -m venv $(VENV)
	$(BIN)/pip install -e $(ROOT)/backend

install-frontend:
	cd $(ROOT)/frontend && npm install

dev:
	@echo "Backend: http://localhost:8000"
	@echo "Frontend: http://localhost:3000"
	@$(MAKE) dev-backend & $(MAKE) dev-frontend

dev-backend:
	$(BIN)/uvicorn main:app --reload --port 8000 --app-dir $(ROOT)/backend

dev-frontend:
	cd $(ROOT)/frontend && npm run dev

test: test-backend test-frontend

test-backend:
	cd $(ROOT)/backend && $(BIN)/python -m pytest

test-frontend:
	cd $(ROOT)/frontend && npm test -- --watchAll=false

clean:
	rm -rf $(VENV) $(ROOT)/backend/.pytest_cache $(ROOT)/frontend/node_modules $(ROOT)/frontend/.next
