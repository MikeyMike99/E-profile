# Prompt the user to enter a word
user_word = input("Enter a word: ")

# Convert the word to uppercase
user_word = user_word.upper()

# Loop through each character in the word
for letter in user_word:
    # Check if the letter is a vowel
    if letter == "A":
        continue
    elif letter == "E":
        continue
    elif letter == "I":
        continue
    elif letter == "O":
        continue
    elif letter == "U":
        continue
    else:
        # Print the uneaten letter
        print(letter)
