# ruby.py - full final version (drop-in)
# Note: big file. Read the notes at the end if something needs tuning.

import subprocess, traceback
import random, math, re, time
import string, hashlib
from requests import get

RAW_BASE_URL = 'https://raw.githubusercontent.com/Backmeet/ruby-on-spaces/main'

def getFileText(filePath):
    url = f"{RAW_BASE_URL}/{filePath}"
    try:
        r = get(url, timeout=6)
        if r.status_code != 200:
            raise Exception(f"Failed to fetch text — Status code: {r.status_code}")
        return r.text
    except Exception as e:
        print(f"[ERROR] getFileText failed for {filePath}: {e}")
        raise

def StableHash(text: str, filename: str = ""):
    data = f"{filename}\n{text}".encode('utf-8')
    return hashlib.sha512(data).hexdigest()

stdLibPath = r"gitPath:code-examples/stdlib/stdLib.ru"
if stdLibPath.startswith("gitPath:"):
    try:
        stdLibCode = getFileText(stdLibPath[8:])
    except Exception:
        stdLibCode = ""
else:
    try:
        stdLibCode = open(stdLibPath).read()
    except Exception:
        stdLibCode = ""
stdLibHash = StableHash(stdLibCode)

# ---------------------------------
# evalSafe (simple expression tokenizer + AST builder)
# ---------------------------------
import re

def SafeEval(expr: str, expressionParcer):
    """
    Robust SafeEval:
    - tokenizes strings, numbers, identifiers, parentheses, bracket-lists, function-call syntax (name(...))
    - constructs AST via shunting-yard, supporting unary ops and parentheses
    - returns the evaluated value by calling expressionParcer on AST nodes
    """

    # tokenizer (char-by-char to properly handle nested structures & quotes)
    def tokenize_expr(s: str):
        tokens = []
        i = 0
        n = len(s)
        while i < n:
            ch = s[i]
            if ch.isspace():
                i += 1
                continue
            # strings
            if ch in ('"', "'"):
                quote = ch
                j = i + 1
                buf = quote
                while j < n:
                    if s[j] == "\\" and j + 1 < n:
                        buf += s[j:j+2]
                        j += 2
                        continue
                    if s[j] == quote:
                        buf += quote
                        j += 1
                        break
                    buf += s[j]
                    j += 1
                tokens.append(buf)
                i = j
                continue
            # brackets/lists: capture balanced [...]
            if ch == '[':
                depth = 0
                j = i
                buf = ""
                while j < n:
                    if s[j] == '[':
                        depth += 1
                    elif s[j] == ']':
                        depth -= 1
                    buf += s[j]
                    j += 1
                    if depth == 0:
                        break
                tokens.append(buf)
                i = j
                continue
            # parentheses: but we treat '(' and ')' as tokens (not capture entire subexpr as single token)
            if ch in '()':
                tokens.append(ch)
                i += 1
                continue
            # multi-char operators
            two = s[i:i+2]
            if two in ('==', '!=', '>=', '<=', '//', '**'):
                tokens.append(two)
                i += 2
                continue
            # single-char operators / punctuation
            if ch in '+-*/%^<>|&~,':
                tokens.append(ch)
                i += 1
                continue
            # identifier or number or function-call start
            if ch.isalnum() or ch == '_' :
                j = i
                while j < n and (s[j].isalnum() or s[j] == '_' ):
                    j += 1
                ident = s[i:j]
                # if next non-space char is '(' then capture function-call token name(...) as a single token
                k = j
                while k < n and s[k].isspace():
                    k += 1
                if k < n and s[k] == '(':
                    # capture balanced parentheses including nested ones and content
                    depth = 0
                    m = k
                    buf = ident
                    while m < n:
                        if s[m] == '(':
                            depth += 1
                        elif s[m] == ')':
                            depth -= 1
                        buf += s[m]
                        m += 1
                        if depth == 0:
                            break
                    tokens.append(buf)
                    i = m
                else:
                    tokens.append(ident)
                    i = j
                continue
            # otherwise unknown char, treat as single char token
            tokens.append(ch)
            i += 1
        return tokens

    toks = tokenize_expr(expr)

    # precedence and associativity
    precedence = {
        '**': (9, 'right'),
        '^': (9, 'right'),
        '*': (8, 'left'),
        '/': (8, 'left'),
        '//': (8, 'left'),
        '%': (8, 'left'),
        '+': (7, 'left'),
        '-': (7, 'left'),
        '|': (6, 'left'),
        '&': (6, 'left'),
        '==': (5, 'left'),
        '!=': (5, 'left'),
        '>=': (5, 'left'),
        '<=': (5, 'left'),
        '>': (5, 'left'),
        '<': (5, 'left'),
        'in': (5, 'left'),
        'and': (3, 'left'),
        'or': (2, 'left'),
    }
    unary_ops = {'-', 'not', '~', 'sqrt', 'cbrt', 'sin', 'cos', 'tan', 'len'}

    output = []
    stack = []

    def pop_op():
        typ, op = stack.pop()
        if typ == 'unary':
            arg = output.pop()
            output.append([op, arg])
        else:
            b = output.pop()
            a = output.pop()
            output.append([a, op, b])

    expect_operand = True
    i = 0
    while i < len(toks):
        tok = toks[i]
        # normalize 'and'/'or'/'not' tokens if they are identifiers
        if isinstance(tok, str) and tok in unary_ops and expect_operand:
            stack.append(('unary', tok))
            expect_operand = True
            i += 1
            continue
        if tok in precedence:
            # binary op
            while stack and stack[-1][0] == 'binary':
                _, top = stack[-1]
                p1, assoc1 = precedence[tok]
                p2, _ = precedence[top]
                if (assoc1 == 'left' and p1 <= p2) or (assoc1 == 'right' and p1 < p2):
                    pop_op()
                else:
                    break
            stack.append(('binary', tok))
            expect_operand = True
            i += 1
            continue
        # numbers
        if re.fullmatch(r'\d+\.?\d*', tok):
            output.append(tok)
            expect_operand = False
            i += 1
            continue
        # strings or quoted tokens
        if (tok.startswith('"') and tok.endswith('"')) or (tok.startswith("'") and tok.endswith("'")):
            output.append(tok)
            expect_operand = False
            i += 1
            continue
        # function-call token like name(...) or identifier
        if re.fullmatch(r'\w+\(.*\)', tok):
            # keep as a single token, SafeEval's expressionParcer (math_parcer) / resolve_operand will handle it
            output.append(tok)
            expect_operand = False
            i += 1
            continue
        if re.fullmatch(r'\w+', tok):
            output.append(tok)
            expect_operand = False
            i += 1
            continue
        if tok == '[' and tok.endswith(']') is False:
            # this shouldn't happen because tokenize captured full [...], but handle if seen
            # find matching ]
            depth = 0
            j = i
            buf = ""
            while j < len(toks):
                piece = toks[j]
                if piece == '[':
                    depth += 1
                elif piece == ']':
                    depth -= 1
                buf += piece
                j += 1
                if depth == 0:
                    break
            output.append(buf)
            expect_operand = False
            i = j
            continue
        if tok.startswith('[') and tok.endswith(']'):
            output.append(tok)
            expect_operand = False
            i += 1
            continue
        if tok == '(':
            stack.append(('paren', tok))
            expect_operand = True
            i += 1
            continue
        if tok == ')':
            while stack and stack[-1][1] != '(':
                pop_op()
            if stack and stack[-1][1] == '(':
                stack.pop()
            if stack and stack[-1][0] == 'unary':
                typ, op = stack.pop()
                arg = output.pop()
                output.append([op, arg])
            expect_operand = False
            i += 1
            continue
        # fallback
        output.append(tok)
        expect_operand = False
        i += 1

    while stack:
        pop_op()

    if not output:
        return 0
    ast = output[0]

    # evaluate ast recursively via expressionParcer
    def evaluate(node):
        if isinstance(node, str):
            return node
        if len(node) == 2:
            op, a = node
            aval = evaluate(a)
            return expressionParcer([op, aval if isinstance(aval, list) else str(aval)])
        elif len(node) == 3:
            a, op, b = node
            aval = evaluate(a)
            bval = evaluate(b)
            return expressionParcer([
                aval if isinstance(aval, list) else str(aval),
                op,
                bval if isinstance(bval, list) else str(bval)
            ])
        else:
            raise ValueError("Unexpected AST node in SafeEval")
    return evaluate(ast)

# ---------------------------------
# Interpreter
# ---------------------------------
def runRuby(main_code: str, source_dict: dict[str, str] = {}, bound: bool = True) -> None:
    """
    Complete interpreter:
    - new def syntax storing (startIndex, [numArgs, arg1, arg2, ...])
    - calls in expressions and as statements
    - list ops, recursive list call
    - for/if/while/try/import/export/system/delay/error etc.
    - clear errors with file / line info
    """

    initBounded = bound
    sources = {"main": main_code.splitlines()}
    files = {name: content.splitlines() for name, content in source_dict.items()}

    # regex helpers
    comment_re = re.compile(r'\s*//')
    token_re = re.compile(r'''\[[^\]]*\] | "(?:\\.|[^"\\])*" | '(?:\\.|[^'\\])*' | \w+\(.*?\) | \w+ | == | != | >= | <= | // | \*\* | [\+\-\*/%^<>=|&~]''', re.VERBOSE)

    def tokenize(line: str):
        return token_re.findall(comment_re.split(line, maxsplit=1)[0])

    def resolve_list_call(chain):
        """
        Recursively resolves a list call chain.
        Example: list1.list2.func
        - If a function is found at any point before the last element, return it immediately.
        - If nested lists exist, drill down until the last element.
        """
        current_val, current_type = parseValue(chain[0])

        for part in chain[1:]:
            if current_type in ["var list", "literal list"]:
                found = None
                for item in current_val:
                    # Match variable name or literal that equals part
                    if isinstance(item, str) and item == part:
                        found = parseValue(item)
                        break
                if not found:
                    raise NameError(f"List element '{part}' not found in list at line {current_index} in {current_source}")
                current_val, current_type = found

            elif current_type == "func":
                # Early return if we hit a function before the end
                return current_val

            else:
                raise TypeError(f"Cannot drill into type '{current_type}' at line {current_index} in {current_source}")

        return current_val


    def is_number(s: str):
        try:
            float(s)
            return True
        except:
            return False

    # interpreter state
    variables = {"return": None}
    functionIndexs = {"main": {}}
    sources_state = sources  # alias
    current_source = "main"
    current_lines = sources_state[current_source]
    current_index = 0
    while_stack = []      # stack of (loop_start_index, condition_expr)
    for_stack = []        # stack of begin indices (we'll store begin_index)
    try_state = [False, None, None]  # [in_try, except_line, exception_string]
    bound_mode = initBounded

    # ---------- parseValue (recursive) ----------
    def parseValue(val_str, local_vars=None):
        """
        Returns (value, type_str)
        type_str one of: literal int/str/list, var int/str/list, func, var unknown
        """
        if local_vars is None:
            local_vars = variables

        # If passed non-str (already evaluated), accept directly
        if not isinstance(val_str, str):
            if isinstance(val_str, list):
                return val_str, "literal list"
            if isinstance(val_str, (int, float)):
                return val_str, "literal int"
            return val_str, "var unknown"

        vs = val_str.strip()
        low = vs.lower()
        if low in ["null", "none", "nil"]:
            return 0, "literal int"
        if low == "true":
            return 1, "literal int"

        # variable lookup
        if vs in local_vars:
            v = local_vars[vs]
            if isinstance(v, list): return v, "var list"
            if isinstance(v, (int, float)): return v, "var int"
            if isinstance(v, str): return v, "var str"
            return v, "var unknown"

        # string literal
        if (vs.startswith('"') and vs.endswith('"')) or (vs.startswith("'") and vs.endswith("'")):
            return vs[1:-1], "literal str"

        # numeric literal
        if is_number(vs):
            return (float(vs) if "." in vs else int(vs)), "literal int"

        # list literal -> evaluate contained tokens
        if vs.startswith('[') and vs.endswith(']'):
            inner = vs[1:-1]
            toks = tokenize(inner)
            evaluated = [parseValue(t)[0] for t in toks]
            return evaluated, "literal list"

        # function references (registered)
        for src, funcs in functionIndexs.items():
            if vs in funcs:
                return (src, vs), "func"

        # not found
        raise NameError(f"Unknown value '{vs}' at {current_source}:{current_index}")

    # ---------- math_parcer (used by SafeEval) ----------
    def math_parcer(token):
        # token may be ['a', '+', 'b'] or ['op','a'] depending on SafeEval AST usage
        # We'll implement handling similar to previous implementation:
        if isinstance(token, list) and len(token) == 3:
            a_tok, op, b_tok = token
            # evaluate operands possibly containing function calls like name(...)
            a_val, a_type = resolve_operand(a_tok)
            b_val, b_type = resolve_operand(b_tok)

            # numeric ops
            if a_type.endswith("int") and b_type.endswith("int"):
                a = a_val; b = b_val
                match op:
                    case "+": return a + b
                    case "-": return a - b
                    case "/": return a / b
                    case "*": return a * b
                    case "//": return a // b
                    case "**": return a ** b
                    case "^": return int(a) ^ int(b)
                    case "|": return int(a) | int(b)
                    case "&": return int(a) & int(b)
                    case "==": return int(a == b)
                    case "!=": return int(a != b)
                    case ">=": return int(a >= b)
                    case "<=": return int(a <= b)
                    case ">": return int(a > b)
                    case "<": return int(a < b)
                    case "and": return int(bool(a) and bool(b))
                    case "or": return int(bool(a) or bool(b))
            # string operations
            if a_type.endswith("str") and b_type.endswith("str"):
                match op:
                    case "+": return a_val + b_val
                    case "in": return int(a_val in b_val)
                    case "==": return int(a_val == b_val)
                    case "!=": return int(a_val != b_val)
            # string op with int (index, pop, * repetition)
            if a_type.endswith("str") and b_type.endswith("int"):
                match op:
                    case "index": return a_val[b_val]
                    case "pop":
                        lst = list(a_val)
                        idx = int(b_val)
                        if idx < 0 or idx >= len(lst):
                            raise IndexError("pop index out of range")
                        lst.pop(idx)
                        return ''.join(lst)
                    case "*": return a_val * int(b_val)
            # list index
            if a_type.endswith("list") and b_type.endswith("int"):
                match op:
                    case "index":
                        return parseValue(a_val[b_val])[0]
                    case "*": return a_val * int(b_val)

            return 0

        elif isinstance(token, list) and len(token) == 2:
            op, v_tok = token
            v_val, v_type = resolve_operand(v_tok)
            if v_type.endswith("str") or v_type.endswith("list"):
                match op:
                    case "len": return len(v_val)
                    case "not": return int(not bool(v_val))
            if v_type.endswith("int"):
                match op:
                    case "cbrt": return v_val ** (1/3)
                    case "sqrt": return math.sqrt(v_val)
                    case "not": return int(not bool(v_val))
                    case "~": return ~int(v_val)
                    case "-": return -v_val
                    case "tan": return math.tan(v_val)
                    case "sin": return math.sin(v_val)
                    case "cos": return math.cos(v_val)
            return 0
        else:
            # the token may be a simple string number or var
            # fallback: try parseValue
            try:
                val, _ = parseValue(str(token))
                return val
            except Exception:
                return 0

    # helper to resolve an operand which might be:
    # - a literal/var name
    # - a function call like fn(a,b)
    def resolve_operand(tok):
        # tok may be like: 'foo(1,2)' or '123' or '"str"' or '[1,2]' or 'varname'
        if isinstance(tok, str) and re.fullmatch(r'\w+\(.*\)', tok):
            # function call pattern
            m = re.match(r'(\w+)\((.*)\)', tok)
            if not m:
                raise SyntaxError(f"Malformed function call '{tok}' at {current_source}:{current_index}")
            fname = m.group(1)
            args_str = m.group(2).strip()
            # split args by commas but respect strings and brackets (simple split using tokenize)
            arg_toks = []
            if args_str != "":
                parts = []
                depth = 0
                current = ""
                i = 0
                while i < len(args_str):
                    ch = args_str[i]
                    if ch == ',' and depth == 0:
                        parts.append(current.strip())
                        current = ""
                    else:
                        current += ch
                        if ch == '[': depth += 1
                        elif ch == ']': depth -= 1
                        elif ch == '"' or ch == "'":
                            # consume until matching quote
                            quote = ch
                            i += 1
                            while i < len(args_str) and args_str[i] != quote:
                                current += args_str[i]
                                i += 1
                            if i < len(args_str):
                                current += quote
                        # no further handling
                    i += 1
                if current.strip() != "":
                    parts.append(current.strip())
                arg_toks = parts
            # evaluate args
            arg_values = [ (parseValue(a)[0]) for a in arg_toks ]
            # execute function and return its return value
            ret = execute_function_call(fname, arg_values)
            # ret may be any type
            # return as int/float/str/list with appropriate type tag
            if isinstance(ret, list):
                return ret, "literal list"
            if isinstance(ret, (int, float)):
                return ret, "literal int"
            if isinstance(ret, str):
                return ret, "literal str"
            return ret, "var unknown"
        else:
            # simple value or var
            v, t = parseValue(str(tok))
            return v, t

    # ---------- execute_function_call ----------
    def execute_function_call(func_name, arg_values):
        """
        Runs a function synchronously and returns its 'return' value.
        Function metadata stored as functionIndexs[src][name] = (startIndex, [numArgs, argName1,...])
        Search for function in current source, then across sources.
        """
        # find function
        found = None
        found_src = None
        for src, funcs in functionIndexs.items():
            if func_name in funcs:
                found = funcs[func_name]
                found_src = src
                break
        if not found:
            raise NameError(f"Function '{func_name}' not defined (call at {current_source}:{current_index})")
        startIndex, argData = found
        numArgs = argData[0]
        argNames = argData[1:]
        if len(arg_values) != numArgs:
            raise TypeError(f"Function '{func_name}' expects {numArgs} args, got {len(arg_values)} at {current_source}:{current_index}")

        # Save caller state
        saved_source = current_source
        saved_lines = current_lines
        saved_index = current_index
        saved_vars = variables.copy()

        # Prepare function frame
        # Put args into variables by their names
        for i, name in enumerate(argNames):
            variables[name] = arg_values[i]

        # Execute function body from startIndex until matching endfunc
        # We'll execute by iterating lines starting startIndex until endfunc at same nesting level
        depth = 0
        i = startIndex
        ret_val = None
        # Local while to execute lines with same processing logic (we call process_line)
        while i < len(sources_state[found_src]):
            ln = sources_state[found_src][i]
            toks = tokenize(ln)
            if toks:
                if toks[0] == "def":
                    depth += 1
                elif toks[0] == "endfunc":
                    if depth == 0:
                        # function end reached
                        break
                    else:
                        depth -= 1
                elif toks[0] == "return":
                    # evaluate return expression (if provided)
                    if len(toks) > 1:
                        expr = " ".join(toks[1:])
                        # use SafeEval but math_parcer must be able to resolve nested calls; it does via execute_function_call
                        rv = SafeEval(expr, math_parcer_wrapper)
                        variables["return"] = rv
                    else:
                        variables["return"] = None
                    # when return encountered we stop executing function and restore
                    ret_val = variables.get("return", None)
                    break
                else:
                    # process other line in function body via process_line function
                    process_line(toks, ln, in_function=True, source=found_src, local_index=i)
            i += 1

        # restore caller state (but keep variables mutated by function? we'll follow global variable model: function can mutate globals)
        # we restore current_source/current_lines/current_index; variables remain as is except we restore caller's non-local names?
        # To keep semantics simple: function arguments and any local vars remain in variables (like globals)
        # But we must restore current_source/lines/index
        # We restore to caller's position (saved_index) after finishing
        # Return value:
        ret = variables.get("return", None)

        # restore program counter (outer loop manages it), but variables remain (like your original)
        return ret

    def _split_args(args_str: str) -> list:
        """
        Split a comma-separated argument list while respecting nested parentheses,
        brackets, and quoted strings.
        Returns a list of argument strings (trimmed).
        """
        parts = []
        cur = []
        depth_paren = 0
        depth_brack = 0
        i = 0
        n = len(args_str)
        while i < n:
            ch = args_str[i]
            if ch == ',' and depth_paren == 0 and depth_brack == 0:
                part = "".join(cur).strip()
                if part != "":
                    parts.append(part)
                cur = []
                i += 1
                continue
            # handle quotes (consume entire quoted segment)
            if ch in ('"', "'"):
                quote = ch
                cur.append(ch)
                i += 1
                while i < n:
                    cur.append(args_str[i])
                    if args_str[i] == "\\" and i + 1 < n:
                        # escaped char: include and skip
                        i += 2
                        continue
                    if args_str[i] == quote:
                        i += 1
                        break
                    i += 1
                continue
            if ch == '(':
                depth_paren += 1
                cur.append(ch)
            elif ch == ')':
                if depth_paren > 0:
                    depth_paren -= 1
                cur.append(ch)
            elif ch == '[':
                depth_brack += 1
                cur.append(ch)
            elif ch == ']':
                if depth_brack > 0:
                    depth_brack -= 1
                cur.append(ch)
            else:
                cur.append(ch)
            i += 1
        last = "".join(cur).strip()
        if last != "":
            parts.append(last)
        return parts


    def resolve_operand(tok):
        """
        Resolve an operand that may be:
        - a direct literal/variable token (e.g. "10", "x", '"hello"', '[1,2]')
        - a function-call token like name(arg1, arg2)
        Returns (value, type_str).
        Relies on:
        - parseValue(token)  -> returns (value, type)
        - execute_function_call(name, arg_values) -> returns Python value
        """
        # if already a non-str (pre-evaluated), try parseValue will accept
        if not isinstance(tok, str):
            return parseValue(tok)

        tok = tok.strip()
        # detect function-call pattern: name(...)
        m = re.fullmatch(r'([A-Za-z_]\w*)\((.*)\)', tok, flags=re.DOTALL)
        if m:
            fname = m.group(1)
            args_inside = m.group(2).strip()
            if args_inside == "":
                arg_parts = []
            else:
                arg_parts = _split_args(args_inside)
            # evaluate argument expressions (these might be complex expressions,
            # so use SafeEval to evaluate them to final values when appropriate)
            evaluated_args = []
            for p in arg_parts:
                # If p looks like an expression, prefer SafeEval (so nested calls and math work)
                # Use SafeEval with your math_parcer wrapper (must be in scope)
                try:
                    # Note: math_parcer_wrapper should be the wrapper you pass to SafeEval
                    val = SafeEval(p, math_parcer_wrapper)
                except Exception:
                    # fallback to parseValue for simple tokens
                    val = parseValue(p)[0]
                evaluated_args.append(val)
            # call the function synchronously (must exist)
            result = execute_function_call(fname, evaluated_args)
            # map type
            if isinstance(result, list):
                return result, "literal list"
            if isinstance(result, (int, float)):
                return result, "literal int"
            if isinstance(result, str):
                return result, "literal str"
            return result, "var unknown"

        # not a function call — use parseValue
        return parseValue(tok)

    # math_parcer wrapper for SafeEval to reference (it uses resolve_operand and parseValue above)
    def math_parcer_wrapper(ast_token):
        return math_parcer(ast_token)

    # ---------- process_line ----------
    def process_line(parsed_tokens, raw_line, in_function=False, source=None, local_index=None):
        # This function encapsulates the command handling logic so it can be reused
        nonlocal current_source, current_lines, current_index, variables, while_stack, for_stack, try_state, bound_mode

        cmd = parsed_tokens[0]
        args = parsed_tokens[1:]

        # detect direct function call as statement (function name followed by args)
        if cmd in functionIndexs.get(current_source, {}) or cmd in functionIndexs.get("main", {}):
            # call it
            src = current_source if cmd in functionIndexs.get(current_source, {}) else "main"
            startIndex, argData = functionIndexs[src][cmd]
            num_args = argData[0]
            argNames = argData[1:]
            if len(args) != num_args:
                raise TypeError(f"Function {cmd} expects {num_args} args, got {len(args)} at {current_source}:{current_index}")
            arg_vals = [parseValue(a)[0] for a in args]
            # execute synchronously
            _ = execute_function_call(cmd, arg_vals)
            return

        match cmd:
            case "print":
                out = "".join(str(parseValue(tok)[0]) for tok in args)
                print(out.strip())

            case "flush":
                out = "".join(str(parseValue(tok)[0]) for tok in args)
                print(out.strip(), flush=1, end='\r')

            case "rnd":
                # rnd int <var> <origin> <stop>
                # rnd str <var> <len>
                if len(args) >= 1 and args[0] == "int":
                    varname = args[1]
                    origin = parseValue(args[2])[0]
                    stop = parseValue(args[3])[0]
                    variables[varname] = random.randint(int(origin), int(stop))
                elif len(args) >= 1 and args[0] == "str":
                    varname = args[1]
                    length = int(parseValue(args[2])[0])
                    variables[varname] = "".join(string.printable[random.randint(0, len(string.printable)-1)] for _ in range(length))

            case "var":
                # var <var> = <expression>
                rest = raw_line.strip()[4:]
                if "=" not in rest:
                    raise SyntaxError(f"Invalid var assignment at {current_source}:{current_index}")
                varname, expr = rest.split("=", 1)
                varname = varname.strip()
                # evaluate expression via SafeEval
                val = SafeEval(expr.strip(), math_parcer_wrapper)
                variables[varname] = val

            case "list":
                if not args:
                    raise SyntaxError(f"list missing subcommand at {current_source}:{current_index}")
                sub = args[0]
                match sub:
                    case "set":
                        # list set <list> <index> to <value>
                        if len(args) != 5 or args[3].lower() != "to":
                            raise SyntaxError(f"list set syntax error at {current_source}:{current_index}")
                        parsed_list = parseValue(args[1])
                        parsed_index = parseValue(args[2])
                        parsed_value = parseValue(args[4])
                        if parsed_list[1] not in ["var list", "literal list"]:
                            raise TypeError(f"Cannot set value to non-list at {current_source}:{current_index}")
                        if parsed_index[1] not in ["var int", "literal int"]:
                            raise TypeError(f"list set index must be integer at {current_source}:{current_index}")
                        variables[parsed_list[0]][parsed_index[0]] = parsed_value[0]

                    case "append":
                        parsed_list = parseValue(args[1])
                        parsed_value = parseValue(args[2])
                        if parsed_list[1] not in ["var list", "literal list"]:
                            raise TypeError(f"Cannot append to non-list at {current_source}:{current_index}")
                        variables[parsed_list[0]].append(parsed_value[0])

                    case "extend":
                        parsed_list = parseValue(args[1])
                        parsed_value = parseValue(args[2])
                        if parsed_list[1] not in ["var list", "literal list"]:
                            raise TypeError(f"Cannot extend non-list at {current_source}:{current_index}")
                        if parsed_value[1] not in ["var list", "literal list"]:
                            raise TypeError(f"Extend requires second arg to be list at {current_source}:{current_index}")
                        variables[parsed_list[0]].extend(parsed_value[0])

                    case "pop":
                        parsed_list = parseValue(args[1])
                        parsed_index = parseValue(args[2])
                        if parsed_list[1] not in ["var list", "literal list"]:
                            raise TypeError(f"Cannot pop from non-list at {current_source}:{current_index}")
                        if parsed_index[1] not in ["var int", "literal int"]:
                            raise TypeError(f"pop index must be int at {current_source}:{current_index}")
                        popped = variables[parsed_list[0]].pop(parsed_index[0])
                        variables["return"] = popped

                    case "call":
                        # list call <chain> arg1 arg2...
                        chain = args[1].split(".")
                        func_ref = resolve_list_call(chain)
                        if not isinstance(func_ref, tuple) or len(func_ref) != 2:
                            raise NameError(f"Resolved chain is not a function at {current_source}:{current_index}")
                        src, name = func_ref
                        startIndex, argData = functionIndexs[src][name]
                        num_args = argData[0]
                        # evaluate args and call
                        call_args = [parseValue(a)[0] for a in args[2:]]
                        if len(call_args) != num_args:
                            raise TypeError(f"Function {name} expects {num_args} args, got {len(call_args)} at {current_source}:{current_index}")
                        _ = execute_function_call(name, call_args)

                    case _:
                        raise SyntaxError(f"Unknown list subcmd '{sub}' at {current_source}:{current_index}")

            case "def":
                # def name(arg1, arg2, ...)
                if not args:
                    raise SyntaxError(f"def needs a name at {current_source}:{current_index}")
                fname = args[0]
                # remaining tokens form the arglist possibly in single token "(a,b)"
                arglist_token = " ".join(args[1:]).strip()
                # accept either def name (a,b) or def name a,b
                arglist = []
                if arglist_token:
                    # split by comma
                    if arglist_token.strip() != "":
                        arglist = [x.strip() for x in arglist_token.split(" ") if x.strip()]
                # store function metadata (start index is next line)
                functionIndexs.setdefault(current_source, {})[fname] = (current_index + 1, [len(arglist)] + arglist)
                # skip forward to matching endfunc
                depth = 0
                j = current_index + 1
                while j < len(current_lines):
                    toks = tokenize(current_lines[j])
                    if toks:
                        if toks[0] == "def":
                            depth += 1
                        elif toks[0] == "endfunc":
                            if depth == 0:
                                break
                            else:
                                depth -= 1
                    j += 1
                current_index = j

            case "endfunc":
                # end of function when running top-level; nothing to do (function bodies skipped at definition time)
                pass

            case "return":
                # return <expr>
                if args:
                    expr = " ".join(args)
                    variables["return"] = SafeEval(expr, math_parcer_wrapper)
                else:
                    variables["return"] = None
                # when executed inside execute_function_call loop, process_line will exit function after setting return
                # if called at top-level, we set return variable and continue
                return

            case "if":
                if args and args[0] == "end":
                    pass
                else:
                    cond_expr = " ".join(args)
                    cond_result = SafeEval(cond_expr, math_parcer_wrapper)
                    if not cond_result:
                        # skip to matching if end
                        depth = 1
                        j = current_index + 1
                        while j < len(current_lines):
                            toks = tokenize(current_lines[j])
                            if toks:
                                if toks[0] == "if" and not (len(toks) > 1 and toks[1] == "end"):
                                    depth += 1
                                elif toks[0] == "if" and len(toks) > 1 and toks[1] == "end":
                                    depth -= 1
                                    if depth == 0:
                                        break
                            j += 1
                        current_index = j

            case "while":
                if args and args[0] == "end":
                    if not while_stack:
                        raise SyntaxError(f"Unexpected 'while end' at {current_source}:{current_index}")
                    loop_start, cond = while_stack.pop()
                    if SafeEval(cond, math_parcer_wrapper):
                        # jump back to start (will be incremented by main loop)
                        # set current_index to loop_start - 1 so main loop increments to loop_start
                        return_to = loop_start - 1
                        # adjust by returning special marker via global variable (we'll set current_index externally)
                        # For simplicity, set global and let caller adjust
                        variables["_while_return_index"] = return_to
                    else:
                        variables.pop("_while_return_index", None)
                else:
                    cond_expr = " ".join(args)
                    if not SafeEval(cond_expr, math_parcer_wrapper):
                        # skip block
                        depth = 1
                        j = current_index + 1
                        while j < len(current_lines):
                            toks = tokenize(current_lines[j])
                            if toks:
                                if toks[0] == "while" and not (len(toks) > 1 and toks[1] == "end"):
                                    depth += 1
                                elif toks[0] == "while" and len(toks) > 1 and toks[1] == "end":
                                    depth -= 1
                                    if depth == 0:
                                        break
                            j += 1
                        current_index = j
                    else:
                        while_stack.append((current_index, cond_expr))

            case "for":
                # for begin : var; init; condition; delta  OR for end
                if args and args[0] == "end":
                    if not for_stack:
                        raise SyntaxError(f"Unexpected 'for end' at {current_source}:{current_index}")
                    begin_index = for_stack[-1]
                    begin_line = current_lines[begin_index]
                    if ":" not in begin_line:
                        raise SyntaxError(f"Malformed for begin at {current_source}:{begin_index}")
                    data = begin_line.split(":",1)[1].strip()
                    parts = [p.strip() for p in data.split(";")]
                    if len(parts) != 4:
                        raise SyntaxError(f"Malformed for begin parts at {current_source}:{begin_index}")
                    varname, initVal, conditionExpr, deltaExpr = parts
                    # increment var by delta
                    variables[varname] = SafeEval(f"{varname} + ({deltaExpr})", math_parcer_wrapper)
                    if SafeEval(conditionExpr, math_parcer_wrapper):
                        # jump back to begin
                        variables["_for_return_index"] = begin_index
                    else:
                        for_stack.pop()
                        variables.pop("_for_return_index", None)
                else:
                    # begin
                    if ":" not in raw_line:
                        raise SyntaxError(f"for begin missing ':' at {current_source}:{current_index}")
                    data = raw_line.split(":",1)[1].strip()
                    parts = [p.strip() for p in data.split(";")]
                    if len(parts) != 4:
                        raise SyntaxError(f"Malformed for begin; need 4 parts at {current_source}:{current_index}")
                    varname, initVal, conditionExpr, deltaExpr = parts
                    variables[varname] = SafeEval(initVal, math_parcer_wrapper)
                    for_stack.append(current_index)
                    if not SafeEval(conditionExpr, math_parcer_wrapper):
                        # skip loop body
                        depth = 1
                        j = current_index + 1
                        while j < len(current_lines):
                            toks = tokenize(current_lines[j])
                            if toks:
                                if toks[0] == "for" and not (len(toks) > 1 and toks[1] == "end"):
                                    depth += 1
                                elif toks[0] == "for" and len(toks) > 1 and toks[1] == "end":
                                    depth -= 1
                                    if depth == 0:
                                        break
                            j += 1
                        current_index = j

            case "import":
                # import "filename"
                if not args:
                    raise SyntaxError(f"import needs filename at {current_source}:{current_index}")
                parsed_fname = parseValue(args[0])
                if parsed_fname[1] not in ["var str", "literal str"]:
                    raise TypeError(f"import names must be strings at {current_source}:{current_index}")
                fname = parsed_fname[0]
                if fname not in files:
                    raise FileNotFoundError(f"Imported file {fname} not found at {current_source}:{current_index}")
                imported_lines = files[fname]
                sources_state[fname] = imported_lines
                # scan for export/def
                allowed_funcs = []
                file_funcs = {}
                for ln, l in enumerate(imported_lines):
                    toks = tokenize(l)
                    if not toks: continue
                    if toks[0] == "export" and len(toks) > 1 and toks[1] == "functions":
                        for tk in toks[2:]:
                            allowed_funcs.append(tk)
                    if toks[0] == "def":
                        nm = toks[1]
                        arg_token = " ".join(toks[2:]).strip()
                        if arg_token.startswith("(") and arg_token.endswith(")"):
                            arg_token = arg_token[1:-1]
                        arg_names = [x.strip() for x in arg_token.split(",")] if arg_token else []
                        start_idx = ln + 1
                        # find endfunc
                        depth = 0
                        eidx = None
                        for j in range(start_idx, len(imported_lines)):
                            t2 = tokenize(imported_lines[j])
                            if t2:
                                if t2[0] == "def":
                                    depth += 1
                                elif t2[0] == "endfunc":
                                    if depth == 0:
                                        eidx = j
                                        break
                                    else:
                                        depth -= 1
                        if eidx is None:
                            raise ValueError(f"Function {nm} missing endfunc in import {fname}")
                        file_funcs[nm] = (start_idx, [len(arg_names)] + arg_names)
                functionIndexs[fname] = {}
                for name in allowed_funcs:
                    if name in file_funcs:
                        functionIndexs[fname][name] = file_funcs[name]
                    else:
                        raise ImportError(f"{fname} does not export {name} at {current_source}:{current_index}")

            case "export":
                # handled during import time; top-level export ignored
                pass

            case "system":
                if not (StableHash("".join(current_lines)) == stdLibHash or not bound_mode):
                    raise PermissionError(f"system disallowed in bound mode at {current_source}:{current_index}")
                parsed_cmd = parseValue(args[0])
                if parsed_cmd[1] not in ["var str","literal str"]:
                    raise TypeError(f"system command must be string at {current_source}:{current_index}")
                proc = subprocess.run(parsed_cmd[0], capture_output=1, text=1, shell=1)
                variables["_stdout"] = proc.stderr if proc.returncode else proc.stdout
                variables["return"] = proc.returncode

            case "delay":
                if not args:
                    raise SyntaxError(f"delay needs seconds at {current_source}:{current_index}")
                sec = parseValue(args[0])[0]
                time.sleep(float(sec))

            case "error":
                if not args:
                    raise SyntaxError(f"error needs message at {current_source}:{current_index}")
                msg = parseValue(args[0])[0]
                raise Exception(msg)

            case "try":
                # find next except in remainder and register
                except_line = None
                for i, l in enumerate(current_lines[current_index:]):
                    tks = tokenize(l)
                    if tks and tks[0] == "except":
                        except_line = current_index + i
                        break
                if except_line is None:
                    raise SyntaxError(f"try without except at {current_source}:{current_index}")
                try_state[0] = True
                try_state[1] = except_line
                try_state[2] = None

            case "except":
                if not try_state[0]:
                    raise SyntaxError(f"except without try at {current_source}:{current_index}")
                # if there was an exception saved, let execution continue and set Error variable
                if try_state[2]:
                    variables["Error"] = try_state[2]
                    try_state[0] = False
                    try_state[1] = None
                    try_state[2] = None
                else:
                    # no error occurred: skip until done
                    j = current_index + 1
                    while j < len(current_lines):
                        tks = tokenize(current_lines[j])
                        if tks and tks[0] == "done":
                            current_index = j
                            break
                        j += 1

            case "done":
                # close try/except
                try_state = [False, None, None]

            case "end":
                print("\nProgram ended")
                try:
                    input("")
                except:
                    pass
                exit(0)

            case _:
                # unknown command -> maybe the line is an expression starting with a function call (call as statement)
                # we already handled direct function-name call at top; if we get here, line is invalid command
                raise SyntaxError(f"Unknown command '{cmd}' at {current_source}:{current_index}")

    # main execution loop
    while True:
        try:
            # update current_lines (in case current_source changed)
            current_lines = sources_state[current_source]
            if current_index >= len(current_lines):
                # maybe return to a caller frame if we had any (not using functionStack in this version)
                break

            line = current_lines[current_index]
            parsed = tokenize(line)
            if not parsed:
                current_index += 1
                continue

            # detect direct function call as statement
            first = parsed[0]
            if first in functionIndexs.get(current_source, {}) or first in functionIndexs.get("main", {}):
                # call as statement
                src = current_source if first in functionIndexs.get(current_source, {}) else "main"
                startIndex, argData = functionIndexs[src][first]
                num_args = argData[0]
                argNames = argData[1:]
                args_for_call = [ parseValue(tok)[0] for tok in parsed[1:] ]
                if len(args_for_call) != num_args:
                    raise TypeError(f"Function {first} expects {num_args} args, got {len(args_for_call)} at {current_source}:{current_index}")
                execute_function_call(first, args_for_call)
                current_index += 1
                continue

            # normal processing
            process_line(parsed, line)

            # handle while return pointer
            if "_while_return_index" in variables:
                ret_index = variables.pop("_while_return_index")
                current_index = ret_index + 1
                continue
            if "_for_return_index" in variables:
                ret_index = variables.pop("_for_return_index")
                current_index = ret_index + 1
                continue

            current_index += 1

        except Exception as e:
            # try/except support
            if try_state[0]:
                # jump to except and store error message
                current_index = try_state[1]
                try_state[2] = str(e)
                try_state[0] = False  # we'll handle except block next
                continue

            # otherwise print full helpful error and exit loop
            tb = traceback.extract_tb(e.__traceback__)
            lineno = tb[-1].lineno if tb else "?"
            print("=== RUNTIME ERROR ===")
            print(f"Error: {e}")
            print(f"At: {current_source}:{current_index}")
            print(f"Line: {line.strip()}")
            print(f"Traceback line: {lineno}")
            print("Variables snapshot (partial):")
            try:
                # print a small selection to avoid being too verbose
                cnt = 0
                for k, v in list(variables.items())[:50]:
                    print(f"  {k}: {v}")
                    cnt += 1
                    if cnt > 50:
                        break
            except Exception:
                pass
            print("=====================")
            break

    print("\nProgram ended")
    return None

# 1K lines @ 8/10/2025 5:38PM -- back

if __name__ == "__main__":
    import os

    runRuby('''
    def add (a, b)
  return a + b
endfunc

var s = add(2,3) + 10
print "s should be 15 ->", s

add(5,6)
print "after statement call return ->", return
    
    ''')

    runRuby(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "testSuite.ru")).read(), {"mylib":open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mylib.ru")).read()})

