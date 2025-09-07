local ROSL = require("./ROSL")
env = ROSL.BasicEnv({
test = [[
module = {}

def module.hi()
    print("hi")
end

end]]}
)

ROSL.run(
    [[
import "test"
test.hi()
end]], env
)