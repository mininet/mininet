#!/usr/bin/env python

"""
Test for hwintf.py
"""

import unittest
import re

from mininet.util import pexpect

from mininet.log import setLogLevel
from mininet.node import Node
from mininet.link import Link


class testHwintf( unittest.TestCase ):

    prompt = 'mininet>'

    def setUp( self ):
        self.h3 = Node( 't0', ip='10.0.0.3/8' )
        self.n0 = Node( 't1', inNamespace=False )
        Link( self.h3, self.n0 )
        self.h3.configDefault()

    def testLocalPing( self ):
        "Verify connectivity between virtual hosts using pingall"
        p = pexpect.spawn( 'python -m mininet.examples.hwintf %s' % self.n0.intf() )
        p.expect( self.prompt )
        p.sendline( 'pingall' )
        p.expect ( '(\d+)% dropped' )
        percent = int( p.match.group( 1 ) ) if p.match else -1
        self.assertEqual( percent, 0 )
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()

    def testExternalPing( self ):
        "Verify connnectivity between virtual host and virtual-physical 'external' host "
        p = pexpect.spawn( 'python -m mininet.examples.hwintf %s' % self.n0.intf() )
        p.expect( self.prompt )
        # test ping external to internal
        expectStr = '(\d+) packets transmitted, (\d+) received'
        m = re.search( expectStr, self.h3.cmd( 'ping -v -c 1 10.0.0.1' ) )
        tx = m.group( 1 )
        rx = m.group( 2 )
        self.assertEqual( tx, rx )
        # test ping internal to external
        p.sendline( 'h1 ping -c 1 10.0.0.3')
        p.expect( expectStr )
        tx = p.match.group( 1 )
        rx = p.match.group( 2 )
        self.assertEqual( tx, rx )
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()

    def tearDown( self ):
        self.h3.stop( deleteIntfs=True )
        self.n0.stop( deleteIntfs=True )

if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
