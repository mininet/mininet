#!/usr/bin/env python

"""
Tests for controllers.py and controllers2.py
"""

import unittest
from mininet.util import pexpect

class testControllers( unittest.TestCase ):

    prompt = 'mininet>'

    def connectedTest( self, name, cmap ):
        "Verify that switches are connected to the controller specified by cmap"
        p = pexpect.spawn( 'python -m %s' % name )
        p.expect( self.prompt )
        # but first a simple ping test
        p.sendline( 'pingall' )
        p.expect ( '(\d+)% dropped' )
        percent = int( p.match.group( 1 ) ) if p.match else -1
        self.assertEqual( percent, 0 )
        p.expect( self.prompt )
        # verify connected controller
        for switch in cmap:
            p.sendline( 'sh ovs-vsctl get-controller %s' % switch )
            p.expect( 'tcp:([\d.:]+)')
            actual = p.match.group(1)
            expected = cmap[ switch ]
            self.assertEqual( actual, expected )
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()

    def testControllers( self ):
        c0 = '127.0.0.1:6633'
        c1 = '127.0.0.1:6634'
        cmap = { 's1': c0, 's2': c1, 's3': c0 }
        self.connectedTest( 'mininet.examples.controllers', cmap )

    def testControllers2( self ):
        c0 = '127.0.0.1:6633'
        c1 = '127.0.0.1:6634'
        cmap = { 's1': c0, 's2': c1 }
        self.connectedTest( 'mininet.examples.controllers2', cmap )

if __name__ == '__main__':
    unittest.main()
