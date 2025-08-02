# arg1:x arg2:y arg3:size
def drawSquar 3
    var new x1 0
    var new y1 0

    var math arg1 + arg3 = x1
    var math arg2 - arg3 = y1
    
    window draw rect arg1 arg2 x1 y1 255 255 255 
    return 0
endfunc

var new height 600
var new width 900

var new x 450
var new y 300

var new xv 0
var new yv 0

var new size 50

var new fuelLeft 100
var new fuelPower 0

var new drag 0.9
var new gravity 0.5

var new groundY height
var new grounded 0

var new temp 0
var new temp1 0
var new key ""
var new winQuit 0


window init width height
while begin
    window fill 0 0 0

    # event code
    window update
    window event key key

    var math key == "w" = temp
    var math key == " " = temp1
    var math temp1 or temp = temp
    var math temp and fuelLeft = temp
    if begin temp
        var math fuelLeft > 0 = temp1
        if begin temp1
            var math fuelLeft / 10 = fuelPower
            var math yv - fuelPower = yv
            var math fuelLeft - 1 = fuelLeft
        if end
    if end

    var math key == "a" = temp
    if begin temp
        var math xv - 1 = xv
    if end
    
    var math key == "d" = temp
    if begin temp
        var math xv + 1 = xv
    if end

    # apply gravity
    var math yv + gravity = yv

    # Apply drag
    var math xv > 0 = temp
    if begin temp
        var math xv - 0.5 = xv
    if end
    var math xv < 0 = temp
    if begin temp
        var math xv + 0.5 = xv
    if end

    # update position
    var math x + xv = x 
    var math y + yv = y 
    
    # ground collision
    var math height - size = temp
    var math y >= temp = grounded
    if begin grounded
        var set y = height
        var set yv = 0
        var set fuelLeft = 100
    if end
    
    flush xv " | " yv
    
    call drawSquar x y size

    window flip
    
    window event quit winQuit
    var math winQuit not = winQuit
while end winQuit
window quit
end