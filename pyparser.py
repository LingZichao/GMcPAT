import m5

from m5.util import *

def analyze() :
    global _instantiated

    if _instantiated == False:
        fatal("m5.instantiate() not called.")

    root = m5.objects.Root.getInstance()

    if not root:
        fatal("Need to instantiate Root() before calling instantiate()")


    for obj in root.descendants() :
        pass
