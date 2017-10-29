#this class exists to get around pys60 not having
#the tempfile library. We'll wrap it in normal usage
#and generate our own on s60

import os
if (os.name == "e32"): #symbian
    
    import random
    import os

    TEMP_LOC = u"C:\\Data\\pydtn"
    
    tag = u"tmp"

    if not (os.path.exists(TEMP_LOC)):
        os.makedirs(TEMP_LOC)

    def gettempdir():
        return TEMP_LOC

    def mkstemp():
        #not guaranteed to be unique...
        loc = TEMP_LOC + u"\\" + tag + (str(random.random())[2:])
        return (None, loc)
    
else: #everyone else who has actually implemented this
    import tempfile

    def mkstemp():
        return tempfile.mkstemp()

    def gettempdir():
        return tempfile.gettempdir()