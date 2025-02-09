import re
import time
import os
from datetime import datetime, timezone
from pyrogram import Client

class PlaylistSession:
    def __init__(self, playlist_url):
        self.playlist_url = playlist_url
        self.playlist_name = "Unknown Playlist"
        self.total_tracks = None
        self.downloaded_songs = {}
        self.get_all_clicked = False

    def set_playlist_name(self, playlist_name):
        self.playlist_name = playlist_name

    def set_total_tracks(self, total_tracks):
        self.total_tracks = total_tracks

    def add_downloaded_song(self, file_name, metadata):
        self.downloaded_songs[file_name] = metadata

    def all_songs_downloaded(self):
        return (self.total_tracks is not None 
                and len(self.downloaded_songs) >= self.total_tracks)

    def __repr__(self):
        return (f"PlaylistSession(url={self.playlist_url}, "
                f"total={self.total_tracks}, downloaded={len(self.downloaded_songs)})")


def extract_download_progress(msg):
    match = re.search(r"Track (\d+) of (\d+)", msg.text)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None

def find_total_tracks(msg):
    match = re.search(r"Total tracks:\s*(\d+)", msg.text)
    return int(match.group(1)) if match else None

def wait_for_response(app: Client, bot_username, session_start_time, is_button, text, max_wait):
    """
    Repeatedly polls chat history to find a message that either contains a button w/ 'text'
    or has a message w/ 'text' in it.
    """
    start_time = time.time()
    while time.time() - start_time < max_wait:
        messages = list(app.get_chat_history(bot_username, limit=10))
        for msg in messages:
            if msg.date.timestamp() < session_start_time:
                continue
            if is_button and msg.reply_markup:
                # check for a button with the text
                for row in msg.reply_markup.inline_keyboard:
                    for button in row:
                        if button.text == text:
                            return msg, button.callback_data
            else:
                if msg.text and text in msg.text:
                    return msg, True
        time.sleep(0.5)
    return None, None

def click_button(app: Client, bot_username, message_id, callback_data):
    app.request_callback_answer(bot_username, message_id, callback_data)

def download_songs(app: Client, bot_username, session_start_time, playlist_sesh: PlaylistSession):
    messages = list(app.get_chat_history(bot_username, limit=playlist_sesh.total_tracks + 5))
    for msg in messages:
        if msg.date.timestamp() < session_start_time:
            continue
        if playlist_sesh.all_songs_downloaded():
            break
        if msg.audio:
            artist = msg.audio.performer or "Unknown Artist"
            title = msg.audio.title or "Unknown Title"
            metadata = {
                "title": title,
                "artist": artist,
                "file_id": msg.audio.file_id
            }
            safe_playlist_name = "".join(c if c.isalnum() or c in " _-" else "_" 
                                         for c in playlist_sesh.playlist_name)
            download_dir = os.path.join("downloads", safe_playlist_name)
            os.makedirs(download_dir, exist_ok=True)
            safe_file_name = f"{artist} - {title}.mp3"
            safe_file_name = "".join(
                c if c.isalnum() or c in " _-()." 
                else "_" 
                for c in safe_file_name
            )

            playlist_sesh.add_downloaded_song(safe_file_name, metadata)
            file_path = os.path.join(download_dir, safe_file_name)
            downloaded_path = app.download_media(msg.audio.file_id, file_name=file_path)
            print(f"Downloaded {msg.audio.file_name} to {downloaded_path}")

    if playlist_sesh.all_songs_downloaded():
        print("Finished Downloading All Songs.")
        return True

    print(f"Failure to download all songs. Downloaded "
          f"{len(playlist_sesh.downloaded_songs)} / {playlist_sesh.total_tracks}")
    return False

def send_playlist_and_download(app: Client, bot_username, playlist_url, original_name=None):
    """
    Orchestrates sending a playlist URL to the bot, pressing 'GET ALL', 
    waiting for the results, then downloading them.
    """
    session_start_time = datetime.now(timezone.utc).timestamp()
    playlist_sesh = PlaylistSession(playlist_url)

    # Send the playlist link
    app.send_message(bot_username, playlist_url)
    print(f"Sent message to {bot_username}: {playlist_url}")

    # Wait for the "GET ALL" button
    playlist_response, callback_data = wait_for_response(
        app, bot_username, session_start_time, is_button=True,
        text="GET ALL ⬇️", max_wait=15
    )
    if not playlist_response:
        print("No response with 'GET ALL' button found.")
        return

    total_tracks = find_total_tracks(playlist_response)
    if original_name:
            playlist_sesh.set_playlist_name(original_name)
    elif playlist_response.web_page:
        playlist_sesh.set_playlist_name(playlist_response.web_page.title)
    else:
        print("Could not find playlist title via web_page data.")
    playlist_sesh.set_total_tracks(total_tracks)

    # Click the GET ALL button
    click_button(app, bot_username, playlist_response.id, callback_data)
    playlist_sesh.get_all_clicked = True

    # Wait for the bot to finish
    print("Waiting for Bot to Download Songs...")
    finished_msg, msg_found = wait_for_response(
        app, bot_username, session_start_time, is_button=False,
        text="Finished", max_wait=60
    )
    if not msg_found:
        print("Download never finished, check Telegram Bot to see the issue.")
        return

    # Download them from the chat
    download_songs(app, bot_username, session_start_time, playlist_sesh)