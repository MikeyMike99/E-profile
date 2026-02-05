import os
import json

def LOGG(LOGG):
    """
    Logs the given text to a JSON file in the 'logs' directory.
    """
    try:
        # Ensure the 'logs' directory exists
        if not os.path.exists("logs"):
            os.makedirs("logs")

        # Define the file path
        file_path = os.path.join("logs", "log.json")

        # Load existing log data or initialize a new list
        data = []
        if os.path.exists(file_path):
            with open(file_path, 'r') as json_file:
                data = json.load(json_file)

        # Append the provided text to the log
        data.append(LOGG)

        # Save the updated log back to the file
        with open(file_path, 'w') as json_file:
            json.dump(data, json_file, indent=4)
    except Exception as e:
        print("")


LOGG("server IS STARTING!")