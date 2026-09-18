vouls=["a", "e", "i", "o", "u"]
word=input("type your word here.")
new_word=""
for i in word:
    if i in vouls:
        continue
    else:
        new_word += i



print(f"you created a new word, well done! : {new_word}")