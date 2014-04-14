import os
import sys
import Queue
import socket
import json
from select import select

OVSDB_IP = '127.0.0.1'
OVSDB_PORT = 6632
DEFAULT_DB = 'Open_vSwitch'
BUFFER_SIZE = 4096

pid = None
last_id = 0

def generate_id():
    global pid
    global last_id
    if pid is None:
        pid = os.getpid()
    last_id += 1
    return "%d-%d" % (pid, last_id)

# ----------------------------------------------------------------------


# TODO: Could start by getting the DB name and using that for ongoing requests
# TODO: How to keep an eye out for montor, update, echo messages?
def gather_reply(socket):
    #print "Waiting for reply"
    result = ""
    while True:
        reply = socket.recv(BUFFER_SIZE)
        result += reply
        # we got the whole thing if we received all the fields
        if "error" in result and "id" in result and "result" in result:
            try:
                return json.loads(result)
            except ValueError:
                pass

def listen_for_messages(sock, message_queues):
    # To send something, add a message to queue and append sock to outputs
    inputs = [sock, sys.stdin]
    outputs = []
    while sock:
        readable, writable, exceptional = select(inputs, outputs, [])
        for s in readable:
            if s is sock:
                data = sock.recv(4096)
                # should test if its echo, if so, reply
                # message_type = get_msg_type(data)
                # if message_type is "echo":
                #   send_echo(message_
                message_queues[sock].put(data)
                outputs.append(sock)
                print "recv:" + data
            elif s is sys.stdin:
                print sys.stdin.readline()
                sock.close()
                return
            else:
                print "error"
        for w in writable:
            if w is sock:
                sock.send(message_queues[sock].get_nowait())
                outputs.remove(sock)
            else:
                print "error"

def list_dbs():
    list_dbs_query =  {"method":"list_dbs", "params":[], "id": 0}
    return json.dumps(list_dbs_query)

def get_schema(socket, db = DEFAULT_DB, current_id = 0):
    list_schema = {"method": "get_schema", "params":[db_name], "id": current_id}
    socket.send(json.dumps(list_schema))
    result = gather_reply(socket)
    return result

def get_schema_version(socket, db = DEFAULT_DB):
    db_schema = get_schema(socket, db)
    return db_schema['version']

def list_tables(server, db):
    # keys that are under 'tables'
    db_schema = get_schema(socket, db)
    # return db_schema['tables'].keys
    return json.loads()

def list_columns(server, db):
    return

def transact(s, db, operations):
    # Variants of this will add stuff
    request = { "method": "transact",
                "params": [db] + operations,
                "id": generate_id(),
              }

    s.send(json.dumps(request))
    response = gather_reply(s)
    
    #assumtion: no overlapping calls
    assert( request['id'] == response['id'] )
    results = response['result']
    if len(operations) == len(results):
        for i, val in enumerate(zip(operations, results)):
            if 'error' in val[1]:
                raise RuntimeError('Op failed (%d, %s): %s' %
                                   (i, val[0], val[1]))
    else:
        raise RuntimeError('transact failed: %s' % results[-1])

    return results

def monitor(columns, monitor_id = None, db = DEFAULT_DB):
    msg = {"method":"monitor", "params":[db, monitor_id, columns], "id":0}
    return json.dumps(msg)

def monitor_cancel():
    return

def locking():
    return

def echo():
    echo_msg = {"method":"echo","id":"echo","params":[]}
    return json.dumps(echo_msg)

def dump(server, db):
    return

def list_bridges(db = DEFAULT_DB):
    # What if we replaced with a more specific query
    # columns = {"Bridge":{"name"}}
    columns = {"Port":{"columns":["fake_bridge","interfaces","name","tag"]},"Controller":{"columns":[]},"Interface":{"columns":["name"]},"Open_vSwitch":{"columns":["bridges","cur_cfg"]},"Bridge":{"columns":["controller","fail_mode","name","ports"]}}
    # TODO: cancel the monitor after we're done?
    return monitor(columns, db)

daemon_uuid = None
def get_daemon_uuid(socket, db = DEFAULT_DB):
    "Get the uuid from table Open_vSwitch"
    global daemon_uuid
    if daemon_uuid:
        return daemon_uuid
    op = {"op": "select",
          "table": "Open_vSwitch",
          "where": [],
          "columns": ["_uuid"],
          }
    reply = transact(socket, db, [op])
    try:
        if (len(reply[0]['rows']) != 1):
            e = 'There must be exactly one record in the Open_vSwitch table.'
            raise RuntimeError(e) 
        daemon_uuid = reply[0]['rows'][0]['_uuid'][1]
    except (KeyError, TypeError):
        raise RuntimeError("Database schema changed")
    return daemon_uuid

if __name__ == '__main__':
    if False:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((OVSDB_IP, OVSDB_PORT))
    else:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect('/var/run/openvswitch/db.sock')

    current_id = 0

    s.send(list_dbs())
    db_list = gather_reply(s)
    db_name = db_list['result'][0]
    print "db_name", db_list

    print "list bridges:"
    s.send(list_bridges())
    bridge_list = gather_reply(s)
    print bridge_list
    bridges = bridge_list['result']['Bridge']
    print "\nbridges\n"
    print bridges.values()
    for bridge in bridges.values():
        print "---"
        print bridge['new']['name']
    #db_schema = get_schema(s, db_name)
    #print db_schema

    #columns = {"Bridge":{"columns":["name"]}}
    #print monitor(s, columns, 1)

    # TODO: Put this in a thread and use Queues to send/recv data from the thread
    message_queues = {}
    message_queues[s] = Queue.Queue()
    listen_for_messages(s, message_queues)
