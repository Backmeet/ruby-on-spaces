# Ruby on Spaces

**Ruby on Spaces** is a tiny experimental language written in Python.  
It started as a learning project for exploring **interpreters, parsing, and language design**, and can serve as a skeleton for building your own language — whether you’re aiming for the next Rust, Zig, or just want to play around with language concepts.

It’s **minimal, hackable, and verbose by design**. The goal isn’t clean syntax or speed, but to show how a language can be built from the ground up with just Python’s standard library (plus `pygame` for optional graphics).

---

## Features
- Fully interpreted in Python
- Syntax loosely inspired by Ruby (blocks, `def`, `end`, etc.)
- Two core types: `number` (int/float) and `string`
- Mutable variables (backed by Python dictionaries)
- Basic control flow (`if`, `while`)
- Functions with arguments and `return`
- Simple I/O (`print`, `input`)
- Text/graphics support through a lightweight Pygame window system

---

## Example Code
```ruby
# variables
var new x 10
var new y 20

# math
var math x + y = result
print "Sum:" result

# control flow
if begin result
    print "Result is non-zero"
if end

# functions
def greet name
    print "Hello," name
endfunc

greet "World"

