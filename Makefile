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

# The Cloudera custom service descriptor, which is a jar holding the descriptor
# and the script Cloudera Manager runs. See csd/README.md for what it is for, how
# it is validated against Cloudera's schema validator, and how it is installed.
CSD_VERSION := 1.0
CSD_JAR := CONFIGURATION_ASSURANCE-$(CSD_VERSION).jar

# Without this, the `csd` directory is what make considers the target to be, and
# a directory which exists is always up to date.
.PHONY: csd

csd:
	mkdir -p dist
	rm -f dist/$(CSD_JAR)
# The paths inside the jar are the ones the descriptor names, so the archive is
# built from within the CSD directory rather than from here.
	cd csd/configuration_assurance && python3 -m zipfile -c ../../dist/$(CSD_JAR) descriptor scripts
	@echo "Built dist/$(CSD_JAR)"
