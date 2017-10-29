from util import array_into_string
from bundle import *
import filedump
import bp
import sdnv
import util
import re
import os

BUFFER_SIZE = 8192

bip = None #bundle in process

bip_data_len = None

bip_acked = None

dtlsr_re = re.compile(r"dtn://\*/dtlsr\?lsa_seqno=\d+")

#TODO: scan for nontrivial race conditions

#
# FUNCTIONS FOR RECEIVING BUNDLES
#

def parse_message_type(message):
    flags = message & 0x0f
    type = message >> 4
    return (flags, type)

def parse_data_seg(socket):
    return sdnv.decode_from_file(socket)        

def parse_ack(socket):
    return sdnv.decode_from_file(socket)

def parse_new_bundle(message, pack_length):
    global bip, bip_data_len, bip_acked
    if (bip):
        util.debug("Trying to start a bundle while we are waiting to finish a prevous one")
        return
    (bundle, data_length, remainder) = bp.decode(message)
    (file_index, file_loc) = filedump.mkstemp()
    file = open(file_loc, 'wb')
    file.write(remainder)
    file.close()
    bundle.payload = FilePayload(file_loc)
    bip = bundle
    bip_data_len = data_length
    bip_acked = pack_length
    return bip_acked
    
def parse_data_bundle(message, pack_length):
    global bip, bip_data_len, bip_acked
    if not (bip):
        util.debug("Got data bundle without start bundle")
        return
    file = bip.payload.get_file(mode = "ab")
    bip_acked += pack_length
    file.write(message)
    file.close()
    return bip_acked

#returns the finished bundle
def parse_end_bundle():
    global bip, bip_data_len, bip_acked
    temp = bip
    bip_acked = None
    bip = None
    bip_data_len = None
    return dtn_filter(temp)

def dtn_filter(bundle):
    global dtlsr_re
    if (dtlsr_re.match(bundle.dest)): #filter out dtlsr packets
        print ("dropping matching packet %s" % bundle.dest)
        os.remove(bundle.payload.filename)
        return None
    return bundle

#
# FUNCTIONS FOR GENERATING AND SENDING DATA
#

#this is hacked together, I need to clean it up
def gen_bundle(b, queue):
    #first the TCPCL header
    #header indicating the message type, and flags
    data_len = len(b.payload)
    data_file = b.payload.get_file()
    #fencepost!
    start = True
    while (data_len > 0):
        if (start):#start bundle
            util.debug("In start of bundle creation")
            start = False
            primary_block = bp.encode(b)
            preamble = bp.encode_block_preamble(bp.PAYLOAD_BLOCK,
                                                bp.BLOCK_FLAG_LAST_BLOCK,
                                                [], data_len) #using data_len, don't reorder this..
            if (data_len < BUFFER_SIZE): #fully contained
                flags = 0 | bp.START | bp.END
                data = sdnv.encode(len(primary_block) + len(preamble) + len(b.payload))
                data += primary_block + preamble + b.payload.data()
                data_len -= len(b.payload)
            else: #start bundle
                flags = 0 | bp.START
                data = sdnv.encode(len(primary_block) + len(preamble) + BUFFER_SIZE)
                data += primary_block + preamble + data_file.read(BUFFER_SIZE)
                data_len -= BUFFER_SIZE
        elif (data_len < BUFFER_SIZE): #end bundle
            util.debug("End bundle")
            flags = 0 | bp.END
            data = sdnv.encode(data_len)
            data += data_file.read(data_len)
            data_len = 0
        else: #data bundle
            flags = 0
            data = sdnv.encode(BUFFER_SIZE )
            data += data_file.read(BUFFER_SIZE)
            data_len -= BUFFER_SIZE
        packet = chr((bp.DATA_SEGMENT << 4) + flags)
        packet += data
        #this is fuzzy math
        queue.put(packet)
    data_file.close()

def gen_ack(length):
    packet = ''
    #header indicating ack, and empty flags
    packet += chr(0x2 << 4)
    #then the length.
    util.debug("Tagging of length " + str(length))
    packet += sdnv.encode(length)
    return packet

def gen_keepalive():
    #i'll make this more professional later
    return chr(64)

#
# FUNCTIONS FOR CONNECTING TO A DTN SERVER
#

def connect(link, eid, keepalive):
    data = ''
        #first the magic dtn! part
    data += "dtn!"
        #then the version
    data += chr(bp.VERSION)
        #then the connection flags, which we'd OR with stuff in bp if needed
    data += chr(0)
        #keepalive, two bytes
    data += chr(0) 
    data += chr(keepalive)
        #then the length of our address, in sdnv format for some reason
        #i know this a-priori
    data += sdnv.encode(len(eid))
        #then the address itself
    data += eid
    link.socket.send(data)
        #ok, sent. Listen for response
    res = link.socket.recv(4096)
    result = __parse_connect_response(res)
    if not(res): #bad packet
        raise Error("Bad DTN response")
    return min(keepalive,result[2])

def __parse_connect_response(response):
    a = list(response)
    a = map(ord, a)
        ##first, rip off the dtn!
    if (array_into_string(a[0:4]) != "dtn!"): #malformed, drop it
        util.debug("Malformed connect response")
        return None
    else:
        results = []
            #version -this is seemingly wrong
        results.append(a[4])
            #flags
        results.append(a[5])
            #keepalive -two bytes
        results.append((a[6] << 8) + a[7])
        len = a[8]
        results.append(array_into_string(a[9:9+len]))
        return results
