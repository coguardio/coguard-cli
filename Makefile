test:
	cd src && nosetests --exe --with-coverage --cover-inclusive --cover-package=coguard_cli -v
	coverage html -i --directory=coverage_output

lint:
	find src -type f -name "*.py" -not -path "*/tests/*" | xargs pylint --rcfile="./.pylint.rc"

build:
	python -m build
