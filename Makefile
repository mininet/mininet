clean:
	rm -rf build dist build *.egg-info *.pyc

test: mininet/*.py mininet/test/*.py
	mininet/test/test_nets.py