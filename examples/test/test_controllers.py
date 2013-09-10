#!/usr/bin/env python

"""TEST"""

import unittest
import pexpect
#from time import sleep
from mininet.log import setLogLevel
#from mininet.net import Mininet
#from mininet.node import CPULimitedHost
#from mininet.link import TCLink

#from mininet.examples.simpleperf import SingleSwitchTopo

class testControllers( unittest.TestCase ):
    "Test ping with single switch topology (common code)."

    prompt = 'mininet>'

    def connectedTest( self, name, cmap ):
        p = pexpect.spawn( 'python -m %s' % name )
        p.expect( self.prompt )
        p.sendline( 'pingall' )
        p.expect ( '(\d+)% dropped' )
        percent = int( p.match.group( 1 ) ) if p.match else -1
        self.assertEqual( percent, 0 ) # or this
        p.expect( self.prompt )
        for switch in cmap:
            p.sendline( 'sh ovs-vsctl get-controller %s' % switch )
            p.expect( 'tcp:([\d.:]+)')
            actual = p.match.group(1)
            expected = cmap[ switch ]
            self.assertEqual( actual, expected)
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()
        #TODO remove this
        self.assertEqual( percent, 0 )

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
    setLogLevel( 'warning' )
    unittest.main()
