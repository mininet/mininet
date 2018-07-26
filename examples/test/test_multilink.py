#!/usr/bin/env python

'''
Test for multiple links between nodes
validates mininet interfaces against systems interfaces
'''

import unittest
from mininet.util import pexpect

class testMultiLink( unittest.TestCase ):

    prompt = 'mininet>'

    def testMultiLink(self):
        p = pexpect.spawn( 'python -m mininet.examples.multilink' )
        p.expect( self.prompt )
        p.sendline( 'intfs' )
        p.expect( 's(\d): lo' )
        intfsOutput = p.before
        # parse interfaces from mininet intfs, and store them in a list
        hostToIntfs = intfsOutput.split( '\r\n' )[ 1:3 ]
        intfList = []
        for hostToIntf in hostToIntfs:
            intfList += [ intf for intf in
                          hostToIntf.split()[1].split(',') ]

        # get interfaces from system by running ifconfig on every host
        sysIntfList = []
        opts = [ 'h(\d)-eth(\d)', self.prompt ]
        p.expect( self.prompt )

        p.sendline( 'h1 ifconfig' )
        while True:
            p.expect( opts )
            if p.after == self.prompt:
                break
            sysIntfList.append( p.after )

        p.sendline( 'h2 ifconfig' )
        while True:
            p.expect( opts )
            if p.after == self.prompt:
                break
            sysIntfList.append( p.after )

        failMsg = ( 'The systems interfaces and mininet interfaces\n'
                    'are not the same' )

        self.assertEqual( sysIntfList, intfList, msg=failMsg )
        p.sendline( 'exit' )
        p.wait()

if __name__ == '__main__':
        unittest.main()
