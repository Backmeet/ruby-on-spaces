# interpreter_lib.ru
# interpreter as a library
# exports interpret <path>
# ----------------------------
# FUNCTION
# ----------------------------
def interpret 1
  # arg1 = path

    var new main_source ""
  var set main_source = arg1

    var new current_index 0
    var new running 1
    var new current_line ""
    var new linecount 0
    var new token0 ""
    var new arg1 ""
    var new arg2 ""
    var new arg3 ""
    var new arg4 ""
    var new arg5 ""
    var new arg6 ""
    var new arg7 ""
    var new arg8 ""
    var new arg9 ""
    var new arg10 ""
    var new cmd_count 0
    var new windowQuit 0

  # load file lines into the source table
  INTRPRETER_LANG begin
  with open(get_variable("main_source")) as f:
      lines = f.readlines()
  for i, line in enumerate(lines):
      setLineByIndex("main", i, line)
  editVariable("linecount", len(lines))
  editVariable("current_index", 0)
  editVariable("running", 1)
  INTRPRETER_LANG end

  # main interpreter loop
  while begin
    var math current_index >= linecount = running
    var math 1 - running = running

    if begin running

      # get current line
      INTRPRETER_LANG begin
      line = getLines("main")[get_variable("current_index")]
      editVariable("current_line", line)
      INTRPRETER_LANG end

      # tokenize line
      INTRPRETER_LANG begin
      import re
      tokens = re.findall(r"'[^']*'|\"[^\"]*\"|\\S+", get_variable("current_line"))
      editVariable("cmd_count", len(tokens))
      for i in range(0, 11):
          if i < len(tokens):
              editVariable(f"arg{i}", tokens[i])
          else:
              editVariable(f"arg{i}", "")
      if len(tokens) > 0:
          editVariable("token0", tokens[0])
      else:
          editVariable("token0", "")
      INTRPRETER_LANG end

      # process command if not empty
      if begin token0

        # ------------------------------
        # var new
        # ------------------------------
        INTRPRETER_LANG begin
        if get_variable("arg0") == "var" and get_variable("arg1") == "new":
            name = get_variable("arg2")
            val = get_variable("arg3")
            try:
                val = eval(val)
            except:
                pass
            editVariable(name, val)
        INTRPRETER_LANG end

        # ------------------------------
        # var math
        # ------------------------------
        INTRPRETER_LANG begin
        if get_variable("arg0") == "var" and get_variable("arg1") == "math":
            a = get_variable(get_variable("arg2"))
            op = get_variable("arg3")
            b = get_variable(get_variable("arg4"))
            name = get_variable("arg5")
            result = None
            if op == "+": result = a + b
            elif op == "-": result = a - b
            elif op == "*": result = a * b
            elif op == "/": result = a / b
            elif op == "**": result = a ** b
            elif op == "and": result = int(bool(a) and bool(b))
            elif op == "or": result = int(bool(a) or bool(b))
            elif op == "&": result = int(a) & int(b)
            elif op == "|": result = int(a) | int(b)
            editVariable(name, result)
        INTRPRETER_LANG end

        # ------------------------------
        # if begin
        # ------------------------------
        if begin arg1
          # no-op in this interpreter
        if end

        # ------------------------------
        # while begin
        # ------------------------------
        if begin 1
          # no-op in this interpreter
        if end

        # ------------------------------
        # while end <var>
        # ------------------------------
        INTRPRETER_LANG begin
        if get_variable("arg0") == "while" and get_variable("arg1") == "end":
            check = get_variable(get_variable("arg2"))
            if check:
                editVariable("current_index", get_variable("current_index") - 2)
        INTRPRETER_LANG end

        # ------------------------------
        # window commands
        # ------------------------------
        INTRPRETER_LANG begin
        if get_variable("arg0") == "window":
            import pygame
            cmd = get_variable("arg1")
            if cmd == "init":
                w = int(get_variable(get_variable("arg2")))
                h = int(get_variable(get_variable("arg3")))
                screen = pygame.display.set_mode((w, h))
            elif cmd == "update":
                global windowQuit
                windowQuit = False
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        windowQuit = True
            elif cmd == "event" and get_variable("arg2") == "quit":
                target = get_variable("arg3")
                editVariable(target, 1 if windowQuit else 0)
            elif cmd == "flip":
                pygame.display.flip()
            elif cmd == "quit":
                pygame.quit()
            elif cmd == "draw":
                draw_cmd = get_variable("arg2")
                if draw_cmd == "line":
                    x1 = int(get_variable(get_variable("arg3")))
                    y1 = int(get_variable(get_variable("arg4")))
                    x2 = int(get_variable(get_variable("arg5")))
                    y2 = int(get_variable(get_variable("arg6")))
                    r = int(get_variable(get_variable("arg7")))
                    g = int(get_variable(get_variable("arg8")))
                    b = int(get_variable(get_variable("arg9")))
                    thickness = int(get_variable(get_variable("arg10")))
                    pygame.draw.line(screen, (r, g, b), (x1, y1), (x2, y2), thickness)
                elif draw_cmd == "rect":
                    x1 = int(get_variable(get_variable("arg3")))
                    y1 = int(get_variable(get_variable("arg4")))
                    x2 = int(get_variable(get_variable("arg5")))
                    y2 = int(get_variable(get_variable("arg6")))
                    r = int(get_variable(get_variable("arg7")))
                    g = int(get_variable(get_variable("arg8")))
                    b = int(get_variable(get_variable("arg9")))
                    rect_x = min(x1, x2)
                    rect_y = min(y1, y2)
                    rect_w = abs(x2 - x1)
                    rect_h = abs(y2 - y1)
                    pygame.draw.rect(screen, (r, g, b), (rect_x, rect_y, rect_w, rect_h))
        INTRPRETER_LANG end

        # ------------------------------
        # import
        # ------------------------------
        INTRPRETER_LANG begin
        if get_variable("arg0") == "import":
            path = get_variable("arg1")
            with open(path) as f:
                lines = f.readlines()
            for i, line in enumerate(lines):
                setLineByIndex(path, i, line)
        INTRPRETER_LANG end

        # ------------------------------
        # export functions (no-op)
        # ------------------------------
      if end

      # increment
      var math current_index + 1 = current_index

    if end
  while end running

  return 0
return

export functions interpret
