#bit_wise_or.py
#here we are practicing, how bionary values is working for read, write  and excecute
rd=4
w=2
x=1

user_premision=rd | w 




print(f"your premision value is: {user_premision}")
print(bin(user_premision))#converst values to bionary to save space inmemory


#lets add excecute to the use permistion.
user_premision |= x
print(f"your new premision value is: {user_premision}")