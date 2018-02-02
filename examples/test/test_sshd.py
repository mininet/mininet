#!/usr/bin/env python

"""
Test for sshd.py
"""

import unittest
import pexpect
from mininet.clean import sh

class testSSHD( unittest.TestCase ):

    opts = [ '\(yes/no\)\?', 'refused', 'Welcome|\$|#', pexpect.EOF, pexpect.TIMEOUT ]

    def connected( self, ip ):
        "Log into ssh server, check banner, then exit"
        # Note: this test will fail if "Welcome" is not in the sshd banner
        # and '#'' or '$'' are not in the prompt
        p = pexpect.spawn( 'ssh -i /tmp/ssh/test_rsa %s' % ip, timeout=10 )
        while True:
            index = p.expect( self.opts )
            if index == 0:
                print( p.match.group(0) )
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
        sh( 'rm -rf /tmp/ssh' )
        sh( 'mkdir /tmp/ssh' )
        sh( "ssh-keygen -t rsa -P '' -f /tmp/ssh/test_rsa" )
        sh( 'cat /tmp/ssh/test_rsa.pub >> /tmp/ssh/authorized_keys' )
        cmd = ( 'python -m mininet.examples.sshd -D '
                '-o AuthorizedKeysFile=/tmp/ssh/authorized_keys '
                '-o StrictModes=no -o UseDNS=no -u0' )
        # run example with custom sshd args
        self.net = pexpect.spawn( cmd )
        self.net.expect( 'mininet>' )

    def testSSH( self ):
        "Verify that we can ssh into all hosts (h1 to h4)"
        for h in range( 1, 5 ):
            self.assertTrue( self.connected( '10.0.0.%d' % h ) )

    def tearDown( self ):
        self.net.sendline( 'exit' )
        self.net.wait()
        # remove public key pair
        sh( 'rm -rf /tmp/ssh' )

if __name__ == '__main__':
    unittest.main()

