import tcpcl
import bp
import util
import socket
import thread
import e32
import time
import sys
import traceback
from link import Link
from bundle import *

DEFAULT_KEEPALIVE = 60

RETRY_CONNECTION_TIMER = 10

KEEPALIVES_MISSED_TILL_DEATH = 10

DIE = False

KA_DIE = False

EXIT = False

#this is not threaded, but it should start threads.
class DtnDaemon(object):
    
    """This class is mostly an interface over the imperative 
    bullshit symbian thread model"""

    def __init__(self, host, port, local_eid, 
                 timeout=DEFAULT_KEEPALIVE, link=None):
        self.link = link
        self.host = host
        self.port = port
        self.local_eid = local_eid
        self.default_keepalive = timeout
        self.keepalive = self.default_keepalive
        self.last_keepalive = time.time()
        self.bundle_queue = rw_queue() 
        self.received_queue = rw_queue()
        DIE = False

    def start(self):
        DIE = False
        thread.start_new_thread(mainThread_wrapper, (self.bundle_queue, self.received_queue, 
                                                     self.host, self.port, self.local_eid, 
                                                     self.keepalive))
        
    def exit(self):
        global EXIT
        EXIT = True

    def send_string(self, destination, string):
        self.__queue_bundle(destination, StringPayload(string))

    def send_file(self, destination, file_loc):
        self.__queue_bundle(destination, FilePayload(file_loc))

    #doesn't block yet...
    def recv(self, timeout):
        #ignoring timeout for now...
        if (len(self.received_queue) > 0):
            return self.received_queue.pop(0)
        else:
            return None

    def __queue_bundle(self, destination, payload): 
        #needs some thread control
        b = Bundle()
        b.payload = payload
        b.source = self.local_eid
        b.dest = destination
        b.bundle_flags |= bp.BUNDLE_SINGLETON_DESTINATION
        tcpcl.gen_bundle(b, self.bundle_queue)

'''allows us to catch exceptions caused by this thread'''
def mainThread_wrapper(outgoing_queue, incoming_queue, dest, port, local_eid, ka):
    wrapper = lambda: mainThread(outgoing_queue, incoming_queue, dest, port, local_eid, ka)
    util.exception_wrapper(wrapper)
        
#socket has to be completely contained in just this thread
def mainThread(outgoing_queue, incoming_queue, dest, port, local_eid, ka):
    global DIE, KA_DIE, EXIT
    #main loop
    link = None
    while not(EXIT):
        if (DIE or not(link)):
            link = Link("test-link")
            ka = start_dtn(link, dest, port, local_eid, ka) #this blocks until true
            KA_DIE = False
            wrapper = lambda: thread.start_new_thread(keepalive_wrapper, (outgoing_queue,ka))
            util.exception_wrapper(wrapper)
            link.socket.setblocking(5)
            dead = False
            DIE = False
        else:
            util.debug("In main loop")
            while not(DIE):
                #this is a little silly, we want to pop all keepalives off, sending the first packet giving us an
                #ack, breaking the below wait
                data = '@'
                while (len(outgoing_queue) > 0 and data == '@'):
                    try:
                        util.debug("Sending Bundle")
                        data = outgoing_queue.pop(0)
                        link.socket.send(data)
                    except socket.error, e:
                        util.debug ("Error in sending")
                        KA_DIE = True
                        DIE = True
                        break
                #ok, everything sent, try to receive, block if nothing available
                try:
                    res = link.file_int.read(1) #the keepalives will at least bust this...
                    if (res == ""):
                        util.debug("Listener detected error, exiting")
                        KA_DIE = True
                        DIE = True
                        break
                    else:
                        #print ("Received Message")
                        handle_message(link, ord(res), outgoing_queue, incoming_queue)
                except socket.error, e:
                    util.debug ("Error in reading")
                    KA_DIE = True
                    DIE = True
                    break
    #out of main looop, someone broke us
    KA_DIE = True
    DIE = True

def handle_message(link, message, out_q, in_q):
    (flags, type) = tcpcl.parse_message_type(message)
    if (type == bp.DATA_SEGMENT):
        handle_data_segment(link, flags, out_q, in_q)
    elif (type == bp.ACK_SEGMENT):
        handle_ack_segment(link, flags)
    elif (type == bp.REFUSE_BUNDLE):
        handle_refuse_bundle(link, flags)
    elif (type == bp.KEEPALIVE):
        handle_keepalive(link, flags)
    elif (type == bp.SHUTDOWN):
        handle_shutdown(link, flags)
    else:
        util.debug("Malformed Message")

def handle_data_segment(link, flags, out_q, in_q):
    util.debug ("Data Segment")
    pack_length = tcpcl.parse_data_seg(link.file_int)
    util.debug ("pack length: %d"  % pack_length)
    message = link.file_int.read(pack_length)
    if (flags & bp.START):
        util.debug ("got start bundle")
        ack = tcpcl.parse_new_bundle(message, pack_length)
    else:
        util.debug ("non-start bundle")
        ack = tcpcl.parse_data_bundle(message, pack_length)
    if (flags & bp.END):
        bundle = tcpcl.parse_end_bundle()
        if (bundle):
            in_q.put(bundle)
    out_q.put(tcpcl.gen_ack(ack))

def handle_ack_segment(link, flags):
    ack_len = tcpcl.parse_ack(link.file_int)
    util.debug ("ACK of length %d" % ack_len)

def handle_refuse_bundle(link, flags):
    util.debug ("Refusing bundle")

def handle_keepalive(link, flags):
    #print ("Got keepalive")
    pass

def handle_shutdown(link, flags):
    global DIE
    util.debug("Got shutdown")
    DIE = True

def keepalive_wrapper(queue, keepalive):
    wrapper = lambda: keepalive(queue, keepalive)
    util.exception_wrapper(wrapper)

def keepalive(queue, keepalive):
    global KA_DIE
    util.debug ("starting keepaliver")
    while not(KA_DIE):
        util.debug("In Keepalive")
        queue.insert(tcpcl.gen_keepalive(), index=0) #put at head, in case we're processing a lot of packets
        e32.ao_sleep(keepalive)
    util.debug ("exiting keepaliver")

def start_dtn(link, host, port, local_eid, ka):
    global EXIT
    while not(EXIT):
        util.debug ("starting dtn")
        try:
            link.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            link.socket.connect((host, port))
            link.file_int = link.socket.makefile('r+b', tcpcl.BUFFER_SIZE)
            ka = tcpcl.connect(link, local_eid, ka)
            break
        except Exception, e:
            util.debug("Connect Failed ")
            res = sys.exc_info()
            util.debug(res)
            util.tb_debug(res[2])
            #this fails for some reason...
            #e32.ao_sleep(RETRY_CONNECTION_TIMER)
    return ka

#now thread safe
class rw_queue(list):

    def __init__(self):
        self.lock = thread.allocate_lock()

    def put(self, item, block=True, timeout=None):
        self.append(item)
            
    def get(self, block=True, timeout=None):
        return self.pop(0)

    def pop(self, index):
        #util.debug("Acquiring lock - pop")
        self.lock.acquire_lock()
        item = list.pop(self, index)
        #util.debug("Releasing lock - pop")
        self.lock.release()
        return item
        
    def insert(self, item, index):
        #util.debug("Acquiring lock - insert")
        self.lock.acquire_lock()
        list.insert(self, index, item)
        #util.debug("Releasing lock - insert")
        self.lock.release()

    def append(self, item):
        #util.debug("Acquiring lock - append")
        self.lock.acquire_lock()
        list.append(self, item)
        #util.debug("Releasing lock - append")
        self.lock.release()      

    def __len__(self):
        #util.debug("Acquiring lock - length")
        self.lock.acquire_lock()
        len = list.__len__(self)
        #util.debug("Releasing lock - length")
        self.lock.release()
        return len
        