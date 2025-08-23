-- ros_luau_runtime.lua
-- 1:1 port of the provided Python runtime to Luau (Roblox Lua)
-- Port includes everything up to the `run` function. No file-running or REPL.
-- Renames and substitutions applied:
--   py_* -> lua_*
--   execPy -> execLua (uses loadstring)
--   escapeToPython -> escapeToLua
--   pyfunc -> luafunc
--   register_pyfunc -> register_luafunc
-- Comments are mid-amount as requested.

-- ===== Lexer =====
local TOKEN_SPEC = {
    {"NUMBER",   "%d+%.%d+|%d+"},
    {"STRING",   '"([^"\\]|\\.)*"'},
    {"ID",       "[A-Za-z_][A-Za-z0-9_]*"},
    {"OP",       "==|!=|<=|>=|%+|%-|%*|/|<|>|=|%.|,|:|;|%(|%)|%[|%]|%{|%}"},
    {"NL",       "\r?\n"},
    {"WS",       "[ \t]+"},
    {"MISMATCH", "."},
}

local KEYWORDS = {
    ["def"] = true, ["return"] = true, ["end"] = true,
    ["while"] = true, ["for"] = true, ["in"] = true,
    ["true"] = true, ["false"] = true, ["null"] = true,
    ["if"] = true,
}

local Token = {}
Token.__index = Token
function Token.new(kind, text, line, col)
    return setmetatable({kind=kind, text=text, line=line, col=col}, Token)
end
function Token:__tostring()
    return string.format("Token(%s,%q@%d:%d)", tostring(self.kind), tostring(self.text), self.line, self.col)
end

-- We'll implement a lexer that imitates the Python one. Lua's pattern syntax differs slightly.
local function lex(src)
    local toks = {}
    local i = 1
    local line = 1
    local col = 1
    local n = #src
    while i <= n do
        local c = src:sub(i,i)
        -- whitespace
        if c == ' ' or c == '\t' then
            local j = i
            while j <= n and (src:sub(j,j) == ' ' or src:sub(j,j) == '\t') do j = j + 1 end
            local text = src:sub(i, j-1)
            col = col + #text
            i = j
        elseif c == '\r' then
            -- handle CRLF or CR
            if src:sub(i,i+1) == '\r\n' then
                table.insert(toks, Token.new('NL', '\n', line, col))
                i = i + 2
            else
                table.insert(toks, Token.new('NL', '\n', line, col))
                i = i + 1
            end
            line = line + 1
            col = 1
        elseif c == '\n' then
            table.insert(toks, Token.new('NL', '\n', line, col))
            i = i + 1
            line = line + 1
            col = 1
        elseif c:match('%d') then
            local j = i
            while j <= n and src:sub(j,j):match('%d') do j = j + 1 end
            if src:sub(j,j) == '.' then
                j = j + 1
                while j <= n and src:sub(j,j):match('%d') do j = j + 1 end
            end
            local text = src:sub(i, j-1)
            table.insert(toks, Token.new('NUMBER', text, line, col))
            col = col + #text
            i = j
        elseif c == '"' then
            -- naive string capture similar to Python regex "([^"]|\\.)*"
            local j = i+1
            local escaped = false
            while j <= n do
                local ch = src:sub(j,j)
                if ch == '\\' and not escaped then
                    escaped = true
                    j = j + 1
                elseif ch == '"' and not escaped then
                    break
                else
                    escaped = false
                    j = j + 1
                end
            end
            if j > n then error("Unterminated string at "..line..":"..col) end
            local full = src:sub(i, j)
            table.insert(toks, Token.new('STRING', full, line, col))
            col = col + #full
            i = j + 1
        elseif c:match('[A-Za-z_]') then
            local j = i
            while j <= n and src:sub(j,j):match('[A-Za-z0-9_]') do j = j + 1 end
            local text = src:sub(i, j-1)
            if KEYWORDS[text] then
                table.insert(toks, Token.new(text, text, line, col))
            else
                table.insert(toks, Token.new('ID', text, line, col))
            end
            col = col + #text
            i = j
        else
            -- match multi-char ops first like ==, !=, <=, >=
            local two = src:sub(i, i+1)
            if two == '==' or two == '!=' or two == '<=' or two == '>=' then
                table.insert(toks, Token.new(two, two, line, col))
                col = col + 2
                i = i + 2
            else
                -- single char operator or punctuation
                table.insert(toks, Token.new(c, c, line, col))
                col = col + 1
                i = i + 1
            end
        end
    end
    table.insert(toks, Token.new('EOF', 'EOF', line, col))
    return toks
end

-- ===== Parser (Pratt) =====
local Parser = {}
Parser.__index = Parser
function Parser.new(tokens)
    return setmetatable({toks = tokens, i = 1, cur = tokens[1]}, Parser)
end
function Parser:advance()
    self.i = self.i + 1
    if self.i <= #self.toks then
        self.cur = self.toks[self.i]
    else
        self.cur = Token.new('EOF','EOF', -1, -1)
    end
end
function Parser:match(...)
    local kinds = {...}
    for _,k in ipairs(kinds) do
        if self.cur.kind == k or self.cur.text == k then
            local t = self.cur
            self:advance()
            return t
        end
    end
    return nil
end
function Parser:expect(...)
    local t = self:match(...)
    if not t then
        local want = table.concat({...}, ' or ')
        error(string.format("Expected %s at %d:%d, got %s %q", want, self.cur.line, self.cur.col, self.cur.kind, self.cur.text))
    end
    return t
end
function Parser:skip_semi_nl()
    while self:match(';', 'NL') do end
end

function Parser:parse()
    local body = self:parse_block_until_end(true)
    self:expect('EOF')
    return {type='block', stmts = body}
end

function Parser:parse_block_until_end(allow_top_level, terminators)
    allow_top_level = allow_top_level or false
    terminators = terminators or {'end'}
    local stmts = {}
    self:skip_semi_nl()
    while self.cur.kind ~= 'EOF' do
        if self.cur.kind == 'NL' or self.cur.text == ';' then
            self:advance()
            goto continue
        end
        local is_term = false
        for _,t in ipairs(terminators) do if self.cur.text == t then is_term = true break end end
        if is_term then break end
        table.insert(stmts, self:parse_stmt())
        self:skip_semi_nl()
        if allow_top_level and self.cur.kind == 'EOF' then break end
        ::continue::
    end
    -- if 'end' in terminators then expect it
    for _,t in ipairs(terminators) do if t == 'end' then self:expect('end') break end end
    return stmts
end

function Parser:parse_stmt()
    if self.cur.text == 'def' then return self:parse_def() end
    if self.cur.text == 'return' then
        self:advance()
        local expr = self:parse_expression()
        return {type='return', expr = expr}
    end
    if self.cur.text == 'while' then
        self:advance()
        self:expect('(')
        local cond = self:parse_expression()
        self:expect(')')
        self:skip_semi_nl()
        local body = self:parse_block_until_end(false, {'end'})
        return {type='while', cond=cond, body=body}
    end
    if self.cur.text == 'if' then
        self:advance()
        local cond = self:parse_expression()
        local body = self:parse_block_until_end(false, {'end'})
        return {type='if', cond=cond, body=body}
    end
    if self.cur.text == 'for' then return self:parse_for() end
    -- assignment or expr-stmt
    local lhs = self:parse_expression()
    if self.cur.text == '=' and (lhs.type == 'var' or lhs.type == 'index' or lhs.type == 'prop') then
        self:advance()
        local expr = self:parse_expression()
        return {type='assign', target = lhs, expr = expr}
    end
    return {type='exprstmt', expr = lhs}
end

function Parser:parse_def()
    self:expect('def')
    local name1 = self:expect('ID').text
    local full
    if self.cur.text == '.' then
        self:advance()
        local name2 = self:expect('ID').text
        full = {type='methoddef', obj=name1, name=name2}
    else
        full = {type='def', name=name1}
    end
    self:expect('(')
    local params = {}
    if not self:match(')') then
        while true do
            local p = self:expect('ID').text
            table.insert(params, p)
            if self:match(')') then break end
            self:expect(',')
        end
    end
    self:skip_semi_nl()
    local body = self:parse_block_until_end(false, {'end'})
    full.params = params
    full.body = body
    return full
end

function Parser:parse_for()
    self:expect('for')
    if self:match('(') then
        local init = self:parse_stmt()
        self:expect(';')
        local cond = self:parse_expression()
        self:expect(';')
        local step = self:parse_stmt()
        self:expect(')')
        self:skip_semi_nl()
        local body = self:parse_block_until_end(false, {'end'})
        self:expect('end')
        return {type='for_c', init=init, cond=cond, step=step, body=body}
    else
        local var = self:expect('ID').text
        self:expect('in')
        local iterable = self:parse_expression()
        self:skip_semi_nl()
        local body = self:parse_block_until_end(false, {'end'})
        return {type='for_in', var=var, iter=iterable, body=body}
    end
end

-- Pratt expression parser
function Parser:parse_expression(rbp)
    rbp = rbp or 0
    local t = self.cur
    self:advance()
    local left = self:nud(t)
    while true do
        t = self.cur
        local lbp = self:lbp(t)
        if rbp >= lbp then break end
        self:advance()
        left = self:led(t, left)
    end
    return left
end

function Parser:nud(t)
    if t.kind == 'NUMBER' then
        if tostring(t.text):find('%.') then
            return {type='number', value = tonumber(t.text)}
        else
            return {type='number', value = tonumber(t.text)}
        end
    end
    if t.kind == 'STRING' then
        -- remove quotes and unescape simple escapes
        local s = t.text:sub(2, -2)
        s = s:gsub('\\n', '\n'):gsub('\\t','\t'):gsub('\\"','"')
        return {type='string', value = s}
    end
    if t.kind == 'ID' then
        if t.text == 'true' then return {type='bool', value=true} end
        if t.text == 'false' then return {type='bool', value=false} end
        if t.text == 'null' then return {type='null'} end
        return {type='var', name = t.text}
    end
    if t.text == '(' then
        local expr = self:parse_expression()
        self:expect(')')
        return expr
    end
    if t.text == '[' then
        local items = {}
        if not self:match(']') then
            while true do
                table.insert(items, self:parse_expression())
                if self:match(']') then break end
                self:expect(',')
            end
        end
        return {type='list', items=items}
    end
    if t.text == '{' then
        local items = {}
        if not self:match('}') then
            while true do
                local key_node
                if self.cur.kind == 'STRING' then
                    local k = self.cur.text
                    self:advance()
                    local sval = k:sub(2,-2):gsub('\\n','\n')
                    key_node = {type='string', value = sval}
                else
                    local k = self:expect('ID').text
                    key_node = {type='string', value = k}
                end
                self:expect(':')
                local val = self:parse_expression()
                table.insert(items, {key_node, val})
                if self:match('}') then break end
                self:expect(',')
            end
        end
        return {type='dict', items = items}
    end
    if t.text == '-' then
        local expr = self:parse_expression(70)
        return {type='unary', op='-', expr=expr}
    end
    if t.text == '+' then
        local expr = self:parse_expression(70)
        return {type='unary', op='+', expr=expr}
    end
    error('Unexpected token in nud: '..tostring(t))
end

function Parser:lbp(t)
    if t.text == '(' or t.text == '[' or t.text == '.' then return 90 end
    if t.text == '*' or t.text == '/' then return 60 end
    if t.text == '+' or t.text == '-' then return 50 end
    if t.text == '<' or t.text == '>' or t.text == '<=' or t.text == '>=' then return 40 end
    if t.text == '==' or t.text == '!=' then return 35 end
    return 0
end

function Parser:led(t, left)
    if t.text == '(' then
        local args = {}
        if not self:match(')') then
            while true do
                table.insert(args, self:parse_expression())
                if self:match(')') then break end
                self:expect(',')
            end
        end
        return {type='call', func = left, args = args}
    end
    if t.text == '[' then
        local idx = self:parse_expression()
        self:expect(']')
        return {type='index', object = left, index = idx}
    end
    if t.text == '.' then
        local name = self:expect('ID').text
        return {type='prop', object = left, name = name}
    end
    if t.text == '*' or t.text == '/' or t.text == '+' or t.text == '-' or
       t.text == '<' or t.text == '>' or t.text == '<=' or t.text == '>=' or
       t.text == '==' or t.text == '!=' then
        local right = self:parse_expression(self:lbp(t))
        return {type='binop', op = t.text, left = left, right = right}
    end
    error('Unexpected infix '..t.text)
end

-- ===== Runtime / Interpreter =====

-- Return signal used to unwind when 'return' executed inside function
local ReturnSignal = {}
ReturnSignal.__index = ReturnSignal
function ReturnSignal.new(value) return setmetatable({value=value}, ReturnSignal) end

-- Wrapping/unwrapping between host-Lua and runtime value representations
-- In Python version: wrap_for_py / unwrap_from_py. Rename to wrap_for_lua and unwrap_from_lua
local function wrap_for_lua(val)
    if val == nil then return {type='null', value = nil} end
    if type(val) == 'boolean' then return {type='bool', value = val} end
    if type(val) == 'number' then return {type='number', value = val} end
    if type(val) == 'string' then return {type='string', value = val} end
    if type(val) == 'table' then
        -- determine if list or dict heuristically: numeric sequence -> list
        local is_list = true
        local maxn = 0
        for k,_ in pairs(val) do
            if type(k) ~= 'number' then is_list = false; break end
            if k > maxn then maxn = k end
        end
        if is_list then
            local out = {}
            for i=1,maxn do table.insert(out, wrap_for_lua(val[i])) end
            return {type='list', value = out}
        else
            local d = {}
            for k,v in pairs(val) do d[k] = wrap_for_lua(v) end
            return {type='dict', value = d}
        end
    end
    if getmetatable(val) and getmetatable(val).__call == Function.__call then
        return val
    end
    error('Unsupported type for wrap_for_lua: '..type(val))
end

local function unwrap_from_lua(obj)
    local t = obj and obj.type
    local v = obj and obj.value
    if t == 'null' then return nil end
    if t == 'bool' then return v end
    if t == 'number' then return v end
    if t == 'string' then return v end
    if t == 'list' then
        local out = {}
        for i,x in ipairs(v) do out[i] = unwrap_from_lua(x) end
        return out
    end
    if t == 'dict' then
        local out = {}
        for k,x in pairs(v) do out[k] = unwrap_from_lua(x) end
        return out
    end
    -- If it's a Function (callable) then return as-is
    if getmetatable(obj) == Function then
        return obj
    end
    error('Unsupported wrapped type from lua: '..tostring(t))
end

-- Environment class
local EnvClass = {}
EnvClass.__index = EnvClass
function EnvClass.new(parent)
    return setmetatable({parent=parent, map={}}, EnvClass)
end
function EnvClass:get(name)
    if self.map[name] ~= nil then return self.map[name] end
    if self.parent then return self.parent:get(name) end
    error('Undefined variable '..name)
end
function EnvClass:set_here(name, value)
    self.map[name] = value
end
function EnvClass:resolve_scope(name)
    if self.map[name] ~= nil then return self end
    if self.parent then return self.parent:resolve_scope(name) end
    return nil
end
function EnvClass:set(name, value)
    local scope = self:resolve_scope(name)
    if scope == nil then
        self.map[name] = value
    else
        scope.map[name] = value
    end
end

-- Function class
Function = {}
Function.__index = Function
function Function.new(name, params, body, env, escapeToLua, luafunc)
    return setmetatable({name=name, params=params, body=body, env=env, escapeToLua = escapeToLua, luafunc = luafunc}, Function)
end

function Function:call(argvals)
    -- follow Python code semantics: if escapeToLua then wrap args, call luafunc and unwrap
    if self.escapeToLua then
        local wrapped_args = {}
        for i,v in ipairs(argvals) do wrapped_args[i] = wrap_for_lua(v) end
        local res = self.luafunc(wrapped_args)
        return unwrap_from_lua(res)
    end
    local localEnv = EnvClass.new(self.env)
    for i,p in ipairs(self.params) do
        localEnv:set_here(p, argvals[i])
    end
    -- execute body
    local ok, rs = pcall(function()
        exec_block(self.body, localEnv)
    end)
    if not ok then
        if getmetatable(rs) == ReturnSignal then
            return rs.value
        else
            error(rs)
        end
    end
    return nil
end

-- Convenience metamethod to allow calling like fn:call(args)
Function.__call = function(self, argvals) return self:call(argvals) end

-- Truthiness
local function is_truthy(v)
    return not (v == false or v == nil)
end

-- Indexing helpers (lists and dicts are Lua tables)
local function get_indexed(obj, index)
    if type(obj) == 'table' then
        return obj[index]
    end
    error('Indexing only supported on list and dict')
end
local function set_indexed(obj, index, value)
    if type(obj) == 'table' then
        obj[index] = value
        return
    end
    error('Index assignment only supported on list and dict')
end

-- Evaluate expressions
local function eval_expr(node, env)
    local t = node.type
    if t == 'number' then return node.value end
    if t == 'string' then return node.value end
    if t == 'bool' then return node.value end
    if t == 'null' then return nil end
    if t == 'var' then return env:get(node.name) end
    if t == 'list' then
        local out = {}
        for i,x in ipairs(node.items) do out[i] = eval_expr(x, env) end
        return out
    end
    if t == 'dict' then
        local d = {}
        for _, pair in ipairs(node.items) do
            local k_node, v_node = pair[1], pair[2]
            local key = eval_expr(k_node, env)
            local val = eval_expr(v_node, env)
            d[key] = val
        end
        return d
    end
    if t == 'unary' then
        local v = eval_expr(node.expr, env)
        if node.op == '-' then return -v end
        if node.op == '+' then return +v end
    end
    if t == 'binop' then
        local a = eval_expr(node.left, env)
        local b = eval_expr(node.right, env)
        local op = node.op
        if op == '+' then return a + b end
        if op == '-' then return a - b end
        if op == '*' then return a * b end
        if op == '/' then return a / b end
        if op == '<' then return a < b end
        if op == '>' then return a > b end
        if op == '<=' then return a <= b end
        if op == '>=' then return a >= b end
        if op == '==' then return a == b end
        if op == '!=' then return a ~= b end
    end
    if t == 'call' then
        local funcnode = node.func
        if funcnode.type == 'prop' then
            local obj = eval_expr(funcnode.object, env)
            local fn = obj[funcnode.name]
            if getmetatable(fn) ~= Function then error('Attempt to call non-function property') end
            local args = {}
            for i,a in ipairs(node.args) do args[i] = eval_expr(a, env) end
            table.insert(args, 1, obj) -- inject self as first arg
            return fn(args)
        end
        local fn = eval_expr(funcnode, env)
        if getmetatable(fn) ~= Function then error('Attempt to call non-function') end
        local args = {}
        for i,a in ipairs(node.args) do args[i] = eval_expr(a, env) end
        return fn(args)
    end
    if t == 'index' then
        local obj = eval_expr(node.object, env)
        local idx = eval_expr(node.index, env)
        return get_indexed(obj, idx)
    end
    if t == 'prop' then
        local obj = eval_expr(node.object, env)
        if type(obj) ~= 'table' then error('Property access expects a dict') end
        return obj[node.name]
    end
    return nil
end

-- Convert expression node that's lvalue to getter/setter
local function as_lvalue(node, env)
    local t = node.type
    if t == 'var' then
        local name = node.name
        local function get() return env:get(name) end
        local function setv(v) env:set(name, v) end
        return get, setv
    end
    if t == 'index' then
        local obj_node = node.object
        local idx_node = node.index
        local function get()
            local obj = eval_expr(obj_node, env)
            local idx = eval_expr(idx_node, env)
            return get_indexed(obj, idx)
        end
        local function setv(v)
            local obj = eval_expr(obj_node, env)
            local idx = eval_expr(idx_node, env)
            set_indexed(obj, idx, v)
        end
        return get, setv
    end
    if t == 'prop' then
        local obj_node = node.object
        local name = node.name
        local function get()
            local obj = eval_expr(obj_node, env)
            if type(obj) ~= 'table' then error('Property access expects a dict') end
            return obj[name]
        end
        local function setv(v)
            local obj = eval_expr(obj_node, env)
            if type(obj) ~= 'table' then error('Property assignment expects a dict') end
            obj[name] = v
        end
        return get, setv
    end
    error('Invalid left-hand side')
end

-- Execute statements
function exec_stmt(node, env)
    local t = node.type
    if t == 'assign' then
        local getter, setter = as_lvalue(node.target, env)
        local value = eval_expr(node.expr, env)
        setter(value)
        return
    end
    if t == 'exprstmt' then
        eval_expr(node.expr, env)
        return
    end
    if t == 'return' then
        local val = eval_expr(node.expr, env)
        error(ReturnSignal.new(val))
    end
    if t == 'def' then
        local fn = Function.new(node.name, node.params, node.body, EnvClass.new(env), false, nil)
        env:set_here(node.name, fn)
        return
    end
    if t == 'methoddef' then
        local target = env:get(node.obj)
        if type(target) ~= 'table' then error(node.obj..' is not an object') end
        target[node.name] = Function.new(node.name, node.params, node.body, EnvClass.new(env), false, nil)
        return
    end
    if t == 'while' then
        while is_truthy(eval_expr(node.cond, env)) do
            exec_block(node.body, EnvClass.new(env))
        end
        return
    end
    if t == 'if' then
        local cond = eval_expr(node.cond, env)
        if is_truthy(cond) then exec_block(node.body, EnvClass.new(env)) end
        return
    end
    if t == 'for_in' then
        local iterable = eval_expr(node.iter, env)
        if type(iterable) ~= 'table' then error('for-in expects a list') end
        for _,v in ipairs(iterable) do
            env:set(node.var, v)
            exec_block(node.body, EnvClass.new(env))
        end
        return
    end
    if t == 'for_c' then
        exec_stmt(node.init, env)
        while is_truthy(eval_expr(node.cond, env)) do
            exec_block(node.body, EnvClass.new(env))
            exec_stmt(node.step, env)
        end
        return
    end
    if t == 'block' then
        exec_block(node.stmts, env)
        return
    end
    error('Unknown statement '..t)
end

function exec_block(stmts, env)
    for _,s in ipairs(stmts) do exec_stmt(s, env) end
end

-- ===== Builtins and Lua interop =====

local function lua_print(args_wrapped)
    -- args_wrapped are wrapped values (from wrap_for_lua)
    local vals = {}
    for i,a in ipairs(args_wrapped) do vals[i] = unwrap_from_lua(a) end
    print(table.unpack(vals))
    return {type='null', value = nil}
end

local function lua_len(args_wrapped)
    local vals = {}
    for i,a in ipairs(args_wrapped) do vals[i] = unwrap_from_lua(a) end
    if #vals ~= 1 then error('len expects 1 argument') end
    return wrap_for_lua(#vals[1])
end

local function lua_range(args_wrapped)
    local vals = {}
    for i,a in ipairs(args_wrapped) do vals[i] = unwrap_from_lua(a) end
    if not (#vals >=1 and #vals <=3) then error('range expects 1..3 args') end
    local a,b,c
    if #vals == 1 then a = 0; b = vals[1]-1; c = 1
    elseif #vals == 2 then a = vals[1]; b = vals[2]-1; c = 1
    else a,b,c = vals[1], vals[2]-1, vals[3] end
    local out = {}
    for i=a,b,c do table.insert(out, wrap_for_lua(i)) end
    return {type='list', value = out}
end

local function lua_upper(args_wrapped)
    local vals = {}
    for i,a in ipairs(args_wrapped) do vals[i] = unwrap_from_lua(a) end
    if #vals ~= 1 then error('upper expects 1 argument') end
    if type(vals[1]) ~= 'string' then error('can not upper a non string') end
    return wrap_for_lua(string.upper(vals[1]))
end

local function lua_lower(args_wrapped)
    local vals = {}
    for i,a in ipairs(args_wrapped) do vals[i] = unwrap_from_lua(a) end
    if #vals ~= 1 then error('lower expects 1 argument') end
    if type(vals[1]) ~= 'string' then error('can not lower a non string') end
    return wrap_for_lua(string.lower(vals[1]))
end

local function lua_split(args_wrapped)
    local vals = {}
    for i,a in ipairs(args_wrapped) do vals[i] = unwrap_from_lua(a) end
    if #vals ~= 2 then error('split expects 2 arguments') end
    if type(vals[1]) ~= 'string' then error('can not split a non string') end
    if type(vals[2]) ~= 'string' then error('can not split with a non string') end
    local res = {}
    local pattern = "(.-)"..vals[2]
    local last_end = 1
    if vals[2] == '' then
        for c in vals[1]:gmatch('.') do table.insert(res, c) end
    else
        local start = 1
        local sep = vals[2]
        local s = vals[1]
        local cap = ''
        local plain = true
        local idx = 1
        while true do
            local st, en = s:find(sep, start, plain)
            if not st then
                table.insert(res, s:sub(start))
                break
            end
            table.insert(res, s:sub(start, st-1))
            start = en + 1
        end
    end
    return wrap_for_lua(res)
end

local function lua_exec(args_wrapped)
    local vals = {}
    for i,a in ipairs(args_wrapped) do vals[i] = unwrap_from_lua(a) end
    local code = ''
    if #vals == 1 then
        if type(vals[1]) == 'string' then code = vals[1]
        elseif type(vals[1]) == 'table' then
            code = table.concat(vals[1])
        end
    else
        code = table.concat(vals)
    end
    local f, err = loadstring(code)
    if not f then error(err) end
    f()
    return {type='null', value = nil}
end

-- ROS info
local ROS = { ver = "BETA (ver2)" }

local function make_global_env()
    local g = EnvClass.new(nil)
    g:set_here('print', Function.new('print', {'*values'}, nil, g, true, lua_print))
    g:set_here('len',   Function.new('len', {'x'}, nil, g, true, lua_len))
    g:set_here('range', Function.new('range', {'a','b','c'}, nil, g, true, lua_range))
    g:set_here('upper', Function.new('upper', {'x'}, nil, g, true, lua_upper))
    g:set_here('lower', Function.new('lower', {'x'}, nil, g, true, lua_lower))
    g:set_here('split', Function.new('split', {'x','sep'}, nil, g, true, lua_split))
    g:set_here('execLua', Function.new('execLua', {'code'}, nil, g, true, lua_exec))
    g:set_here('ROS', ROS)
    return g
end

local function register_luafunc(env, name, luafunc)
    env:set_here(name, Function.new(name, {'*args'}, nil, env, true, luafunc))
end

-- ===== Runner =====
local function run(src, env)
    local tokens = lex(src)
    local parser = Parser.new(tokens)
    local ast = parser:parse()
    if not env then env = make_global_env() end
    exec_stmt(ast, env)
    return env
end

-- The module returns the run function and environment maker
return {
    run = run,
    make_global_env = make_global_env,
    register_luafunc = register_luafunc,
}
