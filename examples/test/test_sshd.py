#!/usr/bin/env python

"""TEST"""

import unittest
import pexpect
from time import sleep
from mininet.log import setLogLevel
from mininet.clean import cleanup, sh

class testBareSSHD( unittest.TestCase ):
    "Test ping with single switch topology (common code)."

    opts = [ '\(yes/no\)\?', 'refused', 'Welcome', pexpect.EOF, pexpect.TIMEOUT ]

    def connected( self, ip ):
        "check connected"
        p = pexpect.spawn( 'ssh -i /tmp/ssh/test_rsa %s' % ip )
        while True:
            index = p.expect( self.opts )
            if index == 0:
                print p.match.group(0)
                p.sendline( 'yes' )
            elif index == 1:
                return False
            elif index == 2:
                p.sendline( 'exit' )
                p.wait()    
                return True
            else:
                return False

    def setUp( self ):
        # create public key pair for testing
        sh( 'mkdir /tmp/ssh' )
        sh( "ssh-keygen -t rsa -P '' -f /tmp/ssh/test_rsa" )
        sh( 'cat /tmp/ssh/test_rsa.pub >> /tmp/ssh/authorized_keys' )
        cmd = ( 'python -m mininet.examples.sshd -D '
                '-o AuthorizedKeysFile=/tmp/ssh/authorized_keys '
                '-o StrictModes=no' )
        self.net = pexpect.spawn( cmd )
        self.net.expect( 'mininet>' )

    def testSSH( self ):
        for h in range( 1, 5 ):
            self.assertTrue( self.connected( '10.0.0.%d' % h ) )

    def tearDown( self ):
        self.net.sendline( 'exit' )
        self.net.wait()
        # remove public key pair
        sh( 'rm -rf /tmp/ssh' )

if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()

