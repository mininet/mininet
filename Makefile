all: codecheck test

clean:
	rm -rf build dist *.egg-info *.pyc

MININET = mininet/*.py
TEST = mininet/test/*.py
BIN = bin/mn bin/mnclean
PYSRC = $(MININET) $(TEST) $(BIN)

P8IGN = E251,E201,E302

codecheck: $(PYSRC)
	pyflakes $(PYSRC)
	pylint --rcfile=.pylint $(PYSRC)
	pep8 --ignore=$(P8IGN) $(PYSRC)

test: $(MININET) $(TEST)
	mininet/test/test_nets.py

install:
	python setup.py install



