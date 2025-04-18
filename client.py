import asyncio
import re
import traceback
from message_handler import MessageHandler

class AsyncClient:
    def __init__(self, host, port, uname, upass, uhome, log_callback, loop):
        self.host = host
        self.port = port
        self.uname = uname
        self.upass = upass
        self.uhome = uhome
        self.log_callback = lambda msg: log_callback(msg) if callable(log_callback) else None
        self.ui_callback = None
        self.loop = loop
        self.reader = None
        self.writer = None
        self.running = False
        self.delay = 5
        self.timeout = 5

        self.message_handler = MessageHandler(
            send_pong=self.send_pong,
            log_callback=lambda msg: self.log_callback(msg),
            ui_callback=self.ui_callback
        )

    async def connect(self):
        print("AsyncClient: Starting connect")
        self.running = True
        try:
            print(f"AsyncClient: Attempting connection to {self.host}:{self.port}")
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.timeout
            )
            print("AsyncClient: Connection established")
            self.log_callback(f"Connected to {self.host}:{self.port}")
            login_message = f"C1\r\nACCT {self.uname}\r\nPASS {self.upass}\r\nHOME {self.uhome}\r\nLOGIN\r\n"
            self.writer.write(login_message.encode('utf-8'))
            await self.writer.drain()
            print("AsyncClient: Login sequence sent")
            await self.receive_data()
        except ConnectionRefusedError as e:
            self.log_callback(f"Connection refused: {e}")
            await self.cleanup()
        except asyncio.TimeoutError as e:
            self.log_callback(f"Connection timed out: {e}")
            await self.cleanup()
        except Exception as e:
            self.log_callback(f"Connection error: {e}")
            await self.cleanup()

    async def reconnect(self):
        self.log_callback(f"Attempting to reconnect in {self.delay} seconds...")
        await asyncio.sleep(self.delay)
        if self.running:
            await self.connect()

    async def receive_data(self):
        buffer = ""
        while self.running:
            try:
                data = await self.reader.read(1024)
                if not data:
                    break
                buffer += data.decode('utf-8')
                buffer = await self.message_handler.process_buffer(buffer)
            except Exception as e:
                print(f"Receive error: {e}\n{traceback.format_exc()}")
                break
        await self.cleanup()

    async def send_pong(self, ping_id):
        pong_response = f"/PONG {ping_id}\r\n"
        self.writer.write(pong_response.encode('utf-8'))
        await self.writer.drain()

    async def send_command(self, command):
        if self.writer and self.running:
            try:
                self.writer.write(f"{command}\r\n".encode('utf-8'))
                await self.writer.drain()
            except Exception as e:
                print(f"Send error: {e}")

    async def cleanup(self):
        print("AsyncClient: Cleaning up")
        if self.writer:
            self.writer.close()
        self.reader = None
        self.writer = None
        self.log_callback("Connection closed")
        self.channel_users = []
        self.message_handler.channel_users = []
        self.message_handler.current_channel = None
        if self.ui_callback is not None:
            self.ui_callback(self.message_handler.channel_users)
        if self.running:
            await self.reconnect()

    def start(self):
        print("AsyncClient: Scheduling connect")
        asyncio.run_coroutine_threadsafe(self.connect(), self.loop)

    def stop(self):
        print("AsyncClient: Stopping")
        self.running = False

    def send(self, command):
        if self.running:
            print(f"AsyncClient: Scheduling send: {command}")
            asyncio.run_coroutine_threadsafe(self.send_command(command), self.loop)

    def set_ui_callback(self, ui_callback):
        if not callable(ui_callback):
            raise ValueError("ui_callback must be callable")
        self.ui_callback = ui_callback
        self.message_handler.ui_callback = ui_callback
