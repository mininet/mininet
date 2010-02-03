all: codecheck test

clean:
	rm -rf build dist *.egg-info *.pyc

MININET = mininet/*.py
TEST = mininet/test/*.py
BIN = bin/mn bin/mnclean
PYSRC = $(MININET) $(TEST) $(BIN)

codecheck: $(PYSRC)
	pyflakes $(PYSRC)
	pylint --rcfile=.pylint $(PYSRC)
	pep8 --ignore=E251 $(PYSRC)

test: $(MININET) $(TEST)
	mininet/test/test_nets.py
