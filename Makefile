.PHONY: help setup dev test clean install-backend install-fronted

help:
	@echo "Book Illustration Studio - Available commands:"
	@echo "  make setup       - Set up the development environment"
	@echo "  make dev         - Start both frontend and backend"
	@echo "  make test        - Run all tests"
	@echo "  make clean       - Clean build artifacts"
	@echo "  make install-backend - Install backend dependencies"
	@echo "  make install-frontend - Install frontend dependencies"

setup: install-backend install-frontend

install-backend:
	@echo "Setting up backend..."
	cd backend && python -m venv venv
	cd backend && venv/bin/pip install -e . || venv/Scripts/pip install -e .

install-frontend:
	@echo "Setting up frontend..."
	cd frontend && npm install

dev:
	@echo "Starting development servers..."
	@echo "Backend: http://localhost:8000"
	@echo "Frontend: http://localhost:3000"
	@make dev-backend & make dev-frontend

dev-backend:
	cd backend && venv/bin/uvicorn main:app --reload --port 8000 || venv/Scripts/uvicorn main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

test:
	@echo "Running tests..."
	@make test-backend && make test-frontend

test-backend:
	@echo "Running backend tests..."
	cd backend && venv/bin/pytest || venv/Scripts/pytest

test-frontend:
	@echo "Running frontend tests..."
	cd frontend && npm test -- --watchAll=false

clean:
	@echo "Cleaning build artifacts..."
	cd backend && rm -rf venv .pytest_cache __pycache__
	cd frontend && rm -rf node_modules .next