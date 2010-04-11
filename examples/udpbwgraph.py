#!/usr/bin/python

"""
udpbwgraph: Plot network bandwidth over time

Bob Lantz
3/27/10
"""

from time import sleep

import os
import re
import sys
from time import time

from Tkinter import *

from mininet.log import setLogLevel
from mininet.net import init, Mininet
from mininet.node import KernelSwitch, UserSwitch, OVSKernelSwitch
from mininet.node import Controller, NOX
from mininet.topolib import TreeTopo
from mininet.util import quietRun

# bwtest support
    
class Graph( Frame ):

    "Graph that we can add bars to over time."
    
    def __init__( self, master=None,
        bg = 'white',
        gheight=200, gwidth=500,
        barwidth=10,
        ymax=3.5,):
        
        Frame.__init__( self, master )

        self.bg = bg
        self.gheight = gheight
        self.gwidth = gwidth
        self.barwidth = barwidth
        self.ymax = float( ymax )
        self.xpos = 0

        # Create everything
        self.title = self.graph = None
        self.createWidgets()
        self.updateScrollRegions()
        self.yview( 'moveto', '1.0' )
        
    def scale( self ):
        "Create a and return a new canvas with scale markers."
        height = float( self.gheight )
        width = 25
        ymax = self.ymax
        scale = Canvas( self, width=width, height=height, background=self.bg )
        fill = 'red'
        # Draw scale line
        scale.create_line( width - 1, height, width - 1, 0, fill=fill )
        # Draw ticks and numbers
        for y in range( 0, int( ymax + 1 ) ):
            ypos = height * (1 - float( y ) / ymax )
            scale.create_line( width, ypos, width - 10, ypos, fill=fill )
            scale.create_text( 10, ypos, text=str( y ), fill=fill )
            
        return scale
    
    def updateScrollRegions( self ):
        "Update graph and scale scroll regions."
        ofs = 20
        height = self.gheight + ofs
        self.graph.configure( scrollregion=( 0, -ofs, 
            self.xpos * self.barwidth, height ) )
        self.scale.configure( scrollregion=( 0, -ofs, 0, height ) )
        
    def yview( self, *args ):
            "Scroll both scale and graph."
            self.graph.yview( *args )
            self.scale.yview( *args )
                
    def createWidgets( self ):
        "Create initial widget set."

        # Objects
        title = Label( self, text="Bandwidth (Mb/s)", bg=self.bg )
        width = self.gwidth
        height = self.gheight
        scale = self.scale()
        graph = Canvas( self, width=width, height=height, background=self.bg)
        xbar = Scrollbar( self, orient='horizontal', command=graph.xview )
        ybar = Scrollbar( self, orient='vertical', command=self.yview )
        graph.configure( xscrollcommand=xbar.set, yscrollcommand=ybar.set,
            scrollregion=(0, 0, width, height ) )
        scale.configure( yscrollcommand=ybar.set )
        
        # Layout
        title.grid( row=0, columnspan=3, sticky=N+E+W)
        scale.grid( row=1, column=0, sticky=N+S+E+W )
        graph.grid( row=1, column=1, sticky=N+S+E+W )
        ybar.grid( row=1, column=2, sticky=N+S )
        xbar.grid( row=2, column=0, columnspan=2, sticky=E+W )
        self.rowconfigure( 1, weight=1 )
        self.columnconfigure( 1, weight=1 )

        # Save for future reference
        self.title = title
        self.scale = scale
        self.graph = graph
        return graph
            
    def addBar( self, yval ):
        "Add a new bar to our graph."
        percent = yval / self.ymax
        height = percent * self.gheight
        c = self.graph
        x0 = self.xpos * self.barwidth
        x1 = x0 + self.barwidth
        y0 = self.gheight
        y1 = ( 1 - percent ) * self.gheight
        c.create_rectangle( x0 , y0, x1, y1, fill='green' )
        self.xpos += 1
        self.updateScrollRegions()
        self.graph.xview( 'moveto', '1.0' )

    def test( self ):
        "Add a bar for testing purposes."
        ms = 1000
        if self.xpos < 10:
            self.addBar( self.xpos/10 * self.ymax  )
            self.after( ms, self.test )

    def setTitle( self, text ):
        "Set graph title"
        self.title.configure( text=text, font='Helvetica 9 bold' )


class Controls( Frame ):

    "Handy controls for configuring test."
    
    switches = { 
        'Kernel Switch': KernelSwitch,
        'User Switch': UserSwitch,
        'Open vSwitch': OVSKernelSwitch
    }
    
    controllers = {
        'Reference Controller': Controller,
        'NOX': NOX
    }
    
    
    def __init__( self, master=None ):
    
        Frame.__init__( self, master )
        
        self.switch = StringVar()
        self.switch.set( 'Kernel Switch' )
        self.switchMenu = OptionMenu( self, self.switch, 
            *( switches.keys() ) )
        
        self.controller = StringVar()
        self.controller.set( 'Reference Controller' )
        self.controllerMenu = OpetionMenu( self, self.controller,
            *( controllers.keys() ) )

def App( Frame ):

           
def parsebwtest( line,
    r=re.compile( r'(\d+) s: in ([\d\.]+) Mbps, out ([\d\.]+) Mbps' ) ):
    "Parse udpbwtest.c output, returning seconds, inbw, outbw."
    match = r.match( line )
    if match:
        seconds, inbw, outbw = match.group( 1, 2, 3 )
        return int( seconds ), float( inbw ), float( outbw )
    return None, None, None


class UdpBwTest( object ):
    "Test and plot UDP bandwidth over time"

    def __init__( self, graph, net, seconds=60 ):
        "Start up and monitor udpbwtest on each of our hosts."
        
        hosts = net.hosts
        self.graph = graph
        self.hostCount = len( hosts )
        
        print "*** Starting udpbwtest on hosts"
        for host in hosts:
            ips = [ h.IP() for h in hosts if h != host ]
            host.cmdPrint( './udpbwtest ' + ' '.join( ips ) + ' &' )
        
        print "*** Monitoring hosts"
        self.output = net.monitor( hosts, timeoutms=0 )
        self.results = {}
        self.quitTime = time() + seconds
        self.updateGraph()

    # Pylint isn't smart enough to understand iterator.next()
    # pylint: disable-msg=E1101
    
    def updateGraph( self ):
        "Graph input bandwidth."
        while True:
            host, line = self.output.next()
            if host is None or len( line ) == 0:
                break
            seconds, inbw, outbw = parsebwtest( line )
            if seconds is None:
                break
            result = self.results.get( seconds, [] ) + [ ( host, inbw, outbw ) ]
            self.results[ seconds ] = result
            if len( result ) == self.hostCount:
                # Calculate total and update graph
                # We report input bandwidth, i.e. packets that made it
                totalin = 0
                for host, inbw, outbw in result:
                    totalin += inbw
                self.graph.addBar( totalin / 1000.0 )
                print totalin
        if time() < self.quitTime:
            # Fileevent would be better, but for now we just poll every 500ms
            self.graph.after( 10, self.updateGraph )
        else:
            self.shutdown()

    def shutdown( self ):
        "Stop udpbwtest proceses."
        print "*** Stopping udpbwtest processes"
        # We *really* don't want these things hanging around!
        quietRun( 'killall -9 udpbwtest' )

    # pylint: enable-msg=E1101

if __name__ == '__main__':
    setLogLevel( 'info' )
    app = Graph()
    app.master.title( "Mininet Bandwidth" )
    depth, fanout = 1, 2
    net = Mininet( topo=TreeTopo( depth=depth, fanout=fanout), 
        switch=KernelSwitch )
    title = "Bandwidth (Mb/s), (%i hosts, %i switches, depth=%d, fanout=%d)" % (
        len( net.hosts ), len( net.switches), depth, fanout )
    app.setTitle( title )
    net.start()
    test = UdpBwTest( app, net )
    app.mainloop()
    net.stop()
    test.shutdown()  # just in case!
    