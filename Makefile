all: codecheck test

clean:
	rm -rf build dist *.egg-info *.pyc mnexec bin/mnexec

MININET = mininet/*.py
TEST = mininet/test/*.py
EXAMPLES = examples/*.py
BIN = bin/mn
PYSRC = $(MININET) $(TEST) $(EXAMPLES) $(BIN)

P8IGN = E251,E201,E302,E202

codecheck: $(PYSRC)
	-echo "Running code check"
	pyflakes $(PYSRC)
	pylint --rcfile=.pylint $(PYSRC)
	pep8 --repeat --ignore=$(P8IGN) $(PYSRC)

test: $(MININET) $(TEST)
	-echo "Running tests"
	mininet/test/test_nets.py

install: mnexec
	cp mnexec bin/
	python setup.py install

doc:
	doxygen doxygen.cfg

