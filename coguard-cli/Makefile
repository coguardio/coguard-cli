test:
	nosetests --exe --with-coverage --cover-inclusive --cover-package=src -v
	coverage html -i --directory=coverage_output

lint:
	find src -type f -name "*.py" | xargs pylint --rcfile="./.pylint.rc"

build:
	python -m build
