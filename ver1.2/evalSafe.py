import re

def SafeEval(expr: str, expressionParcer):
    # Tokenize
    tokens = re.findall(
        r'''==|!=|>=|<=|//|\*\*|and|or|not|in|index|pop|len|sqrt|cbrt|sin|cos|tan|\d+\.?\d*|\w+|[()+\-*/%^<>=|&~]''',
        expr
    )

    if len(tokens) == 1:
        tokens.extend(["+", "0"])

    # Insert implicit multiplication
    new_tokens = []
    for i, token in enumerate(tokens):
        if i > 0:
            prev = tokens[i - 1]
            if (
                re.fullmatch(r'\w+|\)', prev) and
                (token == '(' or re.fullmatch(r'\w+|\d+', token))
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
        if re.fullmatch(r'\d+\.?\d*|\w+', token):  # literal or variable
            output.append(token)
            expect_operand = False
        elif token in unary_operators and expect_operand:
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
        elif token == '(':
            stack.append(('paren', token))
            expect_operand = True
        elif token == ')':
            while stack and stack[-1][1] != '(':
                pop_op()
            if stack and stack[-1][1] == '(':
                stack.pop()  # remove '('
            if stack and stack[-1][0] == 'unary':
                typ, op = stack.pop()
                arg = output.pop()
                output.append([op, arg])
            expect_operand = False

    while stack:
        pop_op()

    ast = output[0]

    # Evaluate AST bottom-up
    def evaluate(node):
        if isinstance(node, str):
            return node
        if len(node) == 2:  # unary
            op, a = node
            return expressionParcer([op, str(evaluate(a))])
        elif len(node) == 3:  # binary
            a, op, b = node
            return expressionParcer([str(evaluate(a)), op, str(evaluate(b))])

    return evaluate(ast)



if __name__ == "__main__":
    arg1 = 10
    arg2 = 32

    def f(x):
        print(x)
        # Flatten to string expression
        def flatten(e):
            if isinstance(e, list):
                return "(" + " ".join(flatten(i) for i in e) + ")"
            return str(e)
        expr = flatten(x)
        return eval(expr, globals())

    f(SafeEval("arg1 - 1", f))
    f(SafeEval("arg1 + arg2", f))
    f(SafeEval("arg1 // 12", f))
    f(SafeEval("10 / -2", f))
    f(SafeEval("12 * 3", f))
    f(SafeEval("3 + 7 / 2", f))
