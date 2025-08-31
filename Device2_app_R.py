import customtkinter as ctk  # Import the CustomTkinter module for modern UI styling
from customtkinter import CTkImage  
from tkinter import messagebox  # Import messagebox for displaying alerts
import time  # Import time module for time-related functions
import os  # Import os module for handling file paths
import sys  # Import sys module for system-specific parameters and functions
from PIL import Image, ImageTk  # Import PIL for handling images
import serial  # Import serial module for communication with serial devices
import threading  # Import threading module for concurrent operations
import requests  # Import requests for API calls
import logging
import usb.core
import usb.util
import numpy as np
import re
import json

# Configure CustomTkinter appearance settings
custom_color = "#3AF4C5"  # Define a custom color
button_color = "#2EBFA5"  # Define a button color
ctk.set_appearance_mode("dark")  # Set appearance mode to match system theme
ctk.set_default_color_theme("green")  # Set the default color theme to green

# Create the main application window
app = ctk.CTk() # Create the main application window
app.title("UE")  # Set the window title
#app.attributes("-fullscreen", True)
app.geometry("1920x1020")  # Set a smaller default window size
# try:
#     app.state("zoomed")  # Maximize window on start (works on Windows)
# except Exception as e:
#     print(f"Window maximize not supported: {e}")

# Define password variables
password = "1234"  # Main password for authentication
entered_password = ""  # Stores user-entered main password
password_visible = False  # Flag to toggle password visibility

# List to store user actions
user_actions = []  # Tracks user authentication attempts
current_page = None # Current page

# Button names for main menu
button_names = ["Cutting", "Carcas", "Check"]

# Global variable to store the selected type
selected_type_global = "Unknown"

# Variable to control the running of the number update
update_running = False 
 
# Storing the current weight
weight_value = "0"  

# Today's slaughter count ID (fetched at startup)
count_id_today = None
# Placeholder for the API endpoint that returns today's countID
API_URL_TODAY_COUNT = "http://shatat-ue.runasp.net/api/Devices/GetTodayLastCountId"  # Set your GET endpoint here when available
# API_URL_TODAY_COUNT = "http://elmagzer.runasp.net/api/Devices/GetTodayLastCountId"  # Set your GET endpoint here when available

def get_count_id_for_request():
    """Return a safe integer countID for outgoing requests."""
    try:
        return int(count_id_today) if count_id_today is not None else 0
    except Exception:
        return 0

def extract_count_id_from_response(api_response):
    """
    Try to extract a countID integer from a response payload that may be
    JSON (dict) or text. Returns int or None.
    """
    # JSON-like structure
    try:
        if isinstance(api_response, dict):
            for key in ("lastCountId", "countId", "CountID", "CountId", "count"):
                if key in api_response:
                    try:
                        return int(api_response[key])
                    except Exception:
                        pass
            # Nested under data
            data = api_response.get("data") if "data" in api_response else None
            if isinstance(data, dict):
                for key in ("countID", "countId", "CountID", "CountId", "count"):
                    if key in data:
                        try:
                            return int(data[key])
                        except Exception:
                            pass
            # Some APIs return message with info inside
            msg = api_response.get("message") if "message" in api_response else None
            if isinstance(msg, str):
                m = re.search(r"countid\s*[:=]\s*(\d+)", msg, flags=re.I)
                if m:
                    return int(m.group(1))
    except Exception:
        pass

    # Plain string message
    if isinstance(api_response, str):
        m = re.search(r"countid\s*[:=]\s*(\d+)", api_response, flags=re.I)
        if m:
            return int(m.group(1))
    return None

# Loading the image and using it in all pages
image_path = r"/home/pi/Documents/logo.png"  # Replace with the correct file name

try:
    original_image = Image.open(image_path)
    resized_image = ctk.CTkImage(original_image, size=(100, 100))
    print("Image loaded successfully!")
except Exception as e:
    print(f"Error loading image: {e}")
    resized_image = None
    
# Fetch today's slaughter count ID from API (called at startup)
def fetch_today_count_id():
    global count_id_today
    if not API_URL_TODAY_COUNT:
        print("Startup countID fetch skipped: API_URL_TODAY_COUNT is not set.")
        return
    try:
        resp = requests.get(API_URL_TODAY_COUNT, timeout=10)
        resp.raise_for_status()

        # Try parsing as JSON first
        parsed_value = None
        try:
            data = resp.json()
            if isinstance(data, dict):
                # Common key name variations
                for key in ("lastCountId", "countId", "CountID", "CountId", "count", "value"):
                    if key in data:
                        parsed_value = data[key]
                        break
                # Try nested structures like { data: { countID: X } }
                if parsed_value is None and "data" in data and isinstance(data["data"], dict):
                    for key in ("countID", "countId", "CountID", "CountId"):
                        if key in data["data"]:
                            parsed_value = data["data"][key]
                            break
            elif isinstance(data, (int, float, str)):
                parsed_value = data
        except Exception:
            # Fallback: treat as plain text
            parsed_value = resp.text

        # Normalize to integer-like string if possible
        if isinstance(parsed_value, str):
            digits = re.findall(r"\d+", parsed_value)
            count_id_today = int(digits[0]) if digits else None
        elif isinstance(parsed_value, (int, float)):
            count_id_today = int(parsed_value) + 1
        else:
            count_id_today = 1

        print(f"Startup countID fetched: {count_id_today}")
    except Exception as e:
        print(f"Failed to fetch today's countID: {e}")
        count_id_today = 1


# Shut down function
def shutdown():
    os.system("sudo shutdown now")  # Execute system command to shut down the device immediately

# Read data from the serial port until an '=' character is encountered
def read_until_equal():
    ser = serial.Serial('/dev/serial0', baudrate=115200, timeout=1)

    # Ensure the serial connection is properly initialized and open
    if ser is None or not isinstance(ser, serial.Serial) or not ser.is_open:
        raise RuntimeError("Serial connection is not initialized or not open.")
    
    buffer = ""  # Initialize an empty buffer to store received data
    try:
        while True:
            if ser.in_waiting > 0:  # Check if there is data available in the buffer
                char = ser.read().decode('utf-8')  # Read one character and decode it
                buffer += char  # Append the character to the buffer

                if char == "=":  # Stop reading when '=' is encountered
                    return buffer.strip()  # Return the received string after stripping any extra spaces
    except Exception as e:
        print(f"Error while reading from UART: {e}")
        return None  # Return None in case of an error

# Function to read weight from external device
def weight():
    global weight_value
    try:
        while update_running:
            print("Waiting for data...")
            received_data = read_until_equal()
            print(f"Received data: {received_data}")

            if "," in received_data:
                parts = received_data.split(",")
                second_part = parts[1].strip("=").strip()
                weight_value = second_part
                print(f"Updated weight: {weight_value}")

            time.sleep(0.5)  # To reduce processor load
    except Exception as e:
        print(f"Error in weight(): {e}")

# Function to display and update weight continuously
def Calibration():
    global update_running, current_page
    current_page = Calibration
    update_running = True  

    # Clear the window
    for widget in app.winfo_children():
        widget.destroy()
        
    # Add a back button
    back_button(store_page)
        
    frame = ctk.CTkFrame(app)
    frame.pack(pady=30)

    if resized_image:
        logo_label = ctk.CTkLabel(frame, image=resized_image, text="")
        logo_label.grid(row=0, column=1, padx=20)

    text_label = ctk.CTkLabel(frame, text="Calibration", font=("Arial", 30))
    text_label.grid(row=0, column=0, padx=20)

    number_label = ctk.CTkLabel(app, text=weight_value, font=("Arial", 200, "bold"))
    number_label.pack(pady=20)

    def update_number():
        if update_running and number_label.winfo_exists():
            number_label.configure(text=str(read_weight_from_serial()))  
            app.after(500, update_number)  # تحديث الرقم كل 500 مللي ثانية

    update_number()  # بدء التحديث المستمر

    # تشغيل قراءة الوزن في خيط منفصل
    threading.Thread(target=weight, daemon=True).start()

# Function to switch the current page by clearing the existing UI and loading a new one
def show_page(page):
    """
    Switches the current page of the application to the specified page.
    """
    for widget in app.winfo_children():  
        widget.destroy()  # Remove each widget to clear the current page

    page()  # Call the function to display the new page

# Function to create a back button that navigates to a specified page
def back_button(page):
    def back():
        # Access global variables to modify them
        global entered_password, user_actions
        
        # Check if the current page is the password page
        if page == password_page:
            # Clear the entered password
            entered_password = ""
            # Clear all user actions
            user_actions.clear()
            # If the current page is the password page and the password entry widget exists, update the display
            if current_page == password_page and password_entry.winfo_exists():
                update_display()
                
        # Show the specified page after performing the above actions
        show_page(page)

    # Create a back button
    back_btn = ctk.CTkButton(
        app, text="←", command=back, 
        width=80, height=80,
        font=("Arial", 32),
        fg_color="transparent", text_color="#3AF4C5",
        border_width=5, border_color="#3AF4C5"
    )
    
    # Place the back button at the top-left corner of the window
    back_btn.place(x=20, y=20)

# Function to update password entry field
def update_display():
    if current_page == password_page and password_entry.winfo_exists():
        password_entry.configure(show="" if password_visible else "*")
        password_entry.delete(0, "end")
        password_entry.insert(0, entered_password)

# Function to handle numeric keypad button press
def on_keypad_press(num):
    global entered_password
    if current_page == password_page:
        entered_password += str(num)
        update_display()
        
# Function to remove the last entered digit
def clear_last():
    global entered_password
    if current_page == password_page:
        entered_password = entered_password[:-1]
        update_display()

# Function to clear all entered input
def clear_all():
    global entered_password
    if current_page == password_page:
        entered_password = ""
        update_display()
    elif current_page == logout_page:
        logout_password_entry.delete(0, "end")

# Function to toggle password visibility
def toggle_password_visibility():
    global password_visible
    password_visible = not password_visible

    if current_page == password_page:
        password_entry.configure(show="" if password_visible else "*")
        show_password_button.configure(text="🔒" if password_visible else "👁")
    elif current_page == logout_page:
        logout_password_entry.configure(show="" if password_visible else "*")
        show_logout_password_button.configure(text="🔒" if password_visible else "👁")

# Function to confirm password input
def confirm_password():
    global entered_password
    if entered_password == password:
        user_actions.append({"password": entered_password})
        show_page(main_menu)
    else:
        status_label.configure(text="Wrong Password!", text_color="red")
        entered_password = ""
        update_display()

# Function to display the password entry page
def password_page():
    global password_entry, show_password_button, status_label, current_page
    current_page = password_page
    
    # Create a frame that contains the image and text together
    frame = ctk.CTkFrame(app)
    frame.pack(pady=15)

    # Display the image on the right (if available)
    if resized_image:
        logo_label = ctk.CTkLabel(frame, image=resized_image, text="")  
        logo_label.grid(row=0, column=1, padx=20)

    # Add text on the left
    text_label = ctk.CTkLabel(frame, text="Enter Your Password", font=("Arial", 30))
    text_label.grid(row=0, column=0, padx=20)
    
    # Create a frame for the password entry and buttons
    password_frame = ctk.CTkFrame(app, fg_color="transparent")
    password_frame.pack(pady=20)
    
    # Create an entry widget for the password
    password_entry = ctk.CTkEntry(password_frame, width=300, height=80, font=("Arial", 50), show="*")
    password_entry.grid(row=0, column=0, padx=(0, 20))
    
    # Create a button to toggle password visibility
    show_password_button = ctk.CTkButton(password_frame, text="👁", command=toggle_password_visibility, width=80, height=80, font=("Arial", 50, "bold"))
    show_password_button.grid(row=0, column=1, padx=(0, 20))
    
    # Create a button to clear the password entry
    ctk.CTkButton(password_frame, text="X", command=clear_all, width=80, height=80, font=("Arial", 30, "bold"), fg_color="red", text_color="white").grid(row=0, column=2)
    
    # Create a keypad frame using grid for better layout
    keypad_frame = ctk.CTkFrame(app, fg_color="transparent")
    keypad_frame.pack(pady=10, expand=True, fill="both")
    
    # Define the keypad layout
    keypad_layout = [[7, 8, 9], [4, 5, 6], [1, 2, 3], ["Enter", 0, "⌫"]]
    
    # Create buttons for each keypad item using grid
    for row_idx, row in enumerate(keypad_layout):
        for col_idx, item in enumerate(row):
            if item == "Enter":
                btn = ctk.CTkButton(keypad_frame, text=str(item), command=confirm_password, width=120, height=120, font=("Arial", 40, "bold"), text_color="black")
            elif item == "⌫":
                btn = ctk.CTkButton(keypad_frame, text=str(item), command=clear_last, width=120, height=120, fg_color="red", font=("Arial", 50, "bold"))
            else:
                btn = ctk.CTkButton(keypad_frame, text=str(item), command=lambda num=item: on_keypad_press(num), width=120, height=120, font=("Arial", 60, "bold"), text_color="black")
            btn.grid(row=row_idx, column=col_idx, padx=10, pady=10, sticky="nsew")
    # Make the keypad grid cells expand
    for i in range(4):
        keypad_frame.rowconfigure(i, weight=1)
    for j in range(3):
        keypad_frame.columnconfigure(j, weight=1)
    
    # Create a label to display status messages
    status_label = ctk.CTkLabel(app, text="", font=("Arial", 24))
    status_label.pack(pady=30)

# Function to display the logout page
def logout_page():
    global logout_password_entry, show_logout_password_button, status_label, current_page
    current_page = logout_page

    # Clear the window
    for widget in app.winfo_children():
        widget.destroy()
        
    # Add a back button to return to the main menu
    back_button(main_menu)
    
    # Create a frame that contains the image and text together
    frame = ctk.CTkFrame(app)
    frame.pack(pady=30)

    # Display the image on the right (if available)
    if resized_image:
        logo_label = ctk.CTkLabel(frame, image=resized_image, text="")
        logo_label.grid(row=0, column=1, padx=20)

    # Add text on the left
    text_label = ctk.CTkLabel(frame, text="Enter Password to Logout", font=("Arial", 30))
    text_label.grid(row=0, column=0, padx=20)

    # Create a frame to hold the password entry and related buttons
    password_frame = ctk.CTkFrame(app, fg_color="transparent")
    password_frame.pack(pady=20)

    # Create an entry widget for the logout password
    logout_password_entry = ctk.CTkEntry(password_frame, width=300, height=80, font=("Arial", 50), show="*")
    logout_password_entry.grid(row=0, column=0, padx=(0, 20))

    # Create a button to toggle password visibility
    show_logout_password_button = ctk.CTkButton(password_frame, text="👁", command=toggle_password_visibility, width=80, height=80, font=("Arial", 50, "bold"))
    show_logout_password_button.grid(row=0, column=1, padx=(0, 20))

    # Create a button to clear all input in the password entry
    ctk.CTkButton(password_frame, text="X", command=clear_all, width=80, height=80, font=("Arial", 24), fg_color="red", text_color="white").grid(row=0, column=2)

    # Create a frame to hold the numeric keypad
    keypad_frame = ctk.CTkFrame(app, fg_color="transparent")
    keypad_frame.pack(pady=20)

    # Define the layout of the keypad
    keypad_layout = [[7, 8, 9], [4, 5, 6], [1, 2, 3], ["Enter", 0, "⌫"]]
    # Loop through the keypad layout to create buttons
    for row_idx, row in enumerate(keypad_layout):
        for col_idx, item in enumerate(row):
            if item == "Enter":
                # Create an "Enter" button to confirm logout
                btn = ctk.CTkButton(keypad_frame, text=str(item), command=confirm_logout, width=120, height=120, font=("Arial", 40, "bold"), text_color="black")
            elif item == "⌫":
                # Create a backspace button to delete the last character
                btn = ctk.CTkButton(keypad_frame, text=str(item), command=clear_last_logout, width=120, height=120, fg_color="red", font=("Arial", 50, "bold"))
            else:
                # Create a numeric button to input numbers
                btn = ctk.CTkButton(keypad_frame, text=str(item), command=lambda num=item: on_logout_keypad_press(num), width=120, height=120, font=("Arial", 60, "bold"), text_color="black")
            # Place the button in the grid
            btn.grid(row=row_idx, column=col_idx, padx=40, pady=20)

    # Create a label to display the status (e.g., incorrect password)
    status_label = ctk.CTkLabel(app, text="", font=("Arial", 24))
    status_label.pack(pady=30)

# Function to confirm the logout action
def confirm_logout():
    global entered_password, user_actions
    if logout_password_entry.get() == password:
        entered_password = ""
        user_actions.clear()
        shutdown()
    else:
        status_label.configure(text="Incorrect Password!", text_color="red")

# Function to handle numeric keypad button presses for logout
def on_logout_keypad_press(num):
    logout_password_entry.insert("end", str(num))

# Function to delete the last character in the logout password entry
def clear_last_logout():
    current_text = logout_password_entry.get()
    logout_password_entry.delete(0, "end")
    logout_password_entry.insert("end", current_text[:-1])

# ================================
# Function: main_menu
# ================================
def main_menu():
    """
    This function sets up the main menu interface of the application with 3 buttons.
    When a button is clicked, it shows a confirmation page.
    """
    global update_running  
    update_running = False
    
    user_actions.clear()
    user_actions.append({"password": entered_password})
    
    # Clear the window by destroying all existing widgets
    for widget in app.winfo_children():
        widget.destroy()
        
    # Add a back button
    back_button(password_page)
    
    # Create a main container frame
    main_container = ctk.CTkFrame(app)
    main_container.pack(padx=20, pady=20, fill="both", expand=True)
    
    # Create a header frame with logo and title
    header_frame = ctk.CTkFrame(main_container)
    header_frame.pack(pady=(0, 20), fill="x")
    
    # Add the logo if available
    if resized_image:
        logo_label = ctk.CTkLabel(header_frame, image=resized_image, text="")
        logo_label.pack(side="left", padx=20)

    # Add the title
    title_label = ctk.CTkLabel(header_frame, text="Main Menu", font=("Arial", 30, "bold"))
    title_label.pack(side="left", padx=20, pady=10)
    
    # Create a content frame for the buttons
    content_frame = ctk.CTkFrame(main_container)
    content_frame.pack(padx=10, pady=10, fill="both", expand=True)
    
    # Create 3 buttons with random names
    for i, name in enumerate(button_names):
        button = ctk.CTkButton(
            content_frame, 
            text=name,
            command=lambda n=name: show_page(lambda: show_confirmation(n)),
            font=("Arial", 55, "bold"),
            text_color="black",
            width=820,
            height=120,
            fg_color="#2EBFA5",
            corner_radius=10
        )
        button.pack(pady=30, padx=20, anchor="center")
    
    # Create a bottom-right controls frame for system buttons
    controls_frame = ctk.CTkFrame(app, fg_color="transparent")
    controls_frame.place(relx=1.0, rely=1.0, anchor="se", x=-20, y=-20)
    
    # Add Calibration button with consistent sizing
    calibration_btn = ctk.CTkButton(
        controls_frame, 
        text="Calibration",
        command=Calibration,
        font=("Arial", 26, "bold"), 
        fg_color="orange",
        text_color="black",
        width=180, 
        height=50
    )
    calibration_btn.pack(side="left", padx=10)
    
    # Add Shutdown button with consistent sizing
    logout_button = ctk.CTkButton(
        controls_frame, 
        text="Shut down",
        command=lambda: show_page(logout_page),
        font=("Arial", 26, "bold"),
        fg_color="red",
        width=180, 
        height=50
    )
    logout_button.pack(side="left", padx=10)

# Function to show confirmation page
def show_confirmation(selected_option):
    global selected_type_global
    # Clear the window
    for widget in app.winfo_children():
        widget.destroy()
        
    # Store the selected option in user actions
    user_actions.append({"selected_option": selected_option})
    
    # Set the global selected type
    selected_type_global = selected_option
        
    # Create a frame for confirmation
    confirm_frame = ctk.CTkFrame(app)
    confirm_frame.pack(expand=True, fill="both", padx=50, pady=50)
    
    # Show the selected option
    option_label = ctk.CTkLabel(
        confirm_frame, 
        text=f"You selected: {selected_option}", 
        font=("Arial", 40, "bold")
    )
    option_label.pack(pady=50)
    
    # Add confirmation message
    confirm_label = ctk.CTkLabel(
        confirm_frame, 
        text="Are you sure?", 
        font=("Arial", 30)
    )
    confirm_label.pack(pady=20)
    
    # Create a frame for Yes/No buttons
    buttons_frame = ctk.CTkFrame(confirm_frame, fg_color="transparent")
    buttons_frame.pack(pady=50)
    
    # Yes button - now goes to store_page instead of done_page
    yes_button = ctk.CTkButton(
        buttons_frame, 
        text="Yes",
        command=lambda: show_page(store_page),
        font=("Arial", 30, "bold"),
        text_color="black",
        width=200,
        height=80,
        fg_color="green"
    )
    yes_button.pack(side="left", padx=30)
    
    # No button
    no_button = ctk.CTkButton(
        buttons_frame, 
        text="No",
        command=lambda: show_page(main_menu),
        font=("Arial", 30, "bold"),
        text_color="black",
        width=200,
        height=80,
        fg_color="red"
    )
    no_button.pack(side="left", padx=30)

# Function to display the done page
def done_page():
    # Clear the window
    for widget in app.winfo_children():
        widget.destroy()
        
    # Create a frame
    done_frame = ctk.CTkFrame(app)
    done_frame.pack(expand=True, fill="both", padx=60, pady=60)
    
    # Show success message
    done_label = ctk.CTkLabel(
        done_frame, 
        text="Done!", 
        font=("Arial", 80, "bold"),
        text_color="green"
    )
    done_label.pack(pady=100)
    
    # Create a button to return to main menu
    back_to_menu = ctk.CTkButton(
        done_frame, 
        text="Back to Menu",
        command=lambda: show_page(main_menu),
        font=("Arial", 40, "bold"),
        text_color="black",
        width=300,
        height=100,
        fg_color="#2EBFA5"
    )
    back_to_menu.pack(pady=50)

# Function to display the store page
def store_page():
    # If there are more than one user actions, remove the last one
    if len(user_actions) > 1:
        user_actions.pop()
        
    # Clear the window
    for widget in app.winfo_children():
        widget.destroy()
        
    back_button(main_menu)
    
    # Create a frame that contains the image and text together
    frame = ctk.CTkFrame(app)
    frame.pack(pady=30)

    # Display the image on the right (if available)
    if resized_image:
        logo_label = ctk.CTkLabel(frame, image=resized_image, text="")
        logo_label.grid(row=0, column=1, padx=20)

    # Add text on the left
    text_label = ctk.CTkLabel(frame, text="Store Number", font=("Arial", 30))
    text_label.grid(row=0, column=0, padx=20)
    
    # Create a frame to hold the number buttons
    num_frame = ctk.CTkFrame(app)
    num_frame.pack(pady=30)
    
    # Loop to create buttons for numbers 1 to 13
    for i in range(13):
        # Create a button for each number, which will show confirmation page when clicked
        ctk.CTkButton(
            num_frame, 
            text=str(i+1), 
            command=lambda n=i+1: show_store_confirmation(n),
            font=("Arial", 60, "bold"), 
            text_color="black", 
            width=160, 
            height=160,
            fg_color="#2EBFA5"
        ).grid(row=i//5, column=i%5, padx=30, pady=20)

# Function to show store confirmation
def show_store_confirmation(store_number):
    # Clear the window
    for widget in app.winfo_children():
        widget.destroy()
        
    # Create a frame for confirmation
    confirm_frame = ctk.CTkFrame(app)
    confirm_frame.pack(expand=True, fill="both", padx=50, pady=50)
    
    # Show the selected store number
    option_label = ctk.CTkLabel(
        confirm_frame, 
        text=f"You selected Store: {store_number}", 
        font=("Arial", 40, "bold")
    )
    option_label.pack(pady=50)
    
    # Add confirmation message
    confirm_label = ctk.CTkLabel(
        confirm_frame, 
        text="Are you sure?", 
        font=("Arial", 30)
    )
    confirm_label.pack(pady=20)
    
    # Create a frame for Yes/No buttons
    buttons_frame = ctk.CTkFrame(confirm_frame, fg_color="transparent")
    buttons_frame.pack(pady=50)
    
    # Yes button
    yes_button = ctk.CTkButton(
        buttons_frame, 
        text="Yes",
        command=lambda: select_store(store_number),
        font=("Arial", 30, "bold"),
        text_color="black",
        width=200,
        height=80,
        fg_color="green"
    )
    yes_button.pack(side="left", padx=30)
    
    # No button
    no_button = ctk.CTkButton(
        buttons_frame, 
        text="No",
        command=lambda: show_page(store_page),
        font=("Arial", 30, "bold"),
        text_color="black",
        width=200,
        height=80,
        fg_color="red"
    )
    no_button.pack(side="left", padx=30)

data_Mapping = [
    {165: '-', 191: '0', 159: '0', 157: '1', 155: '2', 153: '3', 151: '4', 149: '5', 147: '6', 145: '7', 143: '8', 141: '9', 157: '1', 155: '2', 153: '3', 151: '4', 149: '5', 147: '6', 145: '7', 143: '8', 141: '9'},
    {165: '-', 191: '0', 159: '0', 224: '0', 160: '1', 219: '2', 203: '3', 187: '4', 171: '5', 155: '6', 139: '7', 123: '8', 107: '9', 157: '1', 155: '2', 153: '3', 151: '4', 149: '5', 147: '6', 145: '7', 143: '8', 141: '9'},
    {165: '-', 191: '0', 159: '0', 251: '0', 235: '1', 219: '2', 203: '3', 187: '4', 171: '5', 155: '2', 139: '7', 123: '8', 107: '9', 157: '1', 153: '3', 151: '4', 149: '5', 147: '6', 145: '7', 143: '8', 141: '9', 246: '1'},
    {165: '-', 191: '0', 159: '0', 251: '0', 235: '1', 219: '2', 203: '3', 187: '4', 171: '5', 155: '2', 139: '7', 123: '8', 107: '9', 157: '1', 155: '2', 153: '3', 151: '4', 149: '5', 147: '6', 145: '7', 143: '8', 141: '9'},
    {165: '-', 191: '0', 159: '0', 157: '1', 155: '2', 153: '3', 151: '4', 149: '5', 147: '6', 145: '7', 143: '8', 141: '9', 157: '1', 155: '2', 153: '3', 151: '4', 149: '5', 147: '6', 145: '7', 143: '8', 141: '9'},
    {163: '.'},
    {191: '0', 159: '0', 157: '1', 155: '2', 153: '3', 151: '4', 149: '5', 147: '6', 145: '7', 143: '8', 141: '9', 157: '1', 155: '2', 153: '3', 151: '4', 149: '5', 147: '6', 145: '7', 143: '8', 141: '9'},
    {191: '0', 159: '0', 157: '1', 155: '2', 153: '3', 151: '4', 149: '5', 147: '6', 145: '7', 143: '8', 141: '9', 157: '1', 155: '2', 153: '3', 151: '4', 149: '5', 147: '6', 145: '7', 143: '8', 141: '9'}
]

def read_weight_from_serial(com_port='/dev/serial0', baud_rate=9600):
    try:
        ser = serial.Serial(com_port, baud_rate, timeout=1)
        while True:
            if ser.in_waiting >= 18:
                frame = ser.read(18)
                frame_data_original = [byte for byte in frame]
                if frame_data_original[0] == 0:
                    frame_data_weight = [frame_data_original[6],frame_data_original[7],frame_data_original[8],frame_data_original[9],frame_data_original[10],frame_data_original[11],frame_data_original[12],frame_data_original[13]]
                    mapped_frame_data = [
                        data_Mapping[i].get(byte, byte) for i, byte in enumerate(frame_data_weight)
                    ]
                    weight_str = ''.join(str(x) for x in mapped_frame_data)
                    print(mapped_frame_data)
                    try:
                        current_weight = float(weight_str)
                        return str(current_weight)
                    except Exception as e:
                        print(f"Weight parse error: {e}")
                        return None
    except Exception as e:
        print(f"Serial error: {e}")
    return None

# Function to display a custom error page with refresh and back buttons
def display_error_message(message="Failed to connect to the server", refresh_callback=None):
    """
    Displays an error page with the error message, a Refresh button, and a Back button to store_page.
    Args:
        message (str): The error message to display.
        refresh_callback (function): The function to call when Refresh is pressed.
    """
    for widget in app.winfo_children():
        widget.destroy()

    # Back button (top left)
    back_button(store_page)

    # Error message
    ctk.CTkLabel(app, text=message, font=("Arial", 36), text_color="red").pack(pady=60)

    # Refresh button
    ctk.CTkButton(
        app,
        text="Refresh",
        command=refresh_callback if refresh_callback else store_page,
        font=("Arial", 60, "bold"),
        fg_color="blue",
        width=600,
        height=120
    ).pack(pady=30)

# import customtkinter as ctk
# import threading

# def display_error_message(message="Failed to connect to the server", refresh_callback=None):
#     """
#     Displays an error page with the error message, a Refresh button, and a Back button.
#     Shows a loading popup during the API call when Refresh is clicked.
#     Args:
#         message (str): The error message to display.
#         refresh_callback (function): The function to call when Refresh is pressed.
#     """
#     for widget in app.winfo_children():
#         widget.destroy()

#     # Back button (top left)
#     back_button(store_page)

#     # Error message
#     ctk.CTkLabel(app, text=message, font=("Arial", 36), text_color="red").pack(pady=60)

#     # Function to show loading popup
#     def show_loading_popup():
#         popup = ctk.CTkToplevel(app)
#         popup.title("Loading...")
#         popup.geometry("400x200")
#         popup.grab_set()  # Prevent interaction with main window
#         ctk.CTkLabel(popup, text="Loading, please wait...", font=("Arial", 24)).pack(expand=True, pady=40)
#         return popup

#     # Function to handle refresh
#     def handle_refresh():
#         popup = show_loading_popup()

#         def run_callback():
#             try:
#                 if refresh_callback:
#                     refresh_callback()
#                 else:
#                     store_page()
#             finally:
#                 popup.destroy()  # Close popup after API call

#         threading.Thread(target=run_callback).start()

#     # Refresh button
#     ctk.CTkButton(
#         app,
#         text="Refresh",
#         command=handle_refresh,
#         font=("Arial", 60, "bold"),
#         fg_color="blue",
#         width=600,
#         height=120
#     ).pack(pady=30)



def reprint():

    """
    Function to call the API and parse the returned message data into separate variables
    """
    try:
        # API endpoint
        api_url = "http://shatat-ue.runasp.net/api/Devices/GetLastPiece"
        
        # Make the API request
        response = requests.get(api_url)
        
        # Check if request was successful
        if response.status_code == 200:
            # Parse JSON response
            data = response.json()
            
            # Extract status code and message
            status_code = data.get("statusCode")
            full_message = data.get("message", "")
            
            print(f"API Status Code: {status_code}")
            print(f"Full Message: {full_message}")
            
            # Split the message by commas
            if full_message:
                # Remove the "OK1 " prefix if it exists
                if full_message.startswith("OK1 "):
                    message_data = full_message[4:]  # Remove "OK1 "
                else:
                    message_data = full_message
                
                # Split by comma
                parts = message_data.split(',')
                
                # Assign to meaningful variables (based on the sample data structure)
                QR_id = parts[0][1:] if len(parts) > 0 and parts[0].startswith("Z") else parts[0] if len(parts) > 0 else None
                field_1 = parts[1] if len(parts) > 1 else None  # appears to be null in sample
                market_name = parts[2] if len(parts) > 2 else None
                batch_number = parts[3] if len(parts) > 3 else None
                Order_number = parts[4] if len(parts) > 4 else None
                person_name = parts[5] if len(parts) > 5 else None
                body_part_str = parts[6] if len(parts) > 6 else None
                body_part = None
                if body_part_str:
                    match = re.search(r'\d+$', body_part_str)
                    if match:
                        body_part = match.group()
                weight = parts[7] if len(parts) > 7 else None
                date_info = parts[8].rstrip('L') if len(parts) > 8 else None
                
                # Print parsed data
                print("\n--- Parsed Data ---")
                print(f"QR ID: {QR_id}")
                print(f"Field 1: {field_1}")
                print(f"Market Name: {market_name}")
                print(f"Code Number: {batch_number}")
                print(f"Cut Reference: {Order_number}")
                print(f"Person Name: {person_name}")
                print(f"Body Part: {body_part}")
                print(f"Weight: {weight}")
                print(f"Date Info: {date_info}")
                
                
            else:
                print("No message data found in response")
                return None
                
        else:
            print(f"API request failed with status code: {response.status_code}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Error making API request: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None
    def crop_white_left(image):
        img_array = np.array(image)
        nonwhite = np.where(img_array == 0)
        if nonwhite[1].size:
            left = nonwhite[1].min()
            cropped = image.crop((left, 0, image.width, image.height))
            return cropped
        else:
            return image

    def load_and_prepare_image(path):
        image = Image.open(path).convert('1')
        image = crop_white_left(image)
        width, height = image.size
        if width % 8 != 0:
            padded_width = ((width + 7) // 8) * 8
            new_image = Image.new('1', (padded_width, height), 1)
            new_image.paste(image, (0, 0))
            image = new_image
            width = padded_width
        width_bytes = width // 8
        data = image.tobytes()
        return width_bytes, height, data

    def send_tspl_command(printer, command):
        if printer.is_kernel_driver_active(0):
            printer.detach_kernel_driver(0)
        printer.set_configuration()
        endpoint = printer[0][(0,0)][0]
        printer.write(endpoint.bEndpointAddress, command)
        print("Command sent successfully!")

    def send_multi_bmp_to_printer(printer, bmp_paths_and_coords, extra_text=None):
        command_prefix = (
            f"SIZE 50 mm, 40 mm\r\n"
            "GAP 2 mm, 0 mm\r\n"
            "DENSITY 10\r\n"
            "SPEED 6\r\n"
            "DIRECTION 1\r\n"
            "REFERENCE 0,0\r\n"
            "CLS\r\n"
        )

        # Add any extra text if provided
        if extra_text:
            command_prefix += extra_text

        command = command_prefix.encode('utf-8')

        for bmp_path, (x, y) in bmp_paths_and_coords:
            width_bytes, height, data = load_and_prepare_image(bmp_path)
            bmp_cmd = f"BITMAP {x},{y},{width_bytes},{height},0,".encode('utf-8')
            command += bmp_cmd + data

        print_cmd = b"\r\nPRINT 2\r\n"
        full_command = command + print_cmd
        send_tspl_command(printer, full_command)

    # Example parts list
    meat_parts = [
        "left shoulder",
        "left thigh",
        "right shoulder",
        "right thigh"
    ]

    # Build per selection
    def print_part_by_index(printer, index):
        if index < 1 or index > len(meat_parts):
            print("Out of range!")
            return
        part = meat_parts[index-1]
        # Add multi-image support here:
        bmp_jobs = [
            (f"{part}.bmp", (70, 205)),           # Main image
            # ...add more here if you need for this label
        ]
        # Any extra text?
        extra_text = (
            f'TEXT 0,0,"2",0,1,1,"{field_1}"\r\n'
            f'TEXT 0,30,"2",0,1,1,"{market_name}"\r\n'
            f'TEXT 0,60,"2",0,1,1,"order number:{Order_number}"\r\n'
            f'TEXT 0,90,"2",0,1,1,"batch number:{batch_number}"\r\n'
            f'TEXT 0,120,"2",0,1,1,"Date: {date_info}"\r\n'
            f'TEXT 0,150,"2",0,1,1,"weight:{weight}"\r\n'
            f'TEXT 0,180,"2",0,1,1,"type:{selected_type_global}"\r\n'
            f'TEXT 30,220,"2",0,1,1,"{body_part}"\r\n'
            f'QRCODE 260,120,L,7,A,0,"{QR_id}"\r\n'
            f'TEXT 280,280,"2",0,1,1,"{QR_id}"\r\n'
            
             )       
       
        send_multi_bmp_to_printer(printer, bmp_jobs, extra_text)

    printer = usb.core.find(idVendor=0x2D37, idProduct=0xDEF4)
    if printer:
        index = int(body_part)
        print_part_by_index(printer, index)
        printer.reset()  # Attempt a soft reset to clear any potential issues

    else:
        print("Printer not found.")
        
# Function to handle store selection
# ... existing code ...

def select_store(store_number):
    global selected_type_global
    # Get the selected type from the previous action
    selected_type = user_actions[-1].get("selected_option", button_names[0])
    
    # Update the global selected type
    selected_type_global = selected_type
    
    # Store the selected store number in user actions
    user_actions[-1]["store_number"] = store_number
    
    # Map selected type to numeric value for display
    type_mapping = {
        "Cutting": "1",
        "Carcas": "2",
        "Check": "3"
    }
    type_value = type_mapping.get(selected_type, "1")

    # Get a fresh weight from serial before sending to API
    fresh_weight = read_weight_from_serial()
    print(fresh_weight)
    if fresh_weight:
        weight_to_send = str(fresh_weight)
    else:
        weight_to_send = str(weight_value)  # fallback to last known value

    # Prepare API parameters
    def build_api_url(with_count_id):
        return (
            f"http://shatat-ue.runasp.net/api/Devices/ScanForDevice2?"
            f"weight={weight_to_send}&TypeOfCow={type_value}&TechId=2335C4B&MachId=1&storeId={store_number}&Countid={with_count_id}"
        )

    def do_request(url):
        try:
            response = requests.post(url, timeout=15)
            print(url)
            print(response.text)
            if response.headers.get('Content-Type', '').startswith('application/json'):
                payload = response.json()
            else:
                payload = {
                    "statusCode": response.status_code,
                    "message": response.text
                }
            return response, payload
        except Exception as e:
            print(f"API connection error: {e}")
            return None, None

    # Retry logic - keep trying until we get 200 OK
    retry_count = 0
    api_response = None
    response = None
    
    # Create and show loading popup
    loading_popup = ctk.CTkToplevel(app)
    loading_popup.title("Processing...")
    loading_popup.geometry("500x300")
    
    # Center the popup on screen
    loading_popup.update_idletasks()
    x = (loading_popup.winfo_screenwidth() // 2) - (500 // 2)
    y = (loading_popup.winfo_screenheight() // 2) - (300 // 2)
    loading_popup.geometry(f"500x300+{x}+{y}")
    
    # Simple loading content
    ctk.CTkLabel(loading_popup, text="Processing your request...", font=("Arial", 24, "bold")).pack(pady=30)
    ctk.CTkLabel(loading_popup, text="Please wait while we connect to the server", font=("Arial", 18)).pack(pady=10)
    
    # Add progress bar
    progress_bar = ctk.CTkProgressBar(loading_popup)
    progress_bar.pack(pady=20, padx=50, fill="x")
    progress_bar.set(0)
    
    # Add status label to show current step
    status_label = ctk.CTkLabel(loading_popup, text="Initializing...", font=("Arial", 14))
    status_label.pack(pady=10)
    
    # Update popup to show it
    loading_popup.update()
    
    # Initialize variables that will be used in printer functions
    message_list = []
    extracted_number = None
    
    try:
        while True:  # Infinite loop - keep trying until success
            current_count = get_count_id_for_request()
            api_url = build_api_url(current_count)
            
            print(f"Attempt {retry_count + 1}: Trying API call...")
            
            # Update progress and status
            progress = min(0.1 + (retry_count * 0.15), 0.9)
            progress_bar.set(progress)
            status_label.configure(text=f"Attempt {retry_count + 1}: Connecting to server...")
            loading_popup.update()
            
            response, api_response = do_request(api_url)
            
            if response is None:
                print(f"Attempt {retry_count + 1} failed: No response")
                retry_count += 1
                time.sleep(2)
                continue
                
            # Check if we got 200 OK
            if "statusCode" in api_response and api_response["statusCode"] == 200:
                print(f"Success! Got 200 OK on attempt {retry_count + 1}")
                progress_bar.set(1.0)
                status_label.configure(text="Success! Processing response...")
                loading_popup.update()
                break
            elif api_response.get("statusCode") == 400 and api_response.get("message") == "Update Count Id":
                print("CountID mismatch detected, updating and retrying...")
                status_label.configure(text="CountID mismatch detected, updating...")
                loading_popup.update()
                
                server_count = extract_count_id_from_response(api_response)
                if server_count is not None:
                    try:
                        server_count_int = int(server_count)
                        global count_id_today
                        count_id_today = server_count_int + 1
                        print(f"Updated local countID to: {count_id_today}")
                    except Exception:
                        pass
                retry_count += 1
                time.sleep(5)
                continue
            elif api_response.get("statusCode") == 404 and api_response.get("message") == "Resource was not found":
                status_label.configure(text="Resource not found, stopping...")
                loading_popup.update()
                break
            else:
                print(f"Attempt {retry_count + 1} failed: {api_response.get('message', 'Unknown error')}")
                status_label.configure(text=f"Attempt {retry_count + 1} failed, retrying...")
                loading_popup.update()
                retry_count += 1
                time.sleep(2)
                if retry_count < 5:
                    continue
                else:
                    status_label.configure(text="Max attempts reached, stopping...")
                    loading_popup.update()
                    break
            
        # Small delay to show completion
        time.sleep(0.5)
        loading_popup.destroy()

    except Exception as e:
        status_label.configure(text=f"Error: {str(e)}")
        loading_popup.update()
        time.sleep(2)
        loading_popup.destroy()
    finally:
        if loading_popup.winfo_exists():
            loading_popup.destroy()

    # Create data that would be sent to API (for display)
    data_to_send = {
        "type": selected_type_global,
        "type_value": type_value,
        "store": store_number,
        "weight": weight_to_send,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "attempts": retry_count + 1
    }

    print("Data being sent:")
    print(data_to_send)

    # Process API response message
    if "statusCode" in api_response and api_response["statusCode"] == 200:
        raw_message = api_response.get("message", "")

        if raw_message.startswith("OK1 "):
            raw_message = raw_message[4:]

        message_list = raw_message.split(",")
        print("Raw split message list:", message_list)

        # Remove 'Z' from the first element
        if len(message_list) > 0 and message_list[0].startswith("Z"):
            message_list[0] = message_list[0][1:]

        # Remove 'L' from the last element
        if len(message_list) > 0 and message_list[-1].endswith("L"):
            message_list[-1] = message_list[-1][:-1]

        # Extract number only from Arabic part if exists
        if len(message_list) > 6:
            arabic_text = message_list[6]
            match = re.search(r'\d+', arabic_text)
            if match:
                extracted_number = match.group(0)
                message_list[6] = extracted_number

        print("Processed message list:")
        print(message_list)

        if extracted_number:
            print("Extracted number from Arabic text:", extracted_number)
        
        # On success, increment local countID for next request
        try:
            if count_id_today is None:
                count_id_today = 0
            count_id_today = int(count_id_today) + 1
            print(f"Local countID incremented to: {count_id_today}")
        except Exception as _:
            pass
    elif api_response.get("statusCode") == 400 and api_response.get("message") == "Update Count Id":
        print("CountID is ahead of server")
        server_count = extract_count_id_from_response(api_response)
        if server_count is not None:
            try:
                server_count_int = int(server_count)
                if get_count_id_for_request() != server_count_int:
                    count_id_today = server_count_int + 1
                    retry_url = build_api_url(count_id_today)
                    response, api_response = do_request(retry_url)
                    if response is None:
                        display_error_message("Connection failed", refresh_callback=lambda: select_store(store_number))
                        return
                    if "statusCode" in api_response and api_response["statusCode"] == 200:
                        raw_message = api_response.get("message", "")
                        # Process the successful response
                        if raw_message.startswith("OK1 "):
                            raw_message = raw_message[4:]
                        message_list = raw_message.split(",")
                        # Remove 'Z' and 'L' as before
                        if len(message_list) > 0 and message_list[0].startswith("Z"):
                            message_list[0] = message_list[0][1:]
                        if len(message_list) > 0 and message_list[-1].endswith("L"):
                            message_list[-1] = message_list[-1][:-1]
                        if len(message_list) > 6:
                            arabic_text = message_list[6]
                            match = re.search(r'\d+', arabic_text)
                            if match:
                                extracted_number = match.group(0)
                                message_list[6] = extracted_number
                    else:
                        display_error_message(f"API error: {api_response.get('message', 'Unknown error')}", refresh_callback=lambda: select_store(store_number))
                        return
                else:
                    display_error_message(f"API error: {api_response.get('message', 'Unknown error')}", refresh_callback=lambda: select_store(store_number))
                    return
            except Exception:
                display_error_message(f"API error: {api_response.get('message', 'Unknown error')}", refresh_callback=lambda: select_store(store_number))
                return
        else:
            display_error_message(f"API error: {api_response.get('message', 'Unknown error')}", refresh_callback=lambda: select_store(store_number))
            return
    else:
        display_error_message(f"API error: {api_response.get('message', 'Unknown error')}", refresh_callback=lambda: select_store(store_number))
        return

    # Printer functions (moved outside and properly scoped)
    def crop_white_left(image):
        img_array = np.array(image)
        nonwhite = np.where(img_array == 0)
        if nonwhite[1].size:
            left = nonwhite[1].min()
            cropped = image.crop((left, 0, image.width, image.height))
            return cropped
        else:
            return image

    def load_and_prepare_image(path):
        image = Image.open(path).convert('1')
        image = crop_white_left(image)
        width, height = image.size
        if width % 8 != 0:
            padded_width = ((width + 7) // 8) * 8
            new_image = Image.new('1', (padded_width, height), 1)
            new_image.paste(image, (0, 0))
            image = new_image
            width = padded_width
        width_bytes = width // 8
        data = image.tobytes()
        return width_bytes, height, data

    def send_tspl_command(printer, command):
        if printer.is_kernel_driver_active(0):
            printer.detach_kernel_driver(0)
        printer.set_configuration()
        endpoint = printer[0][(0,0)][0]
        printer.write(endpoint.bEndpointAddress, command)
        print("Command sent successfully!")

    def send_multi_bmp_to_printer(printer, bmp_paths_and_coords, extra_text=None):
        command_prefix = (
            f"SIZE 50 mm, 40 mm\r\n"
            "GAP 2 mm, 0 mm\r\n"
            "DENSITY 10\r\n"
            "SPEED 6\r\n"
            "DIRECTION 1\r\n"
            "REFERENCE 0,0\r\n"
            "CLS\r\n"
        )

        if extra_text:
            command_prefix += extra_text

        command = command_prefix.encode('utf-8')

        for bmp_path, (x, y) in bmp_paths_and_coords:
            width_bytes, height, data = load_and_prepare_image(bmp_path)
            bmp_cmd = f"BITMAP {x},{y},{width_bytes},{height},0,".encode('utf-8')
            command += bmp_cmd + data

        print_cmd = b"\r\nPRINT 2\r\n"
        full_command = command + print_cmd
        send_tspl_command(printer, full_command)

    # Example parts list
    meat_parts = [
        "left shoulder",
        "left thigh", 
        "right shoulder",
        "right thigh"
    ]

    def print_part_by_index(printer, index):
        if index < 1 or index > len(meat_parts):
            print("Out of range!")
            return
        part = meat_parts[index-1]
        bmp_jobs = [
            (f"{part}.bmp", (70, 205)),
        ]
        
        # Use the properly scoped variables here - make sure message_list is available
        if len(message_list) >= 9:  # Ensure we have enough data
            extra_text = (
                f'TEXT 0,0,"2",0,1,1,"{message_list[1]}"\r\n'
                f'TEXT 0,30,"2",0,1,1,"{message_list[2]}"\r\n'
                f'TEXT 0,60,"2",0,1,1,"order number:{message_list[4]}"\r\n'
                f'TEXT 0,90,"2",0,1,1,"batch number:{message_list[3]}"\r\n'
                f'TEXT 0,120,"2",0,1,1,"Date: {message_list[8]}"\r\n'
                f'TEXT 0,150,"2",0,1,1,"weight:{message_list[7]}"\r\n'
                f'TEXT 0,180,"2",0,1,1,"type:{selected_type_global}"\r\n'  # Use the global variable
                f'TEXT 30,220,"2",0,1,1,"{message_list[6]}"\r\n'
                f'QRCODE 260,120,L,7,A,0,"{message_list[0]}"\r\n'
                f'TEXT 280,280,"2",0,1,1,"{message_list[0]}"\r\n'
            )
        else:
            # Fallback if message_list is incomplete
            extra_text = f'TEXT 0,180,"2",0,1,1,"type:{selected_type_global}"\r\n'
       
        send_multi_bmp_to_printer(printer, bmp_jobs, extra_text)

    # Only print if we have valid data and extracted number
    if extracted_number and message_list:
        printer = usb.core.find(idVendor=0x2D37, idProduct=0xDEF4)
        if printer:
            index = int(extracted_number)
            print_part_by_index(printer, index)
            printer.reset()
        else:
            print("Printer not found.")

    # Display confirmation message
    for widget in app.winfo_children():
        widget.destroy()
        
    back_button(store_page)
    
    # Create a frame that contains the image and text
    frame = ctk.CTkFrame(app)
    frame.pack(pady=30)

    if resized_image:
        logo_label = ctk.CTkLabel(frame, image=resized_image, text="")
        logo_label.grid(row=0, column=1, padx=20)

    # Add confirmation text with both type and store - use the updated global variable
    text_label = ctk.CTkLabel(frame, text=f"Type: {selected_type_global} (Value: {type_value})\nSelected Store: {store_number}", font=("Arial", 40))
    text_label.grid(row=0, column=0, padx=30)
    
    if response and response.status_code == 200:
        response_text = "Data sent to API!"
        response_color = custom_color
    else:
        response_text = "Failed to send data!"
        response_color = "red"

    # Add success message
    ctk.CTkLabel(
        app,
        text=response_text,
        font=("Arial", 60),
        text_color=response_color
    ).pack(pady=50)
    
    # Display the data and response in the UI
    data_frame = ctk.CTkFrame(app)
    data_frame.pack(pady=20)
    
    ctk.CTkLabel(
        data_frame,
        text="Data Sent:",
        font=("Arial", 20, "bold"),
    ).pack(anchor="w", padx=20, pady=(10, 0))
    
    data_text = "\n".join([f"{k}: {v}" for k, v in data_to_send.items()])
    ctk.CTkLabel(
        data_frame,
        text=data_text,
        font=("Arial", 28),
        justify="left"
    ).pack(anchor="w", padx=20)
    
    if api_response:
        ctk.CTkLabel(
            data_frame,
            text="API Response:",
            font=("Arial", 20, "bold"),
        ).pack(anchor="w", padx=20, pady=(10, 0))
        
        response_text = "\n".join([f"{k}: {v}" for k, v in api_response.items()])
        ctk.CTkLabel(
            data_frame,
            text=response_text,
            font=("Arial", 20),
            justify="left"
        ).pack(anchor="w", padx=20)
    
    # Button to return to store selection
    ctk.CTkButton(
        app,
        text="Back to Store Selection",
        command=lambda: show_page(store_page),
        font=("Arial", 45, "bold"),
        text_color="black",
        width=500,
        height=75,
        fg_color=button_color
    ).pack(pady=25)
    
    # Updated reprint function to use current scope variables
    def reprint_current():
        if extracted_number and message_list:
            printer = usb.core.find(idVendor=0x2D37, idProduct=0xDEF4)
            if printer:
                index = int(extracted_number)
                print_part_by_index(printer, index)
                printer.reset()
            else:
                print("Printer not found.")
        else:
            print("No valid data to reprint")
    
    ctk.CTkButton(
        app,
        text="Reprint",
        command=reprint_current,  # Use the local function
        font=("Arial", 45, "bold"),
        text_color="black",
        width=500,
        height=75,
        fg_color="red"
    ).pack(pady=30)
    
    # Button to logout
    ctk.CTkButton(
        app,
        text="Shut Down",
        command=lambda: show_page(logout_page),
        font=("Arial", 45, "bold"),
        text_color="black",
        width=500,
        height=75,
        fg_color="red"
    ).pack(pady=20)

# Start the app by fetching today's countID, then showing the password page
fetch_today_count_id()
print(count_id_today)
show_page(password_page)
app.mainloop()  # Run the app's main event loop

#you selected store