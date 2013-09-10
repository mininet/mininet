#!/usr/bin/env python

"""TEST"""

import unittest
import pexpect
from collections import defaultdict
from mininet.log import setLogLevel

class testMultiPing( unittest.TestCase ):
    "Test ping with single switch topology (common code)."

    def testMultiPing( self ):
        p = pexpect.spawn( 'python -m mininet.examples.multiping' )
        opts = []
        opts.append( "Host (h\d+) \(([\d.]+)\) will be pinging ips: ([\d. ]+)" )
        opts.append( "(h\d+): ([\d.]+) -> ([\d.]+) \d packets transmitted, (\d) received" )
        opts.append( pexpect.EOF )
        pings = defaultdict( list )
        while True:
            index = p.expect( opts )
            if index == 0:
                name = p.match.group(1)
                ip = p.match.group(2)
                targets = p.match.group(3).split()
                pings[ name ] += targets
            elif index == 1:
                name = p.match.group(1)
                ip = p.match.group(2)
                target = p.match.group(3)
                received = int( p.match.group(4) )
                if target == '10.0.0.200':
                    self.assertEqual( received, 0 )
                else:
                    self.assertEqual( received, 1 )
                try:
                    pings[ name ].remove( target )
                except:
                    pass
            else:
                break
        self.assertTrue( len(pings) > 0 )
        for t in pings.values():
            self.assertEqual( len( t ), 0 )

if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
