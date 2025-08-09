try:
    import os, random, math
    import re, time, pygame
    import string
    from sys import argv
    sources = {}
    sources["main"] = open(argv[1], "r").readlines()

    def editOrAddVariables(name, value):
        global variables
        variables[name] = value
    
    def get_variable(name):
        global variables
        if name in variables:
            return variables[name]
        else:
            raise NameError("Variable not found")
    
    def axcessFunction(name, source="main"):
        global functionIndexs
        if source in functionIndexs and name in functionIndexs[source]:
            return functionIndexs[source][name]
        else:
            raise NameError(f"Function {name} not found in source {source}")

    def addFunction(name, source, args, start_index, end_index):
        global functionIndexs
        if source not in functionIndexs:
            functionIndexs[source] = {}
        functionIndexs[source][name] = (start_index, args, end_index)

    def getLines(source):
        global sources
        if source in sources:
            return sources[source]
        else:
            raise ImportError(f"Source {source} not found")
    
    def setLineByIndex(source, index, line):
        global sources
        if source in sources:
            if 0 <= index < len(sources[source]):
                sources[source][index] = line
            else:
                while len(sources[source]) <= index:
                    sources[source].append("")
                sources[source][index] = line
        else:
            raise ValueError(f"Source {source} not found")



    def safeExec(code):
        allowed_builtins = {
            "print": print,
            "input": input,
            "format": format,
            "range": range,
            "len": len,
            "open": open
        }

        exec_globals = {
            "__builtins__": allowed_builtins,
            "accessFunction": axcessFunction,
            "editVariable": editOrAddVariables,
            "get_variable": get_variable,
            "addFunction": addFunction,
            "math": math,
            "random": random,
            "pygame": pygame,
            "string": string,
            "re": re,
            "time": time,
            "datetime": __import__("datetime").datetime
        }

        try:
            exec(code, exec_globals, {})
        except Exception as e:
            raise RuntimeError(f"Error executing code: {e}")

    def isdigit(string):
        try:
            float(string)
            return True
        except Exception:
            return False

    t = re.compile(r"'[^']*'|\"[^\"]*\"|\S+")
    def tokenize(line: str):
        global t
        tokens = t.findall(line.strip())
        return tokens

    def parseValue(valueStr, varContext=None):
        global current_index, variables
        if not varContext:
            varContext = variables
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
            raise ValueError(f"Value | {valueStr} | is not valid | line {current_index} in {current_source} |")

    variables = {"return": None}
    whileLoops = []
    functionIndexs = {"main": {}}
    functionStack = []
    screen = None
    windowQuit = False
    namespace = {}
    # {name:{function 1: (start_index, # of args), function 2: (start_index, # of args) ... function n: (start_index, # of args)}}

    current_source = "main"
    current_lines = sources[current_source]
    current_index = 0

    while True:
        if current_index >= len(current_lines):
            if functionStack:
                # Return to caller if stack isn't empty
                current_source, current_index = functionStack.pop()
                continue
            else:
                break

        line = current_lines[current_index]

        parsed = tokenize(line)
        if not parsed:
            current_index += 1
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
            
            case "rnd":
                match args[0]:
                    case "int":
                        parsed1 = parseValue(args[1], variables)
                        origin = parseValue(args[2])
                        stop = parseValue(args[3])
                        if parsed1[1] not in ["var int", "var str"]:
                            raise NameError(f"Can not assign a random int value to a literal on line {current_index} in {current_source}")
                        if origin[1] not in ["literal int", "var int"] or stop[1] not in ["literal int", "var int"]:
                            raise ValueError(f"origin | stop has to be a int for a random int genreation on line {current_index} in {current_source}")
                        
                        variables[args[1]] = random.randint(origin[0], stop[0])
                    
                    case "str":
                        parsed1 = parseValue(args[1])
                        length = parseValue(args[2])
                        if parsed1[1] not in ["var int", "var str"]:
                            raise NameError(f"Can not assign a random string value to a literal on line {current_index} in {current_source}")
                        if origin[1] not in ["literal int", "var int"] or stop[1] not in ["literal int", "var int"]:
                            raise ValueError(f"length has to be a int for a random str genreation on line {current_index} in {current_source}")
                        
                        _ = ""
                        for i in range(length[0]): _ += string.printable[random.randint(0, len(string.printable) - 1)]
                        variables[args[1]] = _
                        
            case "INTERPRETER_LANG":
                match args[0]:
                    case "begin":
                        py_lines = []
                        for j in range(current_index + 1, len(current_lines)):
                            tokens = tokenize(current_lines[j])
                            if not tokens:
                                continue
                            if tokens[0] == "INTERPRETER_LANG" and tokens[1] == "end":
                                break
                            py_lines.append(current_lines[j])
                        
                        safeExec("".join(py_lines))
                        
                    case "end":
                        # This is handled by the loop, so we just continue
                        pass


            case "var":
                match args[0]:
                    case "new":
                        parsed1 = parseValue(args[2])
                        variables[args[1]] = parsed1[0]
                    case "math":
                        # Binary operation: var math <operand1> <op> <operand2> = <target>
                        if len(args) == 6 and args[4] == "=":
                            parsed1 = parseValue(args[1])
                            parsed2 = parseValue(args[3])
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
                                        raise ValueError(f"On line {current_index} in {current_source}: Unsupported operator '{op}' for int operands.")
                                variables[args[5]] = float(result)
                            # Both operands are strings
                            elif parsed1[1] in ["var str", "literal str"] and parsed2[1] in ["var str", "literal str"]:
                                if op not in ["+", "==", "!="]:
                                    raise ValueError(f"On line {current_index} in {current_source}: For string operands, only '+', '==' and '!=' are allowed.")
                                if op == "+":
                                    variables[args[5]] = parsed1[0] + parsed2[0]
                                elif op == "==":
                                    variables[args[5]] = 1 if parsed1[0] == parsed2[0] else 0
                                elif op == "!=":
                                    variables[args[5]] = 1 if parsed1[0] != parsed2[0] else 0
                            else:
                                raise ValueError(f"On line {current_index} in {current_source}: Mixing types is not allowed in binary math.")
                        # Mono-operation: var math <operand> <op> = <target>
                        elif len(args) == 5 and args[3] == "=":
                            parsed1 = parseValue(args[1])
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
                                        raise ValueError(f"On line {current_index} in {current_source}: Unsupported operator '{op}' for int operand.")
                                variables[args[4]] = float(result)
                            elif parsed1[1] in ["var str", "literal str"]:
                                if op != "not":
                                    raise ValueError(f"On line {current_index} in {current_source}: For string operand, only 'not' is allowed.")
                                # For a string: non-empty is True -> convert to 0; empty is False -> convert to 1.
                                variables[args[4]] = 0 if parsed1[0] else 1
                            else:
                                raise ValueError(f"On line {current_index} in {current_source}: Invalid operand type in mono math.")
                        else:
                            raise ValueError(f"On line {current_index} in {current_source}: Invalid math syntax.")
                    case "set":
                        if args[2] != "=":
                            raise SyntaxError(f"= not found in | line {current_index} in {current_source} | syntax error")
                        parsed1 = parseValue(args[1])
                        parsed2 = parseValue(args[3])
                        if parsed1[1] not in ["var str", "var int"]:
                            raise ValueError(f"On line {current_index} in {current_source}: Invalid var name, variable not found")
                        variables[args[1]] = parsed2[0]

            case "while":
                match args[0]:
                    case "begin":
                        whileLoops.append(current_index)
                    case "end":
                        if not whileLoops:
                            raise SyntaxError(f"Unexpected while end with no matching begin | line {current_index} in {current_source}")
                        parsed1 = parseValue(args[1])
                        lastLoopIndex = whileLoops.pop()
                        if parsed1[0]:
                            current_index = lastLoopIndex - 1


            case "if":
                match args[0]:
                    case "begin":
                        parsed1 = parseValue(args[1])
                        if not parsed1[0]:
                            depth = 1
                            j = current_index + 1
                            while j < len(current_lines):
                                tokens = tokenize(current_lines[j])
                                if tokens:
                                    if tokens[0] == "if" and tokens[1] == "begin":
                                        depth += 1
                                    elif tokens[0] == "if" and tokens[1] == "end":
                                        depth -= 1
                                        if depth == 0:
                                            break
                                j += 1
                            current_index = j
                    case "end":
                        pass

            case "def":
                func_name = args[0]
                num_args = parseValue(args[1])
                if num_args[1] not in ["literal int"]:
                    raise SyntaxError(f"invalid function syntax | line {current_index} in {current_source} |")
                num_args = num_args[0]

                start_index = current_index + 1
                end_index = None
                for j in range(start_index, len(current_lines)):
                    tokens = tokenize(current_lines[j])
                    if tokens and tokens[0] == "return":
                        end_index = j
                        break
                if end_index is None:
                    raise ValueError(f"Function {func_name} has no return statement.")
                functionIndexs[current_source][func_name] = (start_index, num_args, end_index)
                current_index = end_index
                current_lines = sources[current_source]
                continue

            case "return":
                ret_val = parseValue(args[0])[0]
                variables["return"] = ret_val
                if functionStack:
                    current_source, current_index = functionStack.pop()
                    current_lines = sources[current_source]
                    continue

            case "call":
                func_name = args[0]
                found = None

                # Search all sources for the function
                for source_id, funcs in functionIndexs.items():
                    if func_name in funcs:
                        found = (source_id, funcs[func_name])
                        break

                if not found:
                    raise ValueError(f"Function {func_name} not defined | line {current_index} in {current_source}")

                target_source, (start_index, num_args, end_index) = found

                if len(args[1:]) != num_args:
                    raise ValueError(f"Function {func_name} expects {num_args} arguments, got {len(args[1:])} | line {current_index} in {current_source}")

                # Set up arguments
                for idx, arg in enumerate(args[1:]):
                    variables[f"arg{idx+1}"] = parseValue(arg)[0]

                # Save current position to return to
                functionStack.append((current_source, current_index + 1))

                # Switch to called function
                current_source = target_source
                current_lines = sources[current_source]
                current_index = start_index
                continue

            case "delay":
                parsed1 = parseValue(args[0])
                if parsed1[1] in ["var int", "literal int"]:
                    time.sleep(parsed1[0])
                else:
                    raise ValueError(f"On line {current_index} in {current_source}: delay value must be an int")
            case "input":
                parsed1 = parseValue(args[0])
                parsed2 = parseValue(args[1])
                if parsed1[1] not in ["var str", "literal str"]:
                    raise ValueError(f"On line {current_index} in {current_source}: prompt string must be a string")
                if parsed2[1] not in ["var str", "var int"]:
                    raise ValueError(f"On line {current_index} in {current_source}: target variable must be a variable")
                variables[args[1]] = input(parsed1[0])
            case "convert":
                parsed1 = parseValue(args[0])
                parsed2 = parseValue(args[1])
                if parsed2[1] not in ["var str", "var int"]:
                    raise ValueError(f"On line {current_index} in {current_source}: target variable not found or is not a convertable type of [int -> str, str -> int]")
                if isinstance(parsed1[0], float) or isinstance(parsed1[0], int):
                    variables[args[1]] = str(parsed1[0])
                elif isinstance(parsed1[0], str):
                    try:
                        variables[args[1]] = float(parsed1[0])
                    except ValueError:
                        raise ValueError(f"wrong format str convert int value | line {current_index} in {current_source} | int convert error")
            case "window":
                match args[0]:
                    case "init":
                        parsed1 = parseValue(args[1])
                        parsed2 = parseValue(args[2])

                        if parsed1[1] not in ["var int", "literal int"] or parsed2[1] not in ["var int", "literal int"]:
                            raise ValueError(f"found str for int in window init | line {current_index} in {current_source} | found str for int")

                        screen = pygame.display.set_mode((parsed1[0], parsed2[0]), pygame.RESIZABLE)
                    
                    case "draw":
                        match args[1]:
                            case "line":
                                # Ensure there are enough arguments for line command
                                if len(args) < 10:
                                    raise ValueError(f"Insufficient arguments for window draw line | line {current_index} in {current_source}")
                                
                                # Check if screen is initialized
                                if screen is None:
                                    raise ValueError(f"Screen not initialized before drawing | line {current_index} in {current_source}")
                                
                                x1 = parseValue(args[2])
                                y1 = parseValue(args[3])
                                x2 = parseValue(args[4])
                                y2 = parseValue(args[5])
                                
                                r = parseValue(args[6])
                                g = parseValue(args[7])
                                b = parseValue(args[8])
                                
                                thickness = parseValue(args[9])

                                for val in [x1, x2, y1, y2, r, g, b, thickness]: 
                                    if val[1] not in ["var int", "literal int"]: 
                                        raise ValueError(f"found str for int | line {current_index} in {current_source} |") 

                                pygame.draw.line(screen, (r[0], g[0], b[0]), (x1[0], y1[0]), (x2[0], y2[0]), thickness[0])
                            
                            case "rect":
                                # Expected: window draw rect <x1> <y1> <x2> <y2> <r> <g> <b>
                                if len(args) < 8:
                                    raise ValueError(f"Insufficient arguments for window draw rect | line {current_index} in {current_source}")
                                
                                if screen is None:
                                    raise ValueError(f"Screen not initialized before drawing | line {current_index} in {current_source}")
                                
                                x1 = parseValue(args[2])
                                y1 = parseValue(args[3])
                                x2 = parseValue(args[4])
                                y2 = parseValue(args[5])
                                
                                r = parseValue(args[6])
                                g = parseValue(args[7])
                                b = parseValue(args[8])

                                for val in [x1, x2, y1, y2, r, g, b]: 
                                    if val[1] not in ["var int", "literal int"]: 
                                        raise ValueError(f"found str for int | line {current_index} in {current_source} |") 


                                # Calculate the top-left coordinates and dimensions
                                rect_x = min(x1[0], x2[0])
                                rect_y = min(y1[0], y2[0])
                                rect_width = abs(x2[0] - x1[0])
                                rect_height = abs(y2[0] - y1[0])
                                
                                pygame.draw.rect(screen, (r[0], g[0], b[0]), (rect_x, rect_y, rect_width, rect_height))

                    case "update":
                        windowQuit = False
                        for event in pygame.event.get():
                            if event.type == pygame.QUIT:
                                windowQuit = True
                        
                    case "flip":
                        pygame.display.flip()
                    
                    case "fill":
                        r = parseValue(args[1])
                        g = parseValue(args[2])
                        b = parseValue(args[3])

                        for val in [r, g, b]: 
                            if val[1] not in ["var int", "literal int"]: 
                                raise ValueError(f"found str for int | line {current_index} in {current_source} |") 


                        screen.fill((r[0], g[0], b[0]))


                    case "event":
                        match args[1]:
                            case "quit":
                                parsed1 = parseValue(args[2])

                                if parsed1[1] not in ["var int", "var str"]:
                                    raise ValueError(f"can not assign event value to literal | line {current_index} in {current_source} | found literla for var")
                                
                                variables[args[2]] = windowQuit
                
                    case "quit":
                        pygame.quit()

            case "import":
                parsed1 = parseValue(args[0])
                # Store imported file lines
                file_path = parsed1[0]
                imported_lines = open(file_path, "r").readlines()
                sources[file_path] = imported_lines

                # Index the functions
                allowedFunctionsNames = []
                fileFunctions = {}

                for line_num, line in enumerate(imported_lines):
                    parsed = tokenize(line)
                    if not parsed:
                        continue

                    cmd = parsed[0]
                    args = parsed[1:]

                    match cmd:
                        case "export":
                            if args[0] == "functions":
                                for token in args[1:]:
                                    allowedFunctionsNames.append(token)
                        case "def":
                            func_name = args[0]
                            num_args = parseValue(args[1])
                            if num_args[1] != "literal int":
                                raise SyntaxError(f"invalid function syntax | during importing {file_path} | line {line_num}")
                            num_args = num_args[0]
                            start_index = line_num + 1

                            end_index = None
                            for j in range(start_index, len(imported_lines)):
                                tokens = tokenize(imported_lines[j])
                                if tokens and tokens[0] == "return":
                                    end_index = j
                                    break
                            if end_index is None:
                                raise ValueError(f"Function {func_name} has no return statement in {file_path}")
                            fileFunctions[func_name] = (start_index, num_args, end_index)

                # Store only allowed functions
                functionIndexs[file_path] = {}
                for name in allowedFunctionsNames:
                    if name in fileFunctions:
                        functionIndexs[file_path][name] = fileFunctions[name]
                    else:
                        raise ImportError(f"namespace {file_path} does not export function {name}")
            case "end":
                print("\nProgram ended")
                input("")
                exit(0)

        current_index += 1


    print("\nProgram ended")
    input("")
except Exception as e:
    print(f"Error: {e}")
    print(f'''CURRENT FRAME:
    varibles:
    ''')
    for i, v in variables.items(): print(f"{i}:{v}")
    print("Souces")
    for i, v in sources.items(): print(f"{i}:{str(v)[0:25]}...")
    print("current source")
    print(current_source)
    print("function Indexs")
    for i, v in functionIndexs.items(): print(f"{i}:{str(v)[0:25]}...")
    print("Index")
    print(current_index)
    input("Press Enter to exit...")
    exit(1)