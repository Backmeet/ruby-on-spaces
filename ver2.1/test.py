import ruby

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