import ruby

ruby.run(ruby.Parser(ruby.lex('''
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
''')).parse(), ruby.make_global_env())




"""
env = ruby.make_global_env({
        "test": '''
module = {}

def module.hi()
    print("Hello from test module!")
end

end'''
    }
)
ruby.run(
    '''
    import "test"
    test.hi()
    end
    ''', env
)
"""