
from bundle import *
from link   import *

import bp
import socket
import sys

def init_link(link, host, port):
    link.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    link.socket.connect((host, port))

def send(bundle, link):
    # For UDP we want all bundle data into a single packet, so
    # concatenate the protocol-formatted beginning part with the whole
    # payload.
    primary_block = bp.encode(bundle)
    block_preamble = bp.encode_block_preamble(bp.PAYLOAD_BLOCK,
                                              bp.BLOCK_FLAG_LAST_BLOCK,
                                              [], len(bundle.payload))
    packet = ''.join((primary_block + block_preamble,
                      bundle.payload.data()))
    link.socket.send(packet)

if __name__ == '__main__':
    host    = sys.argv[1]
    port    = sys.argv[2]
    dest    = sys.argv[3]
    payload = sys.argv[4]

    b = Bundle()
    b.source = 'dtn://udpcl.test.dtn/test'
    b.dest   = dest
    b.bundle_flags |= bp.BUNDLE_SINGLETON_DESTINATION
    b.payload = StringPayload(payload)
    
    l = Link('test-link')
    init_link(l, host, int(port))

    send(b, l)
    
    
    
