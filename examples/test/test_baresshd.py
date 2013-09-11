#!/usr/bin/env python

"""
Tests for baresshd.py
"""

import unittest
import pexpect
from time import sleep
from mininet.clean import cleanup, sh

class testBareSSHD( unittest.TestCase ):

    opts = [ '\(yes/no\)\?', 'Welcome to h1', 'refused', pexpect.EOF, pexpect.TIMEOUT ]

    def connected( self ):
        "Log into ssh server, check banner, then exit"
        p = pexpect.spawn( 'ssh 10.0.0.1 -i /tmp/ssh/test_rsa exit' )
        while True:
            index = p.expect( self.opts )
            if index == 0:
                p.sendline( 'yes' )
            elif index == 1:
                return True
            else:
                return False

    def setUp( self ):
        # verify that sshd is not running
        self.assertFalse( self.connected() )
        # create public key pair for testing
        sh( 'rm -rf /tmp/ssh' )
        sh( 'mkdir /tmp/ssh' )
        sh( "ssh-keygen -t rsa -P '' -f /tmp/ssh/test_rsa" )
        sh( 'cat /tmp/ssh/test_rsa.pub >> /tmp/ssh/authorized_keys' )
        # run example with custom sshd args
        cmd = ( 'python -m mininet.examples.baresshd '
                '-o AuthorizedKeysFile=/tmp/ssh/authorized_keys '
                '-o StrictModes=no' )
        sh( cmd )

    def testSSH( self ):
        "Simple test to verify that we can ssh into h1"
        result = False
        # try to connect up to 3 times; sshd can take a while to start
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
    unittest.main()
