
__all__ = ['encode', 'decode', 'decode_from_file']

import struct

def encode(val):
    """Encode val as an SDNV, returning a string with the
    encoded value."""

    s=''
    high_bit=0
    while (True):
        s = struct.pack('B', ((high_bit | (val & 0x7f)))) + s
        high_bit = (1<<7)
        val = val >> 7

        if val == 0: break

    return s

def decode(s):
    """Decode the sdnv at the beginning of the given string into a
    (len, value) tuple that it encoded."""

    v = 0
    l = 0

    for c in s:
        v = (v << 7) | (ord(c) & 0x7f)
        l = l + 1
        
        if (ord(c) & (1<<7) == 0):
            return (l, v)

    raise ValueError('SDNV too short')

#decode the sdnv at the head of this file, reading as few bytes
#as possible returns just the result
def decode_from_file(file, get_length = False):
    bytes = ''
    while(1):
        bytes += file.read(1)
        try:
            res = decode(bytes)
            if (get_length):
                return res
            else:
                return res[1]
        except ValueError:
            pass

if (__name__ == "__main__"):
    from binascii import hexlify
    
    print "Testing SDNV encode/decode..."
    for x in (0, 1, 8, 127, 128, 1024, 0xffff):
        s = encode(x)
        l = len(s)
        print "encode(%d):\t0x%s\t(len %d)" % (x, hexlify(s), l)
        (l2, v) = decode(s)
        print "decode(0x%s):\t%d\t(len %d)" % (hexlify(s), v, l2)
    
