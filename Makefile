SHELL := /bin/bash

unit-test:
# In order to have the tests run as expected, I need to set read/write rights here properly
	chmod 0400 ./src/coguard_cli/tests/auth/resources/sample_config
	chmod 0400 ./src/coguard_cli/tests/auth/resources/sample_config_not_json
# And now to the actual tests
	cd src && coverage run --source=coguard_cli -m pytest --ignore coverity_integration --capture=sys -x
	cd src && coverage html -i --directory=coverage_output --fail-under=80
# Testing that the PyPi and GitHub READMEs do not differ except for the logo at the top
	diff <(tail -n +10 README.md) <(tail -n +3 README_PYPI.md)
# Testing that we have no docker run without a fixed version
	ansible-playbook tests/docker_images_up_to_date.yml -e "search_path=../src/coguard_cli"

integration-test:
# Consistency test with older versions
	./tests/test_reports_remain_the_same.sh ${IS_TEST}

lint:
	find src -type f -name "*.py" -not -path "*/tests/*" | xargs pylint --rcfile="./.pylint.rc"
	find tests -iname "*.yml" -exec ansible-lint {} \;

build:
	python -m build
