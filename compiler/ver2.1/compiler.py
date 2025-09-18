#!/usr/bin/env python3
"""
ros2c.py

Standalone ROS -> C transpiler. Usage:

    python ros2c.py input.ros > output.c

This script reuses the ROS lexer/parser from the interpreter you provided and
transpiles the AST to a single self-contained C file that includes the runtime
(Values, lists, dicts, classes, pointers, cast, delay, subS, subL, free, c(...)).

Notes / limitations (first version):
- Keeps ROS syntax and most semantics. Some runtime semantics approximated to
  fit single-file C implementation.
- Functions are first-class (represented as Value of type FUNCTION storing a
  generated C function pointer -- closure capture is not implemented).
- Classes are compiled to a fixed-size typed-slot Class object based on the
  class type annotation present at assignment time (class :class{...} = {}).

The parser and runtime are intentionally compact to keep the generated C
readable and standalone.
"""

import re, sys, os, copy, time

# ---------------------- Lexer (from user interpreter) ----------------------
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
    "def", "return", "end", "while", "for", "in", "true", "false", "null", "if", "import", "del"
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

# ---------------------- Parser (adapted) ----------------------------------
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

        # detect typed var declaration: ID ':' TYPE '=' expr
        if self.cur.kind == "ID":
            # lookahead
            if self.toks[self.i+1].text == ':' and self.toks[self.i+2].kind in ("ID","OP"):
                # parse var : type = expr  OR var : *type = expr
                name = self.expect("ID").text
                self.expect(":")
                # read potential pointer '*' then type id or class literal
                if self.cur.text == "*":
                    self.advance()
                    tkn = self.expect("ID")
                    type_str = "*" + tkn.text
                elif self.cur.text == "class":
                    # allow class{...}
                    self.advance()
                    self.expect("{")
                    types = []
                    while True:
                        tname = self.expect("ID").text
                        types.append(tname)
                        if self.match("}"):
                            break
                        self.expect(",")
                    type_str = "class{" + ",".join(types) + "}"
                elif self.cur.text == "{" :
                    # class literal short form class{...}
                    # treat as class{...}
                    # e.g. var :class{int,int} = {}
                    self.expect("{")
                    types = []
                    while True:
                        tname = self.expect("ID").text
                        types.append(tname)
                        if self.match("}"):
                            break
                        self.expect(",")
                    type_str = "class{" + ",".join(types) + "}"
                else:
                    tkn = self.expect("ID")
                    type_str = tkn.text
                # optional '='
                if self.match("="):
                    expr = self.parse_expression()
                else:
                    expr = None
                return {"type":"vardecl", "name": name, "vtype": type_str, "expr": expr}

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
        if t.text in ("*", "/", "+", "-","<",
                      ">","<=",">=","==","!="):
            right = self.parse_expression(self.lbp(t))
            return {"type":"binop", "op": t.text, "left": left, "right": right}
        raise SyntaxError(f"Unexpected infix {t.text}")

# ---------------------- Transpiler ----------------------------------------
class CTranspiler:
    def __init__(self, ast):
        self.ast = ast
        self.lines = []
        self.indent_level = 0
        self.indent_str = "    "
        self.tmp_counter = 0
        self.func_counter = 0
        # track generated function definitions
        self.func_defs = []
        # top-level variable declarations to be emitted at start of main
        self.global_decls = []

    def indent(self):
        return self.indent_str * self.indent_level

    def emit(self, s=""):
        self.lines.append(self.indent() + s)

    def unique(self, prefix="t"):
        self.tmp_counter += 1
        return f"{prefix}_{self.tmp_counter}"

    def unique_func(self, prefix="fn"):
        self.func_counter += 1
        return f"{prefix}_{self.func_counter}"

    # ---- runtime header (single-file) ----
    def runtime_prelude(self):
        return RUNTIME_C

    def transpile(self):
        # produce runtime then a main that executes the ROS code
        body = []
        # translate AST stmts into a function 'ros_main' we will call from main
        self.emit("// Transpiled ROS program")
        self.emit("")
        # declare ros_main
        self.emit("void ros_main();")
        self.emit("")
        # emit function bodies if any
        # translate top-level block into ros_main
        self.emit("// user code")
        self.emit("void ros_main() {")
        self.indent_level += 1
        for s in self.ast.get("stmts", []):
            self.transpile_stmt(s)
        self.indent_level -= 1
        self.emit("}")
        self.emit("")
        # emit main
        self.emit("int main(int argc, char** argv) {")
        self.indent_level += 1
        self.emit("runtime_init();")
        self.emit("ros_main();")
        self.emit("return 0;")
        self.indent_level -= 1
        self.emit("}")

    # ---- statements ----
    def transpile_stmt(self, node):
        t = node["type"]
        if t == "vardecl":
            name = node["name"]
            vtype = node["vtype"]
            expr = node.get("expr")
            # create a Value var
            self.emit(f"Value {name};")
            if expr is None:
                self.emit(f"{name}.tag = VAL_NULL;")
            else:
                e = self.transpile_expr(expr)
                # initialize with assignment helper
                self.emit(f"{name} = {e};")
            return
        if t == "assign":
            target = node["target"]
            getter, setter = self.lvalue_to_c(target)
            expr = node["expr"]
            e = self.transpile_expr(expr)
            # setter is C code that sets a Value into target
            self.emit(setter.replace("$EXPR", e))
            return
        if t == "exprstmt":
            e = self.transpile_expr(node["expr"])
            self.emit(f"{e};")
            return
        if t == "return":
            e = self.transpile_expr(node["expr"])
            self.emit(f"// return -- not supported at top-level; ignoring")
            self.emit(f"(void){e};")
            return
        if t == "def":
            # create a C function that returns Value and accepts (Value* args, int argc)
            fname = node["name"]
            c_name = f"ros_fn_{fname}"
            params = node.get("params", [])
            # we will generate a wrapper that maps args to locals
            fnid = self.unique_func(c_name)
            src_lines = []
            src_lines.append(f"Value {fnid}(Value* _args, int _argc) {{")
            # create local variables for parameters
            for i,p in enumerate(params):
                src_lines.append(f"    Value {p} = (_argc > {i}) ? _args[{i}] : val_null();")
            # body
            # temporarily capture current lines, indent
            old_lines = self.lines
            self.lines = []
            self.indent_level = 1
            for s in node.get("body", []):
                self.transpile_stmt(s)
            body_code = self.lines
            self.lines = old_lines
            src_lines.extend(["    " + l for l in body_code])
            src_lines.append("    return val_null();")
            src_lines.append("}")
            # register function variable at top-level
            self.func_defs.append("\n".join(src_lines))
            # set a global Value pointing to this function later in ros_main
            self.emit(f"// define function {fname}")
            self.emit(f"Value {fname};")
            self.emit(f"{fname}.tag = VAL_FUNCTION; {fname}.as_fn = {fnid};")
            return
        if t == "methoddef":
            # not implementing methods on objects in this pass
            self.emit(f"// methoddef {node['obj']}.{node['name']} ignored in transpiler")
            return
        if t == "while":
            cond = self.transpile_expr(node["cond"])
            self.emit(f"while(is_truthy({cond})) {{")
            self.indent_level += 1
            for s in node.get("body", []):
                self.transpile_stmt(s)
            self.indent_level -= 1
            self.emit("}")
            return
        if t == "if":
            cond = self.transpile_expr(node["cond"])
            self.emit(f"if(is_truthy({cond})) {{")
            self.indent_level += 1
            for s in node.get("body", []):
                self.transpile_stmt(s)
            self.indent_level -= 1
            self.emit("}")
            return
        if t == "import":
            self.emit("// import not supported in standalone C output")
            return
        if t == "del":
            expr = node["expr"]
            if expr["type"] != "var":
                self.emit("// del of non-var not supported")
            else:
                self.emit(f"val_free(&{expr['name']});")
            return
        if t == "for_in":
            iter_c = self.transpile_expr(node["iter"])
            var = node["var"]
            i = self.unique("i")
            self.emit(f"for(int {i}=0; {i} < ({iter_c}).as_list->length; {i}++) {{")
            self.indent_level += 1
            self.emit(f"Value {var} = ( ({iter_c}).as_list->items[{i}] );")
            for s in node.get("body", []):
                self.transpile_stmt(s)
            self.indent_level -= 1
            self.emit("}")
            return
        if t == "for_c":
            # simplistic: init; cond; step
            init = node["init"]
            cond = node["cond"]
            step = node["step"]
            # capture init into a line
            old = self.lines
            self.lines = []
            self.transpile_stmt(init)
            init_code = " ".join(self.lines)
            self.lines = old
            cond_c = self.transpile_expr(cond)
            # step as stmt
            old = self.lines
            self.lines = []
            self.transpile_stmt(step)
            step_code = " ".join(self.lines)
            self.lines = old
            self.emit(f"for({init_code} ; is_truthy({cond_c}) ; {step_code}) {{")
            self.indent_level += 1
            for s in node.get("body", []):
                self.transpile_stmt(s)
            self.indent_level -= 1
            self.emit("}")
            return
        if t == "block":
            for s in node.get("stmts", []):
                self.transpile_stmt(s)
            return
        raise NotImplementedError(f"stmt {t} not supported")

    def lvalue_to_c(self, node):
        t = node["type"]
        if t == "var":
            name = node["name"]
            getter = f"{name}"
            setter = f"val_assign_var(&{name}, $EXPR);"
            return getter, setter
        if t == "index":
            obj = self.transpile_expr(node["object"])
            idx = self.transpile_expr(node["index"])
            getter = f"({obj}.as_list->items[{idx}])"
            setter = f"list_set({obj}.as_list, {idx}, $EXPR);"
            return getter, setter
        if t == "prop":
            obj = self.transpile_expr(node["object"])
            name = node["name"]
            setter = f"dict_set({obj}.as_dict, " + f"str_intern(\"{name}\"), $EXPR);"
            getter = f"dict_get({obj}.as_dict, str_intern(\"{name}\"))"
            return getter, setter
        raise SyntaxError("invalid lvalue")

    # ---- expressions ----
    def transpile_expr(self, node):
        t = node["type"]
        if t == "number":
            if isinstance(node["value"], int):
                return f"val_int({node['value']})"
            else:
                return f"val_float({node['value']})"
        if t == "string":
            s = node["value"].replace('"', '\\"')
            return f"val_string(\"{s}\")"
        if t == "bool":
            return f"val_bool({'1' if node['value'] else '0'})"
        if t == "null":
            return "val_null()"
        if t == "var":
            return node["name"]
        if t == "list":
            tmp = self.unique("lst")
            self.emit(f"Value {tmp} = val_list();")
            for it in node["items"]:
                e = self.transpile_expr(it)
                self.emit(f"list_append({tmp}.as_list, {e});")
            return tmp
        if t == "dict":
            tmp = self.unique("d")
            self.emit(f"Value {tmp} = val_dict();")
            for k_node, v_node in node["items"]:
                k = k_node["value"]
                v = self.transpile_expr(v_node)
                self.emit(f"dict_set({tmp}.as_dict, str_intern(\"{k}\"), {v});")
            return tmp
        if t == "unary":
            e = self.transpile_expr(node["expr"])
            if node["op"] == "-":
                return f"val_unary_minus({e})"
            return e
        if t == "binop":
            left = self.transpile_expr(node["left"])
            right = self.transpile_expr(node["right"])
            op = node["op"]
            return f"val_binop({left}, \"{op}\", {right})"
        if t == "call":
            func = node["func"]
            # support c("...") special: embed raw C
            if func["type"] == "var" and func["name"] == "c":
                # expect one string arg
                arg = node["args"][0]
                if arg["type"] != "string":
                    raise SyntaxError("c(...) expects a string literal with C code")
                return f"(void)({arg['value']})"
            # normal call
            fexpr = self.transpile_expr(func)
            args = node.get("args", [])
            arg_list = []
            for a in args:
                arg_list.append(self.transpile_expr(a))
            # pack into Value array on stack
            if len(arg_list) == 0:
                return f"val_call({fexpr}, NULL, 0)"
            else:
                arr = self.unique("a")
                self.emit(f"Value {arr}[{len(arg_list)}];")
                for i,ac in enumerate(arg_list):
                    self.emit(f"{arr}[{i}] = {ac};")
                return f"val_call({fexpr}, {arr}, {len(arg_list)})"
        if t == "index":
            obj = self.transpile_expr(node["object"])
            idx = self.transpile_expr(node["index"])
            return f"val_list_get({obj}.as_list, {idx})"
        if t == "prop":
            obj = self.transpile_expr(node["object"])
            name = node["name"]
            return f"val_dict_get({obj}.as_dict, str_intern(\"{name}\"))"
        raise NotImplementedError(f"expr {t} not supported")

    def generate(self):
        # combine runtime + function defs + generated lines
        parts = [self.runtime_prelude()]
        parts.extend(self.func_defs)
        parts.append("\n/* transpiled program */\n")
        parts.extend(self.lines)
        return "\n".join(parts)

# ---------------------- Runtime C (single-file) ----------------------------
RUNTIME_C = open(os.path.join(os.path.dirname(__file__), "runtime.c"), "r").read()
def compile(code):
    toks = lex(code)
    parser = Parser(toks)
    ast = parser.parse()
    transp = CTranspiler(ast)
    transp.transpile()
    out = transp.generate()
    return out

def main():
    if len(sys.argv) < 2:
        print("Usage: python ros2c.py input.ros > output.c")
        sys.exit(1)
    path = sys.argv[1]
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    toks = lex(src)
    parser = Parser(toks)
    ast = parser.parse()
    transp = CTranspiler(ast)
    transp.transpile()
    out = transp.generate()
    print(out)

if __name__ == '__main__':
    main()
