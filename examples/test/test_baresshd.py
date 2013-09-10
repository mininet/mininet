#!/usr/bin/env python

"""TEST"""

import unittest
import pexpect
from time import sleep
from mininet.log import setLogLevel
from mininet.clean import cleanup, sh

class testBareSSHD( unittest.TestCase ):
    "Test ping with single switch topology (common code)."

    opts = [ '\(yes/no\)\?', 'Welcome to h1', 'refused', pexpect.EOF, pexpect.TIMEOUT ]

    def connected( self ):
        "check connected"
        p = pexpect.spawn( 'ssh 10.0.0.1 -i /tmp/ssh/test_rsa ' )
        while True:
            index = p.expect( self.opts )
            if index == 0:
                p.sendline( 'yes' )
            elif index == 1:
                return True
            else:
                return False

    def setUp( self ):
        self.assertFalse( self.connected() )
        # create public key pair for testing
        sh( 'mkdir /tmp/ssh' )
        sh( "ssh-keygen -t rsa -P '' -f /tmp/ssh/test_rsa" )
        sh( 'cat /tmp/ssh/test_rsa.pub >> /tmp/ssh/authorized_keys' )
        cmd = ( 'python -m mininet.examples.baresshd '
                '-o AuthorizedKeysFile=/tmp/ssh/authorized_keys '
                '-o StrictModes=no' )
        sh( cmd )

    def testSSH( self ):
        result = False
        # try to connect up to 3 times
        for _ in range( 3 ):
            result = self.connected()
            if result:
                break
            else:
                sleep( 1 )
        self.assertTrue( result )

    def tearDown( self ):
        # kill the ssh process
        sh( "ps aux | grep 'ssh.*Banner' | awk '{ print $2 }' | xargs kill" )
        cleanup()
        # remove public key pair
        sh( 'rm -rf /tmp/ssh' )


if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
