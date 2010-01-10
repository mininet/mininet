all: codecheck test

clean:
	rm -rf build dist build *.egg-info *.pyc

codecheck: mininet/*.py mininet/test/*.py
	pyflakes mininet/*.py mininet/test/*.py bin/*.py
	pylint --rcfile=.pylint mininet/*.py mininet/test/*.py bin/*.py
	pep8 --ignore=E251 mininet/*.py mininet/test/*.py bin/*.py

test: mininet/*.py mininet/test/*.py
	mininet/test/test_nets.py
