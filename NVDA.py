import os
import ctypes

# Set the DLL path relative to current working directory
lib = "lib"
screen_reader_libs = "screen_reader_libs"
windows = "windows"
nvdaControllerClient64 = "nvdaControllerClient64.dll"

# Build the full path to the NVDA DLL
base_path = os.getcwd()
nvda_controller_path = os.path.join(base_path, lib, screen_reader_libs, windows, nvdaControllerClient64)

# Load the DLL using ctypes
nvda_controller = ctypes.WinDLL(nvda_controller_path)

# Define the nvdaController_speakText function
nvda_controller.nvdaController_speakText.argtypes = [ctypes.c_wchar_p]
nvda_controller.nvdaController_speakText.restype = ctypes.c_int

# Function to make NVDA speak
def nvda_speak(text):
    """Sends text to NVDA for speech output."""
    nvda_controller.nvdaController_speakText(text)

