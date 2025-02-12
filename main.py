import os
from dotenv import load_dotenv
from pyrogram import Client

import spotify_playlist_checker as spc
import telegram_bot_com as tbot
import pdb

def main():
    # 1. Load env variables
    load_dotenv()
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    phone_number = os.getenv("PHONE_NUMBER")
    bot_username = "deezload2bot"

    spotify_client_id = os.getenv("SPOTIFY_CLIENT_ID")
    spotify_client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    # redirect_uri could also be read from env or just hard-coded
    spotify_redirect_uri = "http://localhost:8080"

    # 2. Initialize Spotipy
    spc.initialize_spotify(spotify_client_id, spotify_client_secret, redirect_uri=spotify_redirect_uri)

    # 3. Initialize Telegram Client (Pyrogram)
    app = Client(
        "my_account",
        api_id=api_id,
        api_hash=api_hash,
        phone_number=phone_number
    )

    # 4. Initialize the DB
    spc.initialize_db()
    # Check if the user has been prompted about tracking all playlists
    if not spc.has_been_prompted_for_tracking():
        cmd = input("Would you like to track all your playlists? (y/n): ")
        if cmd.strip().lower() == "y":
            spc.track_all_user_playlists()
        # Save that the user has been prompted
        spc.save_prompted_for_tracking()

    # 5. Main logic / loop
    with app:
        while True:
            
            playlist_url = input("Enter Spotify playlist link or 'q' to exit session: ")
            if playlist_url.strip().lower() == "q":
                break

            # Extract ID, try tracking updates
            playlist_id = spc.extract_playlist_id(playlist_url)
            try:
                new_songs = spc.track_playlist_updates(playlist_id)
                original_name = spc.get_playlist_name(playlist_id)
            except Exception as e:
                print("Unable to find playlist based on given URL:", e)
                continue

            if new_songs:
                print("New songs found:")
                for uri, info in new_songs.items():
                    print(f"- {info['name']} by {info['artists']} (URI: {uri})")
                    
                cmd = input("Would you like to download the whole playlist (all), just the new songs (new), or none (n)? (all/new/n): ")
                if cmd.strip().lower() == "all":
                    print("Downloading the whole playlist...")
                    tbot.send_playlist_and_download(app, bot_username, playlist_url=playlist_url, original_name=original_name)
                elif cmd.strip().lower() == "new":
                    print("Downloading the new songs...")
                    user_id = spc.get_current_user_id()
                    temp_playlist_name = f"{original_name} - Newly Added Songs (Temp)"
                    temp_playlist_link = spc.create_new_playlist(
                        new_songs_dict=new_songs,
                        user_id=user_id,
                        playlist_name=temp_playlist_name
                    )
                    print(f"Created new temp playlist: {temp_playlist_link}")
                    tbot.send_playlist_and_download(app, bot_username, playlist_url=temp_playlist_link, original_name=original_name)
                    
                    spc.delete_playlist_with_confirmation(temp_playlist_link)
            else:
                # If there are no new songs, optionally let the user download anyway
                cmd = input("No new songs. Download the original playlist anyway? (y/n): ")
                if cmd.strip().lower() == "y":
                    tbot.send_playlist_and_download(app, bot_username, playlist_url=playlist_url, original_name=original_name)
            
            cmd = input("Would you like to view your playlists being tracked? (y/n): ")
            if cmd.strip().lower() == "y":
                spc.print_tracked_playlists()

if __name__ == "__main__":
    main()
