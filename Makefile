MININET = mininet/*.py
TEST = mininet/test/*.py
EXAMPLES = examples/*.py
MN = bin/mn
BIN = $(MN)
PYSRC = $(MININET) $(TEST) $(EXAMPLES) $(BIN)
MNEXEC = mnexec
MANPAGE = mn.1
P8IGN = E251,E201,E302,E202
BINDIR = /usr/bin
MANDIR = /usr/share/man/man1

all: codecheck test

clean:
	rm -rf build dist *.egg-info *.pyc $(MNEXEC) $(MANPAGE)

codecheck: $(PYSRC)
	-echo "Running code check"
	pyflakes $(PYSRC)
	pylint --rcfile=.pylint $(PYSRC)
	pep8 --repeat --ignore=$(P8IGN) $(PYSRC)

errcheck: $(PYSRC)
	-echo "Running check for errors only"
	pyflakes $(PYSRC)
	pylint -E --rcfile=.pylint $(PYSRC)

test: $(MININET) $(TEST)
	-echo "Running tests"
	mininet/test/test_nets.py

install: $(MNEXEC) $(MANPAGE)
	install $(MNEXEC) $(BINDIR)
	install $(MANPAGE) $(MANDIR)
	python setup.py install

develop: $(MNEXEC) $(MANPAGE)
	# Perhaps we should link these as well
	install $(MNEXEC) $(BINDIR)
	install $(MANPAGE) $(MANDIR)
	python setup.py develop

man: $(MANPAGE)

$(MANPAGE): $(MN)
	PYTHONPATH=. help2man -N -n "create a Mininet network." \
    --no-discard-stderr $(MN) \
    -o $@

doc: man
	doxygen doxygen.cfg

