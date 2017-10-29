from distutils.core import setup, Extension

setup(name="dtn",
      version="0.2.2", 
      description="DTN Python Implementation",
      author="Kurtis Heimerl",
      author_email="kheimerl@cs.berkeley.edu",
      url="http://www.dtnrg.org",
      packages=["dtn"],
      scripts=["apps/pydtnsend.py"]
      )
