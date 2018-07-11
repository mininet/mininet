#!/usr/bin/env python

'''
A simple sanity check test for cluster edition
'''

import unittest
import pexpect
import sys

class clusterSanityCheck( unittest.TestCase ):

    prompt = u'mininet>'

    def testClusterPingAll( self ):
        p = pexpect.spawn( sys.executable + ' -m mininet.examples.clusterSanity', encoding='utf-8' )
        p.expect( self.prompt )
        p.sendline( 'pingall' )
        p.expect ( u'(\d+)% dropped' )
        percent = int( p.match.group( 1 ) ) if p.match else -1
        self.assertEqual( percent, 0 )
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()


if __name__  == '__main__':
    unittest.main()
