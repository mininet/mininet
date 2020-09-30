import os
 
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.net import Mininet
from mininet.node import Node, Controller, CPULimitedHost

class LinuxRouter(Node):     # from the Mininet library
    "A Node with IP forwarding enabled."
    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        info ("Enabling forwarding on ", self)
        self.cmd("sysctl net.ipv4.ip_forward=1")

    def terminate(self):
        self.cmd("sysctl net.ipv4.ip_forward=0")
        super(LinuxRouter, self).terminate()

def Network():
    from mininet.link import TCLink, Intf
    info('*** Creating a network with no nodes or links\n')
    net = Mininet(host=CPULimitedHost, link=TCLink, autoStaticArp=False)

    info('*** Adding hosts\n')
    r1 = net.addHost('r1', cls=LinuxRouter)
    r2 = net.addHost('r2', cls=LinuxRouter)
    r3 = net.addHost('r3', cls=LinuxRouter)
    r4 = net.addHost('r4', cls=LinuxRouter)
    r5 = net.addHost('r5', cls=LinuxRouter)
    r6 = net.addHost('r6', cls=LinuxRouter)
    r7 = net.addHost('r7', cls=LinuxRouter)

    info('*** Creating links\n')
    net.addLink(r1, r2, intfName1="r1-i2", intfName2="r2-i1")
    net.addLink(r1, r3, intfName1="r1-i3", intfName2="r3-i1")
    net.addLink(r1, r5, intfName1="r1-i5", intfName2="r5-i1")
    net.addLink(r1, r6, intfName1="r1-i6", intfName2="r6-i1")
    net.addLink(r2, r3, intfName1="r2-i3", intfName2="r3-i2")
    net.addLink(r3, r4, intfName1="r3-i4", intfName2="r4-i3")
    net.addLink(r4, r7, intfName1="r4-i7", intfName2="r7-i4")
    net.addLink(r6, r7, intfName1="r6-i7", intfName2="r7-i6")

    info('*** Starting network\n')
    net.start()

    info('*** Configuring interface IPs\n')
    for router in net.hosts:
        """Each link between 2 routers is in a 172.16.xy.z/24 subnet, where
            x = lower ID of the 2 routers
            y = higher ID of the 2 routers
            z = local router id
        """
        for idx, r_intf in router.intfs.items():
            local_id, peer_id = map(lambda x: x[-1], r_intf.name[1:].split("-"))
            if local_id < peer_id:
		a = "172.16.{}{}.{}/24".format(local_id, peer_id, local_id)
		print(a)
                router.setIP("172.16.{}{}.{}/24".format(local_id, peer_id, local_id), intf=r_intf)
            else:
                router.setIP("172.16.{}{}.{}/24".format(peer_id, local_id, local_id), intf=r_intf)

    info('*** Running CLI\n')
    CLI(net)

    info('*** Stopping network\n')
    net.stop()

if __name__ == '__main__':
    os.system("sudo mn -c") # Clear out the remnants of failed runs (if they exist).
    setLogLevel( 'info' )
    Network()
