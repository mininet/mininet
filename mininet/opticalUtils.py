#!/usr/bin/python

'''
Notes:

This file contains classes and methods useful for integrating LincOE with Mininet, 
such as startOE, stopOE, LINCLink, and OpticalSwitch

- $ONOS_ROOT ust be set
- Need to run with sudo -E to preserve ONOS_ROOT env var
- We assume LINC-Config-Generator is named LINC-Config-Generator
- We also assume linc-oe is named linc-oe
- LINC-config-generator and linc-oe must be subdirectories of the user's
  home directory

            TODO
        -----------
    - clean up files after runtime
        - maybe save the old files in a separate directory?
    - modify script to allow startOE to run before net.start()
    - add ONOS as a controller in script

            Usage:
        ------------
    - import LINCLink and OpticalSwitch from this module
    - import startOE and stopOE from this module
    - create topology as you would a normal topology. when 
      to an optical switch with topo.addLink, always specify cls=LINCLink
    - when creating an optical switch, use cls=OpticalSwitch in topo.addSwitch
    - for annotations on links and switches, a dictionary must be passed in as
      the annotations argument
    - startOE must be run AFTER net.start() with net as an argument.
    - stopOE can be run at any time

I created a separate function to start lincOE to avoid subclassing Mininet.
In case anyone wants to write something that DOES subclass Mininet, I
thought I would outline how:

If we want an object that starts lincOE within the mininet class itself,
we need to add another object to Mininet that contains all of the json object
information for each switch. We would still subclass switch and link, but these
classes would basically be dummy classes that store their own json information
in the Mininet class object. We may also change the default switch class to add
it's tap interfaces from lincOE during startup. The start() method for mininet would 
grab all of the information from these switches and links, write configuration files
for lincOE using the json module, start lincOE, then run the start methodfor each
switch. The new start() method for each switch would parse through the sys.config
file that was created and find the tap interface it needs to connect to, similar 
to the findTap function that I currently use. After all of the controllers and 
switches have been started, the new Mininet start() method should also push the 
Topology configuration file to ONOS.

'''
import sys
import re
import json
import os
from time import sleep

from mininet.node import Switch, RemoteController
from mininet.topo import Topo
from mininet.util import quietRun
from mininet.net import Mininet
from mininet.log import  setLogLevel, info, error, warn
from mininet.link import Link, Intf
from mininet.cli import CLI

class OpticalSwitch(Switch):
    """
    For now, same as Switch class.
    """
    pass

class OpticalIntf(Intf):
    """
    For now,same as Intf class.
    """
    pass

class OpticalLink(Link):
    """
    For now, same as Link.
    """
    pass
        
class LINCSwitch(OpticalSwitch):
    """
    LINCSwitch class
    """
    # FIXME:Sometimes LINC doesn't remove pipes and on restart increase the pipe
    # number from erlang.pipe.1.* to erlang.pipe.2.*, so should read and write
    # from latest pipe files. For now we are removing all the pipes before
    # starting LINC.
    ### User Name ###
    user = os.getlogin()
    ### pipes ###
    readPipe = "/tmp/home/{}/linc-oe/rel/linc/erlang.pipe.1.r".format(user)
    writePipe = "/tmp/home/{}/linc-oe/rel/linc/erlang.pipe.1.w".format(user)
    ### sys.config path ###
    sysConfig = "/home/{}/linc-oe/rel/linc/releases/1.0/sys.config".format(user)
    @staticmethod
    def findDir(directory, userName):
        "finds and returns the path of any directory in the user's home directory"
        homeDir = '/home/' + userName
        Dir = quietRun('find %s -maxdepth 1 -name %s -type d' % (homeDir, directory)).strip('\n')
        DirList = Dir.split('\n')
        if not Dir:
            return None
        elif len(DirList) > 1 :
            warn('***WARNING: Found multiple instances of %s; using %s\n'
                     % (directory, DirList[ 0 ]))
            return DirList[ 0 ]
        else:
            return Dir
    ### ONOS Directory ###
    try:
        onosDir = os.environ[ 'ONOS_ROOT' ]
    except:
        onosDir = findDir('onos', user)
        if not onosDir:
            error('Please set ONOS_ROOT environment variable!\n')
        else:
            os.environ[ 'ONOS_ROOT' ] = onosDir
    ### LINC-directory
    lincDir = findDir.__func__('linc-oe', user)
    if not lincDir:
        error("***ERROR: Could not find linc-oe in user's home directory\n")
    ### LINC config generator directory###
    configGen = findDir.__func__('LINC-config-generator', user)
    if not configGen:
        error("***ERROR: Could not find LINC-config-generator in user's home directory\n")
    # list of all the controllers
    controllers = None
    def __init__(self, name, dpid=None, allowed=True,
                  switchType='ROADM', topo=None, annotations={}, controller=None, **params):
        params[ 'inNamespace' ] = False
        Switch.__init__(self, name, dpid=dpid, **params)
        self.name = name
        self.annotations = annotations
        self.allowed = allowed
        self.switchType = switchType
        self.configDict = {}  # dictionary that holds all of the JSON configuration data
        self.crossConnects = []
        self.deletedCrossConnects = []
        self.controller = controller
        self.lincId = self._get_linc_id()  # use to communicate with LINC
        self.lincStarted = False

    def start(self, *opts, **params):
        '''Instead of starting a virtual switch, we build the JSON
           dictionary for the emulated optical switch'''
        # TODO:Once LINC has the ability to spawn network element dynamically
        # we need to use this method to spawn new logical LINC switch rather then
        # bulding JSON.
        # if LINC is started then we can start and stop logical switches else create JSON
        if self.lincStarted:
            return self.start_oe()
        self.configDict[ 'uri' ] = 'of:' + self.dpid
        self.configDict[ 'annotations' ] = self.annotations
        self.configDict[ 'annotations' ].setdefault('name', self.name)
        self.configDict[ 'hw' ] = 'LINC-OE'
        self.configDict[ 'mfr' ] = 'Linc'
        self.configDict[ 'mac' ] = 'ffffffffffff' + self.dpid[-2] + self.dpid[-1]
        self.configDict[ 'type' ] = self.switchType
        self.configDict[ 'ports' ] = []
        for port, intf in self.intfs.items():
            if intf.name == 'lo':
                continue
            else:
                self.configDict[ 'ports' ].append(intf.json())
        self.lincStarted = True

    def stop(self, deleteIntfs=False):
        '''
        stop the existing switch
        '''
        # TODO:Add support for deleteIntf
        self.stop_oe()

    def dpctl( self, *args ):
        "Run dpctl command: ignore for now"
        pass

    def write_to_cli(self, command):
        '''
        send command to LINC
        '''
        fd = None
        try:
            fd = open(self.writePipe, 'w', 0)
            fd.write(command)
            fd.close()
        except:
            print "Error working with {}\nError: {}\n".format(self.writePipe, sys.exc_info())
            if fd:
                fd.close()

    def read_from_cli(self):
        '''
        read the output from the LINC CLI
        '''
        response = None
        fd = None
        try:
            fd = open(self.readPipe, 'r', 0)
            fcntl.fcntl(fd, fcntl.F_SETFL, os.O_NONBLOCK)  # for non-blocking read
            # FIXME:Due to non-blocking read most for the time we read nothing
            response = fd.read()
            fd.close()
        except :
            # print "Error working with {}\nError: {}\n".format(self.readPipe, sys.exc_info())
            if fd:
                fd.close()
        return response

    def _dpids_to_ids(self):
        '''
        return the dict containing switch dpids as key and LINC switch id as values
        '''
        dpids_to_ids = {}
        fd = None
        try:
            fd = open(self.sysConfig, 'r', 0)
            switch_id = 1
            while True:
                sys_data = fd.readline()
                if not sys_data:
                    break
                dpid = re.search(r'([0-9A-Fa-f]{2}[:-]){7}([0-9A-Fa-f]{2})+', sys_data, re.I)
                if dpid:
                    dpids_to_ids[dpid.group().replace(':', '')] = switch_id
                    switch_id += 1
            fd.close()
            return dpids_to_ids     
        except:
            print "Error working with {}\nError: {}\n".format(sysConfig, sys.exc_info())
            fd.close()
            return None

    def _get_linc_id(self):
        '''
        retrun the LINC switchId.
        '''
        mmap = self._dpids_to_ids()
        if not mmap:
            return None
        else:
            return mmap.get(self.dpid)

    def start_oe(self):
        '''
        start the existing LINC switch
        '''
        #starting Switch
        cmd = "linc:start_switch({}).\r\n".format(self.lincId)
        self.write_to_cli(cmd)
        #hanlding taps interfaces related to the switch
        crossConnectJSON = {}
        linkConfig = []
        for i in range(0,len(self.deletedCrossConnects)):
            crossConnect = self.deletedCrossConnects.pop()
            tap = None
            if isinstance(crossConnect.intf1.node, LINCSwitch):
                intf = crossConnect.intf2
                tapPort = crossConnect.intf1.port
            else:
                intf = crossConnect.intf1
                tapPort = crossConnect.intf2.port
            tap = LINCSwitch.findTap(self, tapPort)
            if tap:
                LINCSwitch.setupInts([tap])
                intf.node.attach(tap)
            self.crossConnects.append(crossConnect)
            linkConfig.append(crossConnect.json())
        #Sending crossConnect info to the ONOS.
        crossConnectJSON['links'] = linkConfig
        with open("crossConnect.json", 'w') as fd:
            json.dump(crossConnectJSON, fd, indent=4, separators=(',', ': '))
        info('*** Pushing crossConnect.json to ONOS\n')
        output = quietRun('%s/tools/test/bin/onos-topo-cfg %s Topology.json' % (self.onosDir, self.controllers[ 0 ].ip), shell=True)
    #--------------------------------------------------------------------------
    # LINC CLI commands
    #-------------------------------------------------------------------------- 
    def stop_oe(self):
        '''
        stop the existing LINC switch
        '''
        cmd = "linc:stop_switch({}).\r\n".format(self.lincId)
        self.write_to_cli(cmd)
        #handling taps if any
        for i in range(0, len(self.crossConnects)):
            crossConnect = self.crossConnects.pop()
            if isinstance(crossConnect.intf1.node, LINCSwitch):
                intf = crossConnect.intf2
                tapPort = crossConnect.intf1.port
            else:
                intf = crossConnect.intf1
                tapPort = crossConnect.intf2.port
            intf.node.detach(LINCSwitch.findTap(self, tapPort))
            self.deletedCrossConnects.append(crossConnect)

    def w_port_up(self, port):
        '''
        port_up
        '''
        cmd = "linc:port_up({},{}).\r\n".format(self.lincId, port)
        self.write_to_cli(cmd)

    def w_port_down(self, port):
        '''
        port_down
        '''
        cmd = "linc:port_down({},{}).\r\n".format(self.lincId, port)
        self.write_to_cli(cmd)

    # helper functions
    @staticmethod
    def switchJSON(switch):
        "Returns the json configuration for a packet switch"
        configDict = {}
        configDict[ 'uri' ] = 'of:' + switch.dpid
        configDict[ 'mac' ] = quietRun('cat /sys/class/net/%s/address' % switch.name).strip('\n').translate(None, ':')
        configDict[ 'hw' ] = 'PK'  # FIXME what about OVS?
        configDict[ 'mfr' ] = 'Linc'  # FIXME what about OVS?
        configDict[ 'type' ] = 'SWITCH'  # FIXME what about OVS?
        annotations = switch.params.get('annotations', {})
        annotations.setdefault('name', switch.name)
        configDict[ 'annotations' ] = annotations
        ports = []
        for port, intf in switch.intfs.items():
            if intf.name == 'lo':
                continue
            portDict = {}
            portDict[ 'port' ] = port
            portDict[ 'type' ] = 'FIBER' if isinstance(intf.link, LINCLink) else 'COPPER'
            intfList = [ intf.link.intf1, intf.link.intf2 ]
            intfList.remove(intf)
            portDict[ 'speed' ] = intfList[ 0 ].speed if isinstance(intf.link, LINCLink) else 0
            ports.append(portDict)
        configDict[ 'ports' ] = ports
        return configDict

    @staticmethod
    def bootOE(net):
        "Start the LINC optical emulator within a mininet instance"
        opticalJSON = {}
        linkConfig = []
        devices = []
        #setting up the controllers for LINCSwitch class
        LINCSwitch.controllers = net.controllers

        for switch in net.switches:
            if isinstance(switch, OpticalSwitch):
                devices.append(switch.json())
            else:
                devices.append(LINCSwitch.switchJSON(switch))
        opticalJSON[ 'devices' ] = devices

        for link in net.links:
            if isinstance(link, LINCLink) :
                linkConfig.append(link.json())
        opticalJSON[ 'links' ] = linkConfig

        info('*** Writing Topology.json file\n')
        with open('Topology.json', 'w') as outfile:
            json.dump(opticalJSON, outfile, indent=4, separators=(',', ': '))

        info('*** Converting Topology.json to linc-oe format (TopoConfig.json) file\n')
        output = quietRun('%s/tools/test/bin/onos-oecfg ./Topology.json > TopoConfig.json' % LINCSwitch.onosDir, shell=True)
        if output:
            error('***ERROR: Error creating topology file: %s ' % output + '\n')
            return False

        info('*** Creating sys.config...\n')
        output = quietRun('%s/config_generator TopoConfig.json %s/sys.config.template %s %s'
                        % (LINCSwitch.configGen, LINCSwitch.configGen, LINCSwitch.controllers[ 0 ].ip, LINCSwitch.controllers[ 0 ].port), shell=True)
        if output:
            error('***ERROR: Error creating sys.config file: %s\n' % output)
            return False

        info ('*** Setting multiple controllers in sys.config...\n')
        searchStr = '\[{"Switch.*$'
        ctrlStr = ''
        for index in range(len(LINCSwitch.controllers)):
            ctrlStr += '{"Switch%d-Controller","%s",%d,tcp},' % (index, net.controllers[index].ip, net.controllers[index].port)
        replaceStr = '[%s]},' % ctrlStr[:-1]  # Cut off last comma
        sedCmd = 'sed -i \'s/%s/%s/\' sys.config' % (searchStr, replaceStr)
        output = quietRun(sedCmd, shell=True)

        info('*** Copying sys.config to linc-oe directory: ', output + '\n')
        output = quietRun('cp -v sys.config %s/rel/linc/releases/1.0/' % LINCSwitch.lincDir, shell=True).strip('\n')
        info(output + '\n')

        info('*** Adding taps and bringing them up...\n')
        LINCSwitch.setupInts(LINCSwitch.getTaps())

        info('*** removing pipes if any \n')
        quietRun('rm /tmp/home/%s/linc-oe/rel/linc/*' % LINCSwitch.user, shell=True)

        info('*** Starting linc OE...\n')
        output = quietRun('%s/rel/linc/bin/linc start' % LINCSwitch.lincDir, shell=True)
        if output:
            error('***ERROR: LINC-OE: %s' % output + '\n')
            quietRun('%s/rel/linc/bin/linc stop' % LINCSwitch.lincDir, shell=True)
            return False

        info('*** Waiting for linc-oe to start...\n')
        LINCSwitch.waitStarted(net)

        info('*** Adding cross-connect (tap) interfaces to packet switches...\n')
        for link in net.links:
            if isinstance(link, LINCLink):
                if link.annotations[ 'optical.type' ] == 'cross-connect':
                    for intf in [ link.intf1, link.intf2 ]:
                        if not isinstance(intf, LINCIntf):
                            intfList = [ intf.link.intf1, intf.link.intf2 ]
                            intfList.remove(intf)
                            intf2 = intfList[ 0 ]
                            intf.node.attach(LINCSwitch.findTap(intf2.node, intf2.node.ports[ intf2 ]))

        info('*** Press ENTER to push Topology.json to onos...\n')
        raw_input()  # FIXME... we should eventually remove this
        info('*** Pushing Topology.json to ONOS\n')
        output = quietRun('%s/tools/test/bin/onos-topo-cfg %s Topology.json' % (LINCSwitch.onosDir, LINCSwitch.controllers[ 0 ].ip), shell=True)
        # successful output contains the two characters '{}'
        # if there is more output than this, there is an issue
        if output.strip('{}'):
            warn('***WARNING: Could not push topology file to ONOS: %s' % output)

    @staticmethod
    def waitStarted(net, timeout=None):
        "wait until all tap interfaces are available"
        tapCount = 0
        time = 0
        for link in net.links:
            if isinstance(link, LINCLink):
                if link.annotations[ 'optical.type' ] == 'cross-connect':
                    tapCount += 1
        
        while True:
            if str(tapCount) == quietRun('ip addr | grep tap | wc -l', shell=True).strip('\n'):
                return True
            if timeout:
                if time >= timeout:
                    error('***ERROR: Linc OE did not start within %s seconds' % timeout)
                    return False
                time += .5
            sleep(.5)

    @staticmethod
    def shutdownOE():
        "stop the optical emulator"
        info('*** Stopping linc OE...\n')
        quietRun('%s/rel/linc/bin/linc stop' % LINCSwitch.lincDir, shell=True)

    @staticmethod
    def setupInts(intfs):
        '''
        add taps and bring them up.
        '''
        for i in intfs:
            quietRun('ip tuntap add dev %s mode tap' % i)
            quietRun('ip link set dev %s up' % i)
            info('*** Intf %s set\n' % i)

    @staticmethod
    def getTaps(path=None):
        '''
        return list of all the tops in sys.config
        '''
        if path is None:
            path = '%s/rel/linc/releases/1.0/sys.config' % LINCSwitch.lincDir
        fd = open(path, 'r', 0)
        sys_data = fd.read()
        taps = re.findall('tap\d+', sys_data)
        fd.close()
        return taps

    @staticmethod
    def findUser():
        "Try to return logged-in (usually non-root) user"
        try:
            # If we're running sudo
            return os.environ[ 'SUDO_USER' ]
        except:
            try:
                # Logged-in user (if we have a tty)
                return quietRun('who am i').split()[ 0 ]
            except:
                # Give up and return effective user
                return quietRun('whoami')


    @staticmethod
    def findTap(node, port, path=None):
        '''utility function to parse through a sys.config
           file to find tap interfaces for a switch'''
        switch = False
        portLine = ''
        intfLines = []

        if path is None:
            path = '%s/rel/linc/releases/1.0/sys.config' % LINCSwitch.lincDir

        with open(path) as f:
            for line in f:
                if 'tap' in line:
                    intfLines.append(line)
                if node.dpid in line.translate(None, ':'):
                    switch = True
                    continue
                if switch:
                    if 'switch' in line:
                        switch = False
                    if 'port_no,%s}' % port in line:
                        portLine = line
                        break 

        if portLine:
            m = re.search('port,\d+', portLine)
            port = m.group(0).split(',')[ 1 ]
        else:
            error('***ERROR: Could not find any ports in sys.config\n')
            return

        for intfLine in intfLines:
            if 'port,%s' % port in intfLine:
                return re.findall('tap\d+', intfLine)[ 0 ]

    def json(self):
        "return json configuration dictionary for switch"
        return self.configDict

    def terminate(self):
        pass

class LINCLink(Link):
    """
    LINC link class
    """
    def __init__(self, node1, node2, port1=None, port2=None, allowed=True,
                  intfName1=None, intfName2=None, linkType='OPTICAL',
                  annotations={}, speed1=0, speed2=0, **params):
        "Creates a dummy link without a virtual ethernet pair."
        self.allowed = allowed
        self.annotations = annotations
        self.linkType = linkType
        self.port1 = port1
        self.port2 = port2
        params1 = { 'speed': speed1 }
        params2 = { 'speed': speed2 }
        # self.isCrossConnect = True if self.annotations.get('optical.type') == 'cross-connect' else False
        if isinstance(node1, LINCSwitch) and isinstance(node2, LINCSwitch):
            self.isCrossConnect = False
        else:
            self.isCrossConnect = True
        if isinstance(node1, LINCSwitch):
            cls1 = LINCIntf
            if self.isCrossConnect:
                node1.crossConnects.append(self)
        else:
            cls1 = Intf
            # bad hack to stop error message from appearing when we try to set up intf in a packet switch, 
            # and there is no interface there( because we do not run makeIntfPair ). This way, we just set lo up
            intfName1 = 'lo'
        if isinstance(node2, LINCSwitch):
            cls2 = LINCIntf
            if self.isCrossConnect:
                node2.crossConnects.append(self)
        else:
            cls2 = Intf
            intfName2 = 'lo'
        Link.__init__(self, node1, node2, port1=port1, port2=port2,
                       intfName1=intfName1, intfName2=intfName2, cls1=cls1,
                       cls2=cls2, params1=params1, params2=params2)

    @classmethod
    def makeIntfPair(_cls, intfName1, intfName2, *args, **kwargs):
        pass

    def json(self):
        "build and return the json configuration dictionary for this link"
        configData = {}
        configData[ 'src' ] = ('of:' + self.intf1.node.dpid + 
                                '/%s' % self.intf1.node.ports[ self.intf1 ])
        configData[ 'dst' ] = ('of:' + self.intf2.node.dpid + 
                                '/%s' % self.intf2.node.ports[ self.intf2 ])
        configData[ 'type' ] = self.linkType
        configData[ 'annotations' ] = self.annotations
        return configData

class LINCIntf(OpticalIntf):
    """
    LINC interface class
    """
    def __init__(self, name=None, node=None, speed=0,
                  port=None, link=None, **params):
        self.node = node
        self.speed = speed
        self.port = port
        self.link = link
        self.name = name
        node.addIntf(self, port=port)
        self.params = params
        self.ip = None

    def json(self):
        "build and return the JSON information for this interface( not used right now )"
        configDict = {}
        configDict[ 'port' ] = self.port
        configDict[ 'speed' ] = self.speed
        configDict[ 'type' ] = 'FIBER'
        return configDict

    def config(self, *args, **kwargs):
        "dont configure a dummy interface"
        pass

    def ifconfig(self, status):
        "configure the status"
        if status == "up":
            return self.node.w_port_up(self.port)
        elif status == "down":
            return self.node.w_port_down(self.port)


class MininetOE(Mininet):
    "Mininet with Linc-OE support (starts and stops linc-oe)"

    def start(self):
        Mininet.start(self)
        LINCSwitch.bootOE(self)

    def stop(self):
        Mininet.stop(self)
        LINCSwitch.shutdownOE()

    def addControllers(self, controllers):
        i = 0
        for ctrl in controllers:
            self.addController(RemoteController('c%d' % i, ip=ctrl))


class OpticalTestTopo(Topo):

    def build(self):
        opticalAnn = { 'optical.waves': 80, 'optical.type': "WDM", 'durable': True }
        switchAnn = { 'bandwidth': 100000, 'optical.type': 'cross-connect', 'durable': True }
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        O4 = self.addSwitch('O4', cls=OpticalSwitch)
        O5 = self.addSwitch('O5', cls=OpticalSwitch)
        O6 = self.addSwitch('O6', cls=OpticalSwitch)
        self.addLink(O4, O5, cls=LINCLink, annotations=opticalAnn)
        self.addLink(O5, O6, cls=LINCLink, annotations=opticalAnn)
        self.addLink(s1, O4, cls=LINCLink, annotations=switchAnn)
        self.addLink(s2, O6, cls=LINCLink, annotations=switchAnn)
        self.addLink(h1, s1)
        self.addLink(h2, s2)

if __name__ == '__main__':
    # import sys
    # if len( sys.argv ) >= 2:
    #    controllers = sys.argv[1:]
    # else:
    #    print 'Usage: ./opticalUtils.py (<Controller IP>)+'
    #    print 'Using localhost...\n'
    #    controllers = [ '127.0.0.1' ]

    # setLogLevel( 'info' )
    # net = MininetOE( topo=OpticalTestTopo(), controller=None, autoSetMacs=True )
    # net.addControllers( controllers )
    # net.start()
    # CLI( net )
    # net.stop()
    pass
