import e32db
import filedump

DB_LOC = filedump.gettempdir() + u"\\bundledb"

#encapsulates the DB properties for pydtn
#used for client-side interactions
#maybe I should subclass the real DBMS object?
class Dbms(object):

    def __init__(self):
        self.db = e32db.Dbms()
        try:
            self.db.open(DB_LOC)
        except:#doesn't exist
            self.db.create(DB_LOC)
            self.db.open(DB_LOC)
        create = u"create table bundles \
(id counter, \
bundle_flags integer, \
priority integer, \
srr_flags integer, \
source varchar, \
dest varchar, \
replyto varchar, \
custodian varchar, \
prevhop varchar, \
creation_secs integer, \
creation_seqno integer, \
expiration integer, \
payload_file varchar, \
time integer)"

        create_send_bundles = u"create table outbundles \
(id counter, \
dest varchar, \
payload_file varchar, \
sent integer)"
        for com in [create, create_send_bundles]:
            self.db.begin()
            try:
                self.db.execute(com)
                self.db.commit()
            except Exception, e: #already created exception
                self.db.rollback()
                
    def begin(self):
        self.db.begin()

    def execute(self, command):
        self.db.execute(command)

    def commit(self):
        self.db.commit()

    def rollback(self):
        self.db.rollback()

    #returns a e32db.Db_view object
    def gen_view(self, command):
        view = e32db.Db_view()
        view.prepare(self.db, command)
        return view
