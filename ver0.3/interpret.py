import math
import re, time, pygame
from sys import argv

fileRead = open(argv[1], "r").readlines()

def isdigit(string):
    try:
        float(string)
        return True
    except Exception:
        return False

def tokenize(line: str):
    tokens = re.findall(r"'[^']*'|\"[^\"]*\"|\S+", line.strip())
    return tokens

def parseValue(valueStr, varContext):
    global i
    if valueStr in varContext:  # Variable lookup
        val = varContext[valueStr]
        value_type = "var int" if isinstance(val, int) or isinstance(val, float) else "var str"
        return val, value_type
    elif (valueStr.startswith("'") and valueStr.endswith("'")) or \
         (valueStr.startswith('"') and valueStr.endswith('"')):
        return valueStr[1:-1], "literal str"
    elif isdigit(valueStr):
        if "." in valueStr:
            return float(valueStr), "literal int"
        else:
            return int(valueStr), "literal int"
    else:
        raise ValueError(f"Value | {valueStr} | is not valid | line {i} |")

variables = {"return": None}
whileLoops = []
functionIndexs = {}
functionStack = []
screen = None
clock = None
windowQuit = False
keydown, keyup = "", ""
key = ""

i = 0
while i < len(fileRead):
    line = fileRead[i]
    parsed = tokenize(line)
    if not parsed:
        i += 1
        continue

    cmd = parsed[0]
    args = parsed[1:]

    match cmd:
        case "print":
            out = "".join(str(parseValue(token, variables)[0]) for token in args)
            print(out.strip())
        
        case "flush":
            out = "".join(str(parseValue(token, variables)[0]) for token in args)
            print(out.strip(), flush=1, end='\r')
        

        case "var":
            match args[0]:
                case "new":
                    parsed1 = parseValue(args[2], variables)
                    variables[args[1]] = parsed1[0]
                case "math":
                    # Binary operation: var math <operand1> <op> <operand2> = <target>
                    if len(args) == 6 and args[4] == "=":
                        parsed1 = parseValue(args[1], variables)
                        parsed2 = parseValue(args[3], variables)
                        op = args[2]
                        # Check if both operands are ints...
                        if parsed1[1] in ["var int", "literal int"] and parsed2[1] in ["var int", "literal int"]:
                            value1 = parsed1[0]
                            value2 = parsed2[0]
                            match op:
                                case "+": result = value1 + value2
                                case "-": result = value1 - value2
                                case "*": result = value1 * value2
                                case "//": result = value1 // value2
                                case "/": result = value1 / value2
                                case "**": result = value1 ** value2
                                case "&": result = value1 & value2
                                case "|": result = value1 | value2
                                case "^": result = value1 ^ value2
                                case "==": result = 1 if value1 == value2 else 0
                                case "!=": result = 1 if value1 != value2 else 0
                                case ">=": result = 1 if value1 >= value2 else 0
                                case "<=": result = 1 if value1 <= value2 else 0
                                case ">": result = 1 if value1 > value2 else 0
                                case "<": result = 1 if value1 < value2 else 0
                                case "and": result = 1 if value1 and value2 else 0
                                case "or": result = 1 if value1 or value2 else 0
                                case _:
                                    raise ValueError(f"On line {i}: Unsupported operator '{op}' for int operands.")
                            variables[args[5]] = float(result)
                        # Both operands are strings
                        elif parsed1[1] in ["var str", "literal str"] and parsed2[1] in ["var str", "literal str"]:
                            if op not in ["+", "==", "!="]:
                                raise ValueError(f"On line {i}: For string operands, only '+', '==' and '!=' are allowed.")
                            if op == "+":
                                variables[args[5]] = parsed1[0] + parsed2[0]
                            elif op == "==":
                                variables[args[5]] = 1 if parsed1[0] == parsed2[0] else 0
                            elif op == "!=":
                                variables[args[5]] = 1 if parsed1[0] != parsed2[0] else 0
                        else:
                            raise ValueError(f"On line {i}: Mixing types is not allowed in binary math.")
                    # Mono-operation: var math <operand> <op> = <target>
                    elif len(args) == 5 and args[3] == "=":
                        parsed1 = parseValue(args[1], variables)
                        op = args[2]
                        if parsed1[1] in ["var int", "literal int"]:
                            value1 = parsed1[0]
                            match op:
                                case "sqrt": result = value1 ** 0.5
                                case "cbrt": result = value1 ** (1/3)
                                case "~": result = ~value1
                                case "not": result = 0 if value1 else 1
                                case "tan": result = math.tan(value1)
                                case "sin": result = math.sin(value1)
                                case "cos": result = math.cos(value1)
                                case _:
                                    raise ValueError(f"On line {i}: Unsupported operator '{op}' for int operand.")
                            variables[args[4]] = float(result)
                        elif parsed1[1] in ["var str", "literal str"]:
                            if op != "not":
                                raise ValueError(f"On line {i}: For string operand, only 'not' is allowed.")
                            # For a string: non-empty is True -> convert to 0; empty is False -> convert to 1.
                            variables[args[4]] = 0 if parsed1[0] else 1
                        else:
                            raise ValueError(f"On line {i}: Invalid operand type in mono math.")
                    else:
                        raise ValueError(f"On line {i}: Invalid math syntax.")
                case "set":
                    if args[2] != "=":
                        raise SyntaxError(f"= not found in | line {i} | syntax error")
                    parsed1 = parseValue(args[1], variables)
                    parsed2 = parseValue(args[3], variables)
                    if parsed1[1] not in ["var str", "var int"]:
                        raise ValueError(f"On line {i}: Invalid var name, variable not found")
                    variables[args[1]] = parsed2[0]

        case "while":
            match args[0]:
                case "begin":
                    whileLoops.append(i)
                case "end":
                    parsed1 = parseValue(args[1], variables)
                    lastLoopIndex = whileLoops.pop()
                    if parsed1[0]:
                        i = lastLoopIndex - 1

        case "if":
            match args[0]:
                case "begin":
                    parsed1 = parseValue(args[1], variables)
                    if not parsed1[0]:
                        for j in range(i + 1, len(fileRead)):
                            tokens = tokenize(fileRead[j])
                            if tokens and tokens[0] == "if" and tokens[1] == "end":
                                i = j
                                break
                case "end":
                    pass

        case "def":
            func_name = args[0]
            num_args = parseValue(args[1], variables)
            if num_args[1] not in ["literal int"]:
                raise SyntaxError(f"invalid function syntax | line {i} |")
            num_args = num_args[0]

            start_index = i + 1
            end_index = None
            for j in range(start_index, len(fileRead)):
                tokens = tokenize(fileRead[j])
                if tokens and tokens[0] == "endfunc":
                    end_index = j
                    break
            if end_index is None:
                raise ValueError(f"Function {func_name} has no return statement.")
            functionIndexs[func_name] = (start_index, num_args, end_index)
            i = end_index

        case "return":
            ret_val = parseValue(args[0], variables)[0]
            variables["return"] = ret_val
            if functionStack:
                i = functionStack.pop() - 1

        case "call":
            func_name = args[0]
            if func_name not in functionIndexs:
                raise ValueError(f"Function {func_name} not defined | line {i}")
            start_index, num_args, end_index = functionIndexs[func_name]
            if len(args[1:]) != num_args:
                raise ValueError(f"Function {func_name} expects {num_args} arguments, got {len(args[1:])} | line {i}")
            for idx, arg in enumerate(args[1:]):
                variables[f"arg{idx+1}"] = parseValue(arg, variables)[0]
            functionStack.append(i + 1)
            i = start_index - 1

        case "delay":
            parsed1 = parseValue(args[0], variables)
            if parsed1[1] in ["var int", "literal int"]:
                time.sleep(parsed1[0])
            else:
                raise ValueError(f"On line {i}: delay value must be an int")
        case "input":
            parsed1 = parseValue(args[0], variables)
            parsed2 = parseValue(args[1], variables)
            if parsed1[1] not in ["var str", "literal str"]:
                raise ValueError(f"On line {i}: prompt string must be a string")
            if parsed2[1] not in ["var str", "var int"]:
                raise ValueError(f"On line {i}: target variable must be a variable")
            variables[args[1]] = input(parsed1[0])
        case "convert":
            parsed1 = parseValue(args[0], variables)
            parsed2 = parseValue(args[1], variables)
            if parsed2[1] not in ["var str", "var int"]:
                raise ValueError(f"On line {i}: target variable not found")
            if isinstance(parsed1[0], float) or isinstance(parsed1[0], int):
                variables[args[1]] = str(parsed1[0])
            elif isinstance(parsed1[0], str):
                try:
                    variables[args[1]] = float(parsed1[0])
                except ValueError:
                    raise ValueError(f"wrong format str convert int value | line {i} | int convert error")
        case "window":
            match args[0]:
                case "init":
                    parsed1 = parseValue(args[1], variables)
                    parsed2 = parseValue(args[2], variables)

                    if parsed1[1] not in ["var int", "literal int"] or parsed2[1] not in ["var int", "literal int"]:
                        raise ValueError(f"found str for int in window init | line {i} | found str for int")

                    screen = pygame.display.set_mode((parsed1[0], parsed2[0]))
                    clock = pygame.time.Clock()
                
                case "draw":
                    match args[1]:
                        case "line":
                            # Ensure there are enough arguments for line command
                            if len(args) < 10:
                                raise ValueError(f"Insufficient arguments for window draw line | line {i}")
                            
                            # Check if screen is initialized
                            if screen is None:
                                raise ValueError(f"Screen not initialized before drawing | line {i}")
                            
                            x1 = parseValue(args[2], variables)
                            y1 = parseValue(args[3], variables)
                            x2 = parseValue(args[4], variables)
                            y2 = parseValue(args[5], variables)
                            
                            r = parseValue(args[6], variables)
                            g = parseValue(args[7], variables)
                            b = parseValue(args[8], variables)
                            
                            thickness = parseValue(args[9], variables)

                            for val in [x1, x2, y1, y2, r, g, b, thickness]: 
                                if val[1] not in ["var int", "literal int"]: 
                                    raise ValueError("found str for int | line {i} |") 

                            pygame.draw.line(screen, (r[0], g[0], b[0]), (x1[0], y1[0]), (x2[0], y2[0]), thickness[0])
                        
                        case "rect":
                            # Expected: window draw rect <x1> <y1> <x2> <y2> <r> <g> <b>
                            if len(args) < 8:
                                raise ValueError(f"Insufficient arguments for window draw rect | line {i}")
                            
                            if screen is None:
                                raise ValueError(f"Screen not initialized before drawing | line {i}")
                            
                            x1 = parseValue(args[2], variables)
                            y1 = parseValue(args[3], variables)
                            x2 = parseValue(args[4], variables)
                            y2 = parseValue(args[5], variables)
                            
                            r = parseValue(args[6], variables)
                            g = parseValue(args[7], variables)
                            b = parseValue(args[8], variables)

                            for val in [x1, x2, y1, y2, r, g, b]: 
                                if val[1] not in ["var int", "literal int"]: 
                                    raise ValueError("found str for int | line {i} |") 


                            # Calculate the top-left coordinates and dimensions
                            rect_x = min(x1[0], x2[0])
                            rect_y = min(y1[0], y2[0])
                            rect_width = abs(x2[0] - x1[0])
                            rect_height = abs(y2[0] - y1[0])
                            
                            pygame.draw.rect(screen, (r[0], g[0], b[0]), (rect_x, rect_y, rect_width, rect_height))

                case "update":
                    windowQuit = False
                    keydown, keyup, key = "", "", ""

                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            windowQuit = True
                        if event.type == pygame.KEYDOWN:
                            keydown = event.unicode
                        else:
                            keydown = ""
                        if event.type == pygame.KEYUP:
                            keyup = event.unicode
                        else:
                            keyup = ""
                    
                case "flip":
                    pygame.display.update()
                
                case "fill":
                    r = parseValue(args[1], variables)
                    g = parseValue(args[2], variables)
                    b = parseValue(args[3], variables)

                    for val in [r, g, b]: 
                        if val[1] not in ["var int", "literal int"]: 
                            raise ValueError("found str for int | line {i} |") 

                    if screen is None:
                        raise ValueError(f"Screen not initialized before drawing | line {i}")

                    screen.fill((r[0], b[0], g[0]))


                case "event":
                    match args[1]:
                        case "quit":
                            parsed1 = parseValue(args[2], variables)

                            if parsed1[1] not in ["var int", "var str"]:
                                raise ValueError("can not assign event value to literal | line {i} | found literla for var")
                            
                            variables[args[2]] = windowQuit
                        
                        case "keydown":
                            parsed1 = parseValue(args[2], variables)

                            if parsed1[1] not in ["var int", "var str"]:
                                raise ValueError("can not assign event value to literal | line {i} | found literal for var")
                        
                            variables[args[2]] = keydown
                        
                        case "keyup":
                            parsed1 = parseValue(args[2], variables)

                            if parsed1[1] not in ["var int", "var str"]:
                                raise ValueError("can not assign event value to literal | line {i} | found literal for var")
                            
                            variables[args[2]] = keyup
                        
                        case "key":
                            parsed1 = parseValue(args[2], variables)

                            if parsed1[1] not in ["var int", "var str"]:
                                raise ValueError("can not assign event value to literal | line {i} | found literal for var")
                            
                            for key_, pressed in enumerate(pygame.key.get_pressed()):
                                if pressed:
                                    key = key_
                                    break

                            variables[args[2]] = key
                case "fps":
                    parsed1 = parseValue(args[1], variables)

                    if parsed1[1] not in ["var int", "literal int"]:
                        raise ValueError(f"target fps not int | line {i} |")

                    if not clock and screen:
                        raise ValueError(f"Screen and Cloc knot initialized before setting target fps | line {i}")


                case "quit":
                    pygame.quit()

        case "end":
            print("\nProgram ended")
            input("")
            exit(0)

    
    i += 1

print("\nProgram ended")
input("")