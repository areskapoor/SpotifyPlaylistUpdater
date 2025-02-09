import spotipy
from spotipy.oauth2 import SpotifyOAuth
import spotipy.exceptions
import sqlite3
import os
import json
from urllib.parse import urlparse
from dotenv import load_dotenv


load_dotenv()
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = "http://localhost:8080"

DB_FILE = "playlist_memory.db"

sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope="playlist-read-private playlist-modify-private"  
        # If you're creating/deleting playlists, you'll also need
        #   the `playlist-modify-private` (or public) scope
    )
)


def initialize_db():
    """Create an SQLite table if it doesn't already exist."""
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


def store_songs(playlist_id: str, songs_dict: dict):
    """
    Store the entire dictionary of {URI: {name, artists}} as JSON in DB.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    songs_json = json.dumps(songs_dict)  # convert to JSON
    cursor.execute(
        """INSERT OR REPLACE INTO playlist_memory (playlist_id, songs)
           VALUES (?, ?)""",
        (playlist_id, songs_json)
    )
    conn.commit()
    conn.close()


def get_stored_songs(playlist_id: str) -> dict:
    """
    Retrieve the songs dict from the DB and return it. 
    Returns {} if none found.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT songs FROM playlist_memory WHERE playlist_id = ?", (playlist_id,))
    result = cursor.fetchone()
    conn.close()

    if result is None:
        return {}
    else:
        return json.loads(result[0])


def extract_playlist_id(playlist_url: str) -> str:
    """
    Parse the Spotify playlist URL in a robust way.
    Example: https://open.spotify.com/playlist/<ID>?si=<some_string>
    """
    parsed = urlparse(playlist_url)
    path_parts = parsed.path.split('/')
    # Typically path_parts might look like: ['', 'playlist', 'PLAYLIST_ID']
    if len(path_parts) > 2 and path_parts[1] == 'playlist':
        return path_parts[2]
    # Fallback: your code might raise an error or return the original
    return playlist_url  # or raise ValueError("Invalid playlist URL")


def get_playlist_name(playlist_id: str) -> str:
    """
    Return the name of the playlist using its ID.
    """
    # You can request a subset of fields if you want (like just 'name')
    playlist_data = sp.playlist(playlist_id, fields="name")
    # The returned dictionary will contain {'name': '<playlist title>'}
    playlist_name = playlist_data["name"]
    return playlist_name


def get_playlist_songs(playlist_id: str) -> dict:
    """
    Fetch all tracks from a Spotify playlist. 
    Returns a dict keyed by track URI, value = {"name": ..., "artists": ...}
    """
    all_songs = {}
    results = sp.playlist_items(playlist_id, limit=100)
    
    while True:
        for item in results['items']:
            track = item['track']
            if not track:
                # Sometimes local or unavailable tracks can appear as None
                continue

            uri = track['uri']
            name = track['name']
            artists = ", ".join(artist['name'] for artist in track['artists'])
            
            # Use the URI as a key for efficient lookups
            all_songs[uri] = {"name": name, "artists": artists}

        if results['next']:
            results = sp.next(results)
        else:
            break

    return all_songs


def track_playlist_updates(playlist_id: str) -> dict:
    """
    1. Get the current songs from Spotify in dict form.
    2. Compare them with the stored songs in the DB.
    3. Identify newly added URIs.
    4. Store the updated dict in the DB.
    5. Return a dict of newly added songs: {uri: {...}}
    """
    # Pull the current songs from Spotify
    current_songs = get_playlist_songs(playlist_id)
    
    # Get stored songs from DB
    previous_songs = get_stored_songs(playlist_id)
    print(f"current_songs: {current_songs}\n\n previous_songs: {previous_songs}")
    
    # Update DB with the full current set
    store_songs(playlist_id, current_songs)
    
    # No need to create a new playlist if there is no previous version of playist
    if previous_songs == {}:
        print("prev_songs is empty")
        return {}

    # The newly added songs are those URIs in current_songs but not in previous_songs
    current_uris = set(current_songs.keys())
    previous_uris = set(previous_songs.keys())

    new_uris = current_uris - previous_uris
    new_songs = {uri: current_songs[uri] for uri in new_uris}

    return new_songs


def create_new_playlist(new_songs_dict: dict, user_id: str, playlist_name: str = "Newly Added Songs") -> str:
    """
    Create a new Spotify playlist containing the songs in new_songs_dict.
    Return the new playlist's Spotify URL.
    """
    # Create a private playlist
    new_playlist = sp.user_playlist_create(user=user_id, name=playlist_name, public=False)
    new_playlist_id = new_playlist['id']
    
    # Get all URIs from the new_songs_dict
    track_uris = list(new_songs_dict.keys())
    
    # Spotify API expects a list of track URIs for adding items
    if track_uris:
        sp.playlist_add_items(playlist_id=new_playlist_id, items=track_uris)

    # Return the external Spotify link to the newly created playlist
    return new_playlist['external_urls']['spotify']


def delete_playlist_with_confirmation(playlist_url_or_id):
    playlist_id = extract_playlist_id(playlist_url_or_id)
    
    # Fetch playlist details to display name/owner (optional)
    playlist_details = sp.playlist(playlist_id, fields="name,owner")
    playlist_name = playlist_details["name"]
    owner_id = playlist_details["owner"]["id"]

    # Show the user some context
    print(f"You're about to delete/unfollow playlist: '{playlist_name}' owned by {owner_id}.")
    response = input("Are you sure you want to continue? (yes/no): ")

    if response.lower() in ("yes", "y"):
        sp.current_user_unfollow_playlist(playlist_id)
        print(f"Playlist '{playlist_name}' has been unfollowed/deleted.")
    else:
        print("Deletion canceled.")


if __name__ == "__main__":
    initialize_db()
    while True:
        playlist_url = input("Enter Spotify playlist link or q to exit session: ")
        if playlist_url.strip().lower() == "q":
            break
        playlist_id = extract_playlist_id(playlist_url)
        
        try:
            new_songs = track_playlist_updates(playlist_id)
            original_name = get_playlist_name(playlist_id)
        except:
            # print("\nERROR:", ve)
            print("Unable to find playlist based on given URL. Please try again.\n")
            continue  # re-loop, ask for a new URL

        if new_songs:
            print("New songs found:")
            for uri, info in new_songs.items():
                print(f"- {info['name']} by {info['artists']} (URI: {uri})")

            # Suppose you want to create a new "temp" playlist for these new songs:
            user_id = sp.current_user()['id']  # current user's Spotify ID
            temp_playlist_link = create_new_playlist(
                new_songs_dict=new_songs,
                user_id=user_id,
                playlist_name=f"{original_name} - Newly Added Songs (Temp)"
            )
            print(f"Created new temp playlist: {temp_playlist_link}")

            # Now you might pass 'new_songs' to your download routine...
            # download_songs(new_songs)  # (Pseudo-function in your app)

            # ...And then remove the playlist once done:
            delete_playlist_with_confirmation(temp_playlist_link)

        else:
            print("No new songs added.")