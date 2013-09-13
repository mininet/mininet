#!/usr/bin/python

"""
MiniEdit: a simple network editor for Mininet

This is a simple demonstration of how one might build a
GUI application using Mininet as the network model.

Development version - not entirely functional!

Bob Lantz, April 2010

"""

from optparse import OptionParser
from Tkinter import *
#from Tkinter import Frame, Button, Label, Scrollbar, Canvas, Entry, OptionMenu
#from Tkinter import Menu, BitmapImage, PhotoImage, Wm, Toplevel
from tkMessageBox import showinfo, showerror
from subprocess import call
import tkFont
import csv
import tkFileDialog
import tkSimpleDialog
import re
import json

# someday: from ttk import *

from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.util import ipStr, netParse, ipAdd, quietRun
from mininet.term import makeTerm, cleanUpScreens
from mininet.node import Controller, RemoteController, NOX, OVSController
from mininet.node import CPULimitedHost, Host
from mininet.node import OVSKernelSwitch, OVSSwitch
from mininet.link import TCLink, Intf


CONTROLLERDEF = 'ref'
CONTROLLERS = { 'ref': Controller,
                'ovsc': OVSController,
                'nox': NOX,
                'remote': RemoteController,
                'none': lambda name: None }

class PrefsDialog(tkSimpleDialog.Dialog):

        def __init__(self, parent, title, prefDefaults):

            self.prefValues = prefDefaults

            tkSimpleDialog.Dialog.__init__(self, parent, title)

        def body(self, master):

            Label(master, text="IP Base:").grid(row=0, sticky=E)
            Label(master, text="Defaul Terminal:").grid(row=1, sticky=E)

            # Field for Base IP
            self.e1 = Entry(master)
            self.e1.grid(row=0, column=1)
            ipBase =  self.prefValues['ipBase']
            self.e1.insert(0, ipBase)

            # Selection of terminal type
            self.var = StringVar(master)
            self.o1 = OptionMenu(master, self.var, "xterm", "gterm")
            self.o1.grid(row=1, column=1, sticky=W)
            terminalType = self.prefValues['terminalType']
            self.var.set(terminalType)

            return self.e1 # initial focus

        def apply(self):
            ipBase = self.e1.get()
            terminalType = self.var.get()
            #print 'Dialog='+ipBase
            #print 'Terminal='+terminalType
            self.result = ipBase, terminalType

class CustomDialog(object):

        # TODO: Fix button placement and Title and window focus lock
        def __init__(self, master, title):
            self.top=Toplevel(master)

            self.bodyFrame = Frame(self.top)
            self.bodyFrame.grid(row=0, column=0, sticky='nswe')
            self.body(self.bodyFrame)

            #return self.b # initial focus
            buttonFrame = Frame(self.top, relief='ridge', bd=3, bg='lightgrey')
            buttonFrame.grid(row=1 , column=0, sticky='nswe')

            okButton = Button(buttonFrame, width=8, text='OK', relief='groove',
                       bd=4, command=self.okAction)
            okButton.grid(row=0, column=0, sticky=E)

            canlceButton = Button(buttonFrame, width=8, text='Cancel', relief='groove',
                        bd=4, command=self.cancelAction)
            canlceButton.grid(row=0, column=1, sticky=W)

        def body(self, master):
            self.rootFrame = master

        def apply(self):
            self.top.destroy()

        def cancelAction(self):
            self.top.destroy()

        def okAction(self):
            self.apply()
            self.top.destroy()

class HostDialog(CustomDialog):

        def __init__(self, master, title, prefDefaults):

            self.prefValues = prefDefaults
            self.result = None

            CustomDialog.__init__(self, master, title)

        def body(self, master):
            self.rootFrame = master
            self.fieldFrame = Frame(self.rootFrame)
            self.fieldFrame.grid(row=0, column=0, sticky='nswe')
            Label(self.fieldFrame, text="Amount CPU:").grid(row=0, sticky=E)
            Label(self.fieldFrame, text="Cores:").grid(row=1, sticky=E)

            cpu = ''
            cores = ''
            sched = ''
            externalInterfaces = []
            if 'cpu' in self.prefValues:
                cpu =  str(self.prefValues['cpu'])
            if 'cores' in self.prefValues:
                cores =  self.prefValues['cores']
            if 'sched' in self.prefValues:
                sched =  self.prefValues['sched']
            else:
                sched = 'host'
            if 'externalInterfaces' in self.prefValues:
                externalInterfaces = self.prefValues['externalInterfaces']

            # Field for CPU
            self.e1 = Entry(self.fieldFrame)
            self.e1.grid(row=0, column=1)
            self.e1.insert(0, cpu)

            # Selection of Cores
            self.e2 = Entry(self.fieldFrame)
            self.e2.grid(row=1, column=1)
            self.e2.insert(1, cores)

            # Selection of Scheduler
            self.var = StringVar(self.fieldFrame)
            self.o1 = OptionMenu(self.fieldFrame, self.var, "host", "cfs", "rt")
            self.o1.grid(row=0, column=2, sticky=W)
            self.var.set(sched)

            # External Interfaces
            self.externalInterfaces = 0
            Label(self.fieldFrame, text="External Interface:").grid(row=3, sticky=E)
            self.b = Button( self.fieldFrame, text='Add', command=self.addInterface)
            self.b.grid(row=3, column=1)

            self.interfaceFrame = VerticalScrolledTable(self.rootFrame, rows=0, columns=1, title='External Interfaces')
            self.interfaceFrame.grid(row=1, column=0, sticky='nswe')
            self.tableFrame = self.interfaceFrame.interior

            # Add defined interfaces
            for externalInterface in externalInterfaces:
                self.tableFrame.addRow(externalInterface)

        def addInterface( self ):
            self.tableFrame.addRow()

        def apply(self):
            cpu = self.e1.get()
            cores = self.e2.get()
            sched = self.var.get()
            #print 'cpu='+cpu
            #print 'cores='+cores
            #print 'sched='+sched
            externalInterfaces = []
            for row in range(self.tableFrame.rows):
                #print 'Interface is ' + self.tableFrame.get(row, 0)
                if (len(self.tableFrame.get(row, 0)) > 0):
                    externalInterfaces.append(self.tableFrame.get(row, 0))

            results = {'cpu': cpu,
                       'cores':cores,
                       'sched':sched,
                       'externalInterfaces':externalInterfaces}
            self.result = results

class SwitchDialog(CustomDialog):

        def __init__(self, master, title, prefDefaults):

            self.prefValues = prefDefaults
            self.result = None
            CustomDialog.__init__(self, master, title)

        def body(self, master):
            self.rootFrame = master

            externalInterfaces = []
            if 'externalInterfaces' in self.prefValues:
                externalInterfaces = self.prefValues['externalInterfaces']

            self.fieldFrame = Frame(self.rootFrame)
            self.fieldFrame.grid(row=0, column=0, sticky='nswe')

            # External Interfaces
            Label(self.fieldFrame, text="External Interface:").grid(row=0, sticky=E)
            self.b = Button( self.fieldFrame, text='Add', command=self.addInterface)
            self.b.grid(row=0, column=1)

            self.interfaceFrame = VerticalScrolledTable(self.rootFrame, rows=0, columns=1, title='External Interfaces')
            self.interfaceFrame.grid(row=1, column=0, sticky='nswe')
            self.tableFrame = self.interfaceFrame.interior

            # Add defined interfaces
            for externalInterface in externalInterfaces:
                self.tableFrame.addRow(externalInterface)

        def addInterface( self ):
            self.tableFrame.addRow()

        def apply(self):
            externalInterfaces = []
            for row in range(self.tableFrame.rows):
                #print 'Interface is ' + self.tableFrame.get(row, 0)
                if (len(self.tableFrame.get(row, 0)) > 0):
                    externalInterfaces.append(self.tableFrame.get(row, 0))

            results = {'externalInterfaces':externalInterfaces}
            self.result = results

class VerticalScrolledTable(LabelFrame):
    """A pure Tkinter scrollable frame that actually works!

    * Use the 'interior' attribute to place widgets inside the scrollable frame
    * Construct and pack/place/grid normally
    * This frame only allows vertical scrolling
    
    """
    def __init__(self, parent, rows=2, columns=2, title=None, *args, **kw):
        LabelFrame.__init__(self, parent, text=title, padx=5, pady=5, *args, **kw)            

        # create a canvas object and a vertical scrollbar for scrolling it
        vscrollbar = Scrollbar(self, orient=VERTICAL)
        vscrollbar.pack(fill=Y, side=RIGHT, expand=FALSE)
        canvas = Canvas(self, bd=0, highlightthickness=0,
                        yscrollcommand=vscrollbar.set)
        canvas.pack(side=LEFT, fill=BOTH, expand=TRUE)
        vscrollbar.config(command=canvas.yview)

        # reset the view
        canvas.xview_moveto(0)
        canvas.yview_moveto(0)

        # create a frame inside the canvas which will be scrolled with it
        self.interior = interior = TableFrame(canvas, rows=rows, columns=columns)
        #canvas.config(background="blue")
        #interior.config(background="red")
        interior_id = canvas.create_window(0, 0, window=interior,
                                           anchor=NW)

        # track changes to the canvas and frame width and sync them,
        # also updating the scrollbar
        def _configure_interior(event):
            # update the scrollbars to match the size of the inner frame
            size = (interior.winfo_reqwidth(), interior.winfo_reqheight())
            canvas.config(scrollregion="0 0 %s %s" % size)
            if interior.winfo_reqwidth() != canvas.winfo_width():
                # update the canvas's width to fit the inner frame
                canvas.config(width=interior.winfo_reqwidth())
        interior.bind('<Configure>', _configure_interior)

        def _configure_canvas(event):
            if interior.winfo_reqwidth() != canvas.winfo_width():
                # update the inner frame's width to fill the canvas
                canvas.itemconfigure(interior_id, width=canvas.winfo_width())
        canvas.bind('<Configure>', _configure_canvas)

        return

class TableFrame(Frame):
    def __init__(self, parent, rows=2, columns=2):

        Frame.__init__(self, parent, background="black")
        self._widgets = []
        self.rows = rows
        self.columns = columns
        for row in range(rows):
            current_row = []
            for column in range(columns):
                label = Entry(self, borderwidth=0)
                label.grid(row=row, column=column, sticky="wens", padx=1, pady=1)
                current_row.append(label)
            self._widgets.append(current_row)

    def set(self, row, column, value):
        widget = self._widgets[row][column]
        widget.insert(0, value)

    def get(self, row, column):
        widget = self._widgets[row][column]
        return widget.get()

    def addRow( self, value=None ):
        #print "Adding row " + str(self.rows +1)
        current_row = []
        for column in range(self.columns):
            label = Entry(self, borderwidth=0)
            label.grid(row=self.rows, column=column, sticky="wens", padx=1, pady=1)
            if value is not None:
                label.insert(0, value)
            current_row.append(label)
        self._widgets.append(current_row)
        self.update_idletasks()
        self.rows += 1

class LinkDialog(tkSimpleDialog.Dialog):

        def __init__(self, parent, title, linkDefaults):

            self.linkValues = linkDefaults

            tkSimpleDialog.Dialog.__init__(self, parent, title)

        def body(self, master):

            self.var = StringVar(master)
            Label(master, text="Bandwidth:").grid(row=0, sticky=E)
            Label(master, text="Delay:").grid(row=1, sticky=E)
            Label(master, text="Loss:").grid(row=2, sticky=E)
            Label(master, text="Max Queue size:").grid(row=3, sticky=E)

            self.e1 = Entry(master)
            self.e2 = Entry(master)
            self.e3 = Entry(master)
            self.e4 = Entry(master)

            self.e1.grid(row=0, column=1)
            self.e2.grid(row=1, column=1)
            self.e3.grid(row=2, column=1)
            self.e4.grid(row=3, column=1)

            Label(master, text="Mbit").grid(row=0, column=2, sticky=W)
            Label(master, text="%").grid(row=2, column=2, sticky=W)

            bw = ''
            delay = ''
            loss = ''
            max_queue_size = ''
            use_htb = False
            if 'bw' in self.linkValues:
                bw =  str(self.linkValues['bw'])
            if 'delay' in self.linkValues:
                delay =  self.linkValues['delay']
            if 'loss' in self.linkValues:
                loss =  self.linkValues['loss']
            if 'max_queue_size' in self.linkValues:
                max_queue_size =  self.linkValues['max_queue_size']
            self.e1.insert(0, bw)
            self.e2.insert(0, delay)
            self.e3.insert(0, loss)
            self.e4.insert(0, max_queue_size)

            return self.e1 # initial focus

        def apply(self):
            bw = self.e1.get()
            delay = self.e2.get()
            loss = self.e3.get()
            max_queue_size = self.e4.get()
            self.result = bw, delay, loss, max_queue_size

class ControllerDialog(tkSimpleDialog.Dialog):

        def __init__(self, parent, title, ctrlrDefaults=None):

            if ctrlrDefaults:
                self.ctrlrValues = ctrlrDefaults

            tkSimpleDialog.Dialog.__init__(self, parent, title)

        def body(self, master):

            self.var = StringVar(master)
            Label(master, text="Controller Type:").grid(row=0, sticky=E)
            Label(master, text="Remote IP:").grid(row=1, sticky=E)
            Label(master, text="Remote Port:").grid(row=2, sticky=E)

            # Field for Remove Controller IP
            self.e1 = Entry(master)
            self.e1.grid(row=1, column=1)
            self.e1.insert(0, self.ctrlrValues['remoteIP'])

            # Field for Remove Controller Port
            self.e2 = Entry(master)
            self.e2.grid(row=2, column=1)
            self.e2.insert(0, self.ctrlrValues['remotePort'])

            # Field for Controller Type
            controllerType = self.ctrlrValues['controllerType']
            self.o1 = OptionMenu(master, self.var, "Remote", "OpenFlow Reference", "OVS Controller")
            self.o1.grid(row=0, column=1, sticky=W)
            if controllerType == 'ref':
                self.var.set("OpenFlow Reference")
            elif controllerType == 'remote':
                self.var.set("Remote")
            else:
                self.var.set("OVS Controller")

            return self.o1 # initial focus

        def apply(self):
            controllerType = self.var.get()
            if controllerType == 'Remote':
                first = self.e1.get()
                second = int(self.e2.get())
                self.result = 'remote', first, second
            elif controllerType == 'OpenFlow Reference':
                self.result = ['ref']
            else:
                self.result = ['ovsc']

class MiniEdit( Frame ):

    "A simple network editor for Mininet."

    def __init__( self, parent=None, cheight=400, cwidth=800 ):

        self.defaultIpBase='10.0.0.0/8'
        self.defaultTerminal='xterm'

        self.minieditIpBase=self.defaultIpBase
        Frame.__init__( self, parent )
        self.action = None
        self.appName = 'MiniEdit'
        self.fixedFont = tkFont.Font ( family="DejaVu Sans Mono", size="14" )

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
        self.controllers = {}
        self.controllerbar = self.createControllerBar()

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
        self.controllerbar.grid( column=2, row=0, sticky='nsew' )
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

        self.hostPopup = Menu(self.top, tearoff=0)
        self.hostPopup.add_command(label='Host Options', font=self.font)
        self.hostPopup.add_separator()
        self.hostPopup.add_command(label='Terminal', font=self.font, command=self.xterm )
        self.hostPopup.add_command(label='Properties', font=self.font, command=self.hostDetails )

        self.switchPopup = Menu(self.top, tearoff=0)
        self.switchPopup.add_command(label='Swtich Options', font=self.font)
        self.switchPopup.add_separator()
        self.switchPopup.add_command(label='List bridge details', font=self.font, command=self.listBridge )
        self.switchPopup.add_command(label='Properties', font=self.font, command=self.switchDetails )

        self.linkPopup = Menu(self.top, tearoff=0)
        self.linkPopup.add_command(label='Link Options', font=self.font)
        self.linkPopup.add_separator()
        self.linkPopup.add_command(label='Properties', font=self.font, command=self.linkDetails )



        # Event handling initalization
        self.linkx = self.linky = self.linkItem = None
        self.lastSelection = None

        # Model initialization
        self.links = {}
        self.hostOpts = {}
        self.switchOpts = {}
        self.hostCount = 0
        self.switchCount = 0
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


        fileMenu = Menu( mbar, tearoff=False )
        mbar.add_cascade( label="File", font=font, menu=fileMenu )
        fileMenu.add_command( label="New", font=font, command=self.newTopology )
        fileMenu.add_command( label="Open", font=font, command=self.loadTopology )
        fileMenu.add_command( label="Save", font=font, command=self.saveTopology )
        fileMenu.add_command( label="Export", font=font, command=self.exportTopology )
        fileMenu.add_separator()
        fileMenu.add_command( label='Quit', command=self.quit, font=font )

        editMenu = Menu( mbar, tearoff=False )
        mbar.add_cascade( label="Edit", font=font, menu=editMenu )
        editMenu.add_command( label="Cut", font=font,
                              command=lambda: self.deleteSelection( None ) )
        editMenu.add_command( label="Preferences", font=font, command=self.prefDetails)

        runMenu = Menu( mbar, tearoff=False )
        mbar.add_cascade( label="Run", font=font, menu=runMenu )
        runMenu.add_command( label="Run", font=font, command=self.doRun )
        runMenu.add_command( label="Stop", font=font, command=self.doStop )
        fileMenu.add_separator()
        runMenu.add_command( label='Show OVS Summary', font=font, command=self.ovsShow )
        runMenu.add_command( label='Root Terminal', font=font, command=self.rootTerminal )

        # Application menu
        appMenu = Menu( mbar, tearoff=False )
        mbar.add_cascade( label="Help", font=font, menu=appMenu )
        appMenu.add_command( label='About MiniEdit', command=self.about,
                             font=font)
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

    def createControllerBar( self ):
        "Create and return our Controller Bar frame."

        controllerbar = Frame( self )
        Label( controllerbar, text='Controllers' ).pack()
        b = Button( controllerbar, text='c0', font=self.smallFont, command=self.controllerDetails)
        b.pack( fill='x' )

        ctrlr = { 'controllerType': 'ref',
                'remoteIP': '127.0.0.1',
                'remotePort': 6633}

        self.controllers['c0'] = ctrlr

        return controllerbar

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

    def addNode( self, node, nodeNum, x, y):
        "Add a new node to our canvas."
        if 'Switch' == node:
            self.switchCount += 1
        if 'Host' == node:
            self.hostCount += 1
        name = self.nodePrefixes[ node ] + nodeNum
        self.addNamedNode(node, name, x, y)

    def addNamedNode( self, node, name, x, y):
        "Add a new node to our canvas."
        c = self.canvas
        icon = self.nodeIcon( node, name )
        item = self.canvas.create_window( x, y, anchor='c', window=icon,
                                          tags=node )
        self.widgetToItem[ icon ] = item
        self.itemToWidget[ item ] = icon
        icon.links = {}

    def loadTopology( self ):
        "Load command."
        self.newTopology()

        myFormats = [
            ('Mininet Topology','*.mn'),
            ('All Files','*'),
        ]
        f = tkFileDialog.askopenfile(filetypes=myFormats, mode='rb')
        loadedTopology = eval(f.read())

        self.controllers = loadedTopology['controllers']

        if 'application' in loadedTopology:
            applicationPrefs = loadedTopology['application']
            self.minieditIpBase = applicationPrefs['ipBase']

        hosts = loadedTopology['hosts']
        for host in hosts:
            nodeNum = host['number']
            x = host['x']
            y = host['y']
            self.addNode('Host', nodeNum, float(x), float(y))
            self.hostOpts['h'+nodeNum] = host['opts']
            icon = self.findWidgetByName('h'+nodeNum)
            icon.bind('<Button-3>', self.do_hostPopup )

        switches = loadedTopology['switches']
        for switch in switches:
            nodeNum = switch['number']
            x = switch['x']
            y = switch['y']
            self.addNode('Switch', nodeNum, float(x), float(y))
            self.switchOpts['s'+nodeNum] = switch['opts']
            icon = self.findWidgetByName('s'+nodeNum)
            icon.bind('<Button-3>', self.do_switchPopup )

        links = loadedTopology['links']
        for link in links:
            srcNode = link['src']
            src = self.findWidgetByName(srcNode)
            sx, sy = self.canvas.coords( self.widgetToItem[ src ] )

            destNode = link['dest']
            dest = self.findWidgetByName(destNode)
            dx, dy = self.canvas.coords( self.widgetToItem[ dest]  )

            self.link = self.canvas.create_line( sx, sy, dx, dy, width=4,
                                             fill='blue', tag='link' )
            self.addLink( src, dest, linkopts=link['opts'] )
            self.createLinkBindings()

        f.close

    def findWidgetByName( self, name ):
        for widget in self.widgetToItem:
            if name ==  widget[ 'text' ]:
                return widget

    def newTopology( self ):
        "New command."
        for widget in self.widgetToItem.keys():
            self.deleteItem( self.widgetToItem[ widget ] )
        self.hostCount = 0
        self.switchCount = 0
        self.links = {}
        self.hostOpts = {}
        self.switchOpts = {}
        self.minieditIpBase = self.defaultIpBase

    def saveTopology( self ):
        "Save command."
        myFormats = [
            ('Mininet Topology','*.mn'),
            ('All Files','*'),
        ]

        savingDictionary = {}
        fileName = tkFileDialog.asksaveasfilename(filetypes=myFormats ,title="Save the topology as...")
        if len(fileName ) > 0:
            # Save Application preferences
            savingDictionary['version'] = '1'

            # Save Switches and Hosts
            hostsToSave = []
            switchesToSave = []
            for widget in self.widgetToItem:
                name = widget[ 'text' ]
                tags = self.canvas.gettags( self.widgetToItem[ widget ] )
                x1, y1 = self.canvas.coords( self.widgetToItem[ widget ] )
                nodeNum = int( name[ 1: ] )
                if 'Switch' in tags:
                    nodeToSave = {'number':str(nodeNum),
                                  'x':str(x1),
                                  'y':str(y1),
                                  'opts':self.switchOpts[name] }
                    switchesToSave.append(nodeToSave)
                elif 'Host' in tags:
                    nodeToSave = {'number':str(nodeNum),
                                  'x':str(x1),
                                  'y':str(y1),
                                  'opts':self.hostOpts[name] }
                    hostsToSave.append(nodeToSave)
                else:
                    raise Exception( "Cannot create mystery node: " + name )
            savingDictionary['hosts'] = hostsToSave
            savingDictionary['switches'] = switchesToSave

            # Save Links
            linksToSave = []
            for link in self.links.values():
                src = link['src']
                dst = link['dest']
                linkopts = link['linkOpts']

                srcName, dstName = src[ 'text' ], dst[ 'text' ]
                linkToSave = {'src':srcName,
                              'dest':dstName,
                              'opts':linkopts}
                linksToSave.append(linkToSave)
            savingDictionary['links'] = linksToSave

            # Save Controller
            savingDictionary['controllers'] = self.controllers

            # Save Application preferences
            savingDictionary['application'] = {'ipBase':self.minieditIpBase}

            try:
                f = open(fileName, 'wb')
                #f.write(str(savingDictionary))
                f.write(json.dumps(savingDictionary, sort_keys=True, indent=4, separators=(',', ': ')))
            except Exception as er:
                print er
            finally:
                f.close()

    def exportTopology( self ):
        "Export command."
        myFormats = [
            ('Mininet Custom Topology','*.py'),
            ('All Files','*'),
        ]

        fileName = tkFileDialog.asksaveasfilename(filetypes=myFormats ,title="Export the topology as...")
        if len(fileName ) > 0:
            #print "Now saving under %s" % fileName
            f = open(fileName, 'wb')

            f.write("#!/usr/bin/python\n")
            f.write("\n")
            f.write("from mininet.net import Mininet\n")
            f.write("from mininet.node import Controller, RemoteController, OVSController\n")
            f.write("from mininet.node import CPULimitedHost, Host\n")
            f.write("from mininet.cli import CLI\n")
            f.write("from mininet.log import setLogLevel, info\n")
            f.write("from mininet.link import TCLink, Intf\n")

            f.write("\n")
            f.write("def myNetwork():\n")
            f.write("\n")
            f.write("    net = Mininet( topo=None,\n")
            f.write("                   build=False,\n")
            f.write("                   link=TCLink)\n")

            f.write("\n")


            f.write("    info( '*** Adding controller\\n' )\n")
            controllerType = self.controllers['c0']['controllerType']

            if controllerType == 'remote':
                controllerIP = self.controllers['c0']['remoteIP']
                controllerPort = self.controllers['c0']['remotePort']
                f.write("    net.addController(name='c0',\n")
                f.write("                      controller=RemoteController,\n")
                f.write("                      ip='"+controllerIP+"',\n")
                f.write("                      port="+str(controllerPort)+")\n")
            elif controllerType == 'ovsc':
                f.write("    net.addController(name='c0', controller=OVSController)\n")
            else:
                f.write("    net.addController(name='c0', controller=Controller)\n")
            f.write("\n")

            # Save Switches and Hosts
            f.write("    info( '*** Add switches\\n')\n")
            for widget in self.widgetToItem:
                name = widget[ 'text' ]
                tags = self.canvas.gettags( self.widgetToItem[ widget ] )
                nodeNum = int( name[ 1: ] )
                if 'Switch' in tags:
                    f.write("    "+name+" = net.addSwitch('"+name+"')\n")
                    opts = self.switchOpts[name]
                    if ('externalInterfaces' in opts):
                        for extInterface in opts['externalInterfaces']:
                            f.write("    Intf( '"+extInterface+"', node="+name+" )\n")
                elif not 'Host' in tags:
                    raise Exception( "Cannot create mystery node: " + name )

            f.write("\n")
            f.write("    info( '*** Add hosts\\n')\n")
            for widget in self.widgetToItem:
                name = widget[ 'text' ]
                tags = self.canvas.gettags( self.widgetToItem[ widget ] )
                nodeNum = int( name[ 1: ] )
                if 'Host' in tags:
                    opts = self.hostOpts[name]
                    if 'cores' in opts or 'cpu' in opts:
                        f.write("    "+name+" = net.addHost('"+name+"', cls=CPULimitedHost)\n")
                        if 'cores' in opts:
                            f.write("    "+name+".setCPUs(cores='"+opts['cores']+"')\n")
                        if 'cpu' in opts:
                            f.write("    "+name+".setCPUFrac(f="+str(opts['cpu'])+", sched='"+opts['sched']+"')\n")
                    else:
                        f.write("    "+name+" = net.addHost('"+name+"', cls=Host)\n")
                    if ('externalInterfaces' in opts):
                        for extInterface in opts['externalInterfaces']:
                            f.write("    Intf( '"+extInterface+"', node="+name+" )\n")
                elif not 'Switch' in tags:
                    raise Exception( "Cannot create mystery node: " + name )
            f.write("\n")

            # Save Links
            f.write("    info( '*** Add links\\n')\n")
            for linkDetail in self.links.values():
                optsExist = False
                src = linkDetail['src']
                dst = linkDetail['dest']
                linkopts = linkDetail['linkOpts']
                srcName, dstName = src[ 'text' ], dst[ 'text' ]
                bw = ''
                delay = ''
                loss = ''
                max_queue_size = ''
                linkOpts = "{"
                if 'bw' in linkopts:
                    bw =  linkopts['bw']
                    linkOpts = linkOpts + "'bw':"+str(bw)
                    optsExist = True
                if 'delay' in linkopts:
                    delay =  linkopts['delay']
                    if optsExist:
                        linkOpts = linkOpts + ","
                    linkOpts = linkOpts + "'delay':'"+delay+"'"
                    optsExist = True
                if 'loss' in linkopts:
                    loss =  linkopts['loss']
                    if optsExist:
                        linkOpts = linkOpts + ","
                    linkOpts = linkOpts + "'loss':"+str(loss)
                    optsExist = True
                if 'max_queue_size' in linkopts:
                    max_queue_size =  linkopts['max_queue_size']
                    if optsExist:
                        linkOpts = linkOpts + ","
                    linkOpts = linkOpts + "'max_queue_size':"+str(max_queue_size)
                    optsExist = True
                linkOpts = linkOpts + "}"
                if optsExist:
                    f.write("    "+srcName+dstName+" = "+linkOpts+"\n")
                f.write("    net.addLink("+srcName+", "+dstName)
                if optsExist:
                    f.write(", **"+srcName+dstName)
                f.write(")\n")

            f.write("\n")
            f.write("    info( '*** Starting network\\n')\n")
            f.write("    net.interact()\n")
            f.write("\n")
            f.write("if __name__ == '__main__':\n")
            f.write("    setLogLevel( 'info' )\n")
            f.write("    myNetwork()\n")
            f.write("\n")


            f.close()


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
        if self.buttons[ 'Select' ][ 'state' ] == 'disabled':
            return
        # Delete from model
        if item in self.links:
            self.deleteLink( item )
        if item in self.itemToWidget:
            self.deleteNode( item )
        # Delete from view
        self.canvas.delete( item )

    def deleteSelection( self, _event ):
        "Delete the selected item."
        if self.selection is not None:
            self.deleteItem( self.selection )
        self.selectItem( None )

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
        name = self.nodePrefixes[ node ]
        if 'Switch' == node:
            self.switchCount += 1
            name = self.nodePrefixes[ node ] + str( self.switchCount )
        if 'Host' == node:
            self.hostCount += 1
            name = self.nodePrefixes[ node ] + str( self.hostCount )

        icon = self.nodeIcon( node, name )
        item = self.canvas.create_window( x, y, anchor='c', window=icon,
                                          tags=node )
        self.widgetToItem[ icon ] = item
        self.itemToWidget[ item ] = icon
        self.selectItem( item )
        icon.links = {}
        if 'Switch' == node:
            icon.bind('<Button-3>', self.do_switchPopup )
            self.switchOpts[name] = {}
        if 'Host' == node:
            icon.bind('<Button-3>', self.do_hostPopup )
            self.hostOpts[name] = {'sched':'host'}

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

    def releaseLink( self, _event ):
        "Give up on the current link."
        if self.link is not None:
            self.canvas.delete( self.link )
        self.linkWidget = self.linkItem = self.link = None

    # Generic node handlers

    def createNodeBindings( self ):
        "Create a set of bindings for nodes."
        bindings = {
            '<ButtonPress-1>': self.clickNode,
            '<B1-Motion>': self.dragNode,
            '<ButtonRelease-1>': self.releaseNode,
            '<Enter>': self.enterNode,
            '<Leave>': self.leaveNode
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

    def leaveNode( self, _event ):
        "Restore old selection on exit."
        self.selectItem( self.lastSelection )

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

    def createLinkBindings( self ):
        "Create a set of bindings for nodes."
        # Link bindings
        # Selection still needs a bit of work overall
        # Callbacks ignore event

        def select( _event, link=self.link ):
            "Select item on mouse entry."
            self.selectItem( link )

        def highlight( _event, link=self.link ):
            "Highlight item on mouse entry."
            self.selectItem( link )
            self.canvas.itemconfig( link, fill='green' )

        def unhighlight( _event, link=self.link ):
            "Unhighlight item on mouse exit."
            self.canvas.itemconfig( link, fill='blue' )
            #self.selectItem( None )

        self.canvas.tag_bind( self.link, '<Enter>', highlight )
        self.canvas.tag_bind( self.link, '<Leave>', unhighlight )
        self.canvas.tag_bind( self.link, '<ButtonPress-1>', select )
        self.canvas.tag_bind( self.link, '<Button-3>', self.do_linkPopup )


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

        self.createLinkBindings()

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

    def checkIntf( self, intf ):
        "Make sure intf exists and is not configured."
        if ( ' %s:' % intf ) not in quietRun( 'ip link show' ):
            showerror(title="Error",
                      message='External interface ' +intf + ' does not exist! Skipping.')
            return False
        ips = re.findall( r'\d+\.\d+\.\d+\.\d+', quietRun( 'ifconfig ' + intf ) )
        if ips:
            showerror(title="Error",
                      message= intf + ' has an IP address and is probably in use! Skipping.' )
            return False
        return True

    def hostDetails( self, _ignore=None ):
        if ( self.selection is None or
             self.net is not None or
             self.selection not in self.itemToWidget ):
            return
        name = self.itemToWidget[ self.selection ][ 'text' ]
        tags = self.canvas.gettags( self.selection )
        if 'Host' not in tags:
            return

        prefDefaults = self.hostOpts[name]
        hostBox = HostDialog(self, title='Host Details', prefDefaults=prefDefaults)
        self.master.wait_window(hostBox.top)
        if hostBox.result:
            newHostOpts = {}
            newHostOpts['sched'] = hostBox.result['sched']
            if len(hostBox.result['cpu']) > 0:
                newHostOpts['cpu'] = float(hostBox.result['cpu'])
            if len(hostBox.result['cores']) > 0:
                newHostOpts['cores'] = hostBox.result['cores']
            if len(hostBox.result['externalInterfaces']) > 0:
                newHostOpts['externalInterfaces'] = hostBox.result['externalInterfaces']
            self.hostOpts[name] = newHostOpts
            print 'New host details for ' + name + ' = ' + str(newHostOpts)

    def switchDetails( self, _ignore=None ):
        if ( self.selection is None or
             self.net is not None or
             self.selection not in self.itemToWidget ):
            return
        name = self.itemToWidget[ self.selection ][ 'text' ]
        tags = self.canvas.gettags( self.selection )
        if 'Switch' not in tags:
            return

        prefDefaults = self.switchOpts[name]
        switchBox = SwitchDialog(self, title='Switch Details', prefDefaults=prefDefaults)
        self.master.wait_window(switchBox.top)
        if switchBox.result:
            newSwitchOpts = {}
            if len(switchBox.result['externalInterfaces']) > 0:
                newSwitchOpts['externalInterfaces'] = switchBox.result['externalInterfaces']
            self.switchOpts[name] = newSwitchOpts
            print 'New switch details for ' + name + ' = ' + str(newSwitchOpts)

    def linkDetails( self, _ignore=None ):
        if ( self.selection is None or
             self.net is not None):
            return
        link = self.selection

        linkDetail =  self.links[link]
        src = linkDetail['src']
        dest = linkDetail['dest']
        linkopts = linkDetail['linkOpts']
        linkBox = LinkDialog(self, title='Link Details', linkDefaults=linkopts)
        if linkBox.result:
            #print 'Link is '
            #print '  BW=' + linkBox.result[0]
            #print '  BW length =' + str(len(linkBox.result[0]))
            newLinkOpts = {}
            if len(linkBox.result[0]) > 0:
                newLinkOpts['bw'] = int(linkBox.result[0])
            #print '  Delay=' + linkBox.result[1]
            #print '  Delay length =' + str(len(linkBox.result[1]))
            if len(linkBox.result[1]) > 0:
                newLinkOpts['delay'] = linkBox.result[1]
            if len(linkBox.result[2]) > 0:
                newLinkOpts['loss'] = int(linkBox.result[2])
            if len(linkBox.result[3]) > 0:
                newLinkOpts['max_queue_size'] = int(linkBox.result[3])
            linkDetail['linkOpts'] = newLinkOpts
            print 'New link details = ' + str(newLinkOpts)

    def prefDetails( self ):
        prefDefaults = {'ipBase':self.minieditIpBase, 'terminalType':self.defaultTerminal}
        prefBox = PrefsDialog(self, title='Preferences', prefDefaults=prefDefaults)
        if prefBox.result:
            self.minieditIpBase = prefBox.result[0]
            self.defaultTerminal = prefBox.result[1]


    def controllerDetails( self ):
        ctrlrBox = ControllerDialog(self, title='Controller Details', ctrlrDefaults=self.controllers['c0'])
        if ctrlrBox.result:
            #print 'Controller is ' + ctrlrBox.result[0]
            selectedController = 'c0'
            self.controllers[selectedController]['controllerType'] = ctrlrBox.result[0]
            if ctrlrBox.result[0] == 'remote':
                self.controllers[selectedController]['remoteIP'] = ctrlrBox.result[1]
                self.controllers[selectedController]['remotePort'] = ctrlrBox.result[2]
            print 'New controller details for ' + selectedController + ' = ' + str(self.controllers[selectedController])

    def listBridge( self, _ignore=None ):
        if ( self.selection is None or
             self.net is None or
             self.selection not in self.itemToWidget ):
            return
        name = self.itemToWidget[ self.selection ][ 'text' ]
        tags = self.canvas.gettags( self.selection )

        if name not in self.net.nameToNode:
            return
        if 'Switch' in tags:
           call(["xterm -T 'Bridge Details' -sb -sl 2000 -e 'ovs-vsctl list bridge " + name + "; read -p \"Press Enter to close\"' &"], shell=True)

    def ovsShow( self, _ignore=None ):
        call(["xterm -T 'OVS Summary' -sb -sl 2000 -e 'ovs-vsctl show; read -p \"Press Enter to close\"' &"], shell=True)

    def rootTerminal( self, _ignore=None ):
        call(["xterm -T 'Root Terminal' -sb -sl 2000 &"], shell=True)

    # Model interface
    #
    # Ultimately we will either want to use a topo or
    # mininet object here, probably.

    def addLink( self, source, dest, linkopts={} ):
        "Add link to model."
        source.links[ dest ] = self.link
        dest.links[ source ] = self.link
        self.links[ self.link ] = {'src':source, 'dest':dest, 'linkOpts':linkopts}

    def deleteLink( self, link ):
        "Delete link from model."
        pair = self.links.get( link, None )
        if pair is not None:
            source=pair['src']
            dest=pair['dest']
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

    def buildControllers( self, net):
        "Add Controllers"

        # Get controller info from panel
        controllerType = self.controllers['c0']['controllerType']

        c0 = None

        # Make controller
        print 'Getting controller selection:'
        if controllerType == 'remote':
            controllerIP = self.controllers['c0']['remoteIP']
            controllerPort = self.controllers['c0']['remotePort']
            net.addController(name='c0',
                              controller=RemoteController,
                              ip=controllerIP,
                              port=controllerPort)
        elif controllerType == 'ovsc':
            net.addController(name='c0',
                              controller=OVSController)
        else:
            net.addController(name='c0',
                              controller=Controller)


    def buildNodes( self, net):
        # Make nodes
        print "Getting Hosts and Switches."
        for widget in self.widgetToItem:
            name = widget[ 'text' ]
            tags = self.canvas.gettags( self.widgetToItem[ widget ] )
            nodeNum = int( name[ 1: ] )

            if 'Switch' in tags:
                opts = self.switchOpts[name]

                # Create the correct switch class
                newSwitch = net.addSwitch( name , cls=OVSSwitch)

                # Attach external interfaces
                if ('externalInterfaces' in opts):
                    for extInterface in opts['externalInterfaces']:
                        if self.checkIntf(extInterface):
                           Intf( extInterface, node=newSwitch )

            elif 'Host' in tags:
                ipBaseNum, prefixLen = netParse( self.minieditIpBase )
                ip = ipAdd(i=nodeNum, prefixLen=prefixLen, ipBaseNum=ipBaseNum)
                opts = self.hostOpts[name]

                # Create the correct host class
                hostClass=Host
                if 'cores' in opts or 'cpu' in opts:
                    hostClass=CPULimitedHost
                newHost = net.addHost( name, cls=hostClass, ip=ip )

                # Set the CPULimitedHost specific options
                if 'cores' in opts:
                    newHost.setCPUs(cores = opts['cores'])
                if 'cpu' in opts:
                    newHost.setCPUFrac(f=opts['cpu'], sched=opts['sched'])

                # Attach external interfaces
                if ('externalInterfaces' in opts):
                    for extInterface in opts['externalInterfaces']:
                        if self.checkIntf(extInterface):
                           Intf( extInterface, node=newHost )
            else:
                raise Exception( "Cannot create mystery node: " + name )

    def buildLinks( self, net):
        # Make links
        print "Getting Links."
        for link in self.links.values():
            src=link['src']
            dst=link['dest']
            linkopts=link['linkOpts']
            srcName, dstName = src[ 'text' ], dst[ 'text' ]
            src, dst = net.nameToNode[ srcName ], net.nameToNode[ dstName ]
            net.addLink(src, dst, **linkopts)

    def build( self ):
        print "Build network based on our topology."

        net = Mininet( topo=None,
                       build=False,
                       link=TCLink,
                       ipBase=self.minieditIpBase )

        self.buildControllers(net)
        self.buildNodes(net)
        self.buildLinks(net)

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

    def do_linkPopup(self, event):
        # display the popup menu
        try:
            self.linkPopup.tk_popup(event.x_root, event.y_root, 0)
        finally:
            # make sure to release the grab (Tk 8.0a1 only)
            self.linkPopup.grab_release()

    def do_hostPopup(self, event):
        # display the popup menu
        try:
            self.hostPopup.tk_popup(event.x_root, event.y_root, 0)
        finally:
            # make sure to release the grab (Tk 8.0a1 only)
            self.hostPopup.grab_release()

    def do_switchPopup(self, event):
        # display the popup menu
        try:
            self.switchPopup.tk_popup(event.x_root, event.y_root, 0)
        finally:
            # make sure to release the grab (Tk 8.0a1 only)
            self.switchPopup.grab_release()

    def xterm( self, _ignore=None ):
        "Make an xterm when a button is pressed."
        if ( self.selection is None or
             self.net is None or
             self.selection not in self.itemToWidget ):
            return
        name = self.itemToWidget[ self.selection ][ 'text' ]
        if name not in self.net.nameToNode:
            return
        term = makeTerm( self.net.nameToNode[ name ], 'Host', term=self.defaultTerminal )
        self.net.terms += term 

    def iperf( self, _ignore=None ):
        "Make an xterm when a button is pressed."
        if ( self.selection is None or
             self.net is None or
             self.selection not in self.itemToWidget ):
            return
        name = self.itemToWidget[ self.selection ][ 'text' ]
        if name not in self.net.nameToNode:
            return
        self.net.nameToNode[ name ].cmd( 'iperf -s -p 5001 &' )

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

def addDictOption( opts, choicesDict, default, name, helpStr=None ):
    """Convenience function to add choices dicts to OptionParser.
       opts: OptionParser instance
       choicesDict: dictionary of valid choices, must include default
       default: default choice key
       name: long option name
       help: string"""
    if default not in choicesDict:
        raise Exception( 'Invalid  default %s for choices dict: %s' %
                         ( default, name ) )
    if not helpStr:
        helpStr = ( '|'.join( sorted( choicesDict.keys() ) ) +
                    '[,param=value...]' )
    opts.add_option( '--' + name,
                     type='string',
                     default = default,
                     help = helpStr )

if __name__ == '__main__':
    setLogLevel( 'info' )
    app = MiniEdit()
    app.mainloop()
