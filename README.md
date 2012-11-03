
    Mininet: Rapid Prototyping for Software Defined Networks
                            or
    The best way to emulate almost any network on your laptop!

Mininet 2.0.0rc1

---
** Welcome to Mininet! **

Mininet creates virtual SDN/OpenFlow test networks by using process-based
virtualization and network namespaces.

Simulated hosts (as well as switches and controllers with the user
datapath) are created as processes in separate network namespaces. This
allows a complete OpenFlow network to be simulated on top of a single
Linux kernel.

Mininet's support for OpenFlow and Linux allows you to create a custom
network with customized routing, and to run almost any existing Linux
networking application on top of it without modification. OpenFlow-based
designs that work in Mininet can usually be transferred to hardware with
minimal change for full line-rate execution.

Mininet may be invoked directly from the command line, and also provides a
handy Python API for creating networks of varying sizes and topologies.

** Mininet 2.0.0 **

Mininet 2.0.0 is a major upgrade to the Mininet system and provides
a number of enhancements and new features, including:

* First-class Interface (`Intf`) and Link (`Link`) classes

* An upgraded Topology (`Topo`) class which supports node and link
  customization

* Link bandwidth limits using `tc` (`TCIntf` and `TCLink` classes)

* CPU isolation and bandwidth limits (`CPULimitedHost` class)

* Support for the Open vSwitch 1.4+ (including Ubuntu OVS packages)

* Man pages for the `mn` and `mnexec` utilities.

[Since the API (most notably the topology) has changed, existing code that
runs in Mininet 1.0 will need to be changed to run with Mininet 2.0. This
is the primary reason for the major version number change.]

Mininet also includes:

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

- Full API documentation via Python `help()` docstrings, as well as
  the ability to generate PDF/HTML documentation with "make doc."

In order to run Mininet, you must have:

* A Linux kernel compiled with network namespace support
  enabled (see `INSTALL` for additional information.)

* An OpenFlow implementation (either the reference user or kernel
  space implementations, or Open vSwitch.) Appropriate kernel modules
  (e.g. tun and ofdatapath for the reference kernel implementation) must
  be loaded.

* Python, `bash`, `ping`, `iperf`, etc.

* Root privileges (required for network device access)

Installation instructions are available in INSTALL

*** Mininet Documentation ***

In addition to the API documentation (`make doc`) much useful information,
including a Mininet walkthrough and an introduction to the Python API is
available on the [Mininet Web Site](http://openflow.org/mininet). There is
also a wiki which you are encouraged to read and to contribute to,
particularly the Frequently Asked Questions (FAQ.)

*** Mininet Support ***

Mininet is supported by the friendly Mininet community. We encourage you to
join the Mininet mailing list, `mininet-discuss` at:

<https://mailman.stanford.edu/mailman/listinfo/mininet-discuss>

*** Contributing to Mininet ***

Mininet is an open-source project and is currently hosted at
<https://github.com/mininet>. You are encouraged to download the code,
examine it, modify it, and submit bug reports, bug fixes, feature
requests, and enhancements!

Best wishes, and we look forward to seeing what you can do with Mininet
to change the networking world!

---

Bob Lantz
Brandon Heller
Nikhil Handigol
Vimal Jeyakumar

Mininet Project

