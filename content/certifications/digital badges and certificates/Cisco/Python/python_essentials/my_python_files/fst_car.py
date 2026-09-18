var_1= input("Type the name of a the fastest car:  ")
var_2= str("Farari")
var_3= str("   Bogatti")

if var_1== var_2:
    print("No! I think", var_3, "is the fastest, Do you agree?!!!!!")
    
if var_1!= var_3:
    print("You bet it is ! NOT!")
    input(f"try again! {var_3} is the fastest!")
if var_1== var_3:
    print("Yippy! yeah! Yeah!", var_3)
else:
        input(f"Whoops you made a typo!{var_3} is the fastest!")