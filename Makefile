.PHONY: install-dependencies style-reformat check-syntax

install-dependencies:
	python -m pip install --upgrade pip
	python -m pip install -r requirements.txt

style-reformat:
	python -m pip install black isort autoflake
	autoflake --remove-all-unused-imports --recursive --in-place .
	isort .
	black .

check-syntax: install-dependencies
	python -m compileall -q -f .
	python -c "import main"