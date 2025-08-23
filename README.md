# Ruby on Spaces

**Ruby on Spaces** is a small experimental programming language built entirely in Python.  
It’s designed as a learning project in **language design, parsing, and interpreter building**, while still being usable for toy projects, scripting, or experimentation.

This language is **minimal, hackable, and deliberately verbose**.  
It’s not about performance — it’s about showing how a working interpreter can be constructed, extended, and modified.

---

## Overview

- **Implemented in**: Pure Python (no external libraries except optional `pygame` for demos).  
- **Execution model**: Lex → Parse (Pratt parser) → AST → Tree-walking interpreter.  
- **Syntax style**: Ruby-like with `def`, `end`, `while`, `if`, but Python-like in strictness.  
- **Core philosophy**: Easy to extend — you can add new syntax, keywords, or built-ins by editing one file.

---

## Core Features

- **Data types**  
  - `number` → integers and floats  
  - `string` → double quoted, supports escape sequences  
  - `bool` → `true`, `false`  
  - `null` → `null`  
  - `list` → `[1, 2, 3]`  
  - `dict` → `{ key: value, "literal": 123 }`  

- **Variables**  
  - Dynamic, mutable, global by default  
  - Assigned with `=`  

- **Operators**  
  - Arithmetic: `+`, `-`, `*`, `/`  
  - Comparisons: `<`, `>`, `<=`, `>=`, `==`, `!=`  
  - Unary: `+x`, `-x`  
  - Indexing: `list[0]`, `dict["key"]`  
  - Property access sugar: `obj.key`  

- **Control flow**  
  - `if` … `end`  
  - `while (cond)` … `end`  
  - `for x in [list]` … `end`  
  - C-style `for (init; cond; step)` … `end`  

- **Functions**  
  - Define with `def name(params)` … `end`  
  - Return with `return expr`  
  - Functions are first-class values  
  - Method defs: `def obj.method(args)` … `end` (stored in dicts like methods)

- **Built-ins**  
  - `print(x, y, ...)`  
  - `len(x)`  
  - `range(n)` / `range(start, end)` / `range(start, end, step)`  

- **Interop with Python**  
  - You can register any Python function directly as a builtin via `register_pyfunc(env, "name", func)`.

---

## Example Programs

```ruby
# Variables and math
x = 10
y = 20
z = x + y
print("Sum:", z)

# Conditionals
if (x < y)
    print("x is less than y")
end

# While loop
while (x < 15)
    print("x =", x)
    x = x + 1
end

# For-in loop
for item in [1, 2, 3]
    print("Item:", item)
end

# C-style for loop
for (i = 0; i < 3; i = i + 1)
    print("i:", i)
end

# Functions
def greet(name)
    print("Hello,", name)
end
greet("World")

# Methods on objects
person = { name: "Alice" }
def person.greet(self)
    print("Hi, I'm", self.name)
end
person.greet()
```
## Syntax Reference

- **Statements**
  - Expression statements: `foo(1, 2)`  
  - Assignment: `x = expr`  
  - Function definition: `def name(args) … end`  
  - Method definition: `def obj.method(args) … end`  
  - Return: `return expr`  
  - Control: `if`, `while`, `for-in`, `for-c`  

- **Expressions**
  - Literals: `123`, `12.5`, `"text"`, `true`, `false`, `null`  
  - Lists: `[a, b, c]`  
  - Dicts: `{ key: value, "literal": expr }`  
  - Function calls: `f(x, y)`  
  - Indexing: `arr[0]`  
  - Property: `obj.key`  

---

## Runtime Model

- **Environments (scopes)**:  
  - Each function call creates a new `Env` (lexical scope).  
  - Variables are mutable; assignments update the nearest enclosing scope.  

- **Functions**:  
  - Represented by the `Function` class.  
  - Normal functions: run AST in a new local environment.  
  - Escape functions: wrap a Python function for builtin interop.  

- **Return**: implemented using exceptions (`ReturnSignal`).  

- **Truthiness**:  
  - `false` and `null` are falsy  
  - everything else is truthy  

---

## Extending the Language

1. **Add a builtin function (Python interop)**  
   ```python
   def py_upper(args_wrapped):
       s = unwrap_from_py(args_wrapped[0])
       return wrap_for_py(s.upper())

   env = make_global_env()
   register_pyfunc(env, "upper", py_upper)
    ```
2. **Add new keywords / syntax**  
   - Update `KEYWORDS` in the lexer  
   - Add parsing rules in `Parser.parse_stmt` or `Parser.nud/led`  
   - Extend `exec_stmt` / `eval_expr` with runtime behavior  

3. **Add operators**  
   - Modify `Parser.lbp` (precedence table)  
   - Update `Parser.led` to evaluate new operator AST  
   - Extend `eval_expr` with execution logic  

---

## Running

- **As a file**:  
  ```bash
  python ruby.py program.rbs
  ```
- **Via the REPL**
  ```bash
  python ruby.pu
  >>> x = 5
  >>> def sq(n) return n*n end
  >>> print(sq(x))
  ```


## Grammer
```
program        ::= block EOF
block          ::= { stmt (NL | ";")* } [ "end" ]

stmt           ::= exprstmt
                 | assign
                 | defstmt
                 | methoddef
                 | returnstmt
                 | ifstmt
                 | whilestmt
                 | forstmt

exprstmt       ::= expression
assign         ::= lvalue "=" expression
defstmt        ::= "def" ID "(" [paramlist] ")" block "end"
methoddef      ::= "def" ID "." ID "(" [paramlist] ")" block "end"
returnstmt     ::= "return" expression
ifstmt         ::= "if" expression block "end"
whilestmt      ::= "while" "(" expression ")" block "end"
forstmt        ::= "for" "(" stmt ";" expression ";" stmt ")" block "end"
                 | "for" ID "in" expression block "end"

paramlist      ::= ID { "," ID }

expression     ::= primary { infixop expression }
primary        ::= NUMBER
                 | STRING
                 | "true"
                 | "false"
                 | "null"
                 | ID
                 | "(" expression ")"
                 | listliteral
                 | dictliteral
                 | "-" expression
                 | "+" expression

listliteral    ::= "[" [ expression { "," expression } ] "]"
dictliteral    ::= "{" [ dictentry { "," dictentry } ] "}"
dictentry      ::= (STRING | ID) ":" expression

infixop        ::= "+" | "-" | "*" | "/"
                 | "<" | ">" | "<=" | ">="
                 | "==" | "!="
                 | "." | "[" expression "]"
                 | call

call           ::= "(" [ expression { "," expression } ] ")"
lvalue         ::= ID | prop | index
prop           ::= expression "." ID
index          ::= expression "[" expression "]"
```
 