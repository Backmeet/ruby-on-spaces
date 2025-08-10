import re, math

base_pattern = re.compile(
    r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|'
    r'==|!=|>=|<=|//|\*\*|'
    r'and|or|not|index|in|pop|len|sqrt|cbrt|sin|cos|tan|'
    r'\d+\.?\d*|\w+|[()+\-*/%^<>=|&~]'
)

def tokenizeBrackets(s):
    tokens = []
    i = 0
    while i < len(s):
        if s[i] == '[':
            start = i
            depth = 0
            while i < len(s):
                if s[i] == '[':
                    depth += 1
                elif s[i] == ']':
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                i += 1
            tokens.append(s[start:i])
        else:
            m = base_pattern.match(s, i)
            if m:
                tokens.append(m.group(0))
                i = m.end()
            else:
                i += 1
    return tokens

def SafeEval(expr: str, expressionParcer):
    # Tokenize
    tokens = tokenizeBrackets(expr)

    if len(tokens) == 1:
        tokens.extend(["*", "1"])
    
    # reserved so that you dont treat them as varibles
    word_operators = {
        'and', 'or', 'not', 'in', 'index', 'pop', 'len',
        'sqrt', 'cbrt', 'sin', 'cos', 'tan'
    }

    # Insert implicit multiplication
    new_tokens = []
    for i, token in enumerate(tokens):
        if i > 0:
            prev = tokens[i - 1]
            # If previous is a variable or closing paren — and current is a variable, number or opening paren
            if (
                (re.fullmatch(r'\w+', prev) and prev not in word_operators) or prev == ')'
            ) and (
                token == '(' or re.fullmatch(r'\d+\.?\d*|\w+', token) and token not in word_operators
            ):
                new_tokens.append('*')
        new_tokens.append(token)
    tokens = new_tokens

    # Binary operator precedence and associativity
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
        'index': (5, 'left'),
        'pop': (5, 'left'),
        'and': (3, 'left'),
        'or': (2, 'left'),
    }

    # Unary operators
    unary_operators = {'-', 'not', '~', 'sqrt', 'cbrt', 'sin', 'cos', 'tan', 'len'}

    output = []
    stack = []

    def pop_op():
        typ, op = stack.pop()
        if typ == 'unary':
            arg = output.pop()
            output.append([op, arg])
        else:  # binary
            b = output.pop()
            a = output.pop()
            output.append([a, op, b])

    # Parser loop
    expect_operand = True
    for token in tokens:
        if token in unary_operators and expect_operand:
            stack.append(('unary', token))
            expect_operand = True

        elif token in precedence:
            while stack and stack[-1][0] == 'binary':
                _, top = stack[-1]
                p1, a1 = precedence[token]
                p2, _ = precedence[top]
                if (a1 == 'left' and p1 <= p2) or (a1 == 'right' and p1 < p2):
                    pop_op()
                else:
                    break
            stack.append(('binary', token))
            expect_operand = True

        elif re.fullmatch(r'\d+\.?\d*', token):  # number
            output.append(token)
            expect_operand = False

        elif (token.startswith('"') and token.endswith('"')) or (token.startswith("'") and token.endswith("'")):
            output.append(token)
            expect_operand = False

        elif re.fullmatch(r'\w+', token):  # variable name
            output.append(token)
            expect_operand = False

        elif token.startswith("[") and token.endswith("]"):  # list literal
            output.append(token)
            expect_operand = False

        elif token == '(':
            stack.append(('paren', token))
            expect_operand = True

        elif token == ')':
            while stack and stack[-1][1] != '(':
                pop_op()
            if stack and stack[-1][1] == '(':
                stack.pop()  # Remove '('
            if stack and stack[-1][0] == 'unary':
                typ, op = stack.pop()
                arg = output.pop()
                output.append([op, arg])
            expect_operand = False

        else:
            raise ValueError(f"Unexpected token: {token}")

    while stack:
        pop_op()

    ast = output[0]

    # Evaluate AST bottom-up
    def evaluate(node):
        if isinstance(node, str):
            return node
        
        if len(node) == 2:
            op, a = node
            aval = evaluate(a)
            return expressionParcer([op, aval if isinstance(aval, list) else str(aval)])

        elif len(node) == 3:  # binary
            a, op, b = node
            aval = evaluate(a)
            bval = evaluate(b)
            # Only convert to str if not a list
            return expressionParcer([
                aval if isinstance(aval, list) else str(aval),
                op,
                bval if isinstance(bval, list) else str(bval)
            ])

    return evaluate(ast)
