window init 900 600

var new playerx 400
var new playery 300

var new xv 0
var new yv 0

var new winQuit 0
var new temp 0
var new can_jump 1

var new keydown ""
var new keyup ""

var new ground 300

def drawPlayer 0
    var new x1 0
    var new y1 0

    var math playery - 80 = y1
    var math playerx + 50 = x1

    window draw rect x1 y1 playerx playery 255 255 255
    return 0
endfunc

while begin
    window fill 0 0 0

    call drawPlayer
    window flip

    # Gravity
    var math playery < ground = temp
    if begin temp
        var math yv + 0.5 = yv
    if end


    window update
    window event keydown keydown
    window event keyup keyup
    print "keydown: " keydown
    print "keyup: " keyup
    print "xv: " xv "yv: " yv

    # Horizontal movement
    var math keydown == "a" = temp
    if begin temp
        var math xv - 0.5 = xv
    if end

    var math keydown == "d" = temp
    if begin temp
        var math xv + 0.5 = xv
    if end

    # Jumping
    var math keydown == "w" = temp
    if begin temp
        if begin can_jump
            var set -8 = yv
            var set 0 = can_jump
        if end
    if end

    var math keydown == " " = temp
    if begin temp
        if begin can_jump
            var set -8 = yv
            var set 0 = can_jump
        if end
    if end

    # Apply velocity
    var math playerx + xv = playerx
    var math playery + yv = playery

    # Ground collision
    var math playery >= ground = temp
    if begin temp
        var set ground = playery
        var set yv = 0 
        var set can_jump = 1 
    if end

    
    window event quit winQuit
    var math winQuit not = winQuit
while end winQuit

window quit

input " " temp

end
