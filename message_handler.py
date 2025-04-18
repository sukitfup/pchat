import re
import time
import asyncio
from collections import namedtuple
from collections import deque

# User data structure
User = namedtuple("User", ["name", "flags", "ping", "stats"])

class MessageHandler:
    def __init__(self, send_pong, log_callback, ui_callback=None):
        self.channel_users = []
        self.current_channel = None
        self.send_pong = send_pong
        self.log_callback = log_callback
        self.ui_callback = ui_callback

        # Validate callbacks
        if not callable(log_callback):
            raise ValueError("log_callback must be callable")
        if not callable(send_pong):
            raise ValueError("send_pong must be callable")
        if ui_callback is not None and not callable(ui_callback):
            raise ValueError("ui_callback must be callable")

        # Batch processing for user messages
        self.user_message_queue = deque()
        self.batch_task = None
        self.batch_delay = 0.5
        self.last_join_msg = time.time()
        self.last_leave_msg = time.time()

        # Dispatch table for message types
        self.message_handlers = {
            "PING": self.handle_ping,
            "SERVER": {
                "INFO": self.handle_server_info,
                "TOPIC": self.handle_server_topic,
                "UPDATE": self.handle_server_update,
                "ERROR": self.handle_server_error,
                "BROADCAST": self.handle_server_broadcast
            },
            "CHANNEL": {
                "JOIN": self.handle_channel_join
            },
            "USER": {
                "IN": self.queue_user_message,
                "UPDATE": self.queue_user_message,
                "JOIN": self.queue_user_message,
                "LEAVE": self.queue_user_message,
                "TALK": self.handle_user_talk,
                "WHISPER": self.handle_user_whisper
            }
        }

    async def process_buffer(self, buffer):
        while '\r\n' in buffer:
            message, buffer = buffer.split('\r\n', 1)
            message = message.strip()
            if message:
                parts = re.split(r'\s', message)
                try:
                    await self.handle_message(parts)
                except Exception as e:
                    self.log_callback(f"Error in handle_message: {e}")
                    raise
        return buffer

    async def handle_message(self, parts):
        if not parts or parts[0] == "OK":
            return
        msg_type = parts[0]
        if not msg_type == "PING":
            print(' '.join(parts[0:]))
        handler = self.message_handlers.get(msg_type)
        if isinstance(handler, dict):
            submsg_type = parts[1] if len(parts) > 1 else ""
            subhandler = handler.get(submsg_type)
            if subhandler:
                await subhandler(parts)
            else:
                self.log_callback(f"Unknown submsg_type: {submsg_type} for msg_type: {msg_type}")
        elif handler:
            await handler(parts)
        else:
            self.log_callback(f"Unknown msg_type: {msg_type}")

    async def handle_ping(self, parts):
        if len(parts) >= 2:
            ping_id = parts[1]
            await self.send_pong(ping_id)

    async def handle_server_info(self, parts):
        info = ' '.join(parts[2:]).strip()
        if len(parts) > 6 and parts[5] == "Topic:":
            topic = ' '.join(parts[6:]).strip()
            self.log_callback(f"CHANNEL_TOPIC {topic}")
        else:
            self.log_callback(info)

    async def handle_server_topic(self, parts):
        topic = ' '.join(parts[2:]).strip()
        self.log_callback(topic)

    async def handle_server_update(self, parts):
        update = ' '.join(parts[2:]).strip()
        self.log_callback(update)

    async def handle_server_error(self, parts):
        error = ' '.join(parts[2:]).strip()
        self.log_callback(error)

    async def handle_server_broadcast(self, parts):
        broadcast = ' '.join(parts[2:]).strip()
        self.log_callback(broadcast)

    async def handle_channel_join(self, parts):
        self.channel_users = []
        self.current_channel = ' '.join(parts[2:]).strip()
        self.log_callback(f"CHANNEL_JOIN {self.current_channel}")

    async def queue_user_message(self, parts):
        """Queue user-related messages for batch processing."""
        self.user_message_queue.append(parts)
        if self.batch_task is None or self.batch_task.done():
            self.batch_task = asyncio.create_task(self.process_user_message_batch())

    async def process_user_message_batch(self):
        """Process queued user messages after a delay, preserving server order and logging in sequence."""
        await asyncio.sleep(self.batch_delay)
        users_to_add = []
        users_to_update = []
        users_to_remove = set()
        updated_usernames = set()

        while self.user_message_queue:
            parts = self.user_message_queue.popleft()
            msg_subtype = parts[1]

            if msg_subtype in ("IN", "JOIN", "UPDATE"):
                if len(parts) < 8:
                    continue
                flags = parts[4]
                ping = parts[5]
                username = parts[6]
                stats = parts[7]
                user = User(name=username, flags=flags, ping=ping, stats=stats)

                if msg_subtype == "UPDATE":
                    users_to_update.append(user)
                    updated_usernames.add(username)
                elif msg_subtype == "JOIN" and username not in updated_usernames:
                    # Only show join/leave if the last one was greater than x seconds ago
                    if time.time() - self.last_join_msg > 3:
                        self.log_callback(f"User join {username}")
                        self.last_join_msg = time.time()
                    users_to_add.append(user)
                elif msg_subtype == "IN" and username not in updated_usernames:
                    users_to_add.append(user)

            elif msg_subtype == "LEAVE":
                if len(parts) < 7:
                    continue
                username = parts[6]
                users_to_remove.add(username)
                # Only show join/leave if the last one was greater than x seconds ago
                if time.time() - self.last_leave_msg > 3:
                    self.log_callback(f"User leave {username}")
                    self.last_leave_msg = time.time()

        # Remove users
        self.channel_users = [u for u in self.channel_users if u.name not in users_to_remove]

        # Update existing users
        for user in users_to_update:
            for i, existing_user in enumerate(self.channel_users):
                if existing_user.name == user.name:
                    self.channel_users[i] = user
                    break

        # Add new users to end
        for user in users_to_add:
            if user.name not in [u.name for u in self.channel_users]:
                self.channel_users.append(user)

        # Update UI once with the final user list
        if self.ui_callback is not None and (users_to_add or users_to_remove or users_to_update):
            self.ui_callback(self.channel_users)

    async def handle_user_talk(self, parts):
        if len(parts) < 7:
            return
        username = parts[6]
        msg = ' '.join(parts[7:])
        self.log_callback(f"{username}: {msg}")

    async def handle_user_whisper(self, parts):
        if len(parts) < 7:
            return
        username = parts[6]
        msg = ' '.join(parts[7:])
        self.log_callback(f"{username}: {msg}")