#!/usr/bin/python

"""
udpbwgraph: Plot network bandwidth over time

Bob Lantz
3/27/10
"""

import re

from Tkinter import Frame, Label, Button, Scrollbar, OptionMenu, Canvas
from Tkinter import StringVar

from mininet.log import setLogLevel
from mininet.net import Mininet
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
        self.title, self.graph, self.scale = self.createWidgets()
        self.updateScrollRegions()
        self.yview( 'moveto', '1.0' )

    def createScale( self ):
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
            ypos = height * ( 1 - float( y ) / ymax )
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
        scale = self.createScale()
        graph = Canvas( self, width=width, height=height, background=self.bg)
        xbar = Scrollbar( self, orient='horizontal', command=graph.xview )
        ybar = Scrollbar( self, orient='vertical', command=self.yview )
        graph.configure( xscrollcommand=xbar.set, yscrollcommand=ybar.set,
            scrollregion=(0, 0, width, height ) )
        scale.configure( yscrollcommand=ybar.set )

        # Layout
        title.grid( row=0, columnspan=3, sticky='new')
        scale.grid( row=1, column=0, sticky='nsew' )
        graph.grid( row=1, column=1, sticky='nsew' )
        ybar.grid( row=1, column=2, sticky='ns' )
        xbar.grid( row=2, column=0, columnspan=2, sticky='ew' )
        self.rowconfigure( 1, weight=1 )
        self.columnconfigure( 1, weight=1 )
        return title, graph, scale

    def addBar( self, yval ):
        "Add a new bar to our graph."
        percent = yval / self.ymax
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
            self.addBar( self.xpos / 10 * self.ymax  )
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

    def __init__( self, master, startFn, stopFn, quitFn ):

        Frame.__init__( self, master )

        # Option menus
        opts = { 'font': 'Geneva 7 bold' }
        self.switch = self.optionMenu( self.switches,
            KernelSwitch, opts )
        self.controller = self.optionMenu( self.controllers,
            Controller, opts)

        # Spacer
        pk = { 'fill': 'x' }
        Label( self, **opts ).pack( **pk )

        # Buttons
        self.start = Button( self, text='Start', command=startFn, **opts )
        self.stop = Button( self, text='Stop', command=stopFn, **opts )
        self.quit = Button( self, text='Quit', command=quitFn, **opts )
        for button in ( self.start, self.stop, self.quit ):
            button.pack( **pk )

    def optionMenu( self, menuItems, initval, opts ):
        "Add a new option menu. Returns function to get value."
        var = StringVar()
        var.set( findKey( menuItems, initval ) )
        menu = OptionMenu( self, var, *menuItems )
        menu.config( **opts )
        menu.pack( fill='x' )
        return lambda: menuItems[ var.get() ]

def parsebwtest( line,
    r=re.compile( r'(\d+) s: in ([\d\.]+) MB/s, out ([\d\.]+) MB/s' ) ):
    "Parse udpbwtest.c output, returning seconds, inbw, outbw."
    match = r.match( line )
    if match:
        seconds, inbw, outbw = match.group( 1, 2, 3 )
        return int( seconds ), float( inbw ), float( outbw )
    return None, None, None


class UdpBwTest( Frame ):
    "Test and plot UDP bandwidth over time"

    def __init__( self, topo, master=None ):
        "Start up and monitor udpbwtest on each of our hosts."

        Frame.__init__( self, master )

        self.controls = Controls( self, self.start, self.stop, self.quit )
        self.graph = Graph( self )

        # Layout
        self.controls.pack( side='left', expand=False, fill='y' )
        self.graph.pack( side='right', expand=True, fill='both' )
        self.pack( expand=True, fill='both' )

        self.topo = topo
        self.net = None
        self.hosts = []
        self.hostCount = 0
        self.output = None
        self.results = {}
        self.running = False

    def start( self ):
        "Start test."

        if self.running:
            return

        switch = self.controls.switch()
        controller = self.controls.controller()

        self.net = Mininet( self.topo, switch=switch, 
            controller=controller )
        self.hosts = self.net.hosts
        self.hostCount = len( self.hosts )

        print "*** Starting network"
        self.net.start()

        print "*** Starting udpbwtest on hosts"
        hosts = self.hosts
        for host in hosts:
            ips = [ h.IP() for h in hosts if h != host ]
            host.cmdPrint( './udpbwtest ' + ' '.join( ips ) + ' &' )

        print "*** Monitoring hosts"
        self.output = self.net.monitor( hosts, timeoutms=1 )
        self.results = {}
        self.running = True
        self.updateGraph()

    # Pylint isn't smart enough to understand iterator.next()
    # pylint: disable-msg=E1101

    def updateGraph( self ):
        "Graph input bandwidth."

        print "updateGraph"

        if not self.running:
            return

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
                self.graph.addBar( totalin * 8.0/1000.0 )
                print totalin
        # Fileevent might be better, but for now we just poll every 500ms
        self.graph.after( 500, self.updateGraph )

    def stop( self ):
        "Stop test."

        print "*** Stopping udpbwtest processes"
        # We *really* don't want these things hanging around!
        quietRun( 'killall -9 udpbwtest' )

        if not self.running:
            return

        print "*** Stopping network"
        self.running = False
        self.net.stop()

    def quit( self ):
        "Quit app."
        self.stop()
        Frame.quit( self )

    # pylint: enable-msg=E1101

# Useful utilities

def findKey( d, value ):
    "Find some key where d[ key ] == value."
    return [ key for key, val in d.items() if val == value ][ 0 ]

def assign( obj, **kwargs):
    "Set a bunch of fields in an object."
    for name, value in kwargs.items():
        setattr( obj, name, value )

class Object( object ):
    "Generic object you can stuff junk into."
    def __init__( self, **kwargs ):
        assign( self, **kwargs )

if __name__ == '__main__':
    setLogLevel( 'info' )
    app = UdpBwTest( topo=TreeTopo( depth=2, fanout=2 ) )
    app.mainloop()


