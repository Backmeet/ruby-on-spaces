import sys, timeit, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ver1.2"))

from ruby import runRuby, StableHash

fib = '''
def fib 1
var a = 0
var b = 1
while begin 
var c = a + b
var a = b
var b = c
var arg1 = arg1 - 1
while end arg1
endfunc
call fib 1000
'''

print(f"{timeit.timeit(lambda: runRuby(fib), number=100)/100}sec")

