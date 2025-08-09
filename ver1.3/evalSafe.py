import re, math

token_pattern = re.compile(
    r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|==|!=|>=|<=|//|\*\*|'
    r'and|or|not|index|in|pop|len|sqrt|cbrt|sin|cos|tan|'
    r'\d+\.?\d*|\w+|[()+\-*/%^<>=|&~]'
)

def SafeEval(expr: str, expressionParcer):
    # Tokenize
    tokens = token_pattern.findall(
        expr
    )

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
        if len(node) == 2:  # unary
            op, a = node
            return expressionParcer([op, str(evaluate(a))])
        elif len(node) == 3:  # binary
            a, op, b = node
            return expressionParcer([str(evaluate(a)), op, str(evaluate(b))])

    return evaluate(ast)



if __name__ == "__main__":

    variables = {
        "x":0,
        "y":"hello, world",
        "_":0,
        "i":10
    }

    
    def isdigit(string):
        try:
            float(string)
            return True
        except:
            return False

    def parseValue(valueStr, varContext=None):
        if varContext is None:
            varContext = variables
        if valueStr.lower() == "null": return 0, "literal int"
        if valueStr.lower() == "none": return 0, "literal int"
        if valueStr.lower() == "nil": return 0, "literal int"
        if valueStr.lower() == "true": return 1, "literal int"
        if valueStr in varContext:
            val = varContext[valueStr]
            return val, "var int" if isinstance(val, (int, float)) else "var str"
        elif (valueStr.startswith('"') and valueStr.endswith('"')) or (valueStr.startswith("'") and valueStr.endswith("'")):
            return valueStr[1:-1], "literal str"
        elif isdigit(valueStr):
            return (float(valueStr) if "." in valueStr else int(valueStr)), "literal int"
        else:
            raise ValueError(f"Value | {valueStr} | is not valid ")

    def mathParcer(token):
        if len(token) == 3:
            a_ = parseValue(token[0])
            op = token[1]
            b_ = parseValue(token[2])
            a = a_[0]
            b = b_[0]

            if a_[1] in ["var int", "literal int"] and b_[1] in ["var int", "literal int"]:
                match op: # + - * / // ^ | & == != >= <= < > and or
                    case "+": return a + b
                    case "-": return a - b
                    case "/": return a // b
                    case "*": return a * b
                    case "//": return a // b
                    case "**": return a ** b
                    case "^": return a ^ b
                    case "|": return a | b
                    case "&": return a & b
                    case "==": return int(a == b)
                    case "!=": return int(a != b)
                    case ">=": return int(a >= b)
                    case "<=": return int(a <= b)
                    case ">": return int(a > b)
                    case "<": return int(a < b)
                    case "and": return int(a and b)
                    case "or": return int(a or b)
            elif a_[1] in ["var str", "literal str"] and b_[1] in ["var str", "literal str"]:
                match op:
                    case "+": return (a + b)
                    case "in": return (int(a in b))
                    case "==": return (a == b)
                    case "!=": return (a != b)

            elif a_[1] in ["var str", "literal str"] and b_[1] in ["var int", "literal int"]:
                match op:
                    case "index": return (a[b])
                    case "pop": return (''.join((lambda l: (l.pop(b), l)[1])(list(a))))
                    case "*": return (a * b)
        elif len(token) == 2:
            a_ = parseValue(token[1])
            op = token[0]
            a = a_[0]
            if a_[1] in ["var str", "literal str"]:
                match op:
                    case "len": return (len(a))
                    case "not": return (not a)
            elif a_[1] in ["var int", "literal int"]:
                match op: #cbrt sqrt not ~ tan sin cos
                    case "cbrt": return (math.cbrt(a))
                    case "sqrt": return (math.sqrt(a))
                    case "not": return (not a)
                    case "~": return (~a)
                    case "-": return (-a)
                    case "tan": return (math.tan(a))
                    case "sin": return (math.sin(a))
                    case "cos": return (math.cos(a))
        return 0

    print(SafeEval("x - 1",    mathParcer))
    print(SafeEval("x + _", mathParcer))
    print(SafeEval("x // 12",  mathParcer))
    print(SafeEval("10 / -2",     mathParcer))
    print(SafeEval("12 * 3",      mathParcer))
    print(SafeEval("3 + 7 / 2",   mathParcer))
    print(SafeEval("'hello' index 0", mathParcer))
    print(SafeEval("'hello' index 1", mathParcer))
    print(SafeEval("'hello' index 2", mathParcer))
    print(SafeEval("'hello' index 3", mathParcer))
    print(SafeEval("'hello' index 4", mathParcer))
    print(SafeEval("'*' * i", mathParcer))