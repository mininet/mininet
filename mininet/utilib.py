import os
import copy
import glob

def popleft(ipbase):
    ipbase.reverse()
    number = int(ipbase.pop())
    ipbase.reverse()
    return number, ipbase
    
## Updating value for unique naming ##
def valueupdate(entity):
    os.chdir('mininet')
    filename = open('alpha.py')
    with filename as f:
        content = f.readlines()
    filename.close()
    f = open('alpha.py', 'w')
    for i in range (0, len(content)):
        temp = content[i].partition(' = ')
        if temp[0] == entity:
            number = int(temp[2].split('\n')[0])
            #return this number and write the updated value in file
            number = number + 1
            content[i] = temp[0] + temp[1] + str(number) + '\n'
        f.write(content[i])
    f.close()
    os.chdir('..')

def valuefind(entity):
    os.chdir("mininet")
    filename = open('alpha.py')
    with filename as f:
        content = f.readlines()
    filename.close()
    os.chdir("..")
    for i in range (0, len(content)):
        temp = content[i].partition(' = ')
        if temp[0] == entity:
            number = int(temp[2].split('\n')[0])
            if entity != 'multinet':
                number = number + 1
            return (number)

## Clearing the values of the file ##
def putzero():
    os.chdir('mininet')
    filename = open('alpha.py')
    with filename as f:
        content = f.readlines()
    filename.close()
    f = open('alpha.py', 'w')
    for i in range (0, len(content)):
        temp = content[i].partition(' = ')
        content[i] = temp[0] + temp[1] + str(0) + '\n'
        f.write(content[i])
    f.close()
    os.chdir('..')

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

def switchconnect (mn):
    '''for index in range (0, len(mn) - 1):
        print mn[index].switches'''
    con1 =  mn[0].nameToNode[ 'sA1' ]
    con2 =  mn[1].nameToNode[ 'sB1' ]
    
    mn[0].addLink(con1, con2, 3, 3, {})

def getipbasefornetwork(ipdefaultbase, index):
    ipbaseaddr = ipdefaultbase.split('/')
    netw = ipbaseaddr[0].split('.')
    netw[0] = str(int(netw[0]) + index)
    ipbaseaddr = netw[0] + '.' + netw[1] + '.' + netw[2] + '.' + netw[3] + '/' + ipbaseaddr[1]
    return ipbaseaddr
                    
