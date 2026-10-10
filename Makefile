PYTHON ?= python3

.PHONY: test build check

test:
	$(PYTHON) -m unittest discover -s tests -v

build: test
	$(PYTHON) -m build

check:
	$(PYTHON) -m twine check --strict dist/*
