from pyrogram import Client
import time
from datetime import datetime, timezone
import pdb
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Read values from environment
api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")
phone_number = os.getenv("PHONE_NUMBER")
bot_username = "deezload2bot"

class PlaylistSession:
    def __init__(self, playlist_url):
        self.playlist_url = playlist_url  # Spotify playlist URL
        self.total_tracks = None  # Number of tracks expected (set from bot's response)
        self.downloaded_songs = []  # List of downloaded song objects
        self.get_all_clicked = False  # Whether "GET ALL" button was clicked

    def set_total_tracks(self, total_tracks):
        """Set the total number of tracks once bot responds."""
        self.total_tracks = total_tracks

    def add_downloaded_song(self, file_name):
        """Track each downloaded song."""
        self.downloaded_songs.append(file_name)

    def all_songs_downloaded(self):
        """Check if all expected tracks have been downloaded."""
        return self.total_tracks is not None and len(self.downloaded_songs) >= self.total_tracks

    def __repr__(self):
        return f"PlaylistSession(playlist_url={self.playlist_url}, total_tracks={self.total_tracks}, downloaded={len(self.downloaded_songs)})"



# Initialize the client with phone number or bot token
app = Client(
    "my_account",
    api_id=api_id,
    api_hash=api_hash,
    phone_number=phone_number,  # For personal accounts
    # bot_token=bot_token,  # Uncomment if using a bot
)

def wait_for_response(bot_username, session_start_time, is_button, text, max_wait):
    start_time = time.time()
    while time.time() - start_time < max_wait:
        messages = list(app.get_chat_history(bot_username, limit=10))
        for msg in messages:
            # Only consider messages after the session start time
            if msg.date.timestamp() > session_start_time: #and msg.reply_markup
                if is_button:
                    # Check if the message contains the desired button
                    for row in msg.reply_markup.inline_keyboard:
                        for button in row:
                            if button.text == text:
                                print(f"Found button: {button.text}")
                                return msg, button.callback_data
                elif text in msg.text:
                        return msg, True
            else: # Messages in order so stop looking
                break
        time.sleep(0.5)  # Poll every 0.5 seconds
    return None, None

def click_button(bot_username, message_id, callback_data):
    """Click a button using the callback data."""
    app.request_callback_answer(bot_username, message_id, callback_data)
    print(f"Clicked button for message_id: {message_id}")

def send_playlist_and_download(bot_username, playlist_url):
    # Record session start time
    session_start_time = datetime.now(timezone.utc).timestamp()  # Use timezone-aware datetime
    PlaylistSesh = PlaylistSession(playlist_url)
    # Send Playlist Link
    sent_message = app.send_message(bot_username, playlist_url)
    print(f"Sent message to {bot_username}: {playlist_url}")

    # Wait for "GET ALL" Button Response
    playlist_response, callback_data = wait_for_response(
        bot_username, session_start_time, True, "GET ALL ⬇️", 15
    )
    if not playlist_response:
        print("No response with 'GET ALL' button found.")
        return None

    # Click the "GET ALL" button
    click_button(bot_username, playlist_response.id, callback_data)
    PlaylistSesh.get_all_clicked = True
    # Wait for the bot to send downloadable files
    time.sleep(2)  # Allow time for the bot to send files
    msg, msg_found = wait_for_response(
        bot_username, session_start_time, False, "Finished", 60
        )
    if not msg_found:
        print("Download Never Finished, Check Telegram Bot to See What the Issue is")
        return None
    messages = list(app.get_chat_history(bot_username, limit=10))
    
    pdb.set_trace()
    for msg in messages:
        # Only process messages after session start time
        if msg.date.timestamp() > session_start_time and msg.document:
            file_path = app.download_media(msg.document)
            print(f"Downloaded file: {file_path}")
    print("All files downloaded.")

# Replace with the Spotify playlist URL
playlist_url = "https://open.spotify.com/playlist/4qpwfpvpuFm0KPigXsErjD?si=1241eb653e004447"

if __name__ == "__main__":
    with app:  # Start the client once and reuse it
        # playlist_url = input("Input the URL of the Spotify Playlist You Wish To Download Songs From")
        send_playlist_and_download(bot_username, playlist_url)