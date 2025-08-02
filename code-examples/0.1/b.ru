window init 200 200
var new R 255
var new G 0
var new B 0
var new phase 0  // 0=R to G, 1=G to B, 2=B to R
var new inc 1

while begin
	window update

	var math phase == 0 = _
	if begin _
		var math G + inc = G
		var math R - inc = R
		var math G > 254 = _
		if begin _
			var set G = 255
			var set R = 0
			var set phase = 1
		if end
	if end

	var math phase == 1 = _
	if begin _
		var math B + inc = B
		var math G - inc = G
		var math B > 254 = _
		if begin _
			var set B = 255
			var set G = 0
			var set phase = 2
		if end
	if end

	var math phase == 2 = _
	if begin _
		var math R + inc = R
		var math B - inc = B
		var math R > 254 = _
		if begin _
			var set R = 255
			var set B = 0
			var set phase = 0
		if end
	if end

	window fill R G B
	window event quit _
	if begin _
		window quit
		end
	if end
	window flip
while end 1
