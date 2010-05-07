#!/usr/bin/python

"""
MiniEdit: a simple network editor for Mininet

This is a simple demonstration of how one might build a
GUI application using Mininet as the network model.

Development version - not entirely functional!

Bob Lantz, April 2010
"""

from Tkinter import Frame, Button, Label, Scrollbar, Canvas
from Tkinter import Menu, BitmapImage, PhotoImage, Wm, Toplevel

# someday: from ttk import *

from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.util import ipStr
from mininet.term import makeTerm, cleanUpScreens

class MiniEdit( Frame ):

    "A simple network editor for Mininet."

    def __init__( self, parent=None, cheight=200, cwidth=500 ):

        Frame.__init__( self, parent )
        self.action = None
        self.appName = 'MiniEdit'

        # Style
        self.font = ( 'Geneva', 9 )
        self.smallFont = ( 'Geneva', 7 )
        self.bg = 'white'

        # Title
        self.top = self.winfo_toplevel()
        self.top.title( self.appName )

        # Menu bar
        self.createMenubar()

        # Editing canvas
        self.cheight, self.cwidth = cheight, cwidth
        self.cframe, self.canvas = self.createCanvas()

        # Toolbar
        self.images = miniEditImages()
        self.buttons = {}
        self.active = None
        self.tools = ( 'Select', 'Host', 'Switch', 'Link' )
        self.customColors = { 'Switch': 'darkGreen', 'Host': 'blue' }
        self.toolbar = self.createToolbar()

        # Layout
        self.toolbar.grid( column=0, row=0, sticky='nsew')
        self.cframe.grid( column=1, row=0 )
        self.columnconfigure( 1, weight=1 )
        self.rowconfigure( 0, weight=1 )
        self.pack( expand=True, fill='both' )

        # About box
        self.aboutBox = None

        # Initialize node data
        self.nodeBindings = self.createNodeBindings()
        self.nodePrefixes = { 'Switch': 's', 'Host': 'h' }
        self.widgetToItem = {}
        self.itemToWidget = {}

        # Initialize link tool
        self.link = self.linkWidget = None

        # Selection support
        self.selection = None

        # Keyboard bindings
        self.bind( '<Control-q>', lambda event: self.quit() )
        self.bind( '<KeyPress-Delete>', self.deleteSelection )
        self.bind( '<KeyPress-BackSpace>', self.deleteSelection )
        self.focus()

        # Event handling initalization
        self.linkx = self.linky = self.linkItem = None
        self.lastSelection = None

        # Model initialization
        self.links = {}
        self.nodeCount = 0
        self.net = None

        # Close window gracefully
        Wm.wm_protocol( self.top, name='WM_DELETE_WINDOW', func=self.quit )

    def quit( self ):
        "Stop our network, if any, then quit."
        self.stop()
        Frame.quit( self )

    def createMenubar( self ):
        "Create our menu bar."

        font = self.font

        mbar = Menu( self.top, font=font )
        self.top.configure( menu=mbar )

        # Application menu
        appMenu = Menu( mbar, tearoff=False )
        mbar.add_cascade( label=self.appName, font=font, menu=appMenu )
        appMenu.add_command( label='About MiniEdit', command=self.about,
            font=font)
        appMenu.add_separator()
        appMenu.add_command( label='Quit', command=self.quit, font=font )

        #fileMenu = Menu( mbar, tearoff=False )
        #mbar.add_cascade( label="File", font=font, menu=fileMenu )
        #fileMenu.add_command( label="Load...", font=font )
        #fileMenu.add_separator()
        #fileMenu.add_command( label="Save", font=font )
        #fileMenu.add_separator()
        #fileMenu.add_command( label="Print", font=font )

        editMenu = Menu( mbar, tearoff=False )
        mbar.add_cascade( label="Edit", font=font, menu=editMenu )
        editMenu.add_command( label="Cut", font=font,
            command=lambda: self.deleteSelection( None ) )

        runMenu = Menu( mbar, tearoff=False )
        mbar.add_cascade( label="Run", font=font, menu=runMenu )
        runMenu.add_command( label="Run", font=font, command=self.doRun )
        runMenu.add_command( label="Stop", font=font, command=self.doStop )
        runMenu.add_separator()
        runMenu.add_command( label='Xterm', font=font, command=self.xterm )

    # Canvas

    def createCanvas( self ):
        "Create and return our scrolling canvas frame."
        f = Frame( self )

        canvas = Canvas( f, width=self.cwidth, height=self.cheight,
            bg=self.bg )

        # Scroll bars
        xbar = Scrollbar( f, orient='horizontal', command=canvas.xview )
        ybar = Scrollbar( f, orient='vertical', command=canvas.yview )
        canvas.configure( xscrollcommand=xbar.set, yscrollcommand=ybar.set )

        # Resize box
        resize = Label( f, bg='white' )

        # Layout
        canvas.grid( row=0, column=1, sticky='nsew')
        ybar.grid( row=0, column=2, sticky='ns')
        xbar.grid( row=1, column=1, sticky='ew' )
        resize.grid( row=1, column=2, sticky='nsew' )

        # Resize behavior
        f.rowconfigure( 0, weight=1 )
        f.columnconfigure( 1, weight=1 )
        f.grid( row=0, column=0, sticky='nsew' )
        f.bind( '<Configure>', lambda event: self.updateScrollRegion() )

        # Mouse bindings
        canvas.bind( '<ButtonPress-1>', self.clickCanvas )
        canvas.bind( '<B1-Motion>', self.dragCanvas )
        canvas.bind( '<ButtonRelease-1>', self.releaseCanvas )

        return f, canvas

    def updateScrollRegion( self ):
        "Update canvas scroll region to hold everything."
        bbox = self.canvas.bbox( 'all' )
        if bbox is not None:
            self.canvas.configure( scrollregion=( 0, 0, bbox[ 2 ],
                bbox[ 3 ] ) )

    def canvasx( self, x_root ):
        "Convert root x coordinate to canvas coordinate."
        c = self.canvas
        return c.canvasx( x_root ) - c.winfo_rootx()

    def canvasy( self, y_root ):
        "Convert root y coordinate to canvas coordinate."
        c = self.canvas
        return c.canvasy( y_root ) - c.winfo_rooty()

    # Toolbar

    def activate( self, toolName ):
        "Activate a tool and press its button."
        # Adjust button appearance
        if self.active:
            self.buttons[ self.active ].configure( relief='raised' )
        self.buttons[ toolName ].configure( relief='sunken' )
        # Activate dynamic bindings
        self.active = toolName

    def createToolbar( self ):
        "Create and return our toolbar frame."

        toolbar = Frame( self )

        # Tools
        for tool in self.tools:
            cmd = ( lambda t=tool: self.activate( t ) )
            b = Button( toolbar, text=tool, font=self.smallFont, command=cmd)
            if tool in self.images:
                b.config( height=35, image=self.images[ tool ] )
                # b.config( compound='top' )
            b.pack( fill='x' )
            self.buttons[ tool ] = b
        self.activate( self.tools[ 0 ] )

        # Spacer
        Label( toolbar, text='' ).pack()

        # Commands
        for cmd, color in [ ( 'Stop', 'darkRed' ), ( 'Run', 'darkGreen' ) ]:
            doCmd = getattr( self, 'do' + cmd )
            b = Button( toolbar, text=cmd, font=self.smallFont,
                fg=color, command=doCmd )
            b.pack( fill='x', side='bottom' )

        return toolbar

    def doRun( self ):
        "Run command."
        self.activate( 'Select' )
        for tool in self.tools:
            self.buttons[ tool ].config( state='disabled' )
        self.start()

    def doStop( self ):
        "Stop command."
        self.stop()
        for tool in self.tools:
            self.buttons[ tool ].config( state='normal' )

    # Generic canvas handler
    #
    # We could have used bindtags, as in nodeIcon, but
    # the dynamic approach used here
    # may actually require less code. In any case, it's an
    # interesting introspection-based alternative to bindtags.

    def canvasHandle( self, eventName, event ):
        "Generic canvas event handler"
        if self.active is None:
            return
        toolName = self.active
        handler = getattr( self, eventName + toolName, None )
        if handler is not None:
            handler( event )

    def clickCanvas( self, event ):
        "Canvas click handler."
        self.canvasHandle( 'click', event )

    def dragCanvas( self, event ):
        "Canvas drag handler."
        self.canvasHandle( 'drag', event )

    def releaseCanvas( self, event ):
        "Canvas mouse up handler."
        self.canvasHandle( 'release', event )

    # Currently the only items we can select directly are
    # links. Nodes are handled by bindings in the node icon.

    def findItem( self, x, y ):
        "Find items at a location in our canvas."
        items = self.canvas.find_overlapping( x, y, x, y )
        if len( items ) == 0:
            return None
        else:
            return items[ 0 ]

    # Canvas bindings for Select, Host, Switch and Link tools

    def clickSelect( self, event ):
        "Select an item."
        self.selectItem( self.findItem( event.x, event.y ) )

    def deleteItem( self, item ):
        "Delete an item."
        # Don't delete while network is running
        if self.buttons[ 'Select' ][ 'state' ] == 'disabled' :
            return
        # Delete from model
        if item in self.links:
            self.deleteLink( item )
        if item in self.itemToWidget:
            self.deleteNode( item )
        # Delete from view
        self.canvas.delete( item )

    # Callback ignores event
    # pylint: disable-msg=W0613
    def deleteSelection( self, event ):
        "Delete the selected item."
        if self.selection is not None:
            self.deleteItem( self.selection )
        self.selectItem( None )
    # pylint: enable-msg=W0613

    def nodeIcon( self, node, name ):
        "Create a new node icon."
        icon = Button( self.canvas, image=self.images[ node ],
            text=name, compound='top' )
        # Unfortunately bindtags wants a tuple
        bindtags = [ str( self.nodeBindings ) ]
        bindtags += list( icon.bindtags() )
        icon.bindtags( tuple( bindtags ) )
        return icon

    def newNode( self, node, event ):
        "Add a new node to our canvas."
        c = self.canvas
        x, y = c.canvasx( event.x ), c.canvasy( event.y )
        self.nodeCount += 1
        name = self.nodePrefixes[ node ] + str( self.nodeCount )
        icon = self.nodeIcon( node, name )
        item = self.canvas.create_window( x, y, anchor='c',
            window=icon, tags=node )
        self.widgetToItem[ icon ] = item
        self.itemToWidget[ item ] = icon
        self.selectItem( item )
        icon.links = {}

    def clickHost( self, event ):
        "Add a new host to our canvas."
        self.newNode( 'Host', event )

    def clickSwitch( self, event ):
        "Add a new switch to our canvas."
        self.newNode( 'Switch', event )

    def dragLink( self, event ):
        "Drag a link's endpoint to another node."
        if self.link is None:
            return
        # Since drag starts in widget, we use root coords
        x = self.canvasx( event.x_root )
        y = self.canvasy( event.y_root )
        c = self.canvas
        c.coords( self.link, self.linkx, self.linky, x, y )

    # Callback ignores event
    # pylint: disable-msg=W0613
    def releaseLink( self, event ):
        "Give up on the current link."
        if self.link is not None:
            self.canvas.delete( self.link )
        self.linkWidget = self.linkItem = self.link = None
    # pylint: enable-msg=W0613

    # Generic node handlers

    def createNodeBindings( self ):
        "Create a set of bindings for nodes."
        bindings = {
            '<ButtonPress-1>': self.clickNode,
            '<B1-Motion>': self.dragNode,
            '<ButtonRelease-1>': self.releaseNode,
            '<Enter>': self.enterNode,
            '<Leave>': self.leaveNode,
            '<Double-ButtonPress-1>': self.xterm
        }
        l = Label()  # lightweight-ish owner for bindings
        for event, binding in bindings.items():
            l.bind( event, binding )
        return l

    def selectItem( self, item ):
        "Select an item and remember old selection."
        self.lastSelection = self.selection
        self.selection = item

    def enterNode( self, event ):
        "Select node on entry."
        self.selectNode( event )

    # Callback ignores event
    # pylint: disable-msg=W0613
    def leaveNode( self, event ):
        "Restore old selection on exit."
        self.selectItem( self.lastSelection )
    # pylint: enable-msg=W0613

    def clickNode( self, event ):
        "Node click handler."
        if self.active is 'Link':
            self.startLink( event )
        else:
            self.selectNode( event )
        return 'break'

    def dragNode( self, event ):
        "Node drag handler."
        if self.active is 'Link':
            self.dragLink( event )
        else:
            self.dragNodeAround( event )

    def releaseNode( self, event ):
        "Node release handler."
        if self.active is 'Link':
            self.finishLink( event )

    # Specific node handlers

    def selectNode( self, event ):
        "Select the node that was clicked on."
        item = self.widgetToItem.get( event.widget, None )
        self.selectItem( item )

    def dragNodeAround( self, event ):
        "Drag a node around on the canvas."
        c = self.canvas
        # Convert global to local coordinates;
        # Necessary since x, y are widget-relative
        x = self.canvasx( event.x_root )
        y = self.canvasy( event.y_root )
        w = event.widget
        # Adjust node position
        item = self.widgetToItem[ w ]
        c.coords( item, x, y )
        # Adjust link positions
        for dest in w.links:
            link = w.links[ dest ]
            item = self.widgetToItem[ dest ]
            x1, y1 = c.coords( item )
            c.coords( link, x, y, x1, y1 )

    def startLink( self, event ):
        "Start a new link."
        if event.widget not in self.widgetToItem:
            # Didn't click on a node
            return
        w = event.widget
        item = self.widgetToItem[ w ]
        x, y = self.canvas.coords( item )
        self.link = self.canvas.create_line( x, y, x, y, width=4,
            fill='blue', tag='link' )
        self.linkx, self.linky = x, y
        self.linkWidget = w
        self.linkItem = item

        # Link bindings
        # Selection still needs a bit of work overall
        # Callbacks ignore event
        # pylint: disable-msg=W0613

        def select( event, link=self.link ):
            "Select item on mouse entry."
            self.selectItem( link )

        def highlight( event, link=self.link ):
            "Highlight item on mouse entry."
            # self.selectItem( link )
            self.canvas.itemconfig( link, fill='green' )

        def unhighlight( event, link=self.link ):
            "Unhighlight item on mouse exit."
            self.canvas.itemconfig( link, fill='blue' )
            # self.selectItem( None )

        # pylint: disable-msg=W0613
        self.canvas.tag_bind( self.link, '<Enter>', highlight )
        self.canvas.tag_bind( self.link, '<Leave>', unhighlight )
        self.canvas.tag_bind( self.link, '<ButtonPress-1>', select )

    def finishLink( self, event ):
        "Finish creating a link"
        if self.link is None:
            return
        source = self.linkWidget
        c = self.canvas
        # Since we dragged from the widget, use root coords
        x, y = self.canvasx( event.x_root ), self.canvasy( event.y_root )
        target = self.findItem( x, y )
        dest = self.itemToWidget.get( target, None )
        if ( source is None or dest is None or source == dest
            or dest in source.links or source in dest.links ):
            self.releaseLink( event )
            return
        # For now, don't allow hosts to be directly linked
        stags = self.canvas.gettags( self.widgetToItem[ source ] )
        dtags = self.canvas.gettags( target )
        if 'Host' in stags and 'Host' in dtags:
            self.releaseLink( event )
            return
        x, y = c.coords( target )
        c.coords( self.link, self.linkx, self.linky, x, y )
        self.addLink( source, dest )
        # We're done
        self.link = self.linkWidget = None

    # Menu handlers

    def about( self ):
        "Display about box."
        about = self.aboutBox
        if about is None:
            bg = 'white'
            about = Toplevel( bg='white' )
            about.title( 'About' )
            info = self.appName + ': a simple network editor for MiniNet'
            warning = 'Development version - not entirely functional!'
            author = 'Bob Lantz <rlantz@cs>, April 2010'
            line1 = Label( about, text=info, font='Helvetica 10 bold', bg=bg )
            line2 = Label( about, text=warning, font='Helvetica 9', bg=bg )
            line3 = Label( about, text=author, font='Helvetica 9', bg=bg )
            line1.pack( padx=20, pady=10 )
            line2.pack(pady=10 )
            line3.pack(pady=10 )
            hide = ( lambda about=about: about.withdraw() )
            self.aboutBox = about
            # Hide on close rather than destroying window
            Wm.wm_protocol( about, name='WM_DELETE_WINDOW', func=hide )
        # Show (existing) window
        about.deiconify()

    def createToolImages( self ):
        "Create toolbar (and icon) images."

    # Model interface
    #
    # Ultimately we will either want to use a topo or
    # mininet object here, probably.

    def addLink( self, source, dest ):
        "Add link to model."
        source.links[ dest ] = self.link
        dest.links[ source ] = self.link
        self.links[ self.link ] = ( source, dest )

    def deleteLink( self, link ):
        "Delete link from model."
        pair = self.links.get( link, None )
        if pair is not None:
            source, dest = pair
            del source.links[ dest ]
            del dest.links[ source ]
        if link is not None:
            del self.links[ link ]

    def deleteNode( self, item ):
        "Delete node (and its links) from model."
        widget = self.itemToWidget[ item ]
        for link in widget.links.values():
            # Delete from view and model
            self.deleteItem( link )
        del self.itemToWidget[ item ]
        del self.widgetToItem[ widget ]

    def build( self ):
        "Build network based on our topology."

        net = Mininet( topo=None )

        # Make controller
        net.addController( 'c0' )
        # Make nodes
        for widget in self.widgetToItem:
            name = widget[ 'text' ]
            tags = self.canvas.gettags( self.widgetToItem[ widget ] )
            nodeNum = int( name[ 1: ] )
            if 'Switch' in tags:
                net.addSwitch( name )
            elif 'Host' in tags:
                net.addHost( name, ip=ipStr( nodeNum ) )
            else:
                raise Exception( "Cannot create mystery node: " + name )
        # Make links
        for link in self.links.values():
            ( src, dst ) = link
            srcName, dstName = src[ 'text' ], dst[ 'text' ]
            src, dst = net.nameToNode[ srcName ], net.nameToNode[ dstName ]
            src.linkTo( dst )

        # Build network (we have to do this separately at the moment )
        net.build()

        return net

    def start( self ):
        "Start network."
        if self.net is None:
            self.net = self.build()
            self.net.start()

    def stop( self ):
        "Stop network."
        if self.net is not None:
            self.net.stop()
        cleanUpScreens()
        self.net = None

    def xterm( self, ignore=None ):
        "Make an xterm when a button is pressed."
        if ( self.selection is None or
             self.net is None or
             self.selection not in self.itemToWidget ):
            return
        name = self.itemToWidget[ self.selection ][ 'text' ]
        if name not in self.net.nameToNode:
            return
        term = makeTerm( self.net.nameToNode[ name ], 'Host' )
        self.net.terms.append( term )


def miniEditImages():
    "Create and return images for MiniEdit."

    # Image data. Git will be unhappy. However, the alternative
    # is to keep track of separate binary files, which is also
    # unappealing.

    return {
        'Select': BitmapImage(
            file='/usr/include/X11/bitmaps/left_ptr' ),

        'Host': PhotoImage( data=r"""
            R0lGODlhIAAYAPcAMf//////zP//mf//Zv//M///AP/M///MzP/M
            mf/MZv/MM//MAP+Z//+ZzP+Zmf+ZZv+ZM/+ZAP9m//9mzP9mmf9m
            Zv9mM/9mAP8z//8zzP8zmf8zZv8zM/8zAP8A//8AzP8Amf8AZv8A
            M/8AAMz//8z/zMz/mcz/Zsz/M8z/AMzM/8zMzMzMmczMZszMM8zM
            AMyZ/8yZzMyZmcyZZsyZM8yZAMxm/8xmzMxmmcxmZsxmM8xmAMwz
            /8wzzMwzmcwzZswzM8wzAMwA/8wAzMwAmcwAZswAM8wAAJn//5n/
            zJn/mZn/Zpn/M5n/AJnM/5nMzJnMmZnMZpnMM5nMAJmZ/5mZzJmZ
            mZmZZpmZM5mZAJlm/5lmzJlmmZlmZplmM5lmAJkz/5kzzJkzmZkz
            ZpkzM5kzAJkA/5kAzJkAmZkAZpkAM5kAAGb//2b/zGb/mWb/Zmb/
            M2b/AGbM/2bMzGbMmWbMZmbMM2bMAGaZ/2aZzGaZmWaZZmaZM2aZ
            AGZm/2ZmzGZmmWZmZmZmM2ZmAGYz/2YzzGYzmWYzZmYzM2YzAGYA
            /2YAzGYAmWYAZmYAM2YAADP//zP/zDP/mTP/ZjP/MzP/ADPM/zPM
            zDPMmTPMZjPMMzPMADOZ/zOZzDOZmTOZZjOZMzOZADNm/zNmzDNm
            mTNmZjNmMzNmADMz/zMzzDMzmTMzZjMzMzMzADMA/zMAzDMAmTMA
            ZjMAMzMAAAD//wD/zAD/mQD/ZgD/MwD/AADM/wDMzADMmQDMZgDM
            MwDMAACZ/wCZzACZmQCZZgCZMwCZAABm/wBmzABmmQBmZgBmMwBm
            AAAz/wAzzAAzmQAzZgAzMwAzAAAA/wAAzAAAmQAAZgAAM+4AAN0A
            ALsAAKoAAIgAAHcAAFUAAEQAACIAABEAAADuAADdAAC7AACqAACI
            AAB3AABVAABEAAAiAAARAAAA7gAA3QAAuwAAqgAAiAAAdwAAVQAA
            RAAAIgAAEe7u7t3d3bu7u6qqqoiIiHd3d1VVVURERCIiIhEREQAA
            ACH5BAEAAAAALAAAAAAgABgAAAiNAAH8G0iwoMGDCAcKTMiw4UBw
            BPXVm0ixosWLFvVBHFjPoUeC9Tb+6/jRY0iQ/8iVbHiS40CVKxG2
            HEkQZsyCM0mmvGkw50uePUV2tEnOZkyfQA8iTYpTKNOgKJ+C3AhO
            p9SWVaVOfWj1KdauTL9q5UgVbFKsEjGqXVtP40NwcBnCjXtw7tx/
            C8cSBBAQADs=
        """ ),

        'Switch': PhotoImage( data=r"""
            R0lGODlhIAAYAPcAMf//////zP//mf//Zv//M///AP/M///MzP/M
            mf/MZv/MM//MAP+Z//+ZzP+Zmf+ZZv+ZM/+ZAP9m//9mzP9mmf9m
            Zv9mM/9mAP8z//8zzP8zmf8zZv8zM/8zAP8A//8AzP8Amf8AZv8A
            M/8AAMz//8z/zMz/mcz/Zsz/M8z/AMzM/8zMzMzMmczMZszMM8zM
            AMyZ/8yZzMyZmcyZZsyZM8yZAMxm/8xmzMxmmcxmZsxmM8xmAMwz
            /8wzzMwzmcwzZswzM8wzAMwA/8wAzMwAmcwAZswAM8wAAJn//5n/
            zJn/mZn/Zpn/M5n/AJnM/5nMzJnMmZnMZpnMM5nMAJmZ/5mZzJmZ
            mZmZZpmZM5mZAJlm/5lmzJlmmZlmZplmM5lmAJkz/5kzzJkzmZkz
            ZpkzM5kzAJkA/5kAzJkAmZkAZpkAM5kAAGb//2b/zGb/mWb/Zmb/
            M2b/AGbM/2bMzGbMmWbMZmbMM2bMAGaZ/2aZzGaZmWaZZmaZM2aZ
            AGZm/2ZmzGZmmWZmZmZmM2ZmAGYz/2YzzGYzmWYzZmYzM2YzAGYA
            /2YAzGYAmWYAZmYAM2YAADP//zP/zDP/mTP/ZjP/MzP/ADPM/zPM
            zDPMmTPMZjPMMzPMADOZ/zOZzDOZmTOZZjOZMzOZADNm/zNmzDNm
            mTNmZjNmMzNmADMz/zMzzDMzmTMzZjMzMzMzADMA/zMAzDMAmTMA
            ZjMAMzMAAAD//wD/zAD/mQD/ZgD/MwD/AADM/wDMzADMmQDMZgDM
            MwDMAACZ/wCZzACZmQCZZgCZMwCZAABm/wBmzABmmQBmZgBmMwBm
            AAAz/wAzzAAzmQAzZgAzMwAzAAAA/wAAzAAAmQAAZgAAM+4AAN0A
            ALsAAKoAAIgAAHcAAFUAAEQAACIAABEAAADuAADdAAC7AACqAACI
            AAB3AABVAABEAAAiAAARAAAA7gAA3QAAuwAAqgAAiAAAdwAAVQAA
            RAAAIgAAEe7u7t3d3bu7u6qqqoiIiHd3d1VVVURERCIiIhEREQAA
            ACH5BAEAAAAALAAAAAAgABgAAAhwAAEIHEiwoMGDCBMqXMiwocOH
            ECNKnEixosWB3zJq3Mixo0eNAL7xG0mypMmTKPl9Cznyn8uWL/m5
            /AeTpsyYI1eKlBnO5r+eLYHy9Ck0J8ubPmPOrMmUpM6UUKMa/Ui1
            6saLWLNq3cq1q9evYB0GBAA7
        """ ),

        'Link': PhotoImage( data=r"""
            R0lGODlhFgAWAPcAMf//////zP//mf//Zv//M///AP/M///MzP/M
            mf/MZv/MM//MAP+Z//+ZzP+Zmf+ZZv+ZM/+ZAP9m//9mzP9mmf9m
            Zv9mM/9mAP8z//8zzP8zmf8zZv8zM/8zAP8A//8AzP8Amf8AZv8A
            M/8AAMz//8z/zMz/mcz/Zsz/M8z/AMzM/8zMzMzMmczMZszMM8zM
            AMyZ/8yZzMyZmcyZZsyZM8yZAMxm/8xmzMxmmcxmZsxmM8xmAMwz
            /8wzzMwzmcwzZswzM8wzAMwA/8wAzMwAmcwAZswAM8wAAJn//5n/
            zJn/mZn/Zpn/M5n/AJnM/5nMzJnMmZnMZpnMM5nMAJmZ/5mZzJmZ
            mZmZZpmZM5mZAJlm/5lmzJlmmZlmZplmM5lmAJkz/5kzzJkzmZkz
            ZpkzM5kzAJkA/5kAzJkAmZkAZpkAM5kAAGb//2b/zGb/mWb/Zmb/
            M2b/AGbM/2bMzGbMmWbMZmbMM2bMAGaZ/2aZzGaZmWaZZmaZM2aZ
            AGZm/2ZmzGZmmWZmZmZmM2ZmAGYz/2YzzGYzmWYzZmYzM2YzAGYA
            /2YAzGYAmWYAZmYAM2YAADP//zP/zDP/mTP/ZjP/MzP/ADPM/zPM
            zDPMmTPMZjPMMzPMADOZ/zOZzDOZmTOZZjOZMzOZADNm/zNmzDNm
            mTNmZjNmMzNmADMz/zMzzDMzmTMzZjMzMzMzADMA/zMAzDMAmTMA
            ZjMAMzMAAAD//wD/zAD/mQD/ZgD/MwD/AADM/wDMzADMmQDMZgDM
            MwDMAACZ/wCZzACZmQCZZgCZMwCZAABm/wBmzABmmQBmZgBmMwBm
            AAAz/wAzzAAzmQAzZgAzMwAzAAAA/wAAzAAAmQAAZgAAM+4AAN0A
            ALsAAKoAAIgAAHcAAFUAAEQAACIAABEAAADuAADdAAC7AACqAACI
            AAB3AABVAABEAAAiAAARAAAA7gAA3QAAuwAAqgAAiAAAdwAAVQAA
            RAAAIgAAEe7u7t3d3bu7u6qqqoiIiHd3d1VVVURERCIiIhEREQAA
            ACH5BAEAAAAALAAAAAAWABYAAAhIAAEIHEiwoEGBrhIeXEgwoUKG
            Cx0+hGhQoiuKBy1irChxY0GNHgeCDAlgZEiTHlFuVImRJUWXEGEy
            lBmxI8mSNknm1Dnx5sCAADs=
        """ )
    }

if __name__ == '__main__':
    setLogLevel( 'info' )
    app = MiniEdit()
    app.mainloop()
