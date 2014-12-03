#!/usr/bin/env python

"""Package: mininet
   Regression tests for switch dpid assignment."""

import unittest
import sys
from functools import partial
import re

from mininet.net import Mininet
from mininet.node import Host, Controller
from mininet.node import UserSwitch, OVSSwitch, OVSLegacyKernelSwitch, IVSSwitch
from mininet.topo import Topo
from mininet.log import setLogLevel
from mininet.util import quietRun
from mininet.clean import cleanup

class testSwitchDpidAssignmentCommon ( object ):
    """Verify Switch dpid assignment."""

    switchClass = None # overridden in subclasses

    def tearDown( self ):
        "Clean up if necessary"
        if sys.exc_info != ( None, None, None ):
            cleanup()

    def testDefaultDpid ( self ):
        """Verify that the default dpid is assigned using a valid provided
        canonical switchname if no dpid is passed in switch creation."""
        switch = Mininet( Topo(),
                          self.switchClass, Host, Controller ).addSwitch( 's1' )
        self.assertEqual( switch.defaultDpid(), switch.dpid )

    def testActualDpidAssignment( self ):
        """Verify that Switch dpid is the actual dpid assigned if dpid is
        passed in switch creation."""
        switch = Mininet( Topo(), self.switchClass,
                          Host, Controller ).addSwitch( 'A', dpid = '000000000000ABCD' )
        self.assertEqual( switch.dpid, '000000000000ABCD' )

    def testDefaultDpidAssignmentFailure( self ):
        """Verify that Default dpid assignment raises an Exception if the
        name of the switch does not contin a digit. Also verify the
        exception message."""
        with self.assertRaises( Exception ) as raises_cm:
            Mininet( Topo(), self.switchClass,
                     Host, Controller ).addSwitch( 'A' )
        self.assertEqual(raises_cm.exception.message, 'Unable to derive '
                         'default datapath ID - please either specify a dpid '
                         'or use a canonical switch name such as s23.')

    def testDefaultDpidLen( self ):
        """Verify that Default dpid length is 16 characters consisting of
        16 - len(hex of first string of contiguous digits passed in switch
        name) 0's followed by hex of first string of contiguous digits passed
        in switch name."""
        switch = Mininet( Topo(), self.switchClass,
                          Host, Controller ).addSwitch( 's123' )
        dpid = hex( int(re.findall( r'\d+', switch.name ) [0]) ) [ 2: ]
        try:
            if issubclass(UserSwitch, self.switchClass):
                # Dpid lenght of UserSwitch = 12
                self.assertEqual( switch.dpid,
                                  '0' * (12 - len(dpid)) + str(dpid) )
            else:
                self.assertEqual( switch.dpid,
                                  '0' * (16 - len(dpid)) + str(dpid) )
        except TypeError:
            # Switch is OVS User Switch
            self.assertEqual( switch.dpid,
                              '0' * (16 - len(dpid)) + str(dpid) )


class testSwitchOVSKernel( testSwitchDpidAssignmentCommon, unittest.TestCase ):
    """Test dpid assignnment of OVS Kernel Switch."""
    switchClass = OVSSwitch

class testSwitchOVSUser( testSwitchDpidAssignmentCommon, unittest.TestCase ):
    """Test dpid assignnment of OVS User Switch."""
    switchClass = partial(OVSSwitch, datapath = 'user')

@unittest.skipUnless( quietRun( 'which ovs-openflowd' ),
                      'OVS Legacy Kernel switch is not installed' )
class testSwitchOVSLegacyKernel( testSwitchDpidAssignmentCommon,
                                 unittest.TestCase ):
    """Test dpid assignnment of OVS Legacy Kernel Switch."""
    switchClass = OVSLegacyKernelSwitch

@unittest.skipUnless( quietRun( 'which ivs-ctl' ), 'IVS switch is not installed' )
class testSwitchIVS( testSwitchDpidAssignmentCommon,
                     unittest.TestCase ):
    """Test dpid assignment of IVS switch."""
    switchClass = IVSSwitch

@unittest.skipUnless( quietRun( 'which ofprotocol' ), 'Reference user switch is not installed' )
class testSwitchUserspace( testSwitchDpidAssignmentCommon,
                           unittest.TestCase ):
    """Test dpid assignment of Userspace switch."""
    switchClass = UserSwitch


if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
