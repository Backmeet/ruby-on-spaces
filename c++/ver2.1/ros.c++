#include <regex>
#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <format>
#include <array>
#include <set>
#include <stdexcept>
#include <sstream>
#include <algorithm>
#include <optional>
#include <unordered_map>
#include <any>
#include <variant>
#include <chrono>

typedef std::vector<std::string> Strings;
typedef Strings Kinds;
typedef std::unordered_map<std::string, std::any> JsonLike;

std::array<std::pair<std::string, std::string>, 7> TOKEN_SPEC = {
    std::make_pair("NL"      , R"(\r?\n)"),              // <-- moved to top
    std::make_pair("WS"      , R"([ \t\r\f\v]+)"),
    std::make_pair("NUMBER"  , R"(\d+\.\d+|\d+)"),
    std::make_pair("STRING"  , R"("([^"\\]|\\.)*")"),
    std::make_pair("ID"      , R"([A-Za-z_][A-Za-z0-9_]*)"),
    std::make_pair("OP"      , R"(==|!=|<=|>=|\+|-|\*|/|<|>|=|\.|,|:|;|\(|\)|\[|\]|\{|\})"),
    std::make_pair("MISMATCH", R"(.)")
};
std::array<std::string, 7> group_to_name = {
    "NL",
    "WS",
    "NUMBER",
    "STRING",
    "MISMATCH",
    "ID",
    "OP"
};

std::regex TOKEN_RE;

std::string decode_escaped(const std::string& s) {
    std::string result;
    size_t i = 0;
    while (i < s.size()) {
        if (s[i] == '\\' && i + 1 < s.size()) {
            ++i;
            char c = s[i];
            switch (c) {
                case 'n': result += '\n'; break;
                case 'r': result += '\r'; break;
                case 't': result += '\t'; break;
                case 'b': result += '\b'; break;
                case 'f': result += '\f'; break;
                case 'v': result += '\v'; break;
                case '\\': result += '\\'; break;
                case '\'': result += '\''; break;
                case '"': result += '"'; break;
                case 'a': result += '\a'; break;
                case 'x': { // hex escape \xhh
                    ++i;
                    int value = 0;
                    int count = 0;
                    while (i < s.size() && std::isxdigit(s[i]) && count < 2) {
                        value = value * 16 + std::stoi(s.substr(i,1), nullptr, 16);
                        ++i; ++count;
                    }
                    --i; // adjust for outer loop increment
                    result += static_cast<char>(value);
                    break;
                }
                case 'u': { // unicode \uXXXX
                    ++i;
                    if (i + 3 >= s.size()) throw std::runtime_error("Invalid \\u escape");
                    unsigned int code = std::stoi(s.substr(i,4), nullptr, 16);
                    result += static_cast<char>(code); // UTF-8 encoding needed for full unicode
                    i += 3;
                    break;
                }
                case 'U': { // unicode \UXXXXXXXX
                    ++i;
                    if (i + 7 >= s.size()) throw std::runtime_error("Invalid \\U escape");
                    unsigned int code = std::stoul(s.substr(i,8), nullptr, 16);
                    result += static_cast<char>(code); // UTF-8 encoding needed for full unicode
                    i += 7;
                    break;
                }
                default:
                    result += c; // unknown escape, copy as-is
            }
        } else {
            result += s[i];
        }
        ++i;
    }
    return result;
}

void init() {
    std::string combined_pattern;

    for (const auto& [name, pattern] : TOKEN_SPEC) {
        if (!combined_pattern.empty()) combined_pattern += "|";
        combined_pattern += "(" + pattern + ")";
    }

    TOKEN_RE = std::regex(combined_pattern, std::regex_constants::ECMAScript);
}

std::set<std::string> KEYWORDS = {
    "def", "return", "end", "while", "for", "in", "true", "false", "null", "if", "import"
};

struct Token {
    std::string kind;
    std::string text;
    int line;
    int col;

    Token() : kind(""), text(""), line(0), col(0) {}

    Token(std::string kind, std::string text, int line, int col) {
        this->kind = kind;
        this->text = text;
        this->line = line;
        this->col = col;
    }

    std::string repr() {
        std::stringstream ss;
        ss << "Token(" << kind << ", " << text << "@" << line << ":" << col << ")";
        return ss.str();
    }
};


std::string JsonLiketoS(const JsonLike& JL);

struct Node {
    std::string type;
    JsonLike data;     

    Node() : type("null"), data(){};

    Node(std::string type, JsonLike data) {
        this->type = type;
        this->data = data;
    }

    std::string repr() {
        return "Node<" + type + ", " + JsonLiketoS(data) + ">";
    }
};

template<typename T>
bool in(const T& val, const std::vector<T>& v) {
    return std::find(v.begin(), v.end(), val) != v.end();
}

typedef std::vector<Node> Nodes;
typedef std::vector<Token> Tokens;
typedef std::optional<Token> MaybeToken;

std::string JsonLiketoS(const JsonLike& JL) {
    std::function<std::string(const std::any&)> toS = [&](const std::any& v) -> std::string {
        if (v.type() == typeid(int)) return std::to_string(std::any_cast<int>(v));
        if (v.type() == typeid(double)) return std::to_string(std::any_cast<double>(v));
        if (v.type() == typeid(bool)) return std::any_cast<bool>(v) ? "true" : "false";
        if (v.type() == typeid(std::string)) return '"' + std::any_cast<std::string>(v) + '"';
        if (v.type() == typeid(JsonLike)) return JsonLiketoS(std::any_cast<const JsonLike&>(v));
        if (v.type() == typeid(Node)) {return std::any_cast<Node>(v).repr();}
        if (v.type() == typeid(Nodes)) {
            std::string out = "Nodes{";
            for (Node n : std::any_cast<Nodes>(v)) {out += n.repr();}
            return out + "}";
        }
        if (v.type() == typeid(Token)) {
            return std::any_cast<Token>(v).repr();
        }
        if (v.type() == typeid(Tokens)) {
            std::string out = "Tokens{";
            for (Token n : std::any_cast<Tokens>(v)) {out += n.repr();}
            return out + "}";
        }
        if (v.type() == typeid(std::vector<std::any>)) {
            const auto& vec = std::any_cast<const std::vector<std::any>&>(v);
            std::string out;
            out += "vector<any>{";
            bool first = true;
            for (auto& e : vec) {
                if (!first) out += ", ";
                first = false;
                out += toS(e);
            }
            out.erase(out.size() - 2, 2);
            out += "}";
            return out;
        }
        return "<unknown>";
    };

    std::ostringstream out;
    out << "{";
    bool first = true;
    for (auto& [k, v] : JL) {
        if (!first) out << ", ";
        first = false;
        out << '"' << k << "\": " << toS(v);
    }
    out << "}";
    return out.str();
}

Tokens lex(const std::string& src) {
    int line = 1;
    int col = 1;
    Tokens tokens;

    auto begin = std::sregex_iterator(src.begin(), src.end(), TOKEN_RE);
    auto end   = std::sregex_iterator();

    for (auto it = begin; it != end; ++it) {
        std::smatch match = *it;

        // Determine which group matched (like lastgroup)
        std::string kind;
        std::string text;
        for (size_t i = 1; i < match.size(); ++i) {
            if (match[i].matched) {
                kind = group_to_name[i - 1]; // equivalent of .lastgroup
                text = match[i].str();  // equivalent of .group()
                break;                  // first matched group wins
            }
        }

        if (kind == "WS") {
            col += text.length();
            continue;
        } else if (kind == "NL") {
            tokens.push_back(Token("NL", "\n", line, col));
            line += 1;
            col = 1;
        } else if (kind == "ID" && KEYWORDS.count(text)) {
            tokens.push_back(Token(text, text, line, col));
        } else if (kind == "ID") {
            tokens.push_back(Token("ID", text, line, col));
        } else if (kind == "NUMBER") {
            tokens.push_back(Token("NUMBER", text, line, col));
        } else if (kind == "STRING") {
            tokens.push_back(Token("STRING", text, line, col));
        } else if (kind == "OP") {
            tokens.push_back(Token("OP", text, line, col));
        } else if (kind == "MISMATCH") {
            throw std::runtime_error("Unexpected Character " + text);
        }
        col += text.length();
    }
    tokens.push_back(Token("EOF", "EOF", line, col));
    return tokens;
}

// parser
struct Parcer {
    Tokens tokens;
    int i = 0;
    Token cur;


    Parcer(Tokens tokens) {
        this->tokens = tokens;
        cur = this->tokens[i];
    }

    void advance() {
        i++;
        if (i < tokens.size()) {
            cur = tokens[i];
        } else {
            cur = Token("EOF", "EOF", -1, -1);
        }
    }

    MaybeToken match(Kinds kinds) {
        if (in(cur.kind, kinds) || in(cur.text, kinds)) {
            Token t = cur;
            this->advance();
            return t;
        }
        return std::nullopt;
    }

    Token expect(Kinds kinds) {
        MaybeToken t = this->match(kinds);
        if (not t) {
            std::string want = "{";
            for (std::string t : kinds) {
                want += t + ", ";
            }
            if (!want.empty()) want.erase(want.size() - 2, 2);
            want += "}";
            throw std::runtime_error("Expected " + want + " at " + std::to_string(cur.line) + ":" + std::to_string(cur.col) + ", got " + cur.kind + " " + cur.text);
        }
        return t.value();
    }

    void skip_semi_nl() {
        while (this->match(Strings{";", "Nl"})) {}
    }

    Node parse() {
        Nodes body = this->parse_block_until_end(true);
        JsonLike r;
        r["stmts"] = body;
        return Node("block", r);
    }

    Nodes parse_block_until_end(bool allow_top_level=false, Strings terminators = {"end"} ) {
        Nodes stmts;
        this->skip_semi_nl();
        while (cur.kind != "EOF") {
            if (cur.kind == "NL" or cur.text == ";") {
                this->advance();
                continue;
            }
            if (in(cur.text, terminators)) {
                break;
            }
            stmts.push_back(this->parse_stmt());
            this->skip_semi_nl();
            if (allow_top_level and cur.kind == "EOF") {
                break;
            }
        }
        if (in(std::string("end"), terminators)) {
            this->expect(Kinds{"end"});
        }
        return stmts;
    }

    Node parse_stmt() {
        if (cur.text == "def") {
            this->expect({"def"});
            Node N("def", JsonLike{});


            // first obj / indetifier
            std::string name1 = this->expect({"ID"}).text;

            if (cur.text == ".") {
                this->advance();
                std::string name2 = this->expect({"ID"}).text;
                N.type = "methoddef";
                N.data["obj"] = name1;
                N.data["name2"] = name2;
            } else {
                N.data["name"] = name1;
            }

            this->expect({"("});
            Strings params;
            if (this->match({")"}) == std::nullopt) { // if not this->match({")"})
                while (true) {
                    std::string p = this->expect({"ID"}).text;
                    params.push_back(p);
                    if (this->match({")"}) != std::nullopt) {break;}
                    this->expect({","});
                }
            }

            this->skip_semi_nl();
            Nodes body = this->parse_block_until_end();

            N.data["params"] = params;
            N.data["body"] = body;
            return N;            
        } if (cur.text == "return") {
            this->advance();
            Node expr = this->parse_expression();
            return Node("return", JsonLike{{"expr", expr}});
        } if (cur.text == "while") {
            this->advance();
            this->expect({"("});
            Node cond = this->parse_expression();
            this->expect({")"});
            this->skip_semi_nl();
            Nodes body  = this->parse_block_until_end();
            return Node("while", JsonLike{{"cond", cond}, {"body", body}});
        } if (cur.text == "if") {
            this->advance();
            Node cond = this->parse_expression();
            Nodes body = this->parse_block_until_end();
            return Node("if", JsonLike{{"cond", cond}, {"body", body}});
        } if (cur.text == "import") {
            this->advance();
            Node fileName = this->parse_expression();
            return Node("import", JsonLike{{"fileName", fileName}});
        } if (cur.text == "del") {
            this->advance();
            Node expr = this->parse_expression();
            return Node("del", JsonLike{{"expr", expr}});
        } if (cur.text == "for") {
            this->expect({"for"});
            if (this->match({"("}) != std::nullopt) {
                Node init = this->parse_stmt();
                this->expect({";"});
                Node cond = this->parse_expression();
                this->expect({";"});
                Node step = this->parse_stmt();
                this->expect({")"});
                this->skip_semi_nl();
                Nodes body = this->parse_block_until_end();
                return Node("for_c", JsonLike{{"init", init}, {"cond", cond}, {"step", step}, {"body", body}});
            } else {
                std::string var = this->expect({"ID"}).text;
                this->expect({"in"});
                Node iterable = this->parse_expression();
                this->skip_semi_nl();
                Nodes body = this->parse_block_until_end();
                return Node("for_in", JsonLike{{"var", var}, {"iter", iterable}, {"body", body}});
            }
        }

        // assignment or a expression stmt
        Node lhs = this->parse_expression();
        if (cur.text == "=" and in(lhs.type, {"var", "index", "prop"})) {
            this->advance();
            Node expr = this->parse_expression();
            return Node("assign", JsonLike{{"target", lhs}, {"expr", expr}});
        }
        // just a exprestion stmt
        return Node("exprstmt", JsonLike{{"expr", lhs}});
    }

    Node parse_expression(int rbp = 0){
        Token t = cur;
        this->advance();
        Node left = this->nud(t);
        int lbp = this->lbp(t);
        while (true) {
            t = cur;
            lbp = this->lbp(t);
            if (rbp >= lbp) {
                break;
            }
            this->advance();
            left = this->led(t, left);
        }
        return left;
    }

    Node nud(Token t) {
        if (t.kind == "NUMBER") {
            if (t.text.find(".") != std::string::npos) { // "." in t.text
                return Node("number", JsonLike{{"value", std::stof(t.text)}});
            } else {
                return Node("number", JsonLike{{"value", std::stoi(t.text)}});
            } 
        } if (t.kind == "STRING") {
            std::string s = decode_escaped(t.text.substr(1, t.text.length() - 1));
            return Node("string", JsonLike{{"value", s}});
        } if (t.kind =="ID") {
            if (t.text == "true") {
                return Node("bool", JsonLike{{"value", true}});
            } if (t.text == "false") {
                return Node("bool", JsonLike{{"value", false}});
            } if (t.text == "null") {
                return Node("null", JsonLike{});
            } 
            return Node("var", JsonLike{{"name", t.text}});
        } if (t.text == "(") {
            Node expr = this->parse_expression();
            this->expect({")"});
            return expr;
        } if (t.text == "[") {
            Nodes items;
            if (this->match({"]"}) == std::nullopt) {
                while (true) {
                    items.push_back(this->parse_expression());
                    if (this->match({"]"}) != std::nullopt) {break;}
                    this->expect({","});
                }
            }
            return Node("list", JsonLike{{"items", items}});
        } if (t.text == "{") {
            std::vector<std::array<Node, 2>> items;
            if (this->match({""}) == std::nullopt) {
                std::string k;
                while (true) {
                    Node key = this->parse_expression();
                    this->expect({":"});
                    Node val = this->parse_expression();
                    items.push_back({key, val});
                    if (this->match({"}"}) != std::nullopt) {
                        break;
                    }
                    this->expect({","});
                }

            }
            return Node("dict", JsonLike{{"items", items}});
        } if (t.text == "-") {
            Node expr = this->parse_expression(70);
            return Node("unary", JsonLike{{"op", "-"}, {"expr", expr}});
        } if (t.text == "+") {
            Node expr = this->parse_expression(70);
            return Node("unary", JsonLike{{"op", "+"}, {"expr", expr}});
        } 
        throw std::runtime_error("Unexpected token " + t.repr());
    }

    int lbp(Token t) {
        if (in(t.text, {"(", "[", "."})) {
            return 90;
        } if (in(t.text, {"*", "/"})) {
            return 60;
        } if (in(t.text, {"+", "-"})) {
            return 50;
        } if (in(t.text, {">", "<", "<=", ">="})) {
            return 40;
        } if (in(t.text, {"==", "!="})) {
            return 35;
        } return 0;
    }

    Node led(Token t, Node left) {
        if (t.text == "(") {
            // func call
            Nodes args;
            if (this->match({")"}) == std::nullopt) {
                while (true) {
                    args.push_back(this->parse_expression());
                    if (this->match({")"}) != std::nullopt) {
                        break;
                    }
                    this->expect({")"});
                }
            }
            return Node("call", JsonLike{{"func", left}, {"args", args}});
        } if (t.text == "[") {
            Node idx = this->parse_expression();
            this->expect({"]"});
            return Node("index", JsonLike{{"object", left}, {"index", idx}});
        } if (t.text == ".") {
            std::string name = this->expect({"ID"}).text;
            return Node("prop", JsonLike{{"object", left}, {"name", name}});
        } if (in(t.text, {"*", "/", "+", "-", "<", ">", "<=", ">=", "==", "!="})) {
            Node right = this->parse_expression(this->lbp(t));
            return Node("binop", JsonLike{{"op", t.text}, {"left", left}, {"right", right}});
        }
        throw std::runtime_error("Unexprected infix " + t.text);
    }
};

struct Function; // forward declaration

class ReturnSignal : public std::runtime_error {
    public:
    int value = 0;
    ReturnSignal(int value) : std::runtime_error("ReturnSignal"), value(value) {}
};

template<typename T>
Node wrapForCpp(std::any val) {
    if (val.type() == typeid(void)) {
        return Node("null", JsonLike{});
    } if (val.type() == typeid(bool)) {
        return Node("bool", JsonLike{{"value", std::any_cast<bool>(val)}});

    } if (val.type() == typeid(int)) {
        return Node("number", JsonLike{{"value", std::any_cast<int>(val)}});

    } if (val.type() == typeid(float)) {
        return Node("number", JsonLike{{"value", std::any_cast<float>(val)}});

    } if (val.type() == typeid(std::string)) {
        return Node("string", JsonLike{{"value", std::any_cast<std::string>(val)}});

    } if (val.type() == typeid(std::vector<int>)) {
        return Node("list", JsonLike{{"value", std::any_cast<std::vector<int>>(val)}});

    } if (val.type() == typeid(std::vector<std::string>)) {
        return Node("list", JsonLike{{"value", std::any_cast<std::vector<std::string>>(val)}});

    } if (val.type() == typeid(std::vector<float>)) {
        return Node("list", JsonLike{{"value", std::any_cast<std::vector<float>>(val)}});

    } if (val.type() == typeid(std::vector<bool>)) {
        return Node("list", JsonLike{{"value", std::any_cast<std::vector<bool>>(val)}});

    } if (val.type() == typeid(Function)) {
        return Node("Function", JsonLike{{"func", std::any_cast<Function>(val)}});
    } throw std::runtime_error(std::string("Unsupported type for wrap: ") + val.type().name());
}

struct Env {
    Env* parent = nullptr;
    std::unordered_map<std::string, Node> map;

    Env(Env* parent = nullptr) {
        this->parent = parent;
    }

    Node get(const std::string& name) {
        if (map.find(name) != map.end()) {
            return map[name];
        }
        if (parent != nullptr) {
            return parent->get(name);
        }
        throw std::runtime_error("Undefined variable " + name);
    }

    void set_here(const std::string& name, const Node& value) {
        map[name] = value;
    }

    Env* resolve_scope(const std::string& name) {
        if (map.find(name) != map.end()) {
            return this;
        }
        if (parent != nullptr) {
            return parent->resolve_scope(name);
        }
        return nullptr;
    }

    void set(const std::string& name, const Node& value) {
        Env* scope = resolve_scope(name);
        if (scope == nullptr) {
            map[name] = value;
        } else {
            scope->map[name] = value;
        }
    }

    void remove_here(const std::string& name) {
        map.erase(name);
    }

    void remove(const std::string& name) {
        Env* scope = resolve_scope(name);
        if (scope == nullptr) {
            map.erase(name);
        } else {
            scope->map.erase(name);
        }
    }
};
void exec_stmt(Node& node, Env* env);

void exec_block(Nodes nodes, Env* env) {
    for (Node s : nodes) {
        exec_stmt(s, env);
    }
}

struct Function {
    std::string name;
    std::vector<std::string> params;
    Nodes body;
    Env* env;
    bool escapeToCpp = false; // placeholder if you want native escape
    std::function<Node(std::vector<Node>, Env*)> cppfunc;

    Function(std::string name, std::vector<std::string> params, Nodes body, Env* env)
        : name(name), params(params), body(body), env(env) {}

    Node operator()(const std::vector<Node>& argvals) {
        if (escapeToCpp) {
            return cppfunc(argvals, env);
        }
        Env local(env);
        for (size_t i = 0; i < params.size(); ++i) {
            Node val = i < argvals.size() ? argvals[i] : Node("null", JsonLike{});
            local.set_here(params[i], val);
        }
        try {
            exec_block(body, &local);
        } catch (ReturnSignal& rs) {
            return Node("number", JsonLike{{"value", rs.value}});
        }
        return Node("null", JsonLike{});
    }
};

bool is_truthy(const Node& v) {
    if (v.type == "bool") {
        return std::any_cast<bool>(v.data.at("value"));
    }
    if (v.type == "null") return false;
    if (v.type == "number") return std::any_cast<float>(v.data.at("value")) != 0;
    return true;
}

Node get_indexed(const Node& obj, const Node& index) {
    if (obj.type == "list") {
        auto vec = std::any_cast<std::vector<Node>>(obj.data.at("items"));
        int idx = std::any_cast<int>(index.data.at("value"));
        return vec[idx];
    }
    if (obj.type == "dict") {
        auto dict = std::any_cast<JsonLike>(obj.data.at("items"));
        std::string key = std::any_cast<std::string>(index.data.at("value"));
        return std::any_cast<Node>(dict[key]);
    }
    throw std::runtime_error("Indexing only supported on list and dict");
}

void set_indexed(Node& obj, const Node& index, const Node& value) {
    if (obj.type == "list") {
        auto& vec = std::any_cast<std::vector<Node>&>(obj.data.at("items"));
        int idx = std::any_cast<int>(index.data.at("value"));
        vec[idx] = value;
        return;
    }
    if (obj.type == "dict") {
        auto& dict = std::any_cast<JsonLike&>(obj.data.at("items"));
        std::string key = std::any_cast<std::string>(index.data.at("value"));
        dict[key] = value;
        return;
    }
    throw std::runtime_error("Index assignment only supported on list and dict");
}

std::pair<std::function<Node()>, std::function<void(Node)>> as_lvalue(Node& node, Env* env) {
    if (node.type == "var") {
        std::string name = std::any_cast<std::string>(node.data.at("name"));
        return std::make_pair(
            std::function<Node()>([env, name]() { return env->get(name); }),
            std::function<void(Node)>([env, name](Node v) { env->set(name, v); })
        );
    }
    if (node.type == "index") {
        Node obj = std::any_cast<Node>(node.data.at("object"));
        Node idx = std::any_cast<Node>(node.data.at("index"));
        return std::make_pair(
            std::function<Node()>([obj, idx]() { return get_indexed(obj, idx); }),
            std::function<void(Node)>([obj, idx](Node v) mutable { set_indexed(obj, idx, v); })
        );
    }
    if (node.type == "prop") {
        Node obj = std::any_cast<Node>(node.data.at("object"));
        std::string name = std::any_cast<std::string>(node.data.at("name"));
        return std::make_pair(
            std::function<Node()>([env, name]() -> Node { 
                return env->get(name); 
            }),
            std::function<void(Node)>([env, name](Node v) { 
                env->set(name, v); 
            })
        );
    }
    throw std::runtime_error("Invalid lvalue");
}

Node eval_expr(const Node& node, Env* env); // forward

Node get_prop(Node& obj, const std::string& name) {
    if (obj.type != "dict") throw std::runtime_error("Property access expects a dict");
    auto& dict = std::any_cast<JsonLike&>(obj.data.at("items"));
    return std::any_cast<Node>(dict[name]);
}

void set_prop(Node& obj, const std::string& name, Node value) {
    if (obj.type != "dict") throw std::runtime_error("Property assignment expects a dict");
    auto& dict = std::any_cast<JsonLike&>(obj.data.at("items"));
    dict[name] = value;
}

Node eval_expr(const Node& node, Env* env) {
    if (node.type == "number" || node.type == "string" || node.type == "bool" || node.type == "null") {
        return node;
    }
    if (node.type == "var") {
        std::string name = std::any_cast<std::string>(node.data.at("name"));
        return env->get(name);
    }
    if (node.type == "list") {
        Nodes items = std::any_cast<Nodes>(node.data.at("items"));
        Nodes res;
        for (auto& n : items) res.push_back(eval_expr(n, env));
        return Node("list", JsonLike{{"items", res}});
    }
    if (node.type == "dict") {
        auto items = std::any_cast<std::vector<std::array<Node,2>>>(node.data.at("items"));
        JsonLike res;
        for (auto& kv : items) {
            Node k = eval_expr(kv[0], env);
            Node v = eval_expr(kv[1], env);
            res[std::any_cast<std::string>(k.data.at("value"))] = v;
        }
        return Node("dict", JsonLike{{"items", res}});
    }
    if (node.type == "unary") {
        Node tmp = std::any_cast<Node>(node.data.at("expr"));
        Node a = eval_expr(tmp, env);
        std::string op = std::any_cast<std::string>(node.data.at("op"));
        
        if (a.type == "number" or a.type == "bool") {
            float av;
            if (a.data.at("value").type() == typeid(int)) {
                av = std::any_cast<int>(a.data.at("value"));
            } else if (a.data.at("value").type() == typeid(float)) {av = std::any_cast<float>(a.data.at("value"));}
            else {av = (int)(std::any_cast<bool>(a.data.at("value")));}
            if (op == "+") return Node("number", JsonLike{{"value", +av}});
            if (op == "-") return Node("number", JsonLike{{"value", -av}});
        } if (a.type == "list" and op == "-") {
            std::any_cast<Nodes>(a.data.at("items")).pop_back(); return a;
        }

    }
    if (node.type == "binop") {
        Node a = eval_expr(std::any_cast<Node>(node.data.at("left")), env);
        Node b = eval_expr(std::any_cast<Node>(node.data.at("right")), env);
        std::string op = std::any_cast<std::string>(node.data.at("op"));

        if (a.type == "number" and b.type == "number" or a.type == "bool" and b.type == "bool") {
            float av;
            if (a.data.at("value").type() == typeid(int)) {
                av = std::any_cast<int>(a.data.at("value"));
            } else if (a.data.at("value").type() == typeid(float)) {av = std::any_cast<float>(a.data.at("value"));}
            else {av = (int)(std::any_cast<bool>(a.data.at("value")));}

            float bv;
            if (b.data.at("value").type() == typeid(int)) {
                bv = std::any_cast<int>(b.data.at("value"));
            } else if (b.data.at("value").type() == typeid(float)) {bv = std::any_cast<float>(b.data.at("value"));}
            else {bv = (int)(std::any_cast<bool>(b.data.at("value")));}

            if (op == "+") return Node("number", JsonLike{{"value", av + bv}});
            if (op == "-") return Node("number", JsonLike{{"value", av - bv}});
            if (op == "*") return Node("number", JsonLike{{"value", av * bv}});
            if (op == "/") return Node("number", JsonLike{{"value", av / bv}});
            if (op == "<") return Node("bool", JsonLike{{"value", av < bv}});
            if (op == ">") return Node("bool", JsonLike{{"value", av > bv}});
            if (op == "<=") return Node("bool", JsonLike{{"value", av <= bv}});
            if (op == ">=") return Node("bool", JsonLike{{"value", av >= bv}});
            if (op == "==") return Node("bool", JsonLike{{"value", av == bv}});
            if (op == "!=") return Node("bool", JsonLike{{"value", av != bv}});        
        } if (a.type == "string" and b.type == "string") {
            std::string av = std::any_cast<std::string>(a.data.at("value"));
            std::string bv = std::any_cast<std::string>(b.data.at("value"));
            if (op == "+") return Node("number", JsonLike{{"value", av + bv}});
            if (op == "==") return Node("bool", JsonLike{{"value", av == bv}});
            if (op == "!=") return Node("bool", JsonLike{{"value", av != bv}});        
        } if (a.type == "string" and b.type == "number") {
            std::string av = std::any_cast<std::string>(a.data.at("value"));

            int bv;
            if (b.data.at("value").type() == typeid(int)) {
                bv = std::any_cast<int>(b.data.at("value"));
            } else if (b.data.at("value").type() == typeid(bool)) {bv = (int)(std::any_cast<bool>(b.data.at("value")));} 
            else {throw std::runtime_error("Invalid Binop of Op: +, a: string, b: number. b of type number cant be a float in context");}

            std::string out;
            for (int i = 0; i != bv; i++) {out += av;}
            if (op == "*") return Node("string", JsonLike{{"value", out}});
        } if (a.type == "list" and op == "+") {std::any_cast<Nodes>(a.data.at("items")).push_back(b); return a;}
        if (a.type == "list" and op == "-" and (b.type == "number" or b.type == "bool")) {
            int bv;
            if (b.data.at("value").type() == typeid(int)) {
                bv = std::any_cast<int>(b.data.at("value"));
            } else if (b.data.at("value").type() == typeid(bool)) {bv = (int)(std::any_cast<bool>(b.data.at("value")));} 
            else {throw std::runtime_error("Invalid Binop of Op: +, a: string, b: number. b of type number cant be a float in context");}

            std::any_cast<Nodes>(a.data.at("items")).erase(std::any_cast<Nodes>(a.data.at("items")).begin() + bv); return a;   
        }
    }
    if (node.type == "call") {
        Node funcnode = std::any_cast<Node>(node.data.at("func"));
        std::vector<Node> args = std::any_cast<std::vector<Node>>(node.data.at("args"));
        std::vector<Node> evaled_args;
        for (auto& a : args) evaled_args.push_back(eval_expr(a, env));

        if (funcnode.type == "prop") {
            Node obj = eval_expr(std::any_cast<Node>(funcnode.data.at("object")), env);
            std::string name = std::any_cast<std::string>(funcnode.data.at("name"));
            Node fn_node = get_prop(obj, name);
            if (fn_node.type != "function") throw std::runtime_error("Attempt to call non-function property");
            Function fn = std::any_cast<Function>(fn_node.data.at("value"));
            evaled_args.insert(evaled_args.begin(), obj);
            return fn(evaled_args);
        }

        Node fn_node = eval_expr(funcnode, env);
        if (fn_node.type != "function") throw std::runtime_error("Attempt to call non-function");
        Function fn = std::any_cast<Function>(fn_node.data.at("value"));
        return fn(evaled_args);
    }
    if (node.type == "index") {
        Node obj = eval_expr(std::any_cast<Node>(node.data.at("object")), env);
        Node idx = eval_expr(std::any_cast<Node>(node.data.at("index")), env);
        return get_indexed(obj, idx);
    }
    if (node.type == "prop") {
        Node obj = eval_expr(std::any_cast<Node>(node.data.at("object")), env);
        std::string name = std::any_cast<std::string>(node.data.at("name"));
        return get_prop(obj, name);
    }
    return Node("null", JsonLike{});
}

void exec_stmt(Node& node, Env* env) {
    std::string t = node.type;
    if (t == "assign") {
        Node& target = std::any_cast<Node&>(node.data["target"]);
        auto [getter, setter] = as_lvalue(target, env);
        Node value = eval_expr(std::any_cast<Node>(node.data["expr"]), env);
        setter(value);
        return;
    }
    if (t == "exprstmt") {
        eval_expr(std::any_cast<Node>(node.data["expr"]), env);
        return;
    }
    if (t == "return") {
        Node val = eval_expr(std::any_cast<Node>(node.data["expr"]), env);
        throw ReturnSignal(std::any_cast<int>(val.data.at("value")));
    }
    if (t == "def") {
        std::string fname = std::any_cast<std::string>(node.data["name"]);
        auto params = std::any_cast<Strings>(node.data["params"]);
        auto body = std::any_cast<Nodes>(node.data["body"]);
        Function fn(fname, params, body, env);
        env->set_here(fname, Node("function", JsonLike{{"value", fn}}));
        return;
    }
    if (t == "methoddef") {
        Node obj = env->get(std::any_cast<std::string>(node.data["obj"]));
        std::string name = std::any_cast<std::string>(node.data["name2"]);
        Function fn(name, std::any_cast<std::vector<std::string>>(node.data["params"]),
                    std::any_cast<Nodes>(node.data["body"]), env);
        set_prop(obj, name, Node("function", JsonLike{{"value", fn}}));
        return;
    }
    if (t == "while") {
        while (is_truthy(eval_expr(std::any_cast<Node>(node.data["cond"]), env))) {
            exec_block(std::any_cast<Nodes>(node.data["body"]), new Env(env));
        }
        return;
    }
    if (t == "if") {
        if (is_truthy(eval_expr(std::any_cast<Node>(node.data["cond"]), env))) {
            exec_block(std::any_cast<Nodes>(node.data["body"]), new Env(env));
        }
        return;
    }
    if (t == "for_in") {
        Node iterable = eval_expr(std::any_cast<Node>(node.data.at("iter")), env);
        Nodes list = std::any_cast<Nodes>(iterable.data.at("items"));
        std::string varname = std::any_cast<std::string>(
            std::any_cast<Node>(node.data.at("var")).data.at("value")
        );
        for (Node v : list) {
            env->set(varname, v);
            exec_block(std::any_cast<Nodes>(node.data.at("body")), new Env(env));
        }
        return;
    }
    if (t == "for_c") {
        Node initNode = std::any_cast<Node>(node.data["init"]);
        exec_stmt(initNode, env);
        while (is_truthy(eval_expr(std::any_cast<Node>(node.data["cond"]), env))) {
            exec_block(std::any_cast<Nodes>(node.data["body"]), new Env(env));
            Node stepNode = std::any_cast<Node>(node.data["step"]);
            exec_stmt(stepNode, env);
        }
        return;
    }
    if (t == "import") {
        std::string fileName = this->eval_expr(std::any_cast<Node>(node.data["fileName"]), env);
        std::unordered_map<std::string, std::string> files = std::any_cast<auto>(env.get("__importables__"));
        if (files.count(fileName) < 0) {
            throw std::runtime_error("Module '" + fileName + "' does not exist in current env");
        }
        Env runEnv run(files[fileName], basicEnv(files))
        Node lib = std::any_cast<Node>(runEnv.get("module"))
        size_t pos = s.rfind('.');  // find last '.'
        std::string lastPart;

        if (pos != std::string::npos) {
            lastPart = s.substr(pos + 1);  // get substring after last '.'
        } else {
            lastPart = s;  // no '.' found, take whole string
        }
        
        env.set(lastPart, lib);
    }

    if (t == "block") {
        exec_block(std::any_cast<Nodes>(node.data["stmts"]), env);
        return;
    }
}

const std::unordered_map<std::string, Node> PREBUILTS {
    {"null", Node("null", JsonLike{})}
};

typedef std::vector<std::array<Node, 2ULL>> ROSDICT;
typedef std::array<Node, 2ULL> ROSDICTITEM;

typedef Nodes ROSLIST;
typedef Node ROSLISTITEM;

std::string ROSnode_toS(Node n) {
    if (n.type == "string") {
        return std::any_cast<std::string>(n.data.at("value"));
    } if (n.type == "number") {
        if (n.data.at("value").type() == typeid(int)) {
            return std::to_string(std::any_cast<int>(n.data.at("value")));
        } else if (n.data.at("value").type() == typeid(float)) {
            return std::to_string(std::any_cast<float>(n.data.at("value")));
        }
    } if (n.type == "function") {
        return n.repr();
    } if (n.type == "dict") {
        std::string out = "{";
        for (ROSDICTITEM node : std::any_cast<ROSDICT>(n.data.at("items"))) {
            out += ROSnode_toS(node[0]) + ": " + ROSnode_toS(node[1]) + ", ";
        }
        out.erase(out.size() - 2, 2);
        out += "}";
        return out;
    } if (n.type == "list") {
        std::string out = "[";
        for (ROSLISTITEM node : std::any_cast<ROSLIST>(n.data.at("items"))) {
            out += ROSnode_toS(node) + ", ";
        }
        return out;
    }
    throw std::runtime_error("Cant convert ROS node " + n.repr() + " to a formated value string");
}


Node cpp_print(Nodes args, Env* env) {
    for (Node n : args) {
        std::cout << ROSnode_toS(n);
    } std::cout << std::endl;
    return PREBUILTS.at(("null"));
}

Env basicEnv(std::unordered_map<std::string, std::string> files) {
    Env env;

    const std::unordered_map<std::string, std::string> ROS = {{"ver", "BETA (ver2.1) c++"}}

    Function Print = Function("print", {}, {}, nullptr);
    Print.escapeToCpp = true;
    Print.cppfunc = cpp_print;

    env.set("print", Node("function", JsonLike{{"value", Print}}));
    env.set("__importables__", Node("dict", JsonLike{{"items", files}}));
    env.set("ROS", Node("dict", JsonLike{{"items", ROS}}))
    return env;
}

Env run(std::string code, Env env = basicEnv({})) {
    Tokens tokens = lex(code);
    Parcer p = Parcer(tokens);
    Node ast = p.parse();
    exec_stmt(ast, env);
    return Env
}


int main() {
    init();
    std::string code = R"(
def fib(n)
    a = 0
    b = 1
    for (_ = 0; _ != n; _ = _ + 1)
        c = a + b
        a = b
        b = c
        print(b)
    end
end

fib(100)

end)";

    auto start = std::chrono::high_resolution_clock::now();
    run(code);
    auto end = std::chrono::high_resolution_clock::now();

    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end - start);

    std::cout << "Time taken: " << duration.count() << std::endl;
}