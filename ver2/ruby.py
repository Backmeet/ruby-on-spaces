import re
import sys

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
    "def", "return", "end", "while", "for", "in", "true", "false", "null", "if"
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
        self.expect("EOF")
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
            self.expect("end")
            return {"type":"while", "cond":cond, "body":body}
        if self.cur.text == "if":
            self.advance()
            cond = self.parse_expression()
            body = self.parse_block_until_end()
            return {"type":"if", "cond":cond, "body":body}
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
            self.expect("end")
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
    if isinstance(val, list):
        return {"type":"list", "value": [wrap_for_py(v) for v in val]}
    if isinstance(val, dict):
        # plain dict values wrapped
        return {"type":"dict", "value": {k: wrap_for_py(v) for k, v in val.items()}}
    if isinstance(val, Function):
        return {"type":"function", "value": f"<function {val.name}>"}
    raise TypeError(f"Unsupported type for wrap: {type(val)}")

def unwrap_from_py(obj):
    t = obj.get("type")
    v = obj.get("value")
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
        raise NameError(f"Undefined variable {name}")
    def set_here(self, name, value):
        self.map[name] = value
    def set(self, name, value):
        scope = self.resolve_scope(name)
        if scope is None:
            self.map[name] = value
        else:
            scope.map[name] = value
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
            res = self.pyfunc(wrapped_args)
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
    raise TypeError("Indexing only supported on list and dict")

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

def py_print(args_wrapped):
    vals = [unwrap_from_py(a) for a in args_wrapped]
    print(*vals)
    return {"type":"null", "value": None}

def py_len(args_wrapped):
    vals = [unwrap_from_py(a) for a in args_wrapped]
    if len(vals) != 1:
        raise TypeError("len expects 1 argument")
    return wrap_for_py(len(vals[0]))

def py_range(args_wrapped):
    vals = [unwrap_from_py(a) for a in args_wrapped]
    if not (1 <= len(vals) <= 3):
        raise TypeError("range expects 1..3 args")
    r = range(*vals)
    return {"type":"list", "value":[wrap_for_py(int(x)) for x in r]}

def make_global_env():
    g = Env()
    g.set_here("print", Function("print", ["*values"], None, g, escapeToPython=True, pyfunc=py_print))
    g.set_here("len",   Function("len",   ["x"], None, g, escapeToPython=True, pyfunc=py_len))
    g.set_here("range", Function("range", ["a","b","c"], None, g, escapeToPython=True, pyfunc=py_range))
    return g

def register_pyfunc(env, name, pyfunc):
    env.set_here(name, Function(name, ["*args"], None, env, escapeToPython=True, pyfunc=pyfunc))

# ===== Runner =====

def run(src, env=None):
    tokens = lex(src)
    parser = Parser(tokens)
    ast = parser.parse()
    if env is None:
        env = make_global_env()
    exec_stmt(ast, env)
    return env

# ===== Demo / REPL (optional) =====


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            code = f.read()
        run(code)
    else:
        toExec = []
        while True:
            try:
                line = input(">>> ")
                if line.strip() == "":
                    continue
                if line.strip().endswith("RUN"):
                    code = "\n".join(toExec)
                    run(code)
                    toExec = []
                else:
                    toExec.append(line)

            except EOFError:
                break
            except Exception as e:
                print(f"Error: {e}")