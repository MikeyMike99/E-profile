print("Hello world!")
print("Hello, python!")
print("hello! Michael.")
print("The itsy bitsy spider climbed up the waterspout.")
print("Down came the rain and washed the spider out.")
print("The itsy bitsy spider climbed up the waterspout.")
print()
print("Down came the rain and washed the spider out.")
print("The itsy bitsy spider\nclimbed up the waterspout.")
print()
print("Down came the rain\nand washed the spider out.")
print("\\")
# ==========================================
# 1. EXAMPLES FROM THE LESSON (Keyword Args)
# ==========================================

# Using end=" " to keep the next print on the same line
print("My name is", "Python.", end=" ")
print("Monty Python.")

# Using an empty string for end=""
print("My name is ", end="")
print("Monty Python.")

# Using sep="-" to replace spaces with dashes
print("My", "name", "is", "Monty", "Python.", sep="-")

# Combining both sep and end
print("My", "name", "is", sep="_", end="*")
print("Monty", "Python.", sep="*", end="*\n")


# ==========================================
# 2. EXAMPLES FROM THE SUMMARY SECTION
# ==========================================

print("Hello,", "world!")
print("H", "E", "L", "L", "O", sep="-")


# ==========================================
# 3. LAB CHALLENGE: THE STAR ARROW
# ==========================================

print("    *")
print("   * *")
print("  * *")
print(" * *")
print("*** ***")
print("  * *")
print("  * *")
print("  *****")


# ==========================================
# 4. QUIZ QUESTIONS & STRING EXPERIMENTS
# ==========================================

# Quiz Question 1
print("My\nname\nis\nBond.", end=" ")
print("James Bond.")

# Quiz Question 2 
# NOTE: This line will cause a SyntaxError if uncommented 
# because keyword arguments (sep) must come AFTER positional arguments.
# print(sep="&", "fish", "chips")

# Quiz Question 3 (Testing quotes and escape characters)
print('Greg\'s book.')
print("'Greg's book.'")
print('"Greg\'s book."')
print("Greg\'s book.")

# NOTE: This final line causes a SyntaxError because the single quote 
# inside the double quotes breaks the string structure.
# print('"Greg's book."')