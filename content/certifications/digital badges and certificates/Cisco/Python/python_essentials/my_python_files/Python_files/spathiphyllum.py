spat1 = input("Type a name of a plant:  ")
spat2 = str("spathiphyllum")
spat3 = str("Spathiphyllum")

if spat1 == spat2:
    print("No, go bigger, use capital letter!!!!!")
    
if spat1 != spat2:
    print("No, type: spathiphyllum or spathiphillum and not", spat1, end=":  ")
    input()
if spat1 == spat3:
    print("Yes, Spathiphyllum is the best plant ever!!!!!")