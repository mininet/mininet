
    Mininet: A Simple Virtual Testbed for OpenFlow/SDN
                        or
    How to Squeeze an OpenFlow Network onto your Laptop

Mininet 2.0.0d3

---
**Welcome to Mininet!**

Mininet creates OpenFlow test networks by using process-based
virtualization and network namespaces.

Simulated hosts (as well as switches and controllers with the user
datapath) are created as processes in separate network namespaces. This
allows a complete OpenFlow network to be simulated on top of a single
Linux kernel.

Mininet may be invoked directly from the command line, and also provides a
handy Python API for creating networks of varying sizes and topologies.

In order to run Mininet, you must have:

* A Linux kernel compiled with network namespace support
  enabled (see `INSTALL` for additional information.)

* An OpenFlow implementation (either the reference user or kernel
  space implementations, or Open vSwitch.) Appropriate kernel modules
  (e.g. tun and ofdatapath for the reference kernel implementation) must
  be loaded.

* Python, `bash`, `ping`, `iperf`, etc.

* Root privileges (required for network device access)

Currently Mininet includes:

- A simple node infrastructure (`Host`, `Switch`, `Controller` classes) for
  creating virtual OpenFlow networks
	
- A simple network infrastructure (`Mininet` class) supporting parametrized
  topologies (`Topo` subclasses.) For example, a tree network may be created
  with the command
  
  `# mn --topo tree,depth=2,fanout=3`
  
- Basic tests, including connectivity (`ping`) and bandwidth (`iperf`)

- A command-line interface (CLI class) which provides useful 
  diagnostic commands, as well as the ability to send a command to a
  node. For example,
  
  `mininet> h11 ifconfig -a`
  
  tells host h11 to run the command `ifconfig -a`

- A 'cleanup' command to get rid of junk (interfaces, processes, files in
  /tmp, etc.) which might be left around by Mininet or Linux. Try this if 
  things stop working!
  
  `# mn -c`
  
- Examples (in the examples/ directory) to help you get started.

Batteries are not included (yet!)

However, some preliminary installation notes are included in the INSTALL
file.

Additionally, much useful information, including a Mininet tutorial,
is available on the [Mininet Wiki](http://openflow.org/mininet).

Enjoy, and good luck!

---
Bob Lantz
rlantz@cs.stanford.edu

