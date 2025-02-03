import spotipy
from spotipy.oauth2 import SpotifyOAuth
import sqlite3
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Read values from environment
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = "http://localhost:8080"

# Initialize SQLite database
DB_FILE = "playlist_memory.db"
def initialize_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS playlist_memory (
            playlist_id TEXT PRIMARY KEY,
            songs TEXT
        )
    """)
    conn.commit()
    conn.close()

# Authenticate with Spotify API
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope="playlist-read-private"
))

def get_playlist_songs(playlist_url):
    """Fetch all songs from a Spotify playlist."""
    results = sp.playlist_tracks(playlist_url)
    songs = []

    # Extract song names and artists
    for item in results['items']:
        track = item['track']
        song_name = track['name']
        artist_names = ", ".join(artist['name'] for artist in track['artists'])
        songs.append(f"{song_name} by {artist_names}")

    # Handle pagination
    while results['next']:
        results = sp.next(results)
        for item in results['items']:
            track = item['track']
            song_name = track['name']
            artist_names = ", ".join(artist['name'] for artist in track['artists'])
            songs.append(f"{song_name} by {artist_names}")

    return songs

def create_new_playlist(new_songs, user_id, playlist_name="Newly Added Songs"):
    playlist = sp.user_playlist_create(user=user_id, name=playlist_name, public=False)
    track_uris = [song['uri'] for song in new_songs]  # Ensure new_songs includes 'uri' field
    sp.playlist_add_items(playlist_id=playlist['id'], items=track_uris)
    return playlist['external_urls']['spotify']  # Return the new playlist link

def send_songs_to_bot(bot_username, new_songs):
    for song in new_songs:
        track_info = f"{song['name']} by {song['artist']}"  # Adjust to match bot input format
        app.send_message(bot_username, track_info)

def delete_playlist(playlist_id):
    sp.current_user_unfollow_playlist(playlist_id)
    print(f"Playlist {playlist_id} has been deleted.")

def get_stored_songs(playlist_id):
    """Retrieve stored songs for a playlist from the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT songs FROM playlist_memory WHERE playlist_id = ?", (playlist_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0].split("\n") if result else []

def store_songs(playlist_id, songs):
    """Store songs for a playlist in the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    songs_str = "\n".join(songs)
    cursor.execute("""
        INSERT OR REPLACE INTO playlist_memory (playlist_id, songs)
        VALUES (?, ?)
    """, (playlist_id, songs_str))
    conn.commit()
    conn.close()

def track_playlist_updates(playlist_url):
    """Track updates to a playlist and return new songs."""
    playlist_id = playlist_url.split("playlist/")[1].split("?")[0]  # Extract playlist ID

    # Get current songs from the playlist
    current_songs = get_playlist_songs(playlist_url)

    # Get stored songs from the database
    previous_songs = get_stored_songs(playlist_id)

    # Identify new songs
    new_songs = [song for song in current_songs if song not in previous_songs]

    # Update the database with the latest songs
    store_songs(playlist_id, current_songs)

    return new_songs

# Example usage
if __name__ == "__main__":
    initialize_db()
    playlist_url = input("Enter Spotify playlist link: ")
    new_songs = track_playlist_updates(playlist_url)

    if new_songs:
        print("New songs added to the playlist:")
        for song in new_songs:
            print(f"- {song}")
    else:
        print("No new songs added.")
