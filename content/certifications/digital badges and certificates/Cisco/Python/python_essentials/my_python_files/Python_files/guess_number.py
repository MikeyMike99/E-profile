secret_number = 777

print(
"""
+================================+
| Welcome to my game, muggle!    |
| Enter an integer number        |
| and guess what number I've     |
| picked for you.                |
| So, what is the secret number? |
+================================+
""")


chance=2
num=None
while chance:
        chance -= 1
        
        if chance >=1:
            int(input(f"What is your lucky number?"))
        if num == secret_number:
            print(f"You bet it is my secret lucky number, You won!")
            chance=0
        elif chance>= 1 :

            message=f"No, No! I think your chances is running out!, What is your lucky number? "
            if chance <1:
                mesage=f"whoops! Your last chance!, better get it it right this time."
            num=int(input(f"{message}you have {chance} chances, left!"))

if not chance:
    print(f"better luck next time!")