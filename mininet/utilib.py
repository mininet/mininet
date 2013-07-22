def popleft(ipbase):
    ipbase.reverse()
    number = int(ipbase.pop())
    ipbase.reverse()
    return number, ipbase
    
## To avoid common network ips entered ##
def inttobin(power):
    num = 0
    for i in range(0, power):
        num = num + pow(2, i)
    return num

def compare (net1, net2, broad1, broad2):
    if net1 > broad2 or net2 > broad1:
        return False
    else:
        return True

def networkcheck(ipbaseargs):
    ipbaseargs.sort()
    for index in range (0, len(ipbaseargs) - 1):
        network1, subnet1 = ipbaseargs[index].split('/')
        network2, subnet2 = ipbaseargs[index + 1].split('/')
        subnet1 = 32 - int(subnet1)
        subnet2 = 32 - int(subnet2)
        net1 = network1.split('.')
        net2 = network2.split('.')
        j = 3
        while subnet1 >= 0 :
            if subnet1 < 8:
                subnet1 = subnet1 % 8
                net1[j] = str(int(net1[j]) | inttobin(subnet1))
            else:
                net1[j] = str(int(net1[j]) | inttobin(8))
            subnet1 = subnet1 - 8
        broadcast1 = net1[0] + net1[1] + net1[2] + net1[3]
        while subnet2 >= 0 :
            if subnet2 < 8:
                subnet2 = subnet2 % 8
                net2[j] = str(int(net2[j]) | inttobin(subnet2))
            else:
                net2[j] = str(int(net2[j]) | inttobin(8))
            subnet2 = subnet2 - 8
        broadcast2 = net2[0] + net2[1] + net2[2] + net2[3]
        if compare(network1, network2, broadcast1, broadcast2):
            print 'Networks: ' + ipbaseargs[index] + ' and ' + ipbaseargs[index + 1] + ' coincide!'
            return True

'''def switchconnect (mn):
    con1 =  mn[0].nameToNode[ 'sA1' ]
    con2 =  mn[1].nameToNode[ 'sB1' ]
    mn[0].addLink(con1, con2, 3, 3, {})'''

def getipbasefornetwork(ipdefaultbase, index):
    ipbaseaddr = ipdefaultbase.split('/')
    netw = ipbaseaddr[0].split('.')
    netw[0] = str(int(netw[0]) + index)
    ipbaseaddr = netw[0] + '.' + netw[1] + '.' + netw[2] + '.' + netw[3] + '/' + ipbaseaddr[1]
    return ipbaseaddr
