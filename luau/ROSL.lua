-- ===== Lexer =====

local KEYWORDS = {
	["def"] = true, ["return"] = true, ["end"] = true, ["while"] = true, ["for"] = true, ["in"] = true,
			["true"] = true, ["false"] = true, ["null"] = true, ["if"] = true,
}

local function makeToken(kind, text, line, col)
	return { kind = kind, text = text, line = line, col = col }
end

local function isAlpha(c)
	return c:match("[A-Za-z_]") ~= nil
end

local function isAlnum(c)
	return c:match("[A-Za-z0-9_]") ~= nil
end

local function isDigit(c)
	return c:match("%d") ~= nil
end

local function decode_escapes(s)
	-- Python uses unicode_escape; we implement common escapes
	s = s:gsub("\\\"", "\"")
	s = s:gsub("\\\\", "\\")
	s = s:gsub("\\n", "\n")
	s = s:gsub("\\r", "\r")
	s = s:gsub("\\t", "\t")
	return s
end

local function lex(src)
	local i = 1
	local line, col = 1, 1
	local n = #src
	local toks = {}

	local function peek()
		if i > n then return nil end
		return src:sub(i,i)
	end
	local function peek2()
		if i+1 > n then return nil end
		return src:sub(i+1,i+1)
	end
	local function advance()
		local c = peek()
		i += 1
		col += 1
		return c
	end
	local function push(tok)
		toks[#toks+1] = tok
	end

	while i <= n do
		local c = peek()
		-- Whitespace (spaces/tabs)
		if c == " " or c == "\t" then
			local startCol = col
			while peek() == " " or peek() == "\t" do advance() end
			-- skip emitting WS tokens (like Python version)
			 continue
		end

		-- Newlines (support \r\n or \n)
		if c == "\r" or c == "\n" then
			local startCol = col
			if c == "\r" and peek2() == "\n" then
				advance(); advance()
			else
				advance()
			end
			push(makeToken("NL", "\n", line, startCol))
			line += 1; col = 1
			 continue
		end

		-- Number: \d+ or \d+.\d+
		if isDigit(c) then
			local start = i
			local startCol = col
			while peek() and isDigit(peek()) do advance() end
			if peek() == "." and isDigit(peek2() or "") then
				advance()
				while peek() and isDigit(peek()) do advance() end
			end
			local text = src:sub(start, i-1)
			push(makeToken("NUMBER", text, line, startCol))
			 continue
		end

		-- String: " ... " with escapes
		if c == '"' then
			local startCol = col
			advance() -- skip opening quote
			local buf = {}
			local closed = false
			while i <= n do
				local ch = advance()
				if ch == '"' then
					closed = true
					break
				elseif ch == "\\" then
					local nxt = advance()
					if not nxt then break end
					buf[#buf+1] = "\\" .. nxt -- keep escapes; we'll decode in nud
				else
					buf[#buf+1] = ch
				end
			end
			if not closed then error(string.format("Unexpected EOF in string at %d:%d", line, startCol)) end
			local raw = table.concat(buf)
			push(makeToken("STRING", '"'..raw..'"', line, startCol))
			 continue
		end

		-- Identifier / keyword
		if isAlpha(c) then
			local start = i
			local startCol = col
			advance()
			while peek() and isAlnum(peek()) do advance() end
			local text = src:sub(start, i-1)
			if KEYWORDS[text] then
				push(makeToken(text, text, line, startCol))
			else
				push(makeToken("ID", text, line, startCol))
			end
			 continue
		end

		-- Operators and punctuation (match two-char first)
		local two = (c or "") .. (peek2() or "")
		if two == "==" or two == "!=" or two == "<=" or two == ">=" then
			local startCol = col
			advance(); advance()
			push(makeToken(two, two, line, startCol))
			 continue
		end
		local singleOps = {
			["+"] = true, ["-"] = true, ["*"] = true, ["/"] = true,
			["<"] = true, [">"] = true, ["="] = true, ["."] = true,
			[","] = true, [":"] = true, [";"] = true, ["("] = true,
			[")"] = true, ["["] = true, ["]"] = true, ["{"] = true,
			["}"] = true,
		}
		if singleOps[c] then
			local startCol = col
			advance()
			push(makeToken(c, c, line, startCol))
			 continue
		end

		error(string.format("Unexpected character %q at %d:%d", c, line, col))
	end

	push(makeToken("EOF", "EOF", line, col))
	return toks
end

-- ===== Parser (Pratt for expressions) =====

local Parser = {}
Parser.__index = Parser

function Parser.new(tokens)
	local self = setmetatable({}, Parser)
	self.toks = tokens
	self.i = 1
	self.cur = tokens[self.i]
	return self
end

function Parser:advance()
	self.i += 1
	if self.i <= #self.toks then
		self.cur = self.toks[self.i]
	else
		self.cur = { kind = "EOF", text = "EOF", line = -1, col = -1 }
	end
end

function Parser:match(...)
	local kinds = { ... }
	for _, k in ipairs(kinds) do
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
		local want = table.concat({ ... }, " or ")
		error(string.format("Expected %s at %d:%d, got %s %q", want, self.cur.line, self.cur.col, self.cur.kind, self.cur.text))
	end
	return t
end

function Parser:skip_semi_nl()
	while self:match(";", "NL") do end
end

function Parser:parse()
	local body = self:parse_block_until_end(true)
	self:expect("EOF")
	return { type = "block", stmts = body }
end

function Parser:parse_block_until_end(allow_top_level, terminators)
	terminators = terminators or { "end" }
	local termSet = {}
	for _, t in ipairs(terminators) do termSet[t] = true end
	local stmts = {}
	self:skip_semi_nl()
	while self.cur.kind ~= "EOF" do
		if self.cur.kind == "NL" or self.cur.text == ";" then
			self:advance()
		else
			if termSet[self.cur.text] then break end
			stmts[#stmts+1] = self:parse_stmt()
			self:skip_semi_nl()
			if allow_top_level and self.cur.kind == "EOF" then break end
		end
	end
	local needsEnd = false
	for _, t in ipairs(terminators) do if t == "end" then needsEnd = true break end end
	if needsEnd then self:expect("end") end
	return stmts
end

function Parser:parse_stmt()
	if self.cur.text == "def" then
		return self:parse_def()
	end
	if self.cur.text == "return" then
		self:advance()
		local expr = self:parse_expression()
		return { type = "return", expr = expr }
	end
	if self.cur.text == "while" then
		self:advance()
		self:expect("(")
		local cond = self:parse_expression()
		self:expect(")")
		self:skip_semi_nl()
		local body = self:parse_block_until_end(false, { "end" })
		return { type = "while", cond = cond, body = body }
	end
	if self.cur.text == "if" then
		self:advance()
		local cond = self:parse_expression()
		local body = self:parse_block_until_end()
		return { type = "if", cond = cond, body = body }
	end
	if self.cur.text == "for" then
		return self:parse_for()
	end
	local lhs = self:parse_expression()
	if self.cur.text == "=" and (lhs.type == "var" or lhs.type == "index" or lhs.type == "prop") then
		self:advance()
		local expr = self:parse_expression()
		return { type = "assign", target = lhs, expr = expr }
	end
	return { type = "exprstmt", expr = lhs }
end

function Parser:parse_def()
	self:expect("def")
	local name1 = self:expect("ID").text
	local full
	if self.cur.text == "." then
		self:advance()
		local name2 = self:expect("ID").text
		full = { type = "methoddef", obj = name1, name = name2 }
	else
		full = { type = "def", name = name1 }
	end
	self:expect("(")
	local params = {}
	if not self:match(")") then
		while true do
			params[#params+1] = self:expect("ID").text
			if self:match(")") then break end
			self:expect(",")
		end
	end
	self:skip_semi_nl()
	local body = self:parse_block_until_end(false, { "end" })
	full.params = params; full.body = body
	return full
end

function Parser:parse_for()
	self:expect("for")
	if self:match("(") then
		local init = self:parse_stmt()
		self:expect(";")
		local cond = self:parse_expression()
		self:expect(";")
		local step = self:parse_stmt()
		self:expect(")")
		self:skip_semi_nl()
		local body = self:parse_block_until_end(false, { "end" })
		return { type = "for_c", init = init, cond = cond, step = step, body = body }
	else
		local var = self:expect("ID").text
		self:expect("in")
		local iterable = self:parse_expression()
		self:skip_semi_nl()
		local body = self:parse_block_until_end(false, { "end" })
		return { type = "for_in", var = var, iter = iterable, body = body }
	end
end

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
	if t.kind == "NUMBER" then
		if t.text:find(".") then
			return { type = "number", value = tonumber(t.text) }
		else
			return { type = "number", value = tonumber(t.text) }
		end
	end
	if t.kind == "STRING" then
		local inner = t.text:sub(2, -2)
		local s = decode_escapes(inner)
		return { type = "string", value = s }
	end
	if t.kind == "ID" then
		if t.text == "true" then return { type = "bool", value = true } end
		if t.text == "false" then return { type = "bool", value = false } end
		if t.text == "null" then return { type = "null" } end
		return { type = "var", name = t.text }
	end
	if t.text == "(" then
		local expr = self:parse_expression()
		self:expect(")")
		return expr
	end
	if t.text == "[" then
		local items = {}
		if not self:match("]") then
			while true do
				items[#items+1] = self:parse_expression()
				if self:match("]") then break end
				self:expect(",")
			end
		end
		return { type = "list", items = items }
	end
	if t.text == "{" then
		local items = {}
		if not self:match("}") then
			while true do
				local key_node
				if self.cur.kind == "STRING" then
					local k = self.cur.text; self:advance()
					key_node = { type = "string", value = decode_escapes(k:sub(2,-2)) }
				else
					local k = self:expect("ID").text
					key_node = { type = "string", value = k }
				end
				self:expect(":")
				local val = self:parse_expression()
				items[#items+1] = { key_node, val }
				if self:match("}") then break end
				self:expect(",")
			end
		end
		return { type = "dict", items = items }
	end
	if t.text == "-" then
		local expr = self:parse_expression(70)
		return { type = "unary", op = "-", expr = expr }
	end
	if t.text == "+" then
		local expr = self:parse_expression(70)
		return { type = "unary", op = "+", expr = expr }
	end
	error("Unexpected token " .. tostring(t.text))
end

function Parser:lbp(t)
	if not t then return 0 end
	local x = t.text
	if x == "(" or x == "[" or x == "." then return 90 end
	if x == "*" or x == "/" then return 60 end
	if x == "+" or x == "-" then return 50 end
	if x == "<" or x == ">" or x == "<=" or x == ">=" then return 40 end
	if x == "==" or x == "!=" then return 35 end
	return 0
end

function Parser:led(t, left)
	if t.text == "(" then
		local args = {}
		if not self:match(")") then
			while true do
				args[#args+1] = self:parse_expression()
				if self:match(")") then break end
				self:expect(",")
			end
		end
		return { type = "call", func = left, args = args }
	end
	if t.text == "[" then
		local idx = self:parse_expression()
		self:expect("]")
		return { type = "index", object = left, index = idx }
	end
	if t.text == "." then
		local name = self:expect("ID").text
		return { type = "prop", object = left, name = name }
	end
	local ops = { ["*"]=true, ["/"]=true, ["+"]=true, ["-"]=true, ["<"]=true, [">"]=true, ["<="]=true, [">="]=true, ["=="]=true, ["!="]=true }
	if ops[t.text] then
		local right = self:parse_expression(self:lbp(t))
		return { type = "binop", op = t.text, left = left, right = right }
	end
	error("Unexpected infix " .. t.text)
end

-- ===== Runtime / Interpreter =====

local ReturnSignal = {}
ReturnSignal.__index = ReturnSignal
function ReturnSignal.new(value)
	return setmetatable({ value = value }, ReturnSignal)
end

local NULL = {} -- sentinel for null

local function is_list(tbl)
	return type(tbl) == "table" and rawget(tbl, "__list") == true
end

local function is_dict(tbl)
	return type(tbl) == "table" and rawget(tbl, "__dict") == true
end

local function wrap_for_lua(val)
	if val == NULL or val == nil then
		return { type = "null", value = nil }
	end
	local tv = type(val)
	if tv == "boolean" then return { type = "bool", value = val } end
	if tv == "number" then return { type = "number", value = val } end
	if tv == "string" then return { type = "string", value = val } end
	if tv == "table" then
		if is_list(val) then
			local out = {}
			for i = 1, #val do out[#out+1] = wrap_for_lua(val[i]) end
			return { type = "list", value = out }
		elseif is_dict(val) then
			local out = {}
			for k, v in pairs(val) do
				if k ~= "__dict" then out[k] = wrap_for_lua(v) end
			end
			return { type = "dict", value = out }
		end
	end
	if tv == "function" or (tv == "table" and val.__func == true) then
		return val -- Function value
	end
	error("Unsupported type for wrap: " .. tv)
end

local function unwrap_from_lua(obj)
	local t = obj.type
	local v = obj.value
	if t == "null" then return NULL end
	if t == "bool" then return v and true or false end
	if t == "number" then return tonumber(v) end
	if t == "string" then return tostring(v) end
	if t == "list" then
		local out = { __list = true }
		for i = 1, #v do out[i] = unwrap_from_lua(v[i]) end
		return out
	end
	if t == "dict" then
		local out = { __dict = true }
		for k, x in pairs(v) do out[k] = unwrap_from_lua(x) end
		return out
	end
	error("Unsupported wrapped type from lua: " .. tostring(t))
end

local Env = {}
Env.__index = Env
function Env.new(parent)
	return setmetatable({ parent = parent, map = {} }, Env)
end
function Env:get(name)
	if self.map[name] ~= nil then return self.map[name] end
	if self.parent then return self.parent:get(name) end
	error("Undefined variable " .. tostring(name))
end
function Env:set_here(name, value)
	self.map[name] = value
end
function Env:resolve_scope(name)
	if self.map[name] ~= nil then return self end
	if self.parent then return self.parent:resolve_scope(name) end
	return nil
end
function Env:set(name, value)
	local scope = self:resolve_scope(name)
	if scope == nil then self.map[name] = value else scope.map[name] = value end
end

local FunctionVal = {}
FunctionVal.__index = FunctionVal
function FunctionVal.new(name, params, body, env, escapeToLua, luafunc)
	return setmetatable({ __func = true, name = name, params = params, body = body, env = env, escapeToLua = escapeToLua or false, luafunc = luafunc }, FunctionVal)
end
function FunctionVal:__call(argvals)
	if self.escapeToLua then
		local wrapped = {}
		for i = 1, #argvals do wrapped[i] = wrap_for_lua(argvals[i]) end
		local res = self.luafunc(wrapped)
		return unwrap_from_lua(res)
	end
	local localEnv = Env.new(self.env)
	for i, p in ipairs(self.params) do
		localEnv:set_here(p, argvals[i] ~= nil and argvals[i] or NULL)
	end
	local ok, err = pcall(function()
		exec_block(self.body, localEnv)
	end)
	if not ok then
		if type(err) == "table" and getmetatable(err) == ReturnSignal then
			return err.value
		else
			error(err)
		end
	end
	return NULL
end

local function is_truthy(v)
	if v == NULL then return false end
	if v == false then return false end
	local tv = type(v)
	if tv == "number" then return v ~= 0 end
	if tv == "string" then return v ~= "" end
	if tv == "table" then
		if is_list(v) then return #v ~= 0 end
		if is_dict(v) then
			for k,_ in pairs(v) do if k ~= "__dict" then return true end end
			return false
		end
	end
	return true
end

local function get_indexed(obj, index)
	if is_list(obj) then
		if type(index) ~= "number" then error("List index must be integer") end
		return obj[index]
	end
	if is_dict(obj) then
		return obj[index]
	end
	error("Indexing only supported on list and dict")
end

local function set_indexed(obj, index, value)
	if is_list(obj) then
		if type(index) ~= "number" then error("List index must be integer") end
		obj[index] = value
		return
	end
	if is_dict(obj) then
		obj[index] = value
		return
	end
	error("Index assignment only supported on list and dict")
end

function eval_expr(node, env)
	local t = node.type
	if t == "number" then return node.value end
	if t == "string" then return node.value end
	if t == "bool" then return node.value end
	if t == "null" then return NULL end
	if t == "var" then return env:get(node.name) end
	if t == "list" then
		local lst = { __list = true }
		for i, x in ipairs(node.items) do lst[i] = eval_expr(x, env) end
		return lst
	end
	if t == "dict" then
		local d = { __dict = true }
		for _, pair in ipairs(node.items) do
			local k_node, v_node = pair[1], pair[2]
			local key = eval_expr(k_node, env)
			local val = eval_expr(v_node, env)
			d[key] = val
		end
		return d
	end
	if t == "unary" then
		local v = eval_expr(node.expr, env)
		if node.op == "-" then return -v end
		if node.op == "+" then return math.abs(v) end
	end
	if t == "binop" then
		local a = eval_expr(node.left, env)
		local b = eval_expr(node.right, env)
		local op = node.op
		if op == "+" then return a + b end
		if op == "-" then return a - b end
		if op == "*" then return a * b end
		if op == "/" then return a / b end
		if op == "<" then return a < b end
		if op == ">" then return a > b end
		if op == "<=" then return a <= b end
		if op == ">=" then return a >= b end
		if op == "==" then return a == b end
		if op == "!=" then return a ~= b end
	end
	if t == "call" then
		local funcnode = node.func
		if funcnode.type == "prop" then
			local obj = eval_expr(funcnode.object, env)
			if not is_dict(obj) then error("Property access expects a dict") end
			local fn = obj[funcnode.name]
			if not (type(fn) == "table" and fn.__func == true) then error("Attempt to call non-function property") end
			local args = {}
			for i, a in ipairs(node.args) do args[i] = eval_expr(a, env) end
			local args2 = { obj }
			for i = 1, #args do args2[#args2+1] = args[i] end
			return fn(args2)
		end
		local fn = eval_expr(funcnode, env)
		if not (type(fn) == "table" and fn.__func == true) then error("Attempt to call non-function") end
		local args = {}
		for i, a in ipairs(node.args) do args[i] = eval_expr(a, env) end
		return fn(args)
	end
	if t == "index" then
		local obj = eval_expr(node.object, env)
		local idx = eval_expr(node.index, env)
		return get_indexed(obj, idx)
	end
	if t == "prop" then
		local obj = eval_expr(node.object, env)
		if not is_dict(obj) then error("Property access expects a dict") end
		return get_indexed(obj, node.name)
	end
	return NULL
end

local function as_lvalue(node, env)
	local t = node.type
	if t == "var" then
		local name = node.name
		local function get() return env:get(name) end
		local function setv(v) env:set(name, v) end
		return get, setv
	end
	if t == "index" then
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
	if t == "prop" then
		local obj_node = node.object
		local name = node.name
		local function get()
			local obj = eval_expr(obj_node, env)
			if not is_dict(obj) then error("Property access expects a dict") end
			return obj[name]
		end
		local function setv(v)
			local obj = eval_expr(obj_node, env)
			if not is_dict(obj) then error("Property assignment expects a dict") end
			obj[name] = v
		end
		return get, setv
	end
	error("Invalid left-hand side")
end

function exec_stmt(node, env)
	task.wait(0.02)
	local t = node.type
	if t == "assign" then
		local _get, setter = as_lvalue(node.target, env)
		local value = eval_expr(node.expr, env)
		setter(value)
		return
	end
	if t == "exprstmt" then eval_expr(node.expr, env); return end
	if t == "return" then
		local val = eval_expr(node.expr, env)
		error(ReturnSignal.new(val))
	end
	if t == "def" then
		local fn = FunctionVal.new(node.name, node.params, node.body, Env.new(env))
		env:set_here(node.name, fn)
		return
	end
	if t == "methoddef" then
		local target = env:get(node.obj)
		if not is_dict(target) then error(node.obj .. " is not an object") end
		target[node.name] = FunctionVal.new(node.name, node.params, node.body, Env.new(env))
		return
	end
	if t == "while" then
		while is_truthy(eval_expr(node.cond, env)) do
			exec_block(node.body, Env.new(env))
		end
		return
	end
	if t == "if" then
		local cond = eval_expr(node.cond, env)
		if is_truthy(cond) then
			exec_block(node.body, Env.new(env))
		end
		return
	end
	if t == "for_in" then
		local iterable = eval_expr(node.iter, env)
		if not is_list(iterable) then error("for-in expects a list") end
		for i = 1, #iterable do
			env:set(node.var, iterable[i])
			exec_block(node.body, Env.new(env))
		end
		return
	end
	if t == "for_c" then
		exec_stmt(node.init, env)
		while is_truthy(eval_expr(node.cond, env)) do
			exec_block(node.body, Env.new(env))
			exec_stmt(node.step, env)
		end
		return
	end
	if t == "block" then exec_block(node.stmts, env); return end
	error("Unknown statement " .. tostring(t))
end

function exec_block(stmts, env)
	for _, s in ipairs(stmts) do
		exec_stmt(s, env)
	end
end

-- ===== Builtins and Lua interop =====

local function lu_print(args_wrapped)
	local vals = {}
	for i = 1, #args_wrapped do
		local x = unwrap_from_lua(args_wrapped[i])
		if x == NULL then x = nil end
		vals[#vals+1] = x
	end
	print(table.unpack(vals))
	return { type = "null", value = nil }
end

local function lu_len(args_wrapped)
	local vals = {}
	for i = 1, #args_wrapped do vals[i] = unwrap_from_lua(args_wrapped[i]) end
	if #vals ~= 1 then error("len expects 1 argument") end
	local x = vals[1]
	if type(x) == "string" then return wrap_for_lua(#x) end
	if is_list(x) then return wrap_for_lua(#x) end
	if is_dict(x) then
		local c = 0
		for k,_ in pairs(x) do if k ~= "__dict" then c += 1 end end
		return wrap_for_lua(c)
	end
	return wrap_for_lua(0)
end

local function lu_range(args_wrapped)
	local vals = {}
	for i = 1, #args_wrapped do vals[i] = unwrap_from_lua(args_wrapped[i]) end
	local m = #vals
	if not (1 <= m and m <= 3) then error("range expects 1..3 args") end
	local start, stop, step
	if m == 1 then start, stop, step = 0, vals[1], 1
	elseif m == 2 then start, stop, step = vals[1], vals[2], 1
	else start, stop, step = vals[1], vals[2], vals[3] end
	local out = { __list = true }
	if step == 0 then error("range step must not be zero") end
	if step > 0 then
		for v = start, stop-1, step do out[#out+1] = v end
	else
		for v = start, stop+1, step do out[#out+1] = v end
	end
	local wrapped = { type = "list", value = {} }
	for i = 1, #out do wrapped.value[i] = wrap_for_lua(out[i]) end
	return wrapped
end

local function lu_upper(args_wrapped)
	local v = unwrap_from_lua(args_wrapped[1])
	if #args_wrapped ~= 1 then error("upper expects 1 argument") end
	if type(v) ~= "string" then error("can not upper a non string") end
	return wrap_for_lua(string.upper(v))
end

local function lu_lower(args_wrapped)
	local v = unwrap_from_lua(args_wrapped[1])
	if #args_wrapped ~= 1 then error("upper expects 1 argument") end
	if type(v) ~= "string" then error("can not lower a non string") end
	return wrap_for_lua(string.lower(v))
end

local function split_plain(s, sep)
	if sep == "" then
		local out = { __list = true }
		for i = 1, #s do out[#out+1] = s:sub(i,i) end
		return out
	end
	local out = { __list = true }
	local pos = 1
	while true do
		local i1, i2 = string.find(s, sep, pos, true)
		if not i1 then
			out[#out+1] = s:sub(pos)
			break
		end
		out[#out+1] = s:sub(pos, i1-1)
		pos = i2 + 1
	end
	return out
end

local function lu_split(args_wrapped)
	local s = unwrap_from_lua(args_wrapped[1])
	local sep = unwrap_from_lua(args_wrapped[2])
	if #args_wrapped ~= 2 then error("split expects 2 arguments") end
	if type(s) ~= "string" then error("can not split a non string") end
	if type(sep) ~= "string" then error("can not split with a non string") end
	local parts = split_plain(s, sep)
	local wrapped = { type = "list", value = {} }
	for i = 1, #parts do wrapped.value[i] = wrap_for_lua(parts[i]) end
	return wrapped
end

local function lu_exec(args_wrapped)
	local vals = {}
	for i = 1, #args_wrapped do vals[i] = unwrap_from_lua(args_wrapped[i]) end
	local code = nil
	if #vals == 1 then
		if type(vals[1]) == "string" then code = vals[1]
		elseif is_list(vals[1]) then
			local buf = {}
			for i = 1, #vals[1] do buf[#buf+1] = vals[1][i] end
			code = table.concat(buf, "")
		end
	else
		local buf = {}
		for i = 1, #vals do buf[#buf+1] = tostring(vals[i]) end
		code = table.concat(buf, "")
	end
	if not code then return { type = "null", value = nil } end
	local chunk, err = loadstring(code)
	if not chunk then error(err) end
	local ok, e = pcall(chunk)
	if not ok then error(e) end
	return { type = "null", value = nil }
end

local ROS = { ver = "BETA (ver2)" }

local function make_global_env()
	local g = Env.new()
	g:set_here("print",  FunctionVal.new("print",  {"*values"},  nil, g, true, lu_print))
	g:set_here("len",    FunctionVal.new("len",    {"x"},        nil, g, true, lu_len  ))
	g:set_here("range",  FunctionVal.new("range",  {"a","b","c"}, nil, g, true, lu_range))
	g:set_here("upper",  FunctionVal.new("upper",  {"x"},        nil, g, true, lu_upper))
	g:set_here("lower",  FunctionVal.new("lower",  {"x"},        nil, g, true, lu_lower))
	g:set_here("split",  FunctionVal.new("split",  {"x","sep"}, nil, g, true, lu_split))
	g:set_here("execLua",FunctionVal.new("execLua",{"code"},     nil, g, true, lu_exec ))
	g:set_here("ROS", ROS)
	return g
end

local function register_luafunc(env, name, luafunc)
	env:set_here(name, FunctionVal.new(name, {"*args"}, nil, env, true, luafunc))
end

-- ===== Runner =====

function run(src, env)
	local tokens = lex(src)
	local parser = Parser.new(tokens)
	local ast = parser:parse()
	if env == nil then env = make_global_env() end
	exec_stmt(ast, env)
	return env
end

return {
	["run"] = run,
	["Env"] = Env,
	["Function"] = FunctionVal,
	["registorFunc"] = register_luafunc
}