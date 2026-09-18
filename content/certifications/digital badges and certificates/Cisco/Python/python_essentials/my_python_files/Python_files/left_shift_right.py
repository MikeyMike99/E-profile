#shifting bionary bits.
var=16
for var in range(16):
    var_right= var >> 1
    var_left= var << 1


pirnt(var, var_left, var_right)