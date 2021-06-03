# Host Only Network project

The project aims to add support of additional host-only interface to Mininet library.

## Project structure

All sources are located in **project** directory

* custom_node.py -- add node that by default add HostOnly Interface and add in to Host Only network
* test_node.py -- usage example

* test/test_basic.py -- test for network

## Use example with Mininet CLI

```{bash}
mn --custom custom_node.py --host deb_host 
mn --custom custom_node.py --host deb_host --topo single,n=2
```

## Use example of unittest checking
```{bash}
python test/test_basic.py
```

## Team

[Yuriy Pasichnyk](https://github.com/Fenix-125) <br/>
[Danylo Sluzhynskyi](https://github.com/sluzhynskyi)

