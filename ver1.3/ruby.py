import subprocess, traceback
import random, math, re, time
import string, hashlib
from requests import get
from evalSafe import SafeEval

RAW_BASE_URL = 'https://raw.githubusercontent.com/Backmeet/ruby-on-spaces/main'
def getFileText(filePath):
    url = f"{RAW_BASE_URL}/{filePath}"
    try:
        r = get(url)
        if r.status_code != 200:
            raise Exception(f"Failed to fetch text — Status code: {r.status_code}")
        return r.text
    except Exception as e:
        print(f"[ERROR] getFileText failed for {filePath}: {e}")
        raise

def StableHash(text: str, filename: str = ""):
    data = f"{filename}\n{text}".encode('utf-8')
    return hashlib.sha512(data).hexdigest()

stdLibPath:str=r"gitPath:code-examples/stdlib/stdLib.ru"

# Load stdlib from URL or file
if stdLibPath.startswith("gitPath:"):
    stdLibCode = getFileText(stdLibPath[8:])
else:
    stdLibCode = open(stdLibPath).read()
stdLibHash = StableHash(stdLibCode)

def runRuby(main_code: str, source_dict: dict[str, str] = {}, bound:bool=True) -> str:
    initBounded = bound
    sources = {"main": main_code.splitlines()}

    files = {}
    for name, content in source_dict.items():
        files[name] = content.splitlines()

    def isdigit(string):
        try:
            float(string)
            return True
        except:
            return False

    s = re.compile(r'\s*//')  # matches and removes // comments
    # Match: [anything in brackets], "quoted strings", 'quoted strings', or any non-space chunk
    t = re.compile(r'''\[[^\]]*\]|"[^"]*"|'[^']*'|\S+''')

    def tokenize(line: str):
        # remove comments, then tokenize
        return t.findall(s.split(line, maxsplit=1)[0])

    def sourceToFile(source:str):
        if source == "main":
            return main_code
        else:
            return source_dict[source]                    

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
                    case "/": return a / b
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
                    case "+": return a + b
                    case "in": return int(a in b)
                    case "==": return (a == b)
                    case "!=": return (a != b)

            elif (a_[1] in ["var str", "literal str"]) and b_[1] in ["var int", "literal int"]:
                match op:
                    case "index": return (a[b])
                    case "pop": return (''.join((lambda l: (l.pop(b), l)[1])(list(a))))
                    case "*": return (a * b)
            
            elif (a_[1] in ["var list", "literal list"]) and b_[1] in ["var int", "literal int"]:
                match op:
                    case "index": return (parseValue(a[b])[0])
                    case "*": return (a * b)

        elif len(token) == 2:
            a_ = parseValue(token[1])
            op = token[0]
            a = a_[0]
            if a_[1] in ["var str", "literal str"]:
                match op:
                    case "len": return (len(a))
                    case "not": return (not a)
            
            if a_[1] in ["var list", "literal list"]:
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

    def parseValue(valueStr, varContext=None, functionContext=None):
        if varContext is None: varContext = variables
        if functionContext is None: functionContext = functionIndexs
        
        if valueStr.lower() == "null": return 0, "literal int"
        if valueStr.lower() == "none": return 0, "literal int"
        if valueStr.lower() == "nil": return 0, "literal int"
        if valueStr.lower() == "true": return 1, "literal int"
        
        if valueStr in varContext:
            val = varContext[valueStr]
            type_ = ""
            if isinstance(val, list): type_ = "var list"
            elif isinstance(val, int) or isinstance(val, float): type_ = "var int"
            elif isinstance(val, str): type_ = "var str"

            return val, type_
        elif (valueStr.startswith('"') and valueStr.endswith('"')) or (valueStr.startswith("'") and valueStr.endswith("'")):
            return valueStr[1:-1], "literal str"
        
        elif isdigit(valueStr):
            return (float(valueStr) if "." in valueStr else int(valueStr)), "literal int"
        
        elif (valueStr.startswith('[') and valueStr.endswith(']')): # list
            items = tokenize(valueStr[1:-1])
            return items, "literal list"
        
        else:
            for _, functions in functionIndexs.items():
                for name, data in functions.items():
                    if name == valueStr:
                        return (_, name), "func"
                    
            raise ValueError(f"Value | {valueStr} | is not valid | line {current_index} in {current_source} |")

    # Initialize global state
    variables = {"return": None}
    whileLoops = []
    forLoops = [] # [forStart, ...]
    functionIndexs = {"main": {}}
    functionStack = []

    current_source = "main"
    current_lines :list[str]= sources[current_source]
    current_index :int= 0

    INTRY = [False, None, None]
    # Main interpreter loop
    while True:
        try:
            if StableHash(sourceToFile(current_source)) == stdLibHash: bound = False
            else: bound = initBounded
            if current_index >= len(current_lines):
                if functionStack:
                    current_source, current_index = functionStack.pop()
                    current_lines = sources[current_source]
                    continue
                else:
                    break

            line :str= current_lines[current_index]
            parsed :list[str]= tokenize(line)
            if not parsed:
                current_index += 1
                continue
            

            cmd :str= parsed[0]
            args :list[str]= parsed[1:]

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
                            if length[1] not in ["literal int", "var int"]:
                                raise ValueError(f"length has to be a int for a random str genreation on line {current_index} in {current_source}")
                            
                            _ = ""
                            for i in range(length[0]): _ += string.printable[random.randint(0, len(string.printable) - 1)]
                            variables[args[1]] = _

                case "var":
                    equation :str= line.strip()[4:]
                    if equation.count("=") > 1: raise SyntaxError(f"equation {equation} there are more then one = | line {current_index} in {current_source} | expression syntax error")
                    var, expression = equation.split("=")
                    value = SafeEval(expression.strip(), mathParcer)
                    variables[var.strip()] = value

                case "list":
                    match args[0]:
                        case "set": # list set <list> <index> to <value>
                            if len(args) != 5 or args[3].lower() != "to":
                                raise SyntaxError(f"list set syntax error | line {current_index} in {current_source} | list set syntax error")
                            
                            parsed1 = parseValue(args[1])
                            parsed2 = parseValue(args[2])
                            parseValue(args[4])

                            if parsed1[1] not in ["var list", "literal list"]:
                                raise NameError(f"Can not set a value to a literal on line {current_index} in {current_source}")
                            if parsed2[1] not in ["var int", "literal int"]:
                                raise ValueError(f"list set index has to be a int for a list set on line {current_index} in {current_source}")

                            variables[parsed1[0]][parsed2[0]] = args[4]  # Set the value at the specified index

                        case "append":
                            parsed1 = parseValue(args[1])
                            parsed2 = parseValue(args[2])
                            
                            if parsed1[1] not in ["var list", "literal list"]:
                                raise NameError(f"Can not append a value to a literal on line {current_index} in {current_source}")

                            variables[parsed1[0]].append(args[2])

                        case "extend":
                            parsed1 = parseValue(args[1])
                            parsed2 = parseValue(args[2])
                            
                            if parsed1[1] not in ["var list", "literal list"]:
                                raise NameError(f"Can not append a value to a literal on line {current_index} in {current_source}")

                            if parsed2[1] not in ["var list", "literal list"]:
                                raise NameError(f"Can not extend a literal with a non-list value on line {current_index} in {current_source}")
                            
                            variables[parsed1[0]].extend(parsed2[0])
                        
                        case "pop":
                            parsed1 = parseValue(args[1])
                            parsed2 = parseValue(args[2])

                            if parsed1[1] not in ["var list", "literal list"]:
                                raise NameError(f"Can not pop a value from a literal on line {current_index} in {current_source}")
                        
                            if parsed2[1] not in ["var int", "literal int"]:
                                raise ValueError(f"pop index has to be a int for a list pop on line {current_index} in {current_source}")
                            
                            if parsed2[0] < 0 or parsed2[0] >= len(parsed1[0]):
                                raise IndexError(f"pop index out of range | line {current_index} in {current_source} | pop index error")

                            popped_value = variables[parsed1[0]].pop(parsed2[0])
                            variables["return"] = popped_value  # Store popped value in return variable

                        case "call": # call a function from a list | list call <list>.<func_name> <arg1> <arg2> ...

                            if args[1].count(".") != 1:
                                raise SyntaxError(f"list call on line {current_index} in {current_source} has more than one '.'")
                            
                            list_name, func_name = args[1].split(".")
                            parsed1 = parseValue(list_name)
                            
                            if parsed1[1] not in ["var list", "literal list"]:
                                raise NameError(f"Can not call a function from a literal on line {current_index} in {current_source}")
                            
                            for item in parsed1[0]:
                                parsedItem = parseValue(item)
                                if item == func_name and parsedItem[1] == "func":
                                    src, name = parsedItem[0]

                                    startIndex, num_args, endIndex = functionIndexs[src][name]

                                    if len(args[1:]) != num_args:
                                        raise ValueError(f"Function {func_name} expects {num_args} arguments, got {len(args[1:])} | line {current_index} in {current_source}")

                                    # Set up arguments
                                    for idx, arg in enumerate(args[1:]):
                                        variables[f"arg{idx+1}"] = parseValue(arg)[0]
                                                    
                                    # Save current position to return to
                                    functionStack.append((current_source, current_index + 1))

                                    # Switch to called function
                                    current_source = src
                                    current_lines = sources[src]
                                    current_index = startIndex
                                    continue
                                    
                            else:
                                raise NameError(f"Function {func_name} not found in list {list_name} | line {current_index} in {current_source}")

                                
                            



                case "for":
                    match args[0]:
                        case "begin":
                            if line.count(":") != 1:
                                raise SyntaxError(f"for on line {current_index} in {current_source} has more than one ':'")

                            data = line.strip().split(":")[1]
                            var, initValue, expression, deltaValue = map(str.strip, data.split(";"))

                            # Initialize the variable
                            variables[var] = SafeEval(initValue, mathParcer)

                            # Always push this index to the loop stack
                            forLoops.append(current_index)

                            # Check the loop condition
                            if not SafeEval(expression, mathParcer):
                                # Skip ahead to "for end"
                                for i, line_ in enumerate(current_lines[current_index:]):
                                    tokens = tokenize(line_)
                                    if tokens and tokens[0:2] == ["for", "end"]:
                                        current_index += i
                                        break

                        case "end":
                            if not forLoops:
                                raise SyntaxError("Unexpected 'for end' with no matching 'for begin'")

                            # Go back to the matching begin line
                            line_index = forLoops[-1]  # don't pop yet
                            line_ = current_lines[line_index]
                            var, initValue, expression, deltaValue = map(str.strip, line_.split(":")[1].split(";"))

                            # Increment
                            variables[var] += SafeEval(deltaValue, mathParcer)

                            # Recheck the condition
                            if SafeEval(expression, mathParcer):
                                current_index = line_index
                            else:
                                forLoops.pop()  # exit loop



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
                    if not func_name.isidentifier():
                        raise NameError(f"Invalid function name | line {current_index} in {current_source}")
                    num_args = parseValue(args[1])
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
                        raise ValueError(f"Function {func_name} has no endfunc statement.")
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

                case "endfunc":
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
                case "export":
                    pass

                case "import":
                    parsed1 = parseValue(args[0])
                    if parsed1[1] not in ["var str", "literal str"]:
                        raise ValueError(f"import names can only be strings | line {current_index} in {current_source} | import error")

                    # Store imported file lines
                    file_name = parsed1[0]
                    imported_lines = files[file_name]
                    sources[file_name] = imported_lines

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
                                    raise SyntaxError(f"invalid function syntax | during importing {file_name} | line {line_num}")
                                num_args = num_args[0]
                                start_index = line_num + 1

                                end_index = None
                                for j in range(start_index, len(imported_lines)):
                                    tokens = tokenize(imported_lines[j])
                                    if tokens and tokens[0] == "endfunc":
                                        end_index = j
                                        break
                                if end_index is None:
                                    raise ValueError(f"Function {func_name} has no endfunc statement in {file_name}")
                                fileFunctions[func_name] = (start_index, num_args, end_index)

                    # Store only allowed functions
                    functionIndexs[file_name] = {}
                    for name in allowedFunctionsNames:
                        if name in fileFunctions:
                            functionIndexs[file_name][name] = fileFunctions[name]
                        else:
                            raise ImportError(f"namespace {file_name} does not export function {name}")
                case "end":
                    print("\nProgram ended")
                    input("")
                    exit(0)
                
                case "delay":
                    parsed1 = parseValue(args[0])
                    if parsed1[1] not in ["var int", "literal int"]:
                        raise ValueError(f"delay value can only be a number | line {current_index} in {current_source} | delay value error") 
                    time.sleep(parsed1[0])
                
                case "error":
                    parsed1 = parseValue(args[0])
                    if parsed1[1] not in ["var str", "literal str"]:
                        raise ValueError(f"error value can only be a string | line {current_index} in {current_source} | delay value error") 
                    raise Exception(parsed1[0])
                    
                
                case "system":
                    if not bound:
                        parsed1 = parseValue(args[0])
                        if parsed1[1] not in ["var str", "literal str"]:
                            raise ValueError(f"system error | line {current_index} in {current_source}") 

                        process = subprocess.run(parsed1[0], capture_output=1, text=1, shell=1)

                        variables["_stdout"] = process.stderr if process.returncode else process.stdout
                        variables["return"] = process.returncode
                    else:
                        raise PermissionError(f"interpreter is bounded can not run privileged actions | line {current_index} in {current_source} | PrivilegeError")
                
                case "try":
                    except_line = None
                    for i, line_ in enumerate(current_lines[current_index:len(current_lines)]):
                        if tokenize(line_) and tokenize(line_)[0] == "except":
                            except_line = current_index + i
                    if not except_line:
                        raise SyntaxError(f"try has not endeing except line | line {current_index} in {current_source} | try-execpt error")
                    INTRY = [True, except_line, None]

                case "except":
                    ErrorData = INTRY
                    INTRY = [False, None, None]
                    if ErrorData[0]: # this is valid syntax bro
                        if ErrorData[2]:
                            # there is a error
                            variables["Error"] = ErrorData[2]
                        else:
                            for i, line_ in enumerate(current_lines[current_index:len(current_lines)]):
                                if tokenize(line_)[0] == "done":
                                    current_index += i
                    else:
                        raise SyntaxError(f"stray except found with no parent try | line {current_index} in {current_source} | stray except error")
                
                case "done":
                    pass 
                

                case _:
                    _ = '''
                    var // allows for editing or assignment of varibles
                    var <var> = <value>
                    var math <a> <op> <b> = <var> // does mathamathical opreations
                    var math <a> <op> = <var> // does mathamathical opreations that only need 1 argument
                    // opreations are : + - * / // ^ | & == != >= <= < > and or : these ones [+ == !=] are the only ones allowed for strings
                    // cbrt sqrt not ~ tan sin cos : only [not] is allowed as a str opreation and you can get the len of a string via
                    // var math "hello, world" len = x // 11 [indexing starts at 0]
                    // you can a index from a string via var math "foobar" index 2 = x // x is o as
                    // F O O B A R
                    // 0 1 2 3 4 5
                    // 2:o 

                    // ok now for things like geting a Index from a string you can use the opreator index to get one like
                    // var math string index 1 = chr
                    // or var math string index var
                    // indexing starts at 0

                    rnd // allows random values to be genreated
                    rnd int <var> <origin> <stop>
                    rnd str <var> <len>

                    def // begins function defintions when a func is ran the arguments are passed as arg1, arg2. arg3 ...
                    def <name> <number of arguments>
                    return value // ends the func and sets the global varible "return" to the value
                    endfunc // identifys the end of a function
                    
                    call // calls a function with the passed arguments
                    call name arg1 arg2 ...

                    while // runs code untill a condistion is NOT true
                    while begin
                    while end <condistion value (single value only ie no expressions)>

                    if // allows you to run code is a condistion if true
                    if begin <condistion value (single value only ie no expressions)>
                    if end 
                    
                    import "name / path" // imports a file and reads exposed functions and intergreates them into the env
                    
                    export // exposes values from the script 
                    export functions function_name1 function_name2 ...
                    
                    print value1 value2 ...

                    delay <int>

                    error <error message>

                    try
                    code...
                    except
                    code...
                    done

                    '''.splitlines()
                    cmds = ""
                    for i in _: cmds += i.strip() + "\n"
                    raise SyntaxError(f"Root cmd : {cmd} is not a valid cmd; \nvalid cmds are: \n{cmds}")


            
            current_index += 1


        except Exception as e:
            if INTRY[0]:
                current_index = INTRY[1]
                INTRY[2] = str(e)
                continue

            print(f"Error: {e}")
            print(f"Line: {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            print("CURRENT FRAME:")
            print("Variables:")
            for k, v in variables.items():
                print(f"{k}: {v}")
            print("\nSources:", list(sources.keys()))
            print(f"Current source: {current_source} | Hash: {StableHash(sourceToFile(current_source))}")
            print("Function Indexes:")
            for src, funcs in functionIndexs.items():
                print(f"  {src}:")
                for func, (start, nargs, end) in funcs.items():
                    print(f"    {func}: start={start}, nargs={nargs}, end={end}")
            print(f"Index: {current_index + 1}")
            break

    print("\nProgram ended")


if __name__ == "__main__":
    runRuby('''
def fib 1
    var a = 0
    var b = 1
    while begin 
        var c = a + b
        print b
        var a = b
        var b = c
        var arg1 = arg1 - 1
    while end arg1
    endfunc
call fib 10
''')
    runRuby('''
    var _ = "hi" index 0
    print _
    ''')
    runRuby('''
var x = 5
var y = 10
var z = x + y * 2
var greeting = "hi" * 3            
var truthy = 1 and 2
var falsy = 0 or ""
var ch = "hello" index 1           
var popChar = "hi" pop 1          
var randNum = 0
var randWord = 0

rnd int randNum 1 100
rnd str randWord 5


def add 2
  var _ = arg1 + arg2
  return _

endfunc

call add 7 8
print return
            
if begin true
  print "Condition is true"
if end

var counter = 4
while begin
  print "Counting:" counter
  var counter = counter - 1
while end counter

print ch ", " popChar
print "Hello " greeting ", " z ", " randNum ", " randWord

delay 1

try
  error "Boom!"
except
  print "Caught error:" Error
done

    ''')
    runRuby('''
for begin : i; 0; i < 10; 1
print i
for end 
            
for begin : i; ""; i != "******"; "*"
print i
for end
''')
    runRuby('''
var myClass = [0]
def increment 1
    var self = arg1
    var _ = (self index 0) + 1
    list set self 0 _
endfunc
list attatch myClass increment 

var myClassInstance = myClass

print (myClassInstance index 0)
list call myClassInstance.increment
print (myClassInstance index 0)
            
''')