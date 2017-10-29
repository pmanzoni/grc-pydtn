from bundle import *
import bp #id' like to remove this dependency...
import socket
import tcpcl
import util

import sys
import threading #missing
import time
import traceback
import Queue #thread safe

DEFAULT_KEEPALIVE = 60

RETRY_CONNECTION_TIMER = 120

KEEPALIVES_MISSED_TILL_DEATH = 10

class Keepaliver(threading.Thread):

    def __init__(self, link, keepalive, master):
        threading.Thread.__init__(self)
        self.link = link
        self.ka = keepalive
        self.master = master
        self.die = False

    def run(self):
        try:
            self.loop()
        except Exception, e:
            print("Keepaliver Failed")
            res = sys.exc_info()
            print(res)
            traceback.print_tb(res[2])
            self.master.die()

    def loop(self):
        while (1):
            util.debug("In keepalive")
            time.sleep(self.ka)
            if (self.die):
                util.debug("Keepaliver exiting")
                return
            #send keepalive, then wait keepalive seconds
            #this is 64, which is keepalive
            self.master.bundle_queue.put(tcpcl.gen_keepalive())
            util.debug("sent keepalive")

class Listener(threading.Thread):
    def __init__(self, link, master):
        threading.Thread.__init__(self)
        self.link = link
        self.master = master
        self.die = False
        self.bundle_queue = Queue.Queue(0)

    def run(self):
        try:
            self.loop()
        except Exception, e:
            print("Listener Failed")
            res = sys.exc_info()
            print(res)
            traceback.print_tb(res[2])
            self.master.die()
        
    def loop(self):
        while(1):
            util.debug("In Listener")
            if (self.die):
                util.debug("Listener Exiting")
                return
            res = self.link.file_int.read(1)
            if (res == ""):
                self.master.die()
                util.debug("Listener detected error, exiting")
                return
            self.__handle_message(ord(res))

    #i don't like these bps...
    def __handle_message(self, message):
        (flags, type) = tcpcl.parse_message_type(message)
        if (type == bp.DATA_SEGMENT):
            self.__handle_data_segment(flags)
        elif (type == bp.ACK_SEGMENT):
            self.__handle_ack_segment(flags)
        elif (type == bp.REFUSE_BUNDLE):
            self.__handle_refuse_bundle(flags)
        elif (type == bp.KEEPALIVE):
           self. __handle_keepalive(flags)
        elif (type == bp.SHUTDOWN):
            self.__handle_shutdown(flags)
        else:
            util.debug("Malformed Message")

    def __handle_data_segment(self, flags):
        util.debug("Got Data Segment")
        pack_length = tcpcl.parse_data_seg(self.link.file_int)
        util.debug("FLAGS %d LENGTH %d" % (flags, pack_length) )
        #we assume that the first packet
        #contains all of the primary block and preamble
        message = self.link.file_int.read(pack_length)
        if (flags & bp.START):
            util.debug("New bundle transmission")
            ack = tcpcl.parse_new_bundle(message, pack_length)
        else:
            util.debug("Data bundle")
            ack = tcpcl.parse_data_bundle(message, pack_length)
        if (flags & bp.END):
            util.debug("End this bundle")
            self.bundle_queue.put(tcpcl.parse_end_bundle())
        self.master.send_ack(ack)
 
    def __handle_ack_segment(self, flags):
        util.debug("Got ack segment")
        ack_len = tcpcl.parse_ack(self.link.file_int)
        util.debug("Got ack for %d length packet" % ack_len)
    
    def __handle_refuse_bundle(self, flags):
        util.debug("Got Refuse Bundle")

    def __handle_keepalive(self, flags):
        util.debug("Got keepalive")

    def __handle_shutdown(self, flags):
        util.debug("Shutdown message")


class DtnDaemon(threading.Thread):
    
    def __init__(self, link, host, port, local_eid, 
                 timeout=DEFAULT_KEEPALIVE):
        threading.Thread.__init__(self)
        self.link = link
        self.link.socket = socket.socket(socket.AF_INET, 
                                         socket.SOCK_STREAM)
        self.host = host
        self.port = port
        self.local_eid = local_eid
        self.default_keepalive = timeout
        self.keepalive = self.default_keepalive
        self.dead = False
        self.last_keepalive = time.time()
        self.bundle_queue = Queue.Queue(0) #thread safe
        self.really_dead = False
        
    def exit(self):
        util.debug("Told to shut down")
        #should send the shutdown packet...
        self.die()
        #we'll need more complex logic here later
        self.really_dead = True

    def run(self):
        self.__start_dtn()
        while(1): 
            if (self.really_dead):
                return
            util.debug("In DTN")
            if (self.dead):
                self.__start_dtn() #this blocks until the connection is up
                self.dead=False
            #if we've missed 10 keepalives, assume the connection has gone down
            elif (self.last_keepalive < (time.time() - (KEEPALIVES_MISSED_TILL_DEATH * self.keepalive))):
                util.debug("Missing keepalives, dying..")
                self.die()
            else:
                try:
                    self.link.socket.send(self.bundle_queue.get(block=True, timeout=2*self.keepalive))
                except: #empty exception               
                    pass
            
    def die(self):
        self.dead = True
        self.ka_thread.die = True
        self.listener.die = True
        self.keepalive = self.default_keepalive

    def send_string(self, destination, string):
        self.__queue_bundle(destination, StringPayload(string))   

    def send_file(self, destination, file):
        self.__queue_bundle(destination, FilePayload(file))   

    #returns the status, IE are there packets waiting to be sent
    def empty(self):
        return self.bundle_queue.empty()

    def recv(self, timeout):
        try:
            bundle = self.listener.bundle_queue.get(block=True, timeout=timeout)
            return bundle
        except: #empty exception
            return None

    def __queue_bundle(self, destination, payload):
        b = Bundle()
        b.payload = payload
        b.source = self.local_eid
        b.dest = destination
        b.bundle_flags |= bp.BUNDLE_SINGLETON_DESTINATION
        tcpcl.gen_bundle(b, self.bundle_queue)
        #should wake self up here as well

    def send_ack(self, length):
        self.bundle_queue.put(tcpcl.gen_ack(length))

    def __start_dtn(self):
        while(1):
            if (self.really_dead):
                return
            util.debug("In start DTN")
            try:
                self.link.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.link.socket.connect((self.host, self.port))
                self.link.file_int = self.link.socket.makefile('r+b', tcpcl.BUFFER_SIZE)
                self.keepalive = tcpcl.connect(self.link,self.local_eid,self.keepalive)
                break
            except Exception, e:
                print("Connect Failed ")
                res = sys.exc_info()
                print(res)
                traceback.print_tb(res[2])
                time.sleep(RETRY_CONNECTION_TIMER)
        self.ka_thread = Keepaliver(self.link, self.keepalive, self)
        self.listener = Listener(self.link, self)
        self.ka_thread.start()
        self.listener.start()
        self.last_keepalive = time.time()

if (__name__ == "__main__"):
    from link import *
    if (len(sys.argv) > 1):
        util.DEBUG = True
    l = Link('test-link')
    dtn = DtnDaemon(l, "localhost", 4556, "dtn://test.dtn/")
    dtn.start()
    while (True):
        bundle = dtn.recv(10)
        while (bundle):
            print("Received bundle!")
            print (bundle.tostring())
            bundle = dtn.recv(10)
        dtn.send_string("dtn://vmphone2.dtn/foo", "test")
        dtn.send_string("dtn://vmphone2.dtn/foo", "testforreals")
        dtn.send_file("dtn://vmphone2.dtn/file", "/tmp/val.wav")
        print("sent!")
