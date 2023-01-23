unit-test:
# In order to have the tests run as expected, I need to set read/write rights here properly
	chmod 0400 ./src/coguard_cli/tests/auth/resources/sample_config
	chmod 0400 ./src/coguard_cli/tests/auth/resources/sample_config_not_json
# And now to the actual tests
	cd src && nosetests --exe --with-coverage --cover-inclusive --cover-package=coguard_cli -v
	cd src && coverage html -i --directory=coverage_output

integration-test:
# Consistency test with older versions
	./tests/test_reports_remain_the_same.sh

lint:
	find src -type f -name "*.py" -not -path "*/tests/*" | xargs pylint --rcfile="./.pylint.rc"

build:
	python -m build
