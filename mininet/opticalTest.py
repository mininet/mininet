#!/usr/bin/python

from opticalUtils2 import MininetOE, LINCSwitch, LINCLink
from mininet.topo import Topo
from mininet.log import setLogLevel
from mininet.node import RemoteController
from mininet.cli import CLI

class SmallOpticalTopo( Topo ):

    def build( self ):
        o1ann = { "latitude": 37.6, "longitude": -122.3, "optical.regens": 0 }
        O1 = self.addSwitch( 'SFO-W10', dpid='0000ffffffffff01', annotations=o1ann, cls=LINCSwitch )
        o2ann = { "latitude": 37.3, "longitude": -121.9, "optical.regens": 0 }
        O2 = self.addSwitch( 'SJC-W10', dpid='0000ffffffffff02', annotations=o2ann, cls=LINCSwitch )
        o3ann = { "latitude": 33.9, "longitude": -118.4, "optical.regens": 0 }
        O3 = self.addSwitch( 'LAX-W10', dpid='0000ffffffffff03', annotations=o3ann, cls=LINCSwitch )
        o4ann = { "latitude": 32.8, "longitude": -117.1, "optical.regens": 3 }
        O4 = self.addSwitch( 'SDG-W10', dpid='0000ffffffffff04', annotations=o4ann, cls=LINCSwitch )
        o5ann = { "latitude": 44.8, "longitude": -93.1, "optical.regens": 3 }
        O5 = self.addSwitch( 'MSP-M10', dpid='0000ffffffffff05', annotations=o5ann, cls=LINCSwitch )
        o6ann = { "latitude": 32.8, "longitude": -97.1, "optical.regens": 3 }
        O6 = self.addSwitch( 'DFW-M10', dpid='0000ffffffffff06', annotations=o6ann, cls=LINCSwitch )
        o7ann = { "latitude": 41.8, "longitude": -87.6, "optical.regens": 3 }
        O7 = self.addSwitch( 'CHG-N10', dpid='0000ffffffffff07', annotations=o7ann, cls=LINCSwitch )
        o8ann = { "latitude": 38.8, "longitude": -77.1, "optical.regens": 3 }
        O8 = self.addSwitch( 'IAD-M10', dpid='0000ffffffffff08', annotations=o8ann, cls=LINCSwitch )
        o9ann = { "latitude": 40.8, "longitude": -73.1, "optical.regens": 0 }
        O9 = self.addSwitch( 'JFK-M10', dpid='0000ffffffffff09', annotations=o9ann, cls=LINCSwitch )
        o10ann = { "latitude": 33.8, "longitude": -84.1, "optical.regens": 0 }
        O10 = self.addSwitch( 'ATL-S10', dpid='0000ffffffffff0a', annotations=o10ann, cls=LINCSwitch )

        
        SFOR10 = self.addSwitch( 'SFO-R10', dpid='0000ffffffff0001', annotations={"latitude": 37.6, "longitude": -122.3} )
        LAXR10 = self.addSwitch( 'LAX-R10', dpid='0000ffffffff0002', annotations={ "latitude": 33.9, "longitude": -118.4 } )
        SDGR10 = self.addSwitch( 'SDG-R10', dpid='0000ffffffff0003', annotations={ "latitude": 32.8, "longitude": -117.1 } )
        CHGR10 = self.addSwitch( 'CHG-R10', dpid='0000ffffffff0004', annotations={ "latitude": 41.8, "longitude": -87.6 } )
        JFKR10 = self.addSwitch( 'JFK-R10', dpid='0000ffffffff0005', annotations={ "latitude": 40.8, "longitude": -73.1 } )
        ATLR10 = self.addSwitch( 'ATL-R10', dpid='0000ffffffff0006', annotations={ "latitude": 33.8, "longitude": -84.1 } )

        self.addLink( O1, O2, port1=50, port2=30, annotations={ "optical.waves": 80, "optical.type": "WDM", "optical.kms": 1000, "durable": "true" }, cls=LINCLink )
        self.addLink( O2, O3, port1=50, port2=30, annotations={ "optical.waves": 80, "optical.type": "WDM", "optical.kms": 1000, "durable": "true" }, cls=LINCLink )
        self.addLink( O3, O4, port1=50, port2=50, annotations={ "optical.waves": 80, "optical.type": "WDM", "optical.kms": 1000, "durable": "true" }, cls=LINCLink )
        self.addLink( O1, O5, port1=20, port2=50, annotations={ "optical.waves": 80, "optical.type": "WDM", "optical.kms": 1000, "durable": "true" }, cls=LINCLink )
        self.addLink( O2, O5, port1=20, port2=20, annotations={ "optical.waves": 80, "optical.type": "WDM", "optical.kms": 1000, "durable": "true" }, cls=LINCLink )
        self.addLink( O3, O6, port1=20, port2=50, annotations={ "optical.waves": 80, "optical.type": "WDM", "optical.kms": 1000, "durable": "true" }, cls=LINCLink )
        self.addLink( O4, O6, port1=20, port2=20, annotations={ "optical.waves": 80, "optical.type": "WDM", "optical.kms": 1000, "durable": "true" }, cls=LINCLink )
        self.addLink( O5, O6, port1=30, port2=40, annotations={ "optical.waves": 80, "optical.type": "WDM", "optical.kms": 1000, "durable": "true" }, cls=LINCLink )
        self.addLink( O5, O7, port1=40, port2=50, annotations={ "optical.waves": 80, "optical.type": "WDM", "optical.kms": 1000, "durable": "true" }, cls=LINCLink )
        self.addLink( O6, O8, port1=30, port2=50, annotations={ "optical.waves": 80, "optical.type": "WDM", "optical.kms": 1000, "durable": "true" }, cls=LINCLink )
        self.addLink( O7, O8, port1=20, port2=30, annotations={ "optical.waves": 80, "optical.type": "WDM", "optical.kms": 1000, "durable": "true" }, cls=LINCLink )
        self.addLink( O7, O9, port1=30, port2=50, annotations={ "optical.waves": 80, "optical.type": "WDM", "optical.kms": 1000, "durable": "true" }, cls=LINCLink )
        self.addLink( O8, O10, port1=20, port2=50, annotations={ "optical.waves": 80, "optical.type": "WDM", "optical.kms": 1000, "durable": "true" }, cls=LINCLink )
        self.addLink( O9, O10, port1=20, port2=20, annotations={ "optical.waves": 80, "optical.type": "WDM", "optical.kms": 1000, "durable": "true" }, cls=LINCLink )

        self.addLink( SFOR10, O1, port1=2, port2=10, speed1=10000, annotations={ "bandwidth": 100000, "optical.type": "cross-connect", "durable": "true" }, cls=LINCLink )
        self.addLink( LAXR10, O3, port1=2, port2=10, speed1=10000, annotations={ "bandwidth": 100000, "optical.type": "cross-connect", "durable": "true" }, cls=LINCLink )
        # added second tap
        self.addLink( LAXR10, O3, port1=3, port2=11, speed1=10000, annotations={ "bandwidth": 100000, "optical.type": "cross-connect", "durable": "true" }, cls=LINCLink )
        self.addLink( SDGR10, O4, port1=2, port2=10, speed1=10000, annotations={ "bandwidth": 100000, "optical.type": "cross-connect", "durable": "true" }, cls=LINCLink )
        self.addLink( CHGR10, O7, port1=2, port2=10, speed1=10000, annotations={ "bandwidth": 100000, "optical.type": "cross-connect", "durable": "true" }, cls=LINCLink )
        self.addLink( JFKR10, O9, port1=2, port2=10, speed1=10000, annotations={ "bandwidth": 100000, "optical.type": "cross-connect", "durable": "true" }, cls=LINCLink )
        self.addLink( ATLR10, O10, port1=2, port2=10, speed1=10000, annotations={ "bandwidth": 100000, "optical.type": "cross-connect", "durable": "true" }, cls=LINCLink )

        h1 = self.addHost( 'h1' )
        h2 = self.addHost( 'h2' )
        h3 = self.addHost( 'h3' )
        h4 = self.addHost( 'h4' )
        h5 = self.addHost( 'h5' )
        h6 = self.addHost( 'h6' )

        self.addLink( SFOR10, h1, port1=1 )
        self.addLink( LAXR10, h2, port1=1 )
        self.addLink( SDGR10, h3, port1=1 )
        self.addLink( CHGR10, h4, port1=1 )
        self.addLink( JFKR10, h5, port1=1 )
        self.addLink( ATLR10, h6, port1=1 )

if __name__ == '__main__':
    import sys
    if len( sys.argv ) >= 2:
        controllers = sys.argv[1:]
    else:
        print 'Usage: ./opticalUtils.py (<Controller IP>)+'
        print 'Using localhost...\n'
        controllers = [ '127.0.0.1' ]

    setLogLevel( 'info' )
    net = MininetOE( topo=SmallOpticalTopo(), controller=None, autoSetMacs=True )
    net.addControllers( controllers )
    net.start()
    CLI( net )
    net.stop()
