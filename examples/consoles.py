#!/usr/bin/python

"""
consoles.py: bring up a bunch of miniature consoles on a virtual network

This demo shows how to monitor a set of nodes by using
Tkinter's createfilehandler() and Node()'s monitor().
"""

from Tkinter import *

from mininet.log import setLogLevel
from mininet.topolib import TreeNet

class Console( Frame ):
    "A simple console on a host."
    
    def __init__( self, parent, node, height=16, width=32 ):
        Frame.__init__( self, parent )
        self.node = node
        self.height, self.width = height, width
        self.text = self.makeWidgets( )
        self.bindEvents()

    def makeWidgets( self ):
        "Make a label, a text area, and a scroll bar."
        labelStyle = {
            'font': 'Monaco 7',
            'relief': 'sunken'
        }
        textStyle = { 
            'font': 'Monaco 7',
            'bg': 'black',
            'fg': 'green',
            'width': self.width,
            'height': self.height,
            'relief': 'sunken'
        }
        label = Label( self, text=self.node.name, **labelStyle )
        label.pack( side='top', fill='x' )
        text = Text( self, wrap='word', **textStyle )
        ybar = Scrollbar( self, orient='vertical', command=text.yview )
        text.configure( yscrollcommand=ybar.set )
        text.pack( side='left', expand=True, fill='both' )
        ybar.pack( side='right', fill='y' )
        return text

    def bindEvents( self ):
        "Bind keyboard and file events."
        self.text.bind( '<Return>', self.handleReturn )
        self.text.bind( '<Control-c>', self.handleInt )
        self.text.bind( '<KeyPress>', self.handleKey )
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
        print "handleReturn"
    
    def handleInt( self, event=None ):
        "Handle control-c."
        self.node.sendInt()
        
    def sendCmd( self, cmd ):
        "Send a command to our node."
        text, node = self.text, self.node
        node.sendCmd( cmd )

    def handleReadable( self, file, mask ):
        data = self.node.monitor()
        self.append( data )

class Consoles( Frame ):

    def __init__( self, nodes, parent=None, width=4 ):
        Frame.__init__( self, parent )
        self.nodes = nodes
        self.createMenuBar( font='Geneva 7' )
        self.consoles = self.createConsoles( nodes, width )
        self.pack( expand=True, fill='both' )
        
    def createConsoles( self, nodes, width ):
        "Create a grid of consoles in a frame."
        f = Frame( self )
        # Create consoles
        consoles = []
        index = 0
        for node in nodes:
            console = Console( f, node )
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
            ( 'Interrupt', self.stop ),
            ( 'Quit', self.quit )
        ]
        for name, cmd in buttons:
            b = Button( f, text=name, command=cmd, font=font )
            b.pack( side='left' )
        f.pack( padx=4, pady=4, fill='x' )
        return f
    
    def ping( self ):
        "Tell each console to ping the next one."
        consoles = self.consoles
        count = len( consoles )
        i = 1
        for console in consoles:
            ip = consoles[ i ].node.IP()
            console.sendCmd( 'ping ' + ip )
            i = ( i + 1 ) % count
            
    def stop( self ):
        "Interrupt all consoles."
        for console in self.consoles:
            console.handleInt()

    
if __name__ == '__main__':
    setLogLevel( 'info' )
    net = TreeNet( depth=2, fanout=2 )
    net.start()
    app = Consoles( net.hosts, width=2 )
    app.mainloop()
    net.stop()
