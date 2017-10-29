#!/usr/bin/python

import getopt, sys
from dtn import *

def usage():
    print "usage: %s [opts]" % sys.argv[0]
    print ""
    print "   [-h --help]     print this message"
    print "   ...."
    
def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   "ho:s:d:r:e:p:",
                                   ["help",
                                    "output=",
                                    "source=",
                                    "dest=",
                                    "replyto=",
                                    "expiration=",
                                    "payload="]
                                   )
    except getopt.GetoptError, err:
        # print help information and exit:
        print str(err) # will print something like "option -a not recognized"
        usage()
        sys.exit(2)
        
    output = None
    verbose = False
    
    b = Bundle()
    
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-o", "--output"):
            output = a
        elif o in ("-s", "--source"):
            b.source = a
        elif o in ("-d", "--dest"):
            b.dest = a
        elif o in ("-r", "--replyto"):
            b.replyto = a
        elif o in ("-e", "--expiration"):
            b.expiration = int(a)
        elif o in ("-p", "--payload"):
            if a == "-":
                b.payload = StringPayload(sys.stdin.read())
            else:
                b.payload = FilePayload(a)
        else:
            assert False, "unhandled option"

    if b.source == 'dtn:none':
        print "error: must specify bundle source"
        exit()

    if b.dest == 'dtn:none':
        print "error: must specify bundle dest"
        exit()

    if b.payload == None:
        print "error: must specify bundle payload"
        exit()

    blocks = bp.encode(b)
    if output == None or output == "-":
        ofile = sys.stdout
    else:
        ofile = open(output, 'w')
    
    ofile.write(blocks)
    ofile.write(b.payload.data())
    ofile.close()
        
if __name__ == "__main__":
    main()
