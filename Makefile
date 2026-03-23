.PHONY: ci format

ci:
	mypy .
	black --check .
	isort . --profile black --check-only
	PYTHONPATH=src pytest

format:
	black .
	isort . --profile black
