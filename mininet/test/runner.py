#!/usr/bin/env python

"""
Run all mininet core tests
 -v : verbose output
 -quick : skip tests that take more than ~30 seconds
"""

from unittest import defaultTestLoader, TextTestRunner
import os
import sys
from mininet.util import ensureRoot
from mininet.clean import cleanup
from mininet.log import setLogLevel

def runTests( testDir, verbosity=1 ):
    "discover and run all tests in testDir"
    # ensure root and cleanup before starting tests
    ensureRoot()
    cleanup()
    # discover all tests in testDir
    testSuite = defaultTestLoader.discover( testDir )
    # run tests
    success = ( TextTestRunner( verbosity=verbosity )
                .run( testSuite ).wasSuccessful() )
    sys.exit( 0 if success else 1 )


if __name__ == '__main__':
    setLogLevel( 'warning' )
    # get the directory containing example tests
    thisdir = os.path.dirname( os.path.realpath( __file__ ) )
    vlevel = 2 if '-v' in sys.argv else 1
    runTests( testDir=thisdir, verbosity=vlevel )
