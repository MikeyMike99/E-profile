name=''
last_name =''
if not name:
    name = input(f'please input your name here!')
    print(name)

if not last_name:
    input(f'Please enter you last name here!')
    print(last_name)

if name and last_name:
    print('your first name is', name, 'your last name is ', last_name)