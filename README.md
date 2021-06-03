## Project structure

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
