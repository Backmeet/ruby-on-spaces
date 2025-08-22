// mylib (to exercise import/export)
export functions lib_add lib_print

def lib_add(a, b)
    return a + b
endfunc

def lib_print(s)
    print "mylib:", s
    return 0
endfunc
