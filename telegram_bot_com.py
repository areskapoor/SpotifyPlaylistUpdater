from pyrogram import Client
import time
from datetime import datetime, timezone
import pdb
import os
from dotenv import load_dotenv
import re

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
        self.playlist_name = "Unknown Playlist"
        self.total_tracks = None  # Number of tracks expected (set from bot's response)
        self.downloaded_songs = {}  # Dict of file names to file ids #TODO: decide if better to use dict or ordered data structure like a list
        self.get_all_clicked = False  # Whether "GET ALL" button was clicked

    def set_playlist_name(self, playlist_name):
        self.playlist_name = playlist_name    
        
    def set_total_tracks(self, total_tracks):
        """Set the total number of tracks once bot responds."""
        self.total_tracks = total_tracks

    def add_downloaded_song(self, file_name, metadata):
        """Track each downloaded song."""
        self.downloaded_songs[file_name] = metadata

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


def extract_download_progress(msg):
    match = re.search(r"Track (\d+) of (\d+)", msg.text)
    if match:
        current_track = int(match.group(1))  # Extracts "1"
        total_tracks = int(match.group(2))   # Extracts "35"
        return current_track, total_tracks
    return None, None  # Return None if pattern not found


def find_total_tracks(msg):
    match = re.search(r"Total tracks:\s*(\d+)", msg.text)
    return int(match.group(1)) if match else None    


def download_songs(bot_username, session_start_time, PlaylistSesh: PlaylistSession):
    total_tracks = PlaylistSesh.total_tracks
    messages = list(app.get_chat_history(bot_username, 
                                         limit=PlaylistSesh.total_tracks + 5))
    for msg in messages:
        if (msg.date.timestamp() < session_start_time or 
            PlaylistSesh.all_songs_downloaded()):
            break
        if msg.audio:
            artist = msg.audio.performer or "Unknown Artist"
            title = msg.audio.title or "Unknown Title"
            metadata = {
                "title": title,
                "artist": artist,
                "file_id": msg.audio.file_id
                        }
            safe_playlist_name = "".join(c if c.isalnum() or c in " _-" 
                                         else "_" for c in PlaylistSesh.playlist_name)
            download_dir = os.path.join("downloads", safe_playlist_name)
            os.makedirs(download_dir, exist_ok=True)

            # Generate clean file name
            safe_file_name = f"{artist} - {title}.mp3"
            safe_file_name = "".join(c if c.isalnum() or c in " _-()" else "_" for c in safe_file_name)
            PlaylistSesh.add_downloaded_song(safe_file_name, metadata)
            
            # Set the full path
            file_path = os.path.join(download_dir, safe_file_name)

            # Download the file
            downloaded_path = app.download_media(msg.audio.file_id, file_name=file_path)
            print(f"Downloaded {msg.audio.file_name} to {downloaded_path}")
            
    if PlaylistSesh.all_songs_downloaded():
        print("Finished Downloading All Songs")
        return True

    print(f"""Failure to Download All Songs. Downloaded 
            {len(PlaylistSesh.downloaded_songs)} / {total_tracks}""")
    return False
            
            
def wait_for_response(bot_username, session_start_time, is_button, text, max_wait):
    start_time = time.time()
    while time.time() - start_time < max_wait:
        messages = list(app.get_chat_history(bot_username, limit=10))
        for msg in messages:
            # Only consider messages after the session start time
            if msg.date.timestamp() < session_start_time:
                break
            # print(f"Looking at message with text: {msg.text}")
            if is_button and msg.reply_markup:
                # Check if the message contains the desired button
                for row in msg.reply_markup.inline_keyboard:
                    for button in row:
                        if button.text == text:
                            print(f"Found button: {button.text}")
                            return msg, button.callback_data
            else:
                # if msg.text and "💿 Track" in msg.text:
                #     downloading, total = extract_download_progress(msg)
                #     if downloading != None and total != None:
                #         print(f"""Waiting for {bot_username} to download song
                #               {downloading} / {total}""") 
                if msg.text and text in msg.text:
                    return msg, True
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

    total_tracks = find_total_tracks(playlist_response)
    if playlist_response.web_page:
        PlaylistSesh.set_playlist_name(playlist_response.web_page.title)
    else:
        print("Could Not Find Playlist Title, Defaulting Title to Unknown Playlist")
    PlaylistSesh.set_total_tracks(total_tracks)
    
    # Click the "GET ALL" button
    click_button(bot_username, playlist_response.id, callback_data)
    PlaylistSesh.get_all_clicked = True
    
    # Wait for the bot to send downloadable files
    print("Waiting for Bot to Download Songs")
    msg, msg_found = wait_for_response(
        bot_username, session_start_time, False, "Finished", 60
        )
    if not msg_found:
        print("Download Never Finished, Check Telegram Bot to See What the Issue is")
        return None
    
    download_songs(bot_username, session_start_time, PlaylistSesh)

# Replace with the Spotify playlist URL
# playlist_url = "https://open.spotify.com/playlist/4qpwfpvpuFm0KPigXsErjD?si=1241eb653e004447"
# playlist_url = "https://open.spotify.com/playlist/1iMUYSyxrTKX0JUaP3I4DI?si=6619db94e96a4843"

if __name__ == "__main__":
    with app:  # Start the client once and reuse it
        while True:
            playlist_url = input("Input the URL of the Spotify Playlist You Wish To Download Songs From: ")
            send_playlist_and_download(bot_username, playlist_url)
            command = input("press q and hit enter to terminate this session. Press any other key to continue the session: ")
            if command.strip().lower() == "q":
                break