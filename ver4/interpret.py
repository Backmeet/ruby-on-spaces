try:
    import math
    import os
    import re, time, pygame
    from sys import argv

    sources = {}
    sources["main"] = open(argv[1], "r").readlines()

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
        global current_index
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
                        parsed1 = parseValue(args[1], variables)
                        parsed2 = parseValue(args[3], variables)
                        if parsed1[1] not in ["var str", "var int"]:
                            raise ValueError(f"On line {current_index} in {current_source}: Invalid var name, variable not found")
                        variables[args[1]] = parsed2[0]

            case "while":
                match args[0]:
                    case "begin":
                        whileLoops.append(current_index)
                    case "end":
                        parsed1 = parseValue(args[1], variables)
                        lastLoopIndex = whileLoops.pop()
                        if parsed1[0]:
                            current_index = lastLoopIndex - 1

            case "if":
                match args[0]:
                    case "begin":
                        parsed1 = parseValue(args[1], variables)
                        if not parsed1[0]:
                            for j in range(current_index + 1, len(current_lines)):
                                tokens = tokenize(current_lines[j])
                                if tokens and tokens[0] == "if" and tokens[1] == "end":
                                    current_index = j
                                    break
                    case "end":
                        pass

            case "def":
                func_name = args[0]
                num_args = parseValue(args[1], variables)
                if num_args[1] not in ["literal int"]:
                    raise SyntaxError(f"invalid function syntax | line {current_index} in {current_source} |")
                num_args = num_args[0]

                start_index = current_index + 1
                end_index = None
                for j in range(start_index, len(current_lines)):
                    tokens = tokenize(current_lines[j])
                    if tokens and tokens[0] == "endfunc":
                        end_index = j
                        break
                if end_index is None:
                    raise ValueError(f"Function {func_name} has no return statement.")
                functionIndexs[current_source][func_name] = (start_index, num_args, end_index)
                current_index = end_index
                current_lines = sources[current_source]
                continue

            case "return":
                ret_val = parseValue(args[0], variables)[0]
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
                    variables[f"arg{idx+1}"] = parseValue(arg, variables)[0]

                # Save current position to return to
                functionStack.append((current_source, current_index + 1))

                # Switch to called function
                current_source = target_source
                current_lines = sources[current_source]
                current_index = start_index
                continue

            case "delay":
                parsed1 = parseValue(args[0], variables)
                if parsed1[1] in ["var int", "literal int"]:
                    time.sleep(parsed1[0])
                else:
                    raise ValueError(f"On line {current_index} in {current_source}: delay value must be an int")
            case "input":
                parsed1 = parseValue(args[0], variables)
                parsed2 = parseValue(args[1], variables)
                if parsed1[1] not in ["var str", "literal str"]:
                    raise ValueError(f"On line {current_index} in {current_source}: prompt string must be a string")
                if parsed2[1] not in ["var str", "var int"]:
                    raise ValueError(f"On line {current_index} in {current_source}: target variable must be a variable")
                variables[args[1]] = input(parsed1[0])
            case "convert":
                parsed1 = parseValue(args[0], variables)
                parsed2 = parseValue(args[1], variables)
                if parsed2[1] not in ["var str", "var int"]:
                    raise ValueError(f"On line {current_index} in {current_source}: target variable not found")
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
                        parsed1 = parseValue(args[1], variables)
                        parsed2 = parseValue(args[2], variables)

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
                                        raise ValueError(f"found str for int | line {current_index} in {current_source} |") 

                                pygame.draw.line(screen, (r[0], g[0], b[0]), (x1[0], y1[0]), (x2[0], y2[0]), thickness[0])
                            
                            case "rect":
                                # Expected: window draw rect <x1> <y1> <x2> <y2> <r> <g> <b>
                                if len(args) < 8:
                                    raise ValueError(f"Insufficient arguments for window draw rect | line {current_index} in {current_source}")
                                
                                if screen is None:
                                    raise ValueError(f"Screen not initialized before drawing | line {current_index} in {current_source}")
                                
                                x1 = parseValue(args[2], variables)
                                y1 = parseValue(args[3], variables)
                                x2 = parseValue(args[4], variables)
                                y2 = parseValue(args[5], variables)
                                
                                r = parseValue(args[6], variables)
                                g = parseValue(args[7], variables)
                                b = parseValue(args[8], variables)

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
                        r = parseValue(args[1], variables)
                        g = parseValue(args[2], variables)
                        b = parseValue(args[3], variables)

                        for val in [r, g, b]: 
                            if val[1] not in ["var int", "literal int"]: 
                                raise ValueError(f"found str for int | line {current_index} in {current_source} |") 


                        screen.fill((r[0], g[0], b[0]))


                    case "event":
                        match args[1]:
                            case "quit":
                                parsed1 = parseValue(args[2], variables)

                                if parsed1[1] not in ["var int", "var str"]:
                                    raise ValueError(f"can not assign event value to literal | line {current_index} in {current_source} | found literla for var")
                                
                                variables[args[2]] = windowQuit
                
                    case "quit":
                        pygame.quit()

            case "import":
                parsed1 = parseValue(args[0], variables)
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
                            num_args = parseValue(args[1], variables)
                            if num_args[1] != "literal int":
                                raise SyntaxError(f"invalid function syntax | during importing {file_path} | line {line_num}")
                            num_args = num_args[0]
                            start_index = line_num + 1

                            end_index = None
                            for j in range(start_index, len(imported_lines)):
                                tokens = tokenize(imported_lines[j])
                                if tokens and tokens[0] == "endfunc":
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
    input("Press Enter to exit...")
    exit(1)
