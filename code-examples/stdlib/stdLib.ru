// Sequences_Section <S> <start> <end> -> <S>[start:end]
// Time_GetUnixTime                    -> seconds sinces 12:00 ... as a int
// Time_GetLocalTime                   -> string "date:month:year day hr:min:sec:milisecond"
// System_Username                     -> string Username
// System_LastBootTime                 -> string 
// Math_Clamp <x> <min> <max>          -> <value>
// Math_Floor <x>                      -> <value>
// Math_Ceil <x>                       -> <value>
// Math_Mod <a> <b>                    -> <value>

def Sequences_Section 3
    var currentIndex = arg2
    var return = ""
    var math arg3 - 1 = endIndex
    while begin
        var math arg1 index currentIndex = chr
        var math return + chr = return

        var math currentIndex != endIndex = continue
        var math currentIndex + 1 = currentIndex
    while end continue
    return return
endfunc

def Time_GetUnixTime 0
    system 'powershell -Command "[int](Get-Date -UFormat %s)"'
    var time = 0
    var math return not = return
    if begin return
        convert _stdout time
        return time      
    if end
    return 0
endfunc

def Time_GetLocalTime 0
    system 'powershell -Command "Get-Date -Format \"yyyy:MM:dd:dddd:HH:mm:ss:fff\""'
    var time = 0
    var math return not = return
    if begin return
        return _stdout
    if end
    return 0
endfunc

def System_Username 0
    system 'powershell -Command "$env:USERNAME"'
    var time = 0
    var math return not = return
    if begin return
        return _stdout
    if end
    return 0
endfunc

def System_LastBootTime 0
    system 'powershell -Command "((Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalSeconds"'
    var time = 0
    var math return not = return
    if begin return
        return _stdout
    if end
    return 0
endfunc

def Math_Clamp 3
    var math arg1 < arg2 = minCheck
    if begin minCheck
        return arg2
    if end

    var math arg1 > arg3 = maxCheck
    if begin maxCheck
        return arg3
    if end

    return arg1
endfunc

def Math_Floor 1
    var math arg1 // 1 = floorVal
    return floorVal
endfunc

def Math_Ceil 1
    var math arg1 // 1 = floorVal
    var math floorVal != arg1 = isFloat
    if begin isFloat
        var math floorVal + 1 = ceilVal
        return ceilVal
    if end
    return floorVal
endfunc

def Math_Mod 2
    var math arg1 // arg2 = div
    var math div * arg2 = mult
    var math arg1 - mult = mod
    return mod
endfunc

def String_Find 2
    var main = arg1
    var sub = arg2
    var i = 0
    var j = 0
    var found = 0
    var math 0 - 1 = negOne

    call String_Length main
    var mainLen = return

    call String_Length sub
    var subLen = return

    var start_index = negOne
    var end_index = negOne

    while begin
        var math i <= mainLen = notEnd
        if begin notEnd
            var math subLen + i - 1 = subEnd
            var math subEnd >= mainLen = exceeds
            if begin exceeds
                return 0
            if end

            var j = 0
            var match = 1
            while begin
                var math j < subLen = loop
                if begin loop
                    var math main index i + j = chr1
                    var math sub index j = chr2
                    var math chr1 != chr2 = diff
                    if begin diff
                        var match = 0
                        break
                    if end
                    var math j + 1 = j
                if end
            while end loop

            if begin match
                var start_index = i
                var math i + subLen - 1 = end_index
                return 1
            if end

            var math i + 1 = i
        if end
    while end notEnd

    return 0
endfunc


export functions Time_GetUnixTime Sequences_Section Time_GetLocalTime System_Username System_LastBootTime Math_Clamp Math_Floor Math_Ceil Math_Mod
