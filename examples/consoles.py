#!/usr/bin/python

"""
consoles.py: bring up a bunch of miniature consoles on a virtual network

This demo shows how to monitor a set of nodes by using
Node's monitor() and Tkinter's createfilehandler().
"""

from Tkinter import *

from mininet.log import setLogLevel
from mininet.topolib import TreeNet
from mininet.term import makeTerms, cleanUpScreens
from mininet.util import quietRun

class Console( Frame ):
    "A simple console on a host."
    
    def __init__( self, parent, net, node, height=10, width=32 ):
        Frame.__init__( self, parent )
        self.net = net
        self.node = node
        self.prompt = node.name + '# '
        self.height, self.width = height, width
        self.text = self.makeWidgets( )
        self.bindEvents()
        self.append( self.prompt )

    def makeWidgets( self ):
        "Make a label, a text area, and a scroll bar."
        buttonStyle = {
            'font': 'Monaco 7',
        }
        textStyle = { 
            'font': 'Monaco 7',
            'bg': 'black',
            'fg': 'green',
            'width': self.width,
            'height': self.height,
            'relief': 'sunken',
            'insertbackground': 'green',
            'highlightcolor': 'green',
            'selectforeground': 'black',
            'selectbackground': 'green'
        }
        def newTerm( net=self.net, node=self.node ):
            "Pop up a new terminal window for a node."
            net.terms += makeTerms( [ node ] )
        label = Button( self, text=self.node.name, command=newTerm, **buttonStyle )
        label.pack( side='top', fill='x' )
        text = Text( self, wrap='word', **textStyle )
        ybar = Scrollbar( self, orient='vertical', width=7, command=text.yview )
        text.configure( yscrollcommand=ybar.set )
        text.pack( side='left', expand=True, fill='both' )
        ybar.pack( side='right', fill='y' )
        return text

    def bindEvents( self ):
        "Bind keyboard and file events."
        self.text.bind( '<Return>', self.handleReturn )
        self.text.bind( '<Control-c>', self.handleInt )
        # self.text.bind( '<KeyPress>', self.handleKey )
        # This is not well-documented, but it is the correct
        # way to trigger a file event handler from Tk's
        # event loop!
        self.tk.createfilehandler( self.node.stdout, READABLE,
            self.handleReadable )

    def append( self, text ):
        "Append something to our text frame."
        self.text.insert( 'end', text )
        self.text.mark_set( 'insert', 'end' )
        self.text.see( 'insert' )
    
    def handleKey( self, event  ):
        "Handle a regular key press."
        self.append( event.char )
    
    def handleReturn( self, event ):
        "Handle a carriage return."
        cmd = self.text.get( 'insert linestart', 'insert lineend' )
        if cmd.find( self.prompt ) == 0:
            cmd = cmd[ len( self.prompt ): ]
        self.sendCmd( cmd )
        
    def handleInt( self, event=None ):
        "Handle control-c."
        self.node.sendInt()

    def sendCmd( self, cmd ):
        "Send a command to our node."
        text, node = self.text, self.node
        if not node.waiting:
            node.sendCmd( cmd )

    def handleReadable( self, file=None, mask=None ):
        "Handle file readable event."
        data = self.node.monitor()
        self.append( data )
        if not self.node.waiting:
            # Print prompt, just for the heck of it
            self.append( self.prompt )
            
    def waitOutput( self ):
        "Wait for any remaining output."
        while self.node.waiting:
            self.handleReadable( self )

    def clear( self ):
        "Clear all of our text."
        self.text.delete( '1.0', 'end' )
        
class ConsoleApp( Frame ):

    def __init__( self, net, nodes, parent=None, width=4 ):
        Frame.__init__( self, parent )
        self.top = self.winfo_toplevel()
        self.top.title( 'Mininet' )
        self.net = net
        self.nodes = nodes
        self.createMenuBar( font='Geneva 7' )
        self.consoles = self.createConsoles( nodes, width )
        self.pack( expand=True, fill='both' )
        cleanUpScreens()
        # Close window gracefully
        Wm.wm_protocol( self.top, name='WM_DELETE_WINDOW', func=self.quit )
        
    def createConsoles( self, nodes, width ):
        "Create a grid of consoles in a frame."
        f = Frame( self )
        # Create consoles
        consoles = []
        index = 0
        for node in nodes:
            console = Console( f, net, node )
            consoles.append( console )
            row = int( index / width )
            column = index % width
            console.grid( row=row, column=column, sticky='nsew' )
            index += 1
            f.rowconfigure( row, weight=1 )
            f.columnconfigure( column, weight=1 )
        f.pack( expand=True, fill='both' )
        return consoles
        
    def createMenuBar( self, font ):
        "Create and return a menu (really button) bar."
        f = Frame( self )
        buttons = [
            ( 'Ping', self.ping ),
            ( 'Iperf', self.iperf ),
            ( 'Interrupt', self.stop ),
            ( 'Clear', self.clear ),
            ( 'Quit', self.quit )
        ]
        for name, cmd in buttons:
            b = Button( f, text=name, command=cmd, font=font )
            b.pack( side='left' )
        f.pack( padx=4, pady=4, fill='x' )
        return f
    
    def clear( self ):
        "Clear all consoles."
        for console in self.consoles:
            console.clear()
            
    def ping( self ):
        "Tell each console to ping the next one."
        consoles = self.consoles
        count = len( consoles )
        i = 0
        for console in consoles:
            i = ( i + 1 ) % count
            ip = consoles[ i ].node.IP()
            console.sendCmd( 'ping ' + ip )

    def iperf( self ):
        "Tell each console to ping the next one."
        consoles = self.consoles
        count = len( consoles )
        for console in consoles:
            console.node.cmd( 'iperf -sD' )
        i = 0
        for console in consoles:
            i = ( i + 1 ) % count
            ip = consoles[ i ].node.IP()
            console.sendCmd( 'iperf -t 99999 -i 1 -c ' + ip )

    def stop( self ):
        "Interrupt all consoles."
        for console in self.consoles:
            console.handleInt()
        for console in self.consoles:
            console.waitOutput()
        # Shut down any iperfs that might still be running
        quietRun( 'killall -9 iperf' )

    def quit( self ):
        "Stope everything and quit."
        print "Quit"
        self.stop()
        Frame.quit( self )

if __name__ == '__main__':
    setLogLevel( 'info' )
    net = TreeNet( depth=2, fanout=4 )
    net.start()
    app = ConsoleApp( net, net.hosts, width=4 )
    app.mainloop()
    net.stop()
