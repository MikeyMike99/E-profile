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

#  The user is prompted for a number
guess_num = int(input("Please type your number:  "))

#  Setting a counter value
#  determins how many guesses a user can have
counter = 10

#  Here the loop starts
while counter != 0:
    if guess_num != secret_number:
        print("Sorry, Hansie maybe next time")
        counter -= 1
        guess_num = int(input("Please type your number:  "))
        if counter == 0:
            print("You ran out of chances, you loose")
        
        
    if guess_num == secret_number:
        print("Great job you are the best!!!")
def        break
        
    
        


        
    
