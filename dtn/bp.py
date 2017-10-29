import sdnv
import struct
from util import array_into_string


__all__ = ( "encode", "decode", "VERSION" )

#
# The currently-implemented version of the bundle protocol
#
VERSION = 6

#
# Time conversion to go from 1/1/1970 to 1/1/2000
#
TIMEVAL_CONVERSION = 946684800

#
# Bit definitions for bundle flags.
#
BUNDLE_IS_FRAGMENT             = 1 << 0
BUNDLE_IS_ADMIN                = 1 << 1
BUNDLE_DO_NOT_FRAGMENT         = 1 << 2
BUNDLE_CUSTODY_XFER_REQUESTED  = 1 << 3
BUNDLE_SINGLETON_DESTINATION   = 1 << 4
BUNDLE_ACK_BY_APP              = 1 << 5
BUNDLE_UNUSED                  = 1 << 6

#
# COS values
#
COS_BULK      = 0 << 7
COS_NORMAL    = 1 << 7
COS_EXPEDITED = 2 << 7

#
# Status report request flags
#
STATUS_RECEIVED         = 1 << 14
STATUS_CUSTODY_ACCEPTED = 1 << 15
STATUS_FORWARDED        = 1 << 16
STATUS_DELIVERED        = 1 << 17
STATUS_DELETED          = 1 << 18
STATUS_ACKED_BY_APP     = 1 << 19
STATUS_UNUSED2          = 1 << 20

#
# Reason codes for status reports
#
REASON_NO_ADDTL_INFO              = 0x00
REASON_LIFETIME_EXPIRED           = 0x01
REASON_FORWARDED_UNIDIR_LINK      = 0x02
REASON_TRANSMISSION_CANCELLED     = 0x03
REASON_DEPLETED_STORAGE           = 0x04
REASON_ENDPOINT_ID_UNINTELLIGIBLE = 0x05
REASON_NO_ROUTE_TO_DEST           = 0x06
REASON_NO_TIMELY_CONTACT          = 0x07
REASON_BLOCK_UNINTELLIGIBLE       = 0x08
REASON_SECURITY_FAILED            = 0x09
    
#
# Custody transfer reason codes
#
CUSTODY_NO_ADDTL_INFO              = 0x00
CUSTODY_REDUNDANT_RECEPTION        = 0x03
CUSTODY_DEPLETED_STORAGE           = 0x04
CUSTODY_ENDPOINT_ID_UNINTELLIGIBLE = 0x05
CUSTODY_NO_ROUTE_TO_DEST           = 0x06
CUSTODY_NO_TIMELY_CONTACT          = 0x07
CUSTODY_BLOCK_UNINTELLIGIBLE       = 0x08

#
# Block type codes
#
PRIMARY_BLOCK               = 0x000
PAYLOAD_BLOCK               = 0x001
BUNDLE_AUTHENTICATION_BLOCK = 0x002
PAYLOAD_SECURITY_BLOCK      = 0x003
CONFIDENTIALITY_BLOCK       = 0x004
PREVIOUS_HOP_BLOCK          = 0x005
METADATA_BLOCK              = 0x008

#
# Block processing flags
#
BLOCK_FLAG_REPLICATE               = 1 << 0
BLOCK_FLAG_REPORT_ONERROR          = 1 << 1
BLOCK_FLAG_DISCARD_BUNDLE_ONERROR  = 1 << 2
BLOCK_FLAG_LAST_BLOCK              = 1 << 3
BLOCK_FLAG_DISCARD_BLOCK_ONERROR   = 1 << 4
BLOCK_FLAG_FORWARDED_UNPROCESSED   = 1 << 5
BLOCK_FLAG_EID_REFS                = 1 << 6

#
# Message type codes
#
DATA_SEGMENT  = 0x1
ACK_SEGMENT   = 0x2
REFUSE_BUNDLE = 0x3
KEEPALIVE     = 0x4
SHUTDOWN      = 0x5

#
# Connection flags for TCP Convergence Layer
#
REQUEST_BUNDLE_ACK    = 1 << 0
REQUEST_REACTIVE_FRAG = 1 << 1
INDICATE_NACK_SUPPORT = 1 << 2

#
# Bundle Data Transmission Flags
#
END = 1 << 0
START = 1 << 1

#depends on the above, so need to be imported after
import bundle 

#----------------------------------------------------------------------
def encode(bundle):
    """Encodes all the bundle blocks, not including the preamble for the
    payload block or the payload data itself, into a binary string."""

    data = ''

    #------------------------------
    # Primary block
    #------------------------------
    
    # Put the eid offsets into the dictionary and append their sdnvs
    # to the data buffer
    #this seems like an optimization --kurtis
    dict_offsets = {}
    dict_buffer  = ''
    for eid in ( bundle.dest,
                 bundle.source,
                 bundle.replyto,
                 bundle.custodian ) :

        (scheme, ssp) = eid.split(':')
        
        if dict_offsets.has_key(scheme):
            scheme_offset = dict_offsets[scheme]
        else:
            dict_offsets[scheme] = scheme_offset = len(dict_buffer)
            dict_buffer += scheme
            dict_buffer += '\0'

        if dict_offsets.has_key(ssp):
            ssp_offset = dict_offsets[ssp]
        else:
            dict_offsets[ssp] = ssp_offset = len(dict_buffer)
            dict_buffer += ssp
            dict_buffer += '\0'

        data += sdnv.encode(scheme_offset)
        data += sdnv.encode(ssp_offset)

    # Now append the creation time and expiration sdnvs, the
    # dictionary length, and the dictionary itself
    data += sdnv.encode(bundle.creation_secs)
    data += sdnv.encode(bundle.creation_seqno)
    data += sdnv.encode(bundle.expiration)
    data += sdnv.encode(len(dict_buffer))
    data += dict_buffer

    # Now fill in the preamble portion, including the version,
    # processing flags and whole length of the block
    preamble = struct.pack('B', VERSION)
    preamble += sdnv.encode(bundle.bundle_flags |
                            bundle.priority |
                            bundle.srr_flags)
    preamble += sdnv.encode(len(data))
    return preamble + data

#----------------------------------------------------------------------
def encode_block_preamble(type, flags, eid_offsets, length):
    """Encode the standard preamble for a block"""
    
    eid_data = ''
    if len(eid_offsets) != 0:
        flags = flags | BLOCK_FLAG_EID_REFS

        eid_data = sdnv.encode(len(eid_offsets))
        for o in eid_offsets:
            eid_data += sdnv.encode(o)

    return ''.join((struct.pack('B', type),
                    sdnv.encode(flags),
                    eid_data,
                    sdnv.encode(length)))

#----------------------------------------------------------------------
#This should decode an encoded bundle, presumably including 
#the block preamble but not including the payload
#this is likely to explode from a bad block, i'm not adding
#error checks
#also assumes that the primary and preamble are completely contained
#takes an string containing the message
#
def decode(message):
    bytes = list(message)
    bytes = map(ord, bytes)
    version = bytes[0]
    if (version != VERSION):
        raise Exception("Version mismatch, decoding failed")
    len = 1
    #there's probably a smarter way to do this
    #my python-fu is weak
    (flags, block_length, len) = __decode_assist(len,bytes)
    (dest_sch_offset, dest_ssp_off, len) = __decode_assist(len,bytes)
    (source_sch_offset, source_ssp_off, len) = __decode_assist(
        len,bytes)
    (reply_sch_offset, reply_ssp_off, len) = __decode_assist(
        len,bytes)
    (cust_sch_offset, cust_ssp_off, len) = __decode_assist(
        len,bytes)
    (creation_ts, creation_ts_sq_no, len) = __decode_assist(
        len,bytes)
    (lifetime, dict_len, len) = __decode_assist(len,bytes)
    #should test if fragment, then see a fragment offset. 
    #Skipping as we say no fragments at this point

    #build the bundle
    b = bundle.Bundle()
    b.creation_secs = creation_ts
    b.creation_seqno = creation_ts_sq_no
    b.expiration = lifetime
    b.dest = __get_decoded_address(bytes[len:], dest_sch_offset, 
                                   dest_ssp_off)
    b.source = __get_decoded_address(bytes[len:], source_sch_offset, 
                                     source_ssp_off)
    b.replyto = __get_decoded_address(bytes[len:], reply_sch_offset, 
                                      reply_ssp_off)
    b.custodian = __get_decoded_address(bytes[len:], cust_sch_offset, 
                                        cust_ssp_off)
    for flag in (BUNDLE_IS_FRAGMENT,
                 BUNDLE_IS_ADMIN,
                 BUNDLE_DO_NOT_FRAGMENT,
                 BUNDLE_CUSTODY_XFER_REQUESTED,
                 BUNDLE_SINGLETON_DESTINATION,
                 BUNDLE_ACK_BY_APP,
                 BUNDLE_UNUSED):
        b.bundle_flags += (flags & flag)
    for flag in (STATUS_RECEIVED,
                 STATUS_CUSTODY_ACCEPTED,
                 STATUS_FORWARDED,
                 STATUS_DELIVERED,
                 STATUS_DELETED,
                 STATUS_ACKED_BY_APP,
                 STATUS_UNUSED2):
        b.srr_flags += (flags & flag)
    b.priority = flags & (COS_BULK | COS_NORMAL | COS_EXPEDITED)

    #ok, primary bundle done. Onto bundle block!
    len += dict_len
    block_type = bytes[len] 
    #we'll ignore the flags for now... 
    (block_proc_cntl_flags, block_len, len) = __decode_assist(len+1, bytes)
    return (b, block_len, array_into_string(bytes[len:]))

def __decode_assist(len, array): #this is not efficient
    (temp_len, one) = sdnv.decode(array_into_string(array[len:]))
    len += temp_len
    (temp_len, two) = sdnv.decode(array_into_string(array[len:]))
    len += temp_len
    return (one, two, len)

def __get_decoded_address(array, sch_off, ssp_off):
    tmp = array[sch_off:]
    zero = __find_zero(tmp)
    res = array_into_string(tmp[0:zero]) + ":"
    tmp = array[ssp_off:]
    zero = __find_zero(tmp)
    res += array_into_string(tmp[0:zero])
    return res

def __find_zero(array):
    for i in range(len(array)):
        if (array[i] == 0):
            return i
    return -1

#----------------------------------------------------------------------
if (__name__ == "__main__"):
    from binascii import hexlify
    from bundle import *

    b = Bundle()
    b.source = 'dtn:me'
    b.dest   = 'dtn:you'
    b.bundle_flags  |= BUNDLE_SINGLETON_DESTINATION
    b.bundle_flags  |= BUNDLE_CUSTODY_XFER_REQUESTED
    b.srr_flags     |= STATUS_DELETED | STATUS_DELIVERED
    b.payload = StringPayload("test")
    
    d = encode(b)
    preamble = encode_block_preamble(PAYLOAD_BLOCK,
                                     BLOCK_FLAG_LAST_BLOCK,
                                     [], len(b.payload))
    message = d + preamble + b.payload.data()
    print "encoded data: ", hexlify(message)
    (bundle, len, remainder) = decode(message)
    bundle.payload = StringPayload(remainder)
    
    print(b.tostring())
    print(bundle.tostring())
    
    assert(bundle == b)
