# RUBY ON SPACES
A Python interpreted language that is a small project I made as a way to help anyone get into making languages. This language is a skeleton for almost any language, whether that may be the new Rust or Zig.

It uses only the standard library for Python and Pygame for window management.
It is meant to be more barebones, and the actual code that it runs is not meant to be the most readable.
It's also as verbose as it needs to be. It also mainly uses all the keywords Ruby has, so you can just use the widely implemented code blocks feature and mask Ruby on spaces code as Ruby.

The basic keywords are shown below, and some small explanations on how they work
```ruby
var new <name> <value(not needed defaults to 0)>
var set <dst> = <src>
var math <a> <opreation> <b> = <result varibles>

if begin <value>
if end

input <prompt> <varible to store text>

convert <value> // takes a value like int or float and makes it a string and vice versa. Also, there are only 2 types: number(int|float) and string

print <value1> <value2> ... <valueN>
flush <value1> <value2> ... <valueN> // prints like a normal print, but it does not go to a new line it just moves the printing pointer back the len(value printed)
// so like a print() and a os.system("cls") in one cmd


while begin
while end <value>

def <name> <number or arguments>
return <value>

window init <width[number]> <height[number]>
window fil r g b
window update // updates only the event loop
window flip // updates screen
window event <name of event> <varible to store event value>
// event names till now [quit]
window draw line x1 y1 x2 y2 r g b thickness
window draw rect x1 y2 x2 y2 r g b
```

All variables are mutable at least that's what I think Python dict items are (god help us with low-level programming)
