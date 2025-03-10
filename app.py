import asyncio
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from multiprocessing import Process
import websockets
from datetime import datetime
import json
import os
from jinja2 import Environment, FileSystemLoader

logging.basicConfig(level=logging.INFO)

DATA_FILE = "storage/data.json"

if not os.path.exists("storage"):
    os.makedirs("storage")


class HttpHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests and serves files."""

    def do_GET(self):
        """Handles GET requests and serves HTML or static files."""
        parsed_url = urlparse(self.path)
        if parsed_url.path == "/":
            self.send_html_file("templates/index.html")
        elif parsed_url.path == "/message.html":
            self.send_html_file("templates/message.html")
        elif parsed_url.path == "/read":
            self.display_messages()
        elif parsed_url.path == "/success.html":
            self.send_html_file("templates/success.html")
        elif parsed_url.path.startswith("/pic/"):
            self.send_static_file(parsed_url.path[1:])
        else:
            self.send_html_file("templates/error.html", 404)

    def do_POST(self):
        """Handles POST requests, saves messages, and redirects to a success page."""
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length)
        parsed_data = parse_qs(post_data.decode("utf-8"))
        username = parsed_data.get("username", [""])[0]
        message = parsed_data.get("message", [""])[0]

        if not username or not message:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid form data")
            return

        message_data = {
            "username": username,
            "message": message,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        }

        self.save_message_to_file(message_data)

        async def send_message_via_websocket():
            """Sends the message data to the WebSocket server."""
            uri = "ws://localhost:6000"
            async with websockets.connect(uri) as websocket:
                await websocket.send(json.dumps(message_data))

        asyncio.run(send_message_via_websocket())

        self.send_response(302)
        self.send_header("Location", "/success.html")
        self.end_headers()

    def send_html_file(self, filename, status=200):
        """Sends an HTML file as a response."""
        try:
            with open(filename, "rb") as file:
                self.send_response(status)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(file.read())
        except FileNotFoundError:
            self.send_html_file("/templates/error.html", 404)

    def send_static_file(self, filename, status=200):
        """Sends static files like CSS or images as a response."""
        try:
            with open(filename, "rb") as file:
                self.send_response(status)
                if filename.endswith(".css"):
                    self.send_header("Content-type", "text/css")
                elif filename.endswith(".png"):
                    self.send_header("Content-type", "image/png")
                self.end_headers()
                self.wfile.write(file.read())
        except FileNotFoundError:
            self.send_html_file("templates/error.html", 404)

    def save_message_to_file(self, message_data):
        """Saves a message to a JSON file with a timestamp as the key."""
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}

        data[message_data["timestamp"]] = {
            "username": message_data["username"],
            "message": message_data["message"],
        }

        with open(DATA_FILE, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)

    def display_messages(self):
        """Renders and displays saved messages on the read page."""
        env = Environment(loader=FileSystemLoader("templates"))
        template = env.get_template("read.html")

        try:
            with open(DATA_FILE, "r") as file:
                messages = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            messages = {}

        logging.info(f"Loaded {len(messages)} messages from {DATA_FILE}")

        html_content = template.render(messages=messages)

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html_content.encode("utf-8"))


class WebSocketServer:
    """Handles WebSocket connections for receiving messages."""

    async def ws_handler(self, websocket):
        """Processes WebSocket connections and logs received messages."""
        async for message in websocket:
            data = json.loads(message)
            logging.info(f"Received message: {data}")


async def run_websocket_server():
    """Starts the WebSocket server."""
    server = WebSocketServer()
    async with websockets.serve(server.ws_handler, "0.0.0.0", 6000):
        logging.info("WebSocket server is running on port 6000")
        await asyncio.Future()


def start_websocket_server():
    """Runs the WebSocket server in a separate process."""
    asyncio.run(run_websocket_server())


def run_http_server():
    """Starts the HTTP server for handling requests."""
    server_address = ("", 3000)
    httpd = HTTPServer(server_address, HttpHandler)
    logging.info("HTTP server is running on port 3000")
    httpd.serve_forever()


if __name__ == "__main__":
    """Runs both the HTTP and WebSocket servers in separate processes."""
    http_process = Process(target=run_http_server)
    ws_process = Process(target=start_websocket_server)

    http_process.start()
    ws_process.start()

    http_process.join()
    ws_process.join()
