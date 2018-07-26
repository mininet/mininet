#!/usr/bin/env python

"""
Tests for bind.py
"""

import unittest
from mininet.util import pexpect

class testBind( unittest.TestCase ):

    prompt = 'mininet>'

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
        "Create a file, a.txt, in the first private directory and verify"
        fileName = 'a.txt'
        directory = self.directories[ 0 ]
        path = directory + '/' + fileName
        self.net.sendline( 'h1 touch %s; ls %s' % ( path, directory ) )
        index = self.net.expect( [ fileName, self.prompt ] )
        self.assertTrue( index == 0 )
        self.net.expect( self.prompt )
        self.net.sendline( 'h1 rm %s' % path )
        self.net.expect( self.prompt )

    def testIsolation( self ):
        "Create a file in two hosts and verify that contents are different"
        fileName = 'b.txt'
        directory = self.directories[ 0 ]
        path = directory + '/' + fileName
        contents = { 'h1' : '1', 'h2' : '2' }
        # Verify file doesn't exist, then write private copy of file
        for host in contents:
            value = contents[ host ]
            self.net.sendline( '%s cat %s' % ( host, path ) )
            self.net.expect( 'No such file' )
            self.net.expect( self.prompt )
            self.net.sendline( '%s echo %s > %s' % ( host, value, path ) )
            self.net.expect( self.prompt )
        # Verify file contents
        for host in contents:
            value = contents[ host ]
            self.net.sendline( '%s cat %s' % ( host, path ) )
            self.net.expect( value )
            self.net.expect( self.prompt )
            self.net.sendline( '%s rm %s' % ( host, path ) )
            self.net.expect( self.prompt )

    # TODO: need more tests

    def tearDown( self ):
        self.net.sendline( 'exit' )
        self.net.wait()

if __name__ == '__main__':
    unittest.main()
