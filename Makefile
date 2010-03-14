all: codecheck test

clean:
	rm -rf build dist *.egg-info *.pyc

MININET = mininet/*.py
TEST = mininet/test/*.py
EXAMPLES = examples/*.py
BIN = bin/mn
PYSRC = $(MININET) $(TEST) $(EXAMPLES) $(BIN)

P8IGN = E251,E201,E302

codecheck: $(PYSRC)
	pyflakes $(PYSRC)
	pylint --rcfile=.pylint $(PYSRC)
	pep8 --repeat --ignore=$(P8IGN) $(PYSRC)

test: $(MININET) $(TEST)
	mininet/test/test_nets.py

install: mnexec
	cp mnexec bin/
	python setup.py install



