# Ruby on Spaces

**Ruby on Spaces** is a tiny experimental language written in Python.  
It started as a learning project for exploring **interpreters, parsing, and language design**, and can serve as a skeleton for building your own language — whether you’re aiming for the next c++, python or just want to play around with language concepts.

It’s **minimal, hackable, and verbose by design**. The goal isn’t clean syntax or speed, but to show how a language can be built from the ground up with just Python’s standard library (plus `pygame` for optional graphics).

---

## Features
- Fully interpreted in Python
- Syntax loosely inspired by Ruby (blocks, `def`, `end`, etc.)
- core types: `number` (int/float), `string`, `list`, `dict`, `bool`, `null`
- Mutable variables (backed by Python dictionaries)
- Basic control flow (`if`, `while`, `for`)
- Functions with arguments and `return`
- Simple I/O (`print`, `input` ... (made my injecting python))
---

## Example Code
```ruby
# variables
x = 10
y = 20
# math
z = x + y
print "Sum:" z

# control flow
if (10 == 2)
print("10 is == to 2! (very much worng)")
end

while (true)
print("yes")
end

for x in [1, 2, 3]
print(x)
end

for (x = 0; x != 0; x++)
print(x)
end

# functions
def greet(name)
    print("hello! " + str(name))
end

greet ("World")
