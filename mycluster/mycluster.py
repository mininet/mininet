from mininet.topo import Topo


class MyCLusterTopo(Topo):
    def build(self):
        # HOSTS
        # vm1
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        # vm2
        h11 = self.addHost('h11')
        h12 = self.addHost('h12')

        # Switches
        # vm1
        s3 = self.addSwitch('s3')
        s4 = self.addSwitch('s4')
        # vm2
        s13 = self.addSwitch('s13')
        s14 = self.addSwitch('s14')

        # Nodes
        # vm1
        ln5 = self.addSwitch('ln5')
        ln6 = self.addSwitch('ln6')
        sn7 = self.addSwitch('sn7')
        # vm2
        ln15 = self.addSwitch('ln15')
        ln16 = self.addSwitch('ln16')
        sn17 = self.addSwitch('sn17')

        # Links
        # vm1
        self.addLink(h1, s3)
        self.addLink(h2, s4)
        self.addLink(s3, ln5)
        self.addLink(s3, ln6)
        self.addLink(s4, ln6)
        self.addLink(s4, ln5)
        self.addLink(ln5, sn7)
        self.addLink(ln6, sn7)
        # vm2
        self.addLink(h11, s13)
        self.addLink(h12, s14)
        self.addLink(s13, ln15)
        self.addLink(s13, ln16)
        self.addLink(s14, ln16)
        self.addLink(s14, ln15)
        self.addLink(ln15, sn17)
        self.addLink(ln16, sn17)
        # vm1 - vm2
        self.addLink(ln5, sn17)
        self.addLink(ln6, sn17)
        self.addLink(ln15, sn7)
        self.addLink(ln16, sn7)


topos = { 'mycluster': ( lambda: MyCLusterTopo() ) }
