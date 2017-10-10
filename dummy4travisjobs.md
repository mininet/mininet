This file goal is to have a modification to commit in order to trigger Travis-CI

20171006: First try after merging master in install_of13 branch
	Job failed because of test_multiping from mininet
	not because of of13()
	which is not called in the install.sh from .travis.yml

20171009: Second try to build 
	Remove 2 spaces in line giving the new netbee source to trigger Travis-CI

20171009: Third try
	Add option '-3' in call to install.sh to test the build with of13()
	Build broke because of mininet tests
	Must check the logs to see what did and did not pass

20171010: Forth try.
	Just modify this file to trigger Travis-CI
