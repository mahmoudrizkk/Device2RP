import customtkinter as ctk
import threading
import time

cancel_flag = False  # Global flag to stop the task

def show_loading_popup(parent, text="Please wait..."):
    popup = ctk.CTkToplevel(parent)
    popup.title("Loading")
    popup.geometry("320x140")
    popup.resizable(False, False)
    popup.grab_set()  # Make popup modal

    # Center popup
    window_width = 320
    window_height = 140
    screen_width = popup.winfo_screenwidth()
    screen_height = popup.winfo_screenheight()
    x = int((screen_width / 2) - (window_width / 2))
    y = int((screen_height / 2) - (window_height / 2))
    popup.geometry(f"{window_width}x{window_height}+{x}+{y}")

    # Label
    label = ctk.CTkLabel(popup, text=text, font=("Arial", 16))
    label.pack(pady=(15, 10))

    # Loading circle (indeterminate progress bar)
    progress = ctk.CTkProgressBar(popup, mode="indeterminate", width=200)
    progress.pack(pady=5)
    progress.start()

    # Cancel Button
    def cancel_action():
        global cancel_flag
        cancel_flag = True
        popup.destroy()

    cancel_btn = ctk.CTkButton(popup, text="Cancel", command=cancel_action)
    cancel_btn.pack(pady=10)

    return popup


# Example usage
def long_task():
    global cancel_flag
    for i in range(10):  # Simulate 10 steps
        if cancel_flag:
            print("Task cancelled by user.")
            return
        time.sleep(0.5)  # Simulate work
    print("Task completed.")
    loading_popup.destroy()  # Close popup when done


if __name__ == "__main__":
    ctk.set_appearance_mode("light")  # or "dark"
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.geometry("400x300")

    def start_task():
        global loading_popup, cancel_flag
        cancel_flag = False
        loading_popup = show_loading_popup(root, "Please wait...")
        threading.Thread(target=long_task, daemon=True).start()

    button = ctk.CTkButton(root, text="Start Task", command=start_task)
    button.pack(pady=50)

    root.mainloop()
