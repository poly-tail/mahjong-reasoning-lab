PYTHON ?= python
UNIT_TEST_PATTERN ?= test_*.py

.PHONY: help validate test docs-graphs docs-graphs-dry-run clean check

help:
	@echo "Available targets:"
	@echo "  make validate            # validate workspace structure"
	@echo "  make test                # run template unit tests"
	@echo "  make docs-graphs-dry-run # list Mermaid render actions"
	@echo "  make docs-graphs         # render Mermaid graphs"
	@echo "  make clean               # remove Python cache artifacts"
	@echo "  make check               # validate + test"

validate:
	$(PYTHON) scripts/validate_workspace.py

test:
	$(PYTHON) -B -m unittest discover -s tests/unit -p "$(UNIT_TEST_PATTERN)"

docs-graphs-dry-run:
	$(PYTHON) scripts/render_docs_graphs.py --dry-run

docs-graphs:
	$(PYTHON) scripts/render_docs_graphs.py

clean:
	$(PYTHON) scripts/clean_python_cache.py

check: validate test
