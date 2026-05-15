.PHONY: install test bench lint fmt dev clean

install:
	pip install -e ".[dev]"

test:
	pytest --cov=stoa --cov-report=term-missing

bench:
	python -c "from benchmarks.runner import BenchmarkRunner; BenchmarkRunner().run()"
	@echo ""
	@echo "Charts written to benchmarks/results/"
	@echo "Summary at benchmarks/results/summary.json"

lint:
	ruff check stoa/ benchmarks/ tests/
	mypy stoa/

fmt:
	ruff format stoa/ benchmarks/ tests/

dev:
	uvicorn stoa.api.main:app --reload --host 127.0.0.1 --port 8000

dashboard:
	streamlit run dashboard/app.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -f stoa.db benchmarks/results/*.png benchmarks/results/summary.json
