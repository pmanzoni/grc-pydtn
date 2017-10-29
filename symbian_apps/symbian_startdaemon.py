from pydtn import symbian_dtndaemon, util
from pydtn.client_db import Dbms
import e32
import time
import thread
import os

dtn_daemon = symbian_dtndaemon.DtnDaemon("vmphone2.cs.berkeley.edu", 4556, "dtn://foo.dtn/foo")
util.exception_wrapper(dtn_daemon.start)

util.set_tofile(False)

RECEIVING_SLEEP = 6
SENDING_SLEEP = 6

def receiving_thread():
    db = Dbms()   
    while(True):
        #hacky for now, the recv call needs to block
        e32.ao_sleep(RECEIVING_SLEEP)
        bundle = dtn_daemon.recv(0)
        if (bundle):
            db.begin()
            #maybe I should be cleaning the bundles of bad stuff like '
            command = u"insert into bundles (bundle_flags, priority, srr_flags, \
source, dest, replyto, custodian, prevhop, creation_secs, creation_seqno, \
expiration, payload_file, time) values (%d, %d, %d, '%s', '%s', '%s', '%s', \
'%s', %d, %d, %d, '%s', %d)" % (bundle.bundle_flags, bundle.priority,
                                bundle.srr_flags, bundle.source,
                                bundle.dest, bundle.replyto,
                                bundle.custodian, bundle.prevhop,
                                bundle.creation_secs, bundle.creation_seqno,
                                bundle.expiration, bundle.payload.filename,
                                time.time())
            db.execute(command)
            db.commit()
        else:
            pass

def sending_thread_main():
    db = Dbms()
    
    while(True):
        e32.ao_sleep(SENDING_SLEEP)
        #we're going to serialize these, waiting for the ack before sending another
        command = u"select * from outbundles where sent = 0"
        dbv = db.gen_view(command)
        if (dbv.count_line() > 0):
            print ("%d messages waiting to be sent" % dbv.count_line())
            dbv.first_line()
            dbv.get_line()
            counter = int(dbv.col(1))
            dest = str(dbv.col(2))
            file = str(dbv.col(3))
            dtn_daemon.send_file(dest, file)
            #would wait here for ack
            command = u"delete from outbundles where id=%d" % counter
            db.begin()
            db.execute(command)
            db.commit()
            os.remove(file)

def sending_thread():
    util.exception_wrapper(sending_thread_main)  

thread.start_new_thread(sending_thread, ())

util.exception_wrapper(receiving_thread)