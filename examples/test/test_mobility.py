#!/usr/bin/env python

"""
Test for mobility.py
"""

import unittest
from subprocess import check_output

class testMobility( unittest.TestCase ):

    def testMobility( self ):
        "Run the example and verify its 4 ping results"
        cmd = 'python -m mininet.examples.mobility 2>&1'
        grep = ' | grep -c " 0% dropped" '
        result = check_output( cmd + grep, shell=True )
        assert int( result ) == 4

if __name__ == '__main__':
    unittest.main()
