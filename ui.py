#ui.py
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

class BotUI:
    def __init__(self, root, client):
        self.root = root
        self.root.title(f"{client.uname} | {client.host}")
        
        # Dark theme and window setup
        self.root.geometry("1024x768")
        self.root.minsize(800, 600)
        self.root.configure(bg="#1C2526")

        # Use the provided client instance
        self.client = client
        self.client.ui_callback = self.update_user_list

        # Load icons for oper, tahc, and px2d
        self.icons = {}
        icon_keys = ["OPER", "TAHC", "PX2D"]
        for key in icon_keys:
            path = f"icons/{key}.png"
            try:
                self.icons[key] = ImageTk.PhotoImage(Image.open(path).resize((32, 16)))
            except FileNotFoundError:
                print(f"Icon file '{path}' not found; using no icon for {key}")
                self.icons[key] = None

        # Top frame for channel/topic labels
        top_frame = tk.Frame(self.root, bg="#1C2526")
        top_frame.pack(fill="x", pady=5)

        # Nested frame for centered labels
        label_frame = tk.Frame(top_frame, bg="#1C2526")
        label_frame.pack(anchor="center")

        # Channel and topic labels
        self.channel_label = tk.Label(
            label_frame,
            text="",
            font=("Courier", 12),
            bg="#1C2526",
            fg="#E0E0E0"
        )
        self.channel_label.pack(side="left", padx=10)

        self.topic_label = tk.Label(
            label_frame,
            text="",
            font=("Courier", 12),
            bg="#1C2526",
            fg="#E0E0E0"
        )
        self.topic_label.pack(side="left", padx=10)

        # Main frame to hold text and user list
        main_frame = tk.Frame(self.root, bg="#1C2526")
        main_frame.pack(pady=5, fill="both", expand=True)

        # Frame for Text widget
        text_frame = tk.Frame(main_frame, bg="#1C2526")
        text_frame.pack(side="left", pady=5, fill="both", expand=True)

        self.output_text = tk.Text(
            text_frame, 
            height=15, 
            font=("Courier", 11), 
            bg="#0F1419", 
            fg="#E0E0E0", 
            insertbackground="#FFFFFF", 
            padx=5,
            pady=5,
            bd=1, 
            relief="solid",
            wrap="word"
        )
        self.output_text.pack(side="left", fill="both", expand=True)

        text_scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.output_text.yview)
        text_scrollbar.pack(side="right", fill="y")
        self.output_text.config(yscrollcommand=text_scrollbar.set)

        # Frame for User List
        user_frame = tk.Frame(main_frame, bg="#1C2526", width=220)
        user_frame.pack(side="right", fill="y", padx=(5, 0))
        user_frame.pack_propagate(False)

        style = ttk.Style()
        style.configure(
            "Custom.Treeview",
            background="#0F1419",
            foreground="#E0E0E0",
            fieldbackground="#0F1419",
            font=("Courier", 11)
        )

        self.user_tree = ttk.Treeview(
            user_frame,
            columns=("Username",),
            show="tree",
            selectmode="browse",
            height=15,
            style="Custom.Treeview"
        )
        self.user_tree.pack(side="left", fill="both", expand=True)
        
        # Configure columns
        self.user_tree.column("#0", width=50, stretch=False)  # Icon column
        self.user_tree.column("Username", width=150, stretch=True)

        user_scrollbar = ttk.Scrollbar(user_frame, orient="vertical", command=self.user_tree.yview)
        user_scrollbar.pack(side="right", fill="y")
        self.user_tree.config(yscrollcommand=user_scrollbar.set)

        # Bind selection event
        self.user_tree.bind("<<TreeviewSelect>>", self.on_user_select)

        # Frame for Entry and Send button (inline)
        input_frame = tk.Frame(self.root, bg="#1C2526")
        input_frame.pack(pady=5, fill="x")

        self.input_entry = tk.Entry(
            input_frame,
            font=("Courier", 12), 
            bg="#2E2E2E", 
            fg="#FFFFFF", 
            insertbackground="#FFFFFF", 
            bd=1, 
            relief="solid"
        )
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.input_entry.bind("<Return>", lambda event: self.send_message())
        self.input_entry.focus_set()

        self.send_button = tk.Button(
            input_frame, 
            text="Send",
            command=self.send_message, 
            width=10, 
            height=1, 
            font=("Courier", 12), 
            bg="#2E2E2E", 
            fg="#FFFFFF", 
            activebackground="#3C3C3C", 
            bd=2, 
            relief="solid",
            pady=0
        )
        self.send_button.pack(side="left")
        self.send_button.config(state="disabled")

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def log(self, message):
        if message.startswith("CHANNEL_JOIN "):
            channel = message[len("CHANNEL_JOIN "):].strip()
            self.channel_label.config(text=f"Channel: {channel}")
            self.topic_label.config(text="")
            self.log(f"Joined {channel}")
        elif message.startswith("CHANNEL_TOPIC "):
            topic = message[len("CHANNEL_TOPIC "):].strip()
            self.topic_label.config(text=f"|  Topic: {topic}")
        else:
            self.output_text.insert(tk.END, message + "\n")
            self.output_text.see(tk.END)

    def update_user_list(self, users, is_leave=False, leaving_user=None):
        """Update the user list atomically, with operators at top and non-operators below, both in server order."""        
        # Handle leave event
        if is_leave and leaving_user:
            for item in self.user_tree.get_children():
                if self.user_tree.item(item, "values")[0] == leaving_user:
                    self.user_tree.delete(item)
                    break
            return

        # Build a map of new users
        new_users = {user.name: user for user in users}
        current_items = self.user_tree.get_children()
        current_users = {self.user_tree.item(item, "values")[0]: item for item in current_items}

        # Remove users no longer in the list
        for username, item in current_users.items():
            if username not in new_users:
                self.user_tree.delete(item)

        # Separate operators and non-operators, preserving server order
        operators = [user for user in users if user.flags == "18"]
        non_operators = [user for user in users if user.flags != "18"]

        # Combine lists: operators first, then non-operators, no sorting
        ordered_users = operators + non_operators

        # Add or update users in the combined order
        for index, user in enumerate(ordered_users):
            icon = self.icons.get("OPER") if user.flags == "18" else self.icons.get(user.stats, self.icons.get("TAHC"))
            if user.name not in current_users:
                # Insert new user at the specified index
                self.user_tree.insert(
                    "", index, text="",
                    image=icon,
                    values=(user.name,)
                )
            else:
                # Update icon and values for existing user
                self.user_tree.item(
                    current_users[user.name],
                    image=icon,
                    values=(user.name,)
                )
                # Move existing user to the correct position
                self.user_tree.move(current_users[user.name], "", index)

    def on_user_select(self, event):
        """Handle user selection in the Treeview."""
        selected_items = self.user_tree.selection()
        if selected_items:
            selected_username = self.user_tree.item(selected_items[0], "values")[0]
            for user in self.client.message_handler.channel_users:
                if user.name == selected_username:
                    self.output_text.see(tk.END)
                    break

    def check_running(self):
        if self.client.running:
            self.root.after(100, self.check_running)
        else:
            print("BotUI: Connection stopped")
            self.send_button.config(state="disabled")
            self.channel_label.config(text="")
            self.topic_label.config(text="")

    def send_message(self):
        command = self.input_entry.get().strip()
        if command:
            print(f"BotUI: Sending message: {command}")
            self.client.send(command)
            self.input_entry.delete(0, tk.END)

    def on_closing(self):
        print("BotUI: Closing window")
        self.client.stop()
        self.root.destroy()
