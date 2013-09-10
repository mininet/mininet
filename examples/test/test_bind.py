#!/usr/bin/env python

"""TEST"""

import unittest
import pexpect
from time import sleep
from mininet.log import setLogLevel
from mininet.clean import cleanup, sh

class testBind( unittest.TestCase ):
    "Test ping with single switch topology (common code)."

    prompt = 'mininet>'

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
        self.net = pexpect.spawn( 'python -m mininet.examples.bind' )
        self.net.expect( "Private Directories: \[([\w\s,'/]+)\]" )
        self.directories = []
        # parse directories from mn output
        for d in self.net.match.group(1).split(', '):
            self.directories.append( d.strip("'") )
        self.net.expect( self.prompt )
        self.assertTrue( len( self.directories ) > 0 )

    def testCreateFile( self ):
        fileName = 'a.txt'
        directory = self.directories[ 0 ]
        self.net.sendline( 'h1 touch %s/%s; ls %s' % ( directory, fileName, directory ) )
        index = self.net.expect( [ fileName, self.prompt ] )
        self.assertTrue( index == 0 )

    # TODO: need more tests

    def tearDown( self ):
        self.net.sendline( 'exit' )
        self.net.wait()

if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()

