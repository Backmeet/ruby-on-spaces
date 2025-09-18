// ================================
// RUBY-ON-SPACES: FULL TEST SUITE
// Paste into your interpreter as the main script.
// Many tests print markers like [OK] or [ERR CAUGHT] so you can scan results.
// ================================

print "=== TEST SUITE START ==="

// --- SECTION: basic arithmetic & precedence ----------------
print "\n-- arithmetic & precedence --"
var a = 3 + 4 * 2
print "a_expected=11 ->", a

var b = (3 + 4) * 2
print "b_expected=14 ->", b

var c = 10 / 4
print "c_expected=2.5 ->", c

var d = 10 // 4
print "d_expected=2 ->", d

var e = 2 ** 3
print "e_expected=8 ->", e

var f = 5 ^ 2
print "f (xor) ->", f

var g = 6 & 3
print "g (and) ->", g

var h = 5 | 2
print "h (or) ->", h

var eq = 5 == 5
print "eq expected 1 ->", eq

var neq = 5 != 2
print "neq expected 1 ->", neq

var ge = 5 >= 6
print "ge expected 0 ->", ge

var le = 5 <= 5
print "le expected 1 ->", le

var andtest = 1 and 0
print "andtest expected 0 ->", andtest

var ortest = 0 or 2
print "ortest expected 2 ->", ortest

var precedence = 3 + 4 * 2 - 1 // 2
print "precedence result ->", precedence

// unary & other ops
var neg = -5
print "neg expected -5 ->", neg

var not0 = not 0
var not1 = not 2
print "not0 expected 1 ->", not0, " not1 expected 0 ->", not1

var lenstr = len("hello")
print "lenstr expected 5 ->", lenstr

var lenlist = len([1, 2, 3])
print "lenlist expected 3 ->", lenlist

// trig / sqrt / cbrt
var s = sqrt 16
print "sqrt 16 expected 4 ->", s

var cb = cbrt 27
print "cbrt 27 expected 3 ->", cb

var si = sin 0
var co = cos 0
var ta = tan 0
print "sin(0), cos(0), tan(0) ->", si, co, ta

// bitwise ~
var tw = ~ 5
print "~5 ->", tw

// --- SECTION: functions (definition + calls, expression & statement) ---
print "\n-- functions --"

// simple add/mul functions (define before use in expressions)
def add(a, b)
    return a + b
endfunc

def mul(a, b)
    return a * b
endfunc

def echo(s)
    print "ECHO->", s
    return 0
endfunc

def factorial(n)
    if n <= 1
        return 1
    if end
    var rem = factorial(n - 1)
    return n * rem
endfunc

// call as expression
var sumexpr = add(2, 3) + 10
print "sumexpr expected 15 ->", sumexpr

// call as statement
var t0 = add(7, 8)
print "add as statement returned ->", t0

// nested call & recursion
var fact5 = factorial(5)
print "factorial(5) expected 120 ->", fact5

// function side effects & globals: function modifies a global variable
var GLOBAL_X = 0
def setX(v)
    var GLOBAL_X = v
    // also set global via variable name (intentional)
    return 0
endfunc
setX(42)
print "GLOBAL_X now ->", GLOBAL_X

// calling with wrong arg count (should be caught)
try
    // too many args
    var z = add(1,2,3)
except
    print "[ERR CAUGHT] wrong arg-count for add:", Error
done

// --- SECTION: lists & list ops --------------------------------
print "\n-- lists & list ops --"

// define functions referenced inside lists (must exist before list literal if parser resolves immediately)
def lf_add(a, b)
    return a + b
endfunc

def lf_print(x)
    print "lf_print:", x
    return 0
endfunc

// list with numbers and nested lists
var Lnums = [1, 2, 3]
var Lnested = [ [1, 2], [3, 4], "foo" ]
print "Lnums", Lnums
print "Lnested", Lnested

// list set/append/extend/pop
list append Lnums 99
print "Lnums after append expected [1,2,3,99] ->", Lnums

list extend Lnums [7,8]
print "Lnums after extend ->", Lnums

list set Lnums 0 to 42
print "Lnums after set index0->42 ->", Lnums

list pop Lnums 2
print "Lnums after pop index2 ->", Lnums, " return:", return

// attempt invalid pop index (wrapped in try)
try
    list pop Lnums 999
except
    print "[ERR CAUGHT] pop out of range ->", Error
done

// extend with non-list should error
try
    list extend Lnums 5
except
    print "[ERR CAUGHT] extend non-list ->", Error
done

// create a list that contains function references (function names)
var funcList = [ lf_add, lf_print ]
print "funcList (should contain callable refs):", funcList

// list call (recursive) — call lf_add from list
// chain: funcList.lf_add 3 4
list call funcList.lf_add 3 4
print "after list call funcList.lf_add (return in 'return') ->", return

// nested list with function inside
var nestedFuncs = [ [ lf_add ] ]
print "nestedFuncs ->", nestedFuncs
// call nestedFuncs.lf_add 5 6  (should drill down)
list call nestedFuncs.lf_add 5 6
print "nested list call ->", return

// --- SECTION: list-call early stop (if function found early) -------
print "\n-- list-call early stop --"
// create list where an intermediate element is a function name
var earlyList = [ lf_print, [lf_add] ]
print "earlyList ->", earlyList
// chain: earlyList.lf_print (should call lf_print without drilling deeper)
list call earlyList.lf_print "called-early"
print "after earlyList.lf_print ->", return

// --- SECTION: if / while / for --------------------------------
print "\n-- if / while / for --"
// if false skip body
if 0
    print "SHOULD NOT PRINT"
if end
print "if skip ok"

// while loop test
var ctr = 0
while ctr < 3
    print "while loop ctr=", ctr
    var ctr = ctr + 1
while end
print "while finished ctr=", ctr

// for loop test: for begin : i; 0; i < 3; 1 ... for end
for begin : i; 0; i < 3; 1
    print "for i=", i
for end

// string for-with-non-number test (edge): iterate via sentinel
for begin : s; "X"; s != "XX"; "X"
    print "for-s:", s
    var s = s + "X"
for end

// --- SECTION: expression parsing & operator edge-cases -------------
print "\n-- expression parsing edge cases --"
var expr1 = (2 + 3) * (4 - 1) / (1 + 1)
print "expr1 ->", expr1

var mix = add(1, mul(2,3)) + factorial(3)
print "mix ->", mix

// function call inside list literal (should store func token/tuple)
var listWithFunc = [ lf_add, 1, "str", [ lf_print ] ]
print "listWithFunc ->", listWithFunc

// --- SECTION: convert / rnd / delay / error / system --------------
print "\n-- convert / rnd / try/except --"

// convert number -> str
var xnum = 123
convert xnum xstr
print "convert int->str xstr type? ->", xstr

// convert str->num good and bad
convert "456" numFromStr
print "convert '456' ->", numFromStr

try
    convert "not_a_number" badconv
except
    print "[ERR CAUGHT] convert bad ->", Error
done

// rnd tests
rnd int RNDINT 1 10
print "random int ->", RNDINT
rnd str RNDSTR 5
print "random str len should be 5 ->", len(RNDSTR)

// try/except/done test: intentionally throw and catch
try
    error "boom-test"
except
    print "[CAUGHT] try/except success ->", Error
done

// nested try: re-raise handling
try
    try
        error "nested"
    except
        // inside inner except – set Error
        print "inner except Error ->", Error
    done
except
    print "outer except ->", Error
done

// --- SECTION: import / export --------------------------------------
print "\n-- import / export --"
// we will import 'mylib' provided via the source_dict argument to runRuby
import "mylib"
// Call the exported lib function
var libres = lib_add(10, 20)
print "lib_add(10,20) ->", libres
lib_print "imported-library-works"

// --- SECTION: tricky edge cases ------------------------------------
// 1) unknown variable
try
    print unknown_var
except
    print "[ERR CAUGHT] unknown var ->", Error
done

// 2) division by zero
try
    var z = 5 / 0
except
    print "[ERR CAUGHT] division by zero ->", Error
done

// 3) malformed list set index type
try
    list set Lnums "one" to 5
except
    print "[ERR CAUGHT] list set bad index ->", Error
done

// 4) call undefined function
try
    not_defined(1)
except
    print "[ERR CAUGHT] undefined fn ->", Error
done

// 5) check len/pop/index off-by-one
var s = "abc"
print "index0..2", s index 0, s index 1, s index 2
try
    print s index 3
except
    print "[ERR CAUGHT] index out ->", Error
done

// 6) check 'not' on strings and lists
var notstr = not ""
var notlist = not []
print "notstr, notlist ->", notstr, notlist

// --- FINISH ---
print "\n=== TEST SUITE FINISHED ==="
