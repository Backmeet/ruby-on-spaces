from compiler import compile
open(r"E:\vs code\files\ruby-on-spaces\compiler\built\hello_world.c", "w").write(compile('''

print(123)
end
'''))
