## Project structure

* custom_node.py -- add node that by default add HostOnly Interface and add in to Host Only network
* test_node.py -- usage example


## Use example with Mininet CLI

```{bash}
mn --custom custom_node.py --host deb_host 
mn --custom custom_node.py --host deb_host --topo single,n=2
```
