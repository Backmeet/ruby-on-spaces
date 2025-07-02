var new projX 0
var new projY 0
var new rotX 0
var new rotY 0
var new rotZ 0

# Rotation angles for the cube (in degrees)
var new angleX 0
var new angleY 0
var new angleZ 0

# Quit flag for the window loop
var new windowQuit 0

def rotatePoint 3
    # args: arg1 = x, arg2 = y, arg3 = z (original point coordinates)
    # Convert rotation angles from degrees to radians
    var math angleX * 0.0174533 = ax
    var math angleY * 0.0174533 = ay
    var math angleZ * 0.0174533 = az

    # Declare intermediate variables for sin and cos calculations
    var new cosax 0
    var new sinax 0
    var new cosay 0
    var new sinay 0
    var new cosaz 0
    var new sinaz 0

    # Compute sin and cos for ax
    var math ax cos = cosax
    var math ax sin = sinax

    # Rotate around X axis:
    var math arg2 * cosax = tempY1
    var math arg3 * sinax = tempY2
    var math tempY1 - tempY2 = newY
    var math arg2 * sinax = tempZ1
    var math arg3 * cosax = tempZ2
    var math tempZ1 + tempZ2 = newZ

    # Compute sin and cos for ay
    var math ay cos = cosay
    var math ay sin = sinay

    # Rotate around Y axis:
    var math arg1 * cosay = newX_part
    var math newZ * sinay = newX_part2
    var math newX_part + newX_part2 = newX
    var math 0 - arg1 = negX
    var math negX * sinay = newZ_part
    var math newZ * cosay = newZ_part2
    var math newZ_part + newZ_part2 = newZ2

    # Compute sin and cos for az
    var math az cos = cosaz
    var math az sin = sinaz

    # Rotate around Z axis:
    var math newX * cosaz = finalX_part
    var math newY * sinaz = finalX_part2
    var math finalX_part - finalX_part2 = finalX
    var math newX * sinaz = finalY_part
    var math newY * cosaz = finalY_part2
    var math finalY_part + finalY_part2 = finalY

    var set rotX = finalX
    var set rotY = finalY
    var set rotZ = newZ2
    return rotX
endfunc

def project 3
    # args: arg1 = x, arg2 = y, arg3 = z (rotated coordinates)
    # Simple perspective projection: factor = 200 / z (assumes z > 0)
    var math 200 / arg3 = factor
    var math arg1 * factor = screenX
    var math arg2 * factor = screenY
    # Offset to center the projection on an 800x600 window
    var math screenX + 400 = screenX
    var math screenY + 300 = screenY
    var set projX = screenX
    var set projY = screenY
    return projX
endfunc

def 3dLine 6
    # args: arg1=x1, arg2=y1, arg3=z1, arg4=x2, arg5=y2, arg6=z2
    # Process first vertex: rotate then project
    call rotatePoint arg1 arg2 arg3
    call project rotX rotY rotZ
    var new p1x projX
    var new p1y projY

    # Process second vertex: rotate then project
    call rotatePoint arg4 arg5 arg6
    call project rotX rotY rotZ
    var new p2x projX
    var new p2y projY

    # Draw the 2D line (white, thickness 1)
    window draw line p1x p1y p2x p2y 255 255 255 1
    return 0
endfunc

# Cube vertices (original coordinates)
var new v0x -50
var new v0y -50
var new v0z 150

var new v1x 50
var new v1y -50
var new v1z 150

var new v2x 50
var new v2y 50
var new v2z 150

var new v3x -50
var new v3y 50
var new v3z 150

var new v4x -50
var new v4y -50
var new v4z 250

var new v5x 50
var new v5y -50
var new v5z 250

var new v6x 50
var new v6y 50
var new v6z 250

var new v7x -50
var new v7y 50
var new v7z 250

# Initialize the window
window init 800 600

while begin
    window fill 0 0 0

    # Draw bottom face of cube
    call 3dLine v0x v0y v0z v1x v1y v1z
    call 3dLine v1x v1y v1z v2x v2y v2z
    call 3dLine v2x v2y v2z v3x v3y v3z
    call 3dLine v3x v3y v3z v0x v0y v0z

    # Draw top face of cube
    call 3dLine v4x v4y v4z v5x v5y v5z
    call 3dLine v5x v5y v5z v6x v6y v6z
    call 3dLine v6x v6y v6z v7x v7y v7z
    call 3dLine v7x v7y v7z v4x v4y v4z

    # Draw vertical edges connecting top and bottom
    call 3dLine v0x v0y v0z v4x v4y v4z
    call 3dLine v1x v1y v1z v5x v5y v5z
    call 3dLine v2x v2y v2z v6x v6y v6z
    call 3dLine v3x v3y v3z v7x v7y v7z

    # Update quit event flag
    window event quit windowQuit
    if begin windowQuit
        window quit
        end
    if end

    window flip

    # Increment rotation angles (wrap at 360 if desired)
    var math angleX + 1 = angleX
    var math angleY + 1 = angleY
    var math angleZ + 1 = angleZ

while end 1

end
