weather=None
if not weather:
    check_weather=True
elif weather:
    weather=check_weather_now()
elif weather == "resturant":
    get_lunch=True
else:
    go_home=True
    {}