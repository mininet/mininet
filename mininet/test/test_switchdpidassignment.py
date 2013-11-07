#!/usr/bin/env python

"""Package: mininet
   Regression tests for switch dpid assignment."""

import unittest
import re

from mininet.net import Mininet
from mininet.node import Switch
from mininet.topo import Topo
from mininet.log import setLogLevel

class testSwitchDpidAssignment ( unittest.TestCase ):
    """Verify Switch dpid assignment."""

    def testDefaultDpid ( self ):
        """Verify that the default dpid is assigned using a valid provided
        canonical switchname if no dpid is passed in switch creation."""
        mn = Mininet( Topo() )
        switch = mn.addSwitch( 's1' )
        self.assertEqual( switch.defaultDpid(), switch.dpid )

    def testActualDpidAssignment( self ):
        """Verify that Switch dpid is the actual dpid assigned if dpid is 
        passed in switch creation."""
        mn = Mininet( Topo() )
        switch = mn.addSwitch( 'A', dpid = '000000000000ABCD' )
        self.assertEqual( switch.dpid, '000000000000ABCD' )

    def testDefaultDpidAssignmentFailure( self ):
        """Verify that Default dpid assignment raises an Exception if the 
        name of the switch does not contin a digit. Also verify the 
        exception message."""
        mn = Mininet( Topo() )
        with self.assertRaises( Exception ) as raises_cm:
            switch = mn.addSwitch( 'A' )
        self.assertEqual(raises_cm.exception.message, 'Unable to derive '
                         'default datapath ID - please either specify a dpid '
                         'or use a canonical switch name such as s23.')

    def testDefaultDpidLen( self ):
        """Verify that Default dpid length is 16 characters consisting of
        16 - len(hex of first string of contiguous digits passed in switch
        name) 0's followed by hex of first string of contiguous digits passed
        in switch name."""
        mn = Mininet( Topo() )
        switch = mn.addSwitch( 's123' )
        dpid = int(re.findall( r'\d+', switch.name ) [0])
        dpid = hex( dpid ) [ 2: ]
        self.assertEqual( switch.dpid, '0' * (16 - len(dpid)) + str(dpid) )


if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
