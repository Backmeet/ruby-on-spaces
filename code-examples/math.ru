var new a 0
var new b 0
var new op 0
var new result 0
var new temp 0

print "use cmd like + - * // ** cbrt sqrt for math!"

while begin
    input "cmd>" op

    var math op == "exit" = temp
    if begin temp
        print "Exiting Program"
        end
    if end
    var math op == "+" = temp
    if begin temp
        input "a?>" a
        input "b?>" b
        convert a a
        convert b b
        var math a + b = result
    if end
    var math op == "-" = temp
    if begin temp 
        input "a?>" a
        input "b?>" b
        convert a a
        convert b b
        var math a - b = result
    if end
    var math op == "*" = temp
    if begin temp
        input "a?>" a
        input "b?>" b
        convert a a
        convert b b
        var math a * b = result
    if end
    var math op == "//" = temp        
    if begin temp 
        input "a?>" a
        input "b?>" b
        convert a a
        convert b b
        var math a // b = result
    if end
    var math op == "**" = temp        
    if begin temp 
        input "a?>" a
        input "b?>" b
        convert a a
        convert b b
        var math a ** b = result
    if end
    var math op == "sqrt" = temp        
    if begin temp
        input "a?>" a
        convert a a
        var math a sqrt = result
    if end
    var math op == "cbrt" = temp        
    if begin temp
        input "a?>" a
        convert a a
        var math a cbrt = result
    if end
    print "Result:" result
    print " "
while end 1
