#!/usr/bin/env python

"""Package: mininet
   Regression tests for switch dpid assignment."""

import unittest
import sys

from mininet.net import Mininet
from mininet.node import Host, Controller
from mininet.node import ( UserSwitch, OVSSwitch, IVSSwitch )
from mininet.topo import Topo
from mininet.log import setLogLevel
from mininet.util import quietRun
from mininet.clean import cleanup


class TestSwitchDpidAssignmentOVS( unittest.TestCase ):
    "Verify Switch dpid assignment."

    switchClass = OVSSwitch  # overridden in subclasses

    def tearDown( self ):
        "Clean up if necessary"
        # satisfy pylint
        assert self
        if sys.exc_info() != ( None, None, None ):
            cleanup()

    def testDefaultDpid( self ):
        """Verify that the default dpid is assigned using a valid provided
        canonical switchname if no dpid is passed in switch creation."""
        net = Mininet( Topo(), self.switchClass, Host, Controller )
        switch = net.addSwitch( 's1' )
        self.assertEqual( switch.defaultDpid(), switch.dpid )
        net.stop()

    def dpidFrom( self, num ):
        "Compute default dpid from number"
        fmt = ( '%0' + str( self.switchClass.dpidLen ) + 'x' )
        return fmt % num

    def testActualDpidAssignment( self ):
        """Verify that Switch dpid is the actual dpid assigned if dpid is
        passed in switch creation."""
        dpid = self.dpidFrom( 0xABCD )
        net = Mininet( Topo(), self.switchClass, Host, Controller )
        switch = net.addSwitch( 's1', dpid=dpid )
        self.assertEqual( switch.dpid, dpid )
        net.stop()

    def testDefaultDpidAssignmentFailure( self ):
        """Verify that Default dpid assignment raises an Exception if the
        name of the switch does not contain a digit. Also verify the
        exception message."""
        net = Mininet( Topo(), self.switchClass, Host, Controller )
        with self.assertRaises( Exception ) as raises_cm:
            net.addSwitch( 'A' )
        self.assertTrue( 'Unable to derive '
                         'default datapath ID - please either specify a dpid '
                         'or use a canonical switch name such as s23.'
                         in str( raises_cm.exception ) )
        net.stop()

    def testDefaultDpidLen( self ):
        """Verify that Default dpid length is 16 characters consisting of
        16 - len(hex of first string of contiguous digits passed in switch
        name) 0's followed by hex of first string of contiguous digits passed
        in switch name."""
        net = Mininet( Topo(), self.switchClass, Host, Controller )
        switch = net.addSwitch( 's123' )
        self.assertEqual( switch.dpid, self.dpidFrom( 123 ) )
        net.stop()


class OVSUser( OVSSwitch):
    "OVS User Switch convenience class"
    def __init__( self, *args, **kwargs ):
        kwargs.update( datapath='user' )
        OVSSwitch.__init__( self, *args, **kwargs )

class testSwitchOVSUser( TestSwitchDpidAssignmentOVS ):
    "Test dpid assignment of OVS User Switch."
    switchClass = OVSUser

@unittest.skipUnless( quietRun( 'which ivs-ctl' ),
                      'IVS switch is not installed' )
class testSwitchIVS( TestSwitchDpidAssignmentOVS ):
    "Test dpid assignment of IVS switch."
    switchClass = IVSSwitch

@unittest.skipUnless( quietRun( 'which ofprotocol' ),
                      'Reference user switch is not installed' )
class testSwitchUserspace( TestSwitchDpidAssignmentOVS ):
    "Test dpid assignment of Userspace switch."
    switchClass = UserSwitch


if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
    cleanup()
