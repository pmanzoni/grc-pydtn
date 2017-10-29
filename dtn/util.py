tofile = True #if debug, print to screen, else log it in a file

import os
import traceback
import sys

def array_into_string(array):
        return ''.join(map(chr,array))

def tb_debug(tb):
        tb_res = ''
        for line in traceback.format_tb(tb):
                tb_res += line
        debug(tb_res)

def set_tofile(file):
        global tofile
        tofile = file

'''wraps any function without args with
an exception printing mechanism'''
def exception_wrapper(func):
        try:
                func()
        except:
                res = sys.exc_info()
                debug(res)
                tb_debug(res[2])
                
if (os.name == "e32"): #symbian
        import time
        LOG_LOC = u"C:\\Data\\pydtn.log"

        #this is dumb, but I can't share file handles across threads.
        #it's probably not a bottleneck so fuck it anyhow. 
        def debug(obj):
                global tofile
                if not(tofile):
                        print (obj)
                else:
                        fh = open(LOG_LOC, 'a')
                        fh.write(time.strftime("%H:%M:%S, %m/%d/%Y") + " " + str(obj) + "\n")
                        fh.close()

else:
        import logging

        LOG_LOC = "./pydtn.log"
        logging.basicConfig(filename=LOG_FILENAME,level=logging.DEBUG,)
        logger = logging.getLogger('PyDTN Logger')

        def debug(string):
                global tofile
                if not(tofile):
                        print (string)
                else:
                        logger.debug(string)