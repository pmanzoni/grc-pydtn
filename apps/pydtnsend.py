#!/usr/bin/python

import sys
import time
import getopt #missing
from dtn import *
from dtn.udpcl import *
from dtn.tcpcl import *

def usage():
    print ("PYDTN dtnsend")
    print ("-d destination EID")
    print ("-s source EID. Default is dtn://test.dtn/foo")
    print ("-t f|s f for file, s for string. Default string")
    print ("-c contents, depends on message type")
    print ("-h for the host to send to")
    print ("-p to change the port, default 4556")

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], "d:s:t:c:h:p:")
    except getopt.GetoptError, err:
        # print help information and exit:
        print str(err) # will print something like "option -a not recognized"
        usage()
        sys.exit(2)

    source = "dtn://test.dtn/foo"
    type = "s"
    dest = None
    payload = None
    host = None
    port = 4556
    for o, a in opts:
        if (o == "-d"):
            dest = a
        elif (o == "-s"):
            source = a
        elif (o == "-c"):
            payload = a
        elif (o == "-t"):
            type = a
        elif (o == "-p"):
            port = int(a)
        elif (o == "-h"):
            host = a
        else:
            print ("%s not recognized" % o)
            usage()
            assert False, "unhandled option"

    if not(source and type and dest and payload and host and port):
        print ("Missing one input")
        usage()
        exit(2)

    if (type == "s"):
        print ("String Message")
    elif (type == "f"):
        print ("File Message")
    else:
        print ("Unknown type")
        usage()
        exit(2)
    print ("Contents: %s" % payload)
    print ("Host: %s" % host)
    print ("Source: %s" % source)
    print ("Destination: %s" % dest)
    print ("Port: %d" % port)
        

    l = Link('test-link')
    dtn = DtnDaemon(l, host, port, source)
    dtn.start()
    print ("Wait a little bit to ensure the connecton is established...")
    #make sure connection is up, wait 5 seconds
    time.sleep(5)
    if (type == "f"):
        dtn.send_file(dest, payload)
    else: #assume all others are strings
        dtn.send_string(dest, payload)
    print ("Sent! Waiting to ensure delivery...")
    while not(dtn.empty()):
        time.sleep(3)
    dtn.exit()

    
    
    
    
