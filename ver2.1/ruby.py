import re, types, time
import sys, copy, os

# ===== Lexer =====
TOKEN_SPEC = [
    ("NUMBER",   r'\d+\.\d+|\d+'),
    ("STRING",   r'"([^"\\]|\\.)*"'),
    ("ID",       r'[A-Za-z_][A-Za-z0-9_]*'),
    ("OP",       r'==|!=|<=|>=|\+|-|\*|/|<|>|=|\.|,|:|;|\(|\)|\[|\]|\{|\}'),
    ("NL",       r'\r?\n'),
    ("WS",       r'[ \t]+'),
    ("MISMATCH", r'.'),
]
TOKEN_RE = re.compile("|".join(f"(?P<{n}>{p})" for n, p in TOKEN_SPEC))

KEYWORDS = {
    "def", "return", "end", "while", "for", "in", "true", "false", "null", "if", "import"
}

class Token:
    def __init__(self, kind, text, line, col):
        self.kind = kind
        self.text = text
        self.line = line
        self.col = col
    def __repr__(self):
        return f"Token({self.kind},{self.text!r}@{self.line}:{self.col})"

def lex(src):
    line = 1
    col = 1
    toks = []
    for m in TOKEN_RE.finditer(src):
        kind = m.lastgroup
        text = m.group()
        if kind == "WS":
            col += len(text)
            continue
        if kind == "NL":
            toks.append(Token("NL", "\n", line, col))
            line += 1
            col = 1
            continue
        if kind == "ID" and text in KEYWORDS:
            toks.append(Token(text, text, line, col))
        elif kind == "ID":
            toks.append(Token("ID", text, line, col))
        elif kind == "NUMBER":
            toks.append(Token("NUMBER", text, line, col))
        elif kind == "STRING":
            toks.append(Token("STRING", text, line, col))
        elif kind == "OP":
            toks.append(Token(text, text, line, col))
        elif kind == "MISMATCH":
            raise SyntaxError(f"Unexpected character {text!r} at {line}:{col}")
        col += len(text)
    toks.append(Token("EOF", "EOF", line, col))
    return toks

# ===== Parser (Pratt for expressions) =====

class Parser:
    def __init__(self, tokens):
        self.toks = tokens
        self.i = 0
        self.cur = self.toks[self.i]

    def advance(self):
        self.i += 1
        if self.i < len(self.toks):
            self.cur = self.toks[self.i]
        else:
            self.cur = Token("EOF", "EOF", -1, -1)


    def match(self, *kinds):
        if self.cur.kind in kinds or self.cur.text in kinds:
            t = self.cur
            self.advance()
            return t
        return None

    def expect(self, *kinds):
        t = self.match(*kinds)
        if t is None:
            want = " or ".join(kinds)
            raise SyntaxError(f"Expected {want} at {self.cur.line}:{self.cur.col}, got {self.cur.kind} {self.cur.text!r}")
        return t

    def skip_semi_nl(self):
        while self.match(";", "NL"):
            pass

    def parse(self):
        body = self.parse_block_until_end(allow_top_level=True)
        return {"type":"block", "stmts": body}

    def parse_block_until_end(self, allow_top_level=False, terminators=("end",)):
        stmts = []
        self.skip_semi_nl()
        while self.cur.kind != "EOF":
            if self.cur.kind == "NL" or self.cur.text == ";":
                self.advance()
                continue
            if self.cur.text in terminators:
                break
            stmts.append(self.parse_stmt())
            self.skip_semi_nl()
            if allow_top_level and self.cur.kind == "EOF":
                break
        if "end" in terminators:
            self.expect("end")
        return stmts

    def parse_stmt(self):
        if self.cur.text == "def":
            return self.parse_def()
        if self.cur.text == "return":
            self.advance()
            expr = self.parse_expression()
            return {"type":"return", "expr":expr}
        if self.cur.text == "while":
            self.advance()
            self.expect("(")
            cond = self.parse_expression()
            self.expect(")")
            self.skip_semi_nl()
            body = self.parse_block_until_end(terminators=("end",))
            return {"type":"while", "cond":cond, "body":body}
        if self.cur.text == "if":
            self.advance()
            cond = self.parse_expression()
            body = self.parse_block_until_end()
            return {"type":"if", "cond":cond, "body":body}
        if self.cur.text == "import":
            self.advance()
            fileName = self.parse_expression()
            return {"type":"import", "fileName":fileName}
        if self.cur.text == "del":
            self.advance()
            expr = self.parse_expression()
            return {"type":"del", "expr":expr}
        if self.cur.text == "for":
            return self.parse_for()
        # assignment or expr-stmt
        lhs = self.parse_expression()
        if self.cur.text == "=" and lhs["type"] in ("var", "index", "prop"):
            self.advance()  # consume '='
            expr = self.parse_expression()
            return {"type":"assign", "target": lhs, "expr": expr}
        # otherwise treat as expression-statement
        return {"type":"exprstmt", "expr": lhs}

    def parse_def(self):
        self.expect("def")

        # First identifier
        name1 = self.expect("ID").text

        # Check if this is obj.method
        if self.cur.text == ".":
            self.advance()
            name2 = self.expect("ID").text
            full = {"type":"methoddef", "obj":name1, "name":name2}
        else:
            full = {"type":"def", "name":name1}

        self.expect("(")
        params = []
        if not self.match(")"):
            while True:
                p = self.expect("ID").text
                params.append(p)
                if self.match(")"):
                    break
                self.expect(",")

        self.skip_semi_nl()
        body = self.parse_block_until_end(terminators=("end",))

        full.update({"params": params, "body": body})
        return full

    def parse_for(self):
        self.expect("for")
        if self.match("("):
            init = self.parse_stmt()
            self.expect(";")
            cond = self.parse_expression()
            self.expect(";")
            step = self.parse_stmt()
            self.expect(")")
            self.skip_semi_nl()
            body = self.parse_block_until_end(terminators=("end",))
            self.expect("end")
            return {"type":"for_c", "init": init, "cond": cond, "step": step, "body": body}
        else:
            var = self.expect("ID").text
            self.expect("in")
            iterable = self.parse_expression()
            self.skip_semi_nl()
            body = self.parse_block_until_end(terminators=("end",))
            return {"type":"for_in", "var": var, "iter": iterable, "body": body}

    def parse_lvalue_or_expr(self):
        expr = self.parse_expression()
        # If expression is a valid lvalue head, convert to lvalue structure
        return expr

    # Pratt parser with postfix (call, index, dot) and infix operators
    def parse_expression(self, rbp=0):
        t = self.cur
        self.advance()
        left = self.nud(t)
        while True:
            t = self.cur
            lbp = self.lbp(t)
            if rbp >= lbp:
                break
            self.advance()
            left = self.led(t, left)
        return left

    def nud(self, t):
        if t.kind == "NUMBER":
            if "." in t.text:
                return {"type":"number", "value": float(t.text)}
            else:
                return {"type":"number", "value": int(t.text)}
        if t.kind == "STRING":
            s = bytes(t.text[1:-1], "utf-8").decode("unicode_escape")
            return {"type":"string", "value": s}
        if t.kind == "ID":
            if t.text == "true":
                return {"type":"bool", "value": True}
            if t.text == "false":
                return {"type":"bool", "value": False}
            if t.text == "null":
                return {"type":"null"}
            return {"type":"var", "name": t.text}
        if t.text == "(":
            expr = self.parse_expression()
            self.expect(")")
            return expr
        if t.text == "[":
            # list literal
            items = []
            if not self.match("]"):
                while True:
                    items.append(self.parse_expression())
                    if self.match("]"):
                        break
                    self.expect(",")
            return {"type":"list", "items": items}
        if t.text == "{":
            # dict literal: key: value, keys can be string or identifier
            items = []
            if not self.match("}"):
                while True:
                    if self.cur.kind == "STRING":
                        k = self.cur.text
                        self.advance()
                        key_node = {"type":"string", "value": bytes(k[1:-1], "utf-8").decode("unicode_escape")}
                    else:
                        k = self.expect("ID").text
                        key_node = {"type":"string", "value": k}
                    self.expect(":")
                    val = self.parse_expression()
                    items.append((key_node, val))
                    if self.match("}"):
                        break
                    self.expect(",")
            return {"type":"dict", "items": items}
        if t.text == "-":
            expr = self.parse_expression(70)
            return {"type":"unary", "op":"-", "expr":expr}
        if t.text == "+":
            expr = self.parse_expression(70)
            return {"type":"unary", "op":"+", "expr":expr}
        raise SyntaxError(f"Unexpected token {t}")

    def lbp(self, t):
        if t.text in ("(", "[", "."):
            return 90
        if t.text in ("*", "/"):
            return 60
        if t.text in ("+", "-"):
            return 50
        if t.text in ("<", ">", "<=", ">="):
            return 40
        if t.text in ("==", "!="):
            return 35
        return 0

    def led(self, t, left):
        if t.text == "(":
            # function call
            args = []
            if not self.match(")"):
                while True:
                    args.append(self.parse_expression())
                    if self.match(")"):
                        break
                    self.expect(",")
            return {"type":"call", "func": left, "args": args}
        if t.text == "[":
            idx = self.parse_expression()
            self.expect("]")
            return {"type":"index", "object": left, "index": idx}
        if t.text == ".":
            name = self.expect("ID").text
            # sugar for dict property access
            return {"type":"prop", "object": left, "name": name}
        if t.text in ("*", "/", "+", "-","<",">","<=",">=","==","!="):
            right = self.parse_expression(self.lbp(t))
            return {"type":"binop", "op": t.text, "left": left, "right": right}
        raise SyntaxError(f"Unexpected infix {t.text}")

# ===== Runtime / Interpreter =====

class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value

def wrap_for_py(val):
    if val is None:
        return {"type":"null", "value": None}
    
    if isinstance(val, bool):
        return {"type":"bool", "value": val}
    
    if isinstance(val, (int, float)):
        return {"type":"number", "value": val}
    
    if isinstance(val, str):
        return {"type":"string", "value": val}
    
    if isinstance(val, (list, tuple)):
        return {"type":"list", "value": [wrap_for_py(v) for v in val]}
    
    if isinstance(val, dict):
        # plain dict values wrapped
        return {"type":"dict", "value": {k: wrap_for_py(v) for k, v in val.items()}}
    
    if isinstance(val, Function):
        return val

    if isinstance(val, type):
        members = {}
        for k, v in vars(val).items():
            if k.startswith("__") and k.endswith("__"):
                continue  # skip Python internals
            if callable(v):
                members[k] = {"type": "function", "value": Function(
                    name=k,
                    params=[],
                    body=None,
                    env=None,
                    escapeToPython=True,
                    pyfunc=lambda args, f=v: f(*[unwrap_from_py(a) for a in args])
                )}
            else:
                members[k] = wrap_for_py(v)  # recurse
        return {"type": "dict", "value": members}

    if hasattr(val, "__dict__"):
        members = {}
        for k, v in vars(val).items():
            if k.startswith("__") and k.endswith("__"):
                continue  # skip dunder attrs
            if callable(v):
                members[k] = {"type": "function", "value": Function(
                    name=k,
                    params=[],
                    body=None,
                    env=None,
                    escapeToPython=True,
                    pyfunc=lambda args, f=v: f(*[unwrap_from_py(a) for a in args])
                )}
            else:
                members[k] = wrap_for_py(v)  # recurse
        return {"type": "dict", "value": members}

    if isinstance(val, types.ModuleType):
        members = {}
        for k, v in vars(val).items():
            if k.startswith("__") and k.endswith("__"):
                continue  # skip internals
            if callable(v):
                members[k] = {"type": "function", "value": Function(
                    name=k,
                    params=[],
                    body=None,
                    env=None,
                    escapeToPython=True,
                    pyfunc=lambda args, f=v: f(*[unwrap_from_py(a) for a in args])
                )}
            else:
                members[k] = wrap_for_py(v)  # recurse
        return {"type": "dict", "value": members}
    
    raise TypeError(f"Unsupported type for wrap: {type(val)}")


def unwrap_from_py(obj):
    if isinstance(obj, Function):
        return obj
    t = obj.get("type")
    v = obj.get("value", None)
    if t == "null":
        return None
    if t == "bool":
        return bool(v)
    if t == "number":
        return float(v) if isinstance(v, float) or (isinstance(v, str) and "." in v) else int(v) if isinstance(v, int) else v
    if t == "string":
        return str(v)
    if t == "list":
        return [unwrap_from_py(x) for x in v]
    if t == "dict":
        return {k: unwrap_from_py(x) for k, x in v.items()}
    raise TypeError(f"Unsupported wrapped type from py: {t}")



class Env:
    def __init__(self, parent=None):
        self.parent = parent
        self.map = {}
    def get(self, name):
        if name in self.map:
            return self.map[name]
        if self.parent:
            return self.parent.get(name)
        raise NameError(f"Undefined variable {name} in context {''.join([f'\n{x}: {y}' for x, y in self.map.items()])}")
    def set_here(self, name, value):
        self.map[name] = copy.deepcopy(value)
    def set(self, name, value):
        scope = self.resolve_scope(name)
        if scope is None:
            self.map[name] = copy.deepcopy(value)
        else:
            scope.map[name] = copy.deepcopy(value)
    def remove_here(self, name):
        del self.map[name]
    
    def remove(self, name):
        scope = self.resolve_Scope(name)
        if scope is None:
            del self.map[name]
        else:
            del scope.map[name]

    def resolve_scope(self, name):
        if name in self.map:
            return self
        if self.parent:
            return self.parent.resolve_scope(name)
        return None

class Function:
    def __init__(self, name, params, body, env, escapeToPython=False, pyfunc=callable):
        self.name = name
        self.params = params
        self.body = body
        self.env = env
        self.escapeToPython = escapeToPython
        self.pyfunc = pyfunc
    def __call__(self, argvals):
        if self.escapeToPython:
            wrapped_args = [wrap_for_py(v) for v in argvals]
            res = self.pyfunc(wrapped_args, self.env)
            return unwrap_from_py(res)
        local = Env(self.env)
        for i, p in enumerate(self.params):
            local.set_here(p, argvals[i] if i < len(argvals) else None)
        try:
            exec_block(self.body, local)
        except ReturnSignal as rs:
            return rs.value
        return None

def is_truthy(v):
    return bool(v)

def get_indexed(obj, index):
    if isinstance(obj, list):
        if not isinstance(index, int):
            raise TypeError("List index must be integer")
        return obj[index]
    if isinstance(obj, dict):
        return obj[index]
    raise TypeError(f"Indexing only supported on list and dict not on {type(obj)} of value {obj}")

def set_indexed(obj, index, value):
    if isinstance(obj, list):
        if not isinstance(index, int):
            raise TypeError("List index must be integer")
        obj[index] = value
        return
    if isinstance(obj, dict):
        obj[index] = value
        return
    raise TypeError("Index assignment only supported on list and dict")

def eval_expr(node, env):
    t = node["type"]
    if t == "number":
        return node["value"]
    if t == "string":
        return node["value"]
    if t == "bool":
        return node["value"]
    if t == "null":
        return None
    if t == "var":
        return env.get(node["name"])
    if t == "list":
        return [eval_expr(x, env) for x in node["items"]]
    if t == "dict":
        d = {}
        for k_node, v_node in node["items"]:
            key = eval_expr(k_node, env)
            val = eval_expr(v_node, env)
            d[key] = val
        return d
    if t == "unary":
        v = eval_expr(node["expr"], env)
        if node["op"] == "-":
            return -v
        if node["op"] == "+":
            return +v
    if t == "binop":
        a = eval_expr(node["left"], env)
        b = eval_expr(node["right"], env)
        op = node["op"]
        if op == "+": return a + b
        if op == "-": return a - b
        if op == "*": return a * b
        if op == "/": return a / b
        if op == "<": return a < b
        if op == ">": return a > b
        if op == "<=": return a <= b
        if op == ">=": return a >= b
        if op == "==": return a == b
        if op == "!=": return a != b

    if t == "call":
        funcnode = node["func"]

        # If calling obj.method(...)
        if funcnode["type"] == "prop":
            obj = eval_expr(funcnode["object"], env)
            fn = obj.get(funcnode["name"])
            if not isinstance(fn, Function):
                raise TypeError("Attempt to call non-function property")
            args = [eval_expr(a, env) for a in node["args"]]
            # inject self as first arg
            return fn([obj] + args)

        # Normal call (just call expression result)
        fn = eval_expr(funcnode, env)
        if not isinstance(fn, Function):
            raise TypeError("Attempt to call non-function")
        args = [eval_expr(a, env) for a in node["args"]]
        return fn(args)

    if t == "index":
        obj = eval_expr(node["object"], env)
        idx = eval_expr(node["index"], env)
        return get_indexed(obj, idx)
    if t == "prop":
        obj = eval_expr(node["object"], env)
        if not isinstance(obj, dict):
            raise TypeError("Property access expects a dict")
        return get_indexed(obj, node["name"])
    return None

def as_lvalue(node, env):
    # returns a pair (getter, setter)
    t = node["type"]
    if t == "var":
        name = node["name"]
        def get():
            return env.get(name)
        def setv(v):
            env.set(name, v)
        return get, setv
    if t == "index":
        obj_node = node["object"]
        idx_node = node["index"]
        def get():
            obj = eval_expr(obj_node, env)
            idx = eval_expr(idx_node, env)
            return get_indexed(obj, idx)
        def setv(v):
            obj = eval_expr(obj_node, env)
            idx = eval_expr(idx_node, env)
            set_indexed(obj, idx, v)
        return get, setv
    if t == "prop":
        obj_node = node["object"]
        name = node["name"]
        def get():
            obj = eval_expr(obj_node, env)
            if not isinstance(obj, dict):
                raise TypeError("Property access expects a dict")
            return obj.get(name)
        def setv(v):
            obj = eval_expr(obj_node, env)
            if not isinstance(obj, dict):
                raise TypeError("Property assignment expects a dict")
            obj[name] = v
        return get, setv
    raise SyntaxError("Invalid left-hand side")

def exec_stmt(node, env):
    t = node["type"]
    if t == "assign":
        getter, setter = as_lvalue(node["target"], env)
        value = eval_expr(node["expr"], env)
        setter(value)
        return
    if t == "exprstmt":
        eval_expr(node["expr"], env)
        return
    if t == "return":
        val = eval_expr(node["expr"], env)
        raise ReturnSignal(val)
    if t == "def":
        fn = Function(node["name"], node["params"], node["body"], Env(env))
        env.set_here(node["name"], fn)
        return

    if t == "methoddef":
        target = env.get(node["obj"])
        if not isinstance(target, dict):
            raise RuntimeError(f"{node['obj']} is not an object")
        target[node["name"]] = Function(node["name"], node["params"], node["body"], Env(env))
        return


    if t == "while":
        while is_truthy(eval_expr(node["cond"], env)):
            exec_block(node["body"], Env(env))
        return
    if t == "if":
        cond = eval_expr(node["cond"], env)
        if is_truthy(cond):
            exec_block(node["body"], Env(env))
        return
    if t == "import":
        fileName = eval_expr(node["fileName"], env)
        files = env.get("__importables__")
        if not isinstance(fileName, str):
            raise TypeError("import path must be a string")
        if fileName not in files.keys():
            raise FileNotFoundError(f"Module '{fileName}' not found")
        runEnv = run(files[fileName], make_global_env(files))
        module = runEnv.get("module")
        env.set(fileName.split(".")[0], module)
        return
    if t == "del":
        expr = node["expr"]
        if expr["type"] != "var":
            raise SyntaxError(f"can only remove variables from run time not {expr['type']}")
        env.remove(expr["name"])
        return

    if t == "for_in":
        iterable = eval_expr(node["iter"], env)
        if not isinstance(iterable, list):
            raise TypeError("for-in expects a list")
        for v in iterable:
            env.set(node["var"], v)
            exec_block(node["body"], Env(env))
        return
    if t == "for_c":
        exec_stmt(node["init"], env)
        while is_truthy(eval_expr(node["cond"], env)):
            exec_block(node["body"], Env(env))
            exec_stmt(node["step"], env)
        return
    if t == "block":
        exec_block(node["stmts"], env)
        return
    raise RuntimeError(f"Unknown statement {t}")

def exec_block(stmts, env):
    for s in stmts:
        exec_stmt(s, env)

# ===== Builtins and Python interop =====

def py_print(args_wrapped, env):
    vals = [unwrap_from_py(a) for a in args_wrapped]
    print(*vals)
    return {"type":"null", "value": None}

def py_input(args_wrapped, env):
    vals = [unwrap_from_py(a) for a in args_wrapped]
    return wrap_for_py(input(*vals))

def py_delay(args_wrapped, env):
    vals = [unwrap_from_py(a) for a in args_wrapped]
    if len(vals) == 1:
        if isinstance(vals[0], (float, int)):
            time.sleep(vals[0])
        else:
            raise TypeError("delay only expects int or floats (sec) as delay value")
    else:
        raise TypeError("delay only expects one delay value")
    return wrap_for_py(None)

def py_len(args_wrapped, env):
    vals = [unwrap_from_py(a) for a in args_wrapped]
    if len(vals) != 1:
        raise TypeError("len expects 1 argument")
    return wrap_for_py(len(vals[0]))

def py_range(args_wrapped, env):
    vals = [unwrap_from_py(a) for a in args_wrapped]
    if not (1 <= len(vals) <= 3):
        raise TypeError("range expects 1..3 args")
    r = range(*vals)
    return {"type":"list", "value":[wrap_for_py(int(x)) for x in r]}

def py_upper(args_wrapped, env):
    vals = [unwrap_from_py(a) for a in args_wrapped]
    if len(vals) != 1:
        raise TypeError("upper expects 1 argument")
    if not isinstance(vals[0], str):
        raise TypeError("can not upper a non string")
    return wrap_for_py(vals[0].upper())

def py_lower(args_wrapped, env):
    vals = [unwrap_from_py(a) for a in args_wrapped]
    if len(vals) != 1:
        raise TypeError("upper expects 1 argument")
    if not isinstance(vals[0], str):
        raise TypeError("can not lower a non string")
    return wrap_for_py(vals[0].lower())

def py_split(args_wrapped, env):
    vals = [unwrap_from_py(a) for a in args_wrapped]
    if len(vals) != 2:
        raise TypeError("split expects 2 arguments")
    if not isinstance(vals[0], str):
        raise TypeError("can not split a non string")
    if not isinstance(vals[1], str):
        raise TypeError("can not split with a non string")
    return wrap_for_py(vals[0].split(vals[1]))

py_globals = {}
py_locals = py_globals  # both point to same dict

def py_exec(args_wrapped, env):
    vals = [unwrap_from_py(a) for a in args_wrapped]
    if len(vals) == 1:
        if isinstance(vals[0], str):
            exec(vals[0], py_globals, py_locals)
        elif isinstance(vals[0], list):
            exec("".join(vals[0]), py_globals, py_locals)
    else:
        exec("".join(vals), py_globals, py_locals)
    return {"type":"null", "value": None}

def py_eval(args_wrapped, env):
    vals = [unwrap_from_py(a) for a in args_wrapped]
    if len(vals) == 1:
        if isinstance(vals[0], str):
            return wrap_for_py(eval(vals[0], py_globals, py_locals))
        else:
            raise TypeError("evalPy expects a string")
    else:
        raise TypeError("evalPy expects 1 argument")

typesTable = {
    types.NoneType: "nil",
    int: "number",
    float: "number",
    str: "str",
    list: "list",
    dict: "obj",
    Function: "function"
}
def py_type(args_wrapped, env):
    vals = [unwrap_from_py(a) for a in args_wrapped]
    if len(vals) == 1:
        obj = vals[0]
        return wrap_for_py(typesTable.get(type(obj), "unknown"))
    raise TypeError("type expects 1 argument")

def py_isType(args_wrapped, env):
    vals = [unwrap_from_py(a) for a in args_wrapped]
    if len(vals) == 2:
        obj, type_name = vals
        return wrap_for_py(typesTable.get(type(obj), "unknown") == type_name)
    raise TypeError("isType expects 2 arguments")

def py_addToEnv(args_wrapped, env:Env):
    vals = [unwrap_from_py(a) for a in args_wrapped]
    if len(vals) == 2:
        name, value = vals
        if not isinstance(name, str):
            raise TypeError("name must be a string")
        
        env.set(name, value)

        return wrap_for_py(None)
    raise TypeError("addToEnv expects 2 arguments")

def py_cast(args_wrapped, env):
    vals = [unwrap_from_py(a) for a in args_wrapped]
    if len(vals) == 2:

        try:    
            match vals[1]:
                case "str":
                    return wrap_for_py(str(vals[0]))
                case "int":
                    return wrap_for_py(int(vals[0]))
                case "float":
                    return wrap_for_py(float(vals[0]))
                case "list":
                    return wrap_for_py(list(vals[0]))
                case "dict":
                    return wrap_for_py(dict(vals[0]))
                case _:
                    raise TypeError(f"Unknown type: {vals[1]}")
        except Exception as e:
            raise TypeError(f"Failed to cast {vals[0]} to {vals[1]}: {e}")
        return wrap_for_py(None)



ROS = {
    "ver": "BETA (ver2)"
}

def register_pyfunc(env, name, pyfunc):
    env.set_here(name, Function(name, ["*args"], None, env, escapeToPython=True, pyfunc=pyfunc))

def make_global_env(files):
    g = Env()
    g.set_here("print"        , Function("print"        , ["*values"]       , None, g, escapeToPython=True, pyfunc=py_print       ))
    g.set_here("len"          , Function("len"          , ["x"]             , None, g, escapeToPython=True, pyfunc=py_len         ))
    g.set_here("range"        , Function("range"        , ["a","b","c"]     , None, g, escapeToPython=True, pyfunc=py_range       ))
    g.set_here("upper"        , Function("upper"        , ["x"]             , None, g, escapeToPython=True, pyfunc=py_upper       ))
    g.set_here("lower"        , Function("lower"        , ["x"]             , None, g, escapeToPython=True, pyfunc=py_lower       ))
    g.set_here("split"        , Function("split"        , ["x", "sep"]      , None, g, escapeToPython=True, pyfunc=py_split       ))
    g.set_here("execPy"       , Function("execPy"       , ["code"]          , None, g, escapeToPython=True, pyfunc=py_exec        ))
    g.set_here("evalPy"       , Function("evalPy"       , ["expression"]    , None, g, escapeToPython=True, pyfunc=py_eval        ))
    g.set_here("cast"         , Function("cast"         , ["value", "type"] , None, g, escapeToPython=True, pyfunc=py_cast        ))
    g.set_here("type"         , Function("type"         , ["value"]         , None, g, escapeToPython=True, pyfunc=py_type        ))
    g.set_here("isType"       , Function("isType"       , ["value", "type"] , None, g, escapeToPython=True, pyfunc=py_isType      ))
    g.set_here("addPyFunction", Function("addPyFunction", []                , None, g, escapeToPython=True, pyfunc=register_pyfunc))
    g.set_here("addToEnv"     , Function("addToEnv"     , ["name", "value"] , None, g, escapeToPython=True, pyfunc=py_addToEnv    ))
    g.set_here("input"        , Function("input"        , []                , None, g, escapeToPython=True, pyfunc=py_input       ))
    g.set_here("delay"        , Function("delay"        , ["sec"]           , None, g, escapeToPython=True, pyfunc=py_delay       ))

    g.set_here("ROS"   , ROS)
    g.set_here("__importables__", files)
    return g

# ===== Runner =====

def run(src, env=None):
    tokens = lex(src)
    parser = Parser(tokens)
    ast = parser.parse()
    if env is None:
        env = make_global_env({})
    exec_stmt(ast, env)
    return env

# ===== Demo / REPL (optional) =====


if __name__ == "__main__":

    def read_files_recursive(path):
        files_dict = {}
        for root, dirs, files in os.walk(path):
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        files_dict[fname] = f.read()
                except Exception as e:
                    files_dict[fname] = f"[Error reading file: {e}]"
        return files_dict
    
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            code = f.read()
        if len(sys.argv) == 4 and sys.argv[2] == "--libs" and os.path.exists(sys.argv[3]):
            run(code, make_global_env(read_files_recursive(sys.argv[3])))
        else:
            run(code)
    else:
        print(f"ROS(Ruby On Spaces) ver:{ROS['ver']}")
        print("Type 'run' to execute block \n'clear' to clear block \n'save <path>' to save block into a file \n'load <path>' to load a file \n'last' to load the last ran block into the current block \n'cls' to clear the terminal.")
        lineNo = 1
        toExec = []
        lastRan = []
        maxDigits = 4
        while True:
            try:
                line = input(f"[{str(lineNo).zfill(maxDigits)}]> ")
                striped = line.strip()
                if striped.lower().startswith("run"):
                    code = "\n".join(toExec)
                    lastRan = toExec
                    toExec = []
                    lineNo = 1
                    run(code)
                    continue
                
                elif striped.lower().startswith("cls"):
                    os.system("cls")

                elif striped.lower().startswith("clear"):
                    toExec = []
                    lineNo = 1
                    continue

                elif striped.lower().startswith("save"):
                    with open(line.split()[1], "w") as f:
                        f.writelines(toExec)
                    toExec = []
                    lineNo = 1
                    print("---")
                    continue

                elif striped.lower().startswith("load"):
                    with open(striped[5:], "r") as f:
                        toExec = f.readlines()
                        lineNo = len(toExec) + 1
                        for i, line in enumerate(toExec):
                            print(f"[{str(i + 1).zfill(maxDigits)}]> {line.strip()}")
                    continue

                elif striped.lower().startswith("last"):
                    toExec = lastRan
                    for i, line in enumerate(lastRan):
                        print(f"[{str(i + 1).zfill(maxDigits)}]> {line.strip()}")
                    i = len(toExec) + 1
                    continue

                else:
                    toExec.append(line)

                lineNo += 1

            except EOFError:
                break
            except Exception as e:
                print(f"Error: {e}")
                toExec = []
                lineNo = 0
