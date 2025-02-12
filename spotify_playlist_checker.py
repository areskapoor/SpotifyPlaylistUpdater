import spotipy
from spotipy.oauth2 import SpotifyOAuth
import sqlite3
import json
from urllib.parse import urlparse

sp = None  

DB_FILE = "playlist_memory.db"

def initialize_spotify(client_id, client_secret, redirect_uri="http://localhost:8080"):
    """
    Create and store a Spotipy client in the global 'sp' variable.
    Must be called before any other Spotify operations.
    """
    global sp
    sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope="playlist-read-private playlist-modify-private"
        )
    )

def get_current_user_id():
    """
    Return the current Spotify user ID (requires that 'sp' is already initialized).
    """
    if not sp:
        raise RuntimeError("Spotify client not initialized. Call initialize_spotify first.")
    return sp.current_user()["id"]


# --------------------------- DATABASE STUFF ---------------------------

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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_prompts (
            user_id TEXT PRIMARY KEY,
            prompted INTEGER
        )
    """)
    conn.commit()
    conn.close()
    
    
def set_prompted_status(prompted: bool):
    """
    Set the prompted status for a user in the database.
    
    :param user_id: The Spotify user ID.
    :param prompted: A boolean indicating whether the user has been prompted.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    user_id = get_current_user_id()
    prompted_value = 1 if prompted else 0
    cursor.execute("""
        INSERT OR REPLACE INTO user_prompts (user_id, prompted)
        VALUES (?, ?)
    """, (user_id, prompted_value))
    conn.commit()
    conn.close()

  
def has_been_prompted_for_tracking():
    """Check if the user has been prompted for tracking all playlists."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    user_id = get_current_user_id()
    cursor.execute("SELECT prompted FROM user_prompts WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None and result[0] == 1


def save_prompted_for_tracking():
    """Save that the user has been prompted for tracking all playlists."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    user_id = get_current_user_id()
    cursor.execute("""
        INSERT OR REPLACE INTO user_prompts (user_id, prompted)
        VALUES (?, 1)
    """, (user_id,))
    conn.commit()
    conn.close()


def store_songs(playlist_id: str, songs_dict: dict):
    """Store the entire dictionary of {URI: {name, artists}} as JSON in DB."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    songs_json = json.dumps(songs_dict)
    cursor.execute("""
        INSERT OR REPLACE INTO playlist_memory (playlist_id, songs)
        VALUES (?, ?)
    """, (playlist_id, songs_json))
    conn.commit()
    conn.close()


def get_stored_songs(playlist_id: str) -> dict:
    """Retrieve the songs dict from the DB and return it. Returns {} if none found."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT songs FROM playlist_memory WHERE playlist_id = ?", (playlist_id,))
    result = cursor.fetchone()
    conn.close()

    if result is None:
        return {}
    else:
        return json.loads(result[0])
    
    
def print_tracked_playlists():
    """
    Prints all playlists currently tracked in the DB, showing:
      - The playlist's name
      - The number of songs in it
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Fetch all rows from the 'playlist_memory' table
    cursor.execute("SELECT playlist_id, songs FROM playlist_memory")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("No playlists are currently being tracked.")
        return
    
    print("Playlists currently tracked:\n")
    
    for (playlist_id, songs_json) in rows:
        # Parse the JSON to get a dict of URIs -> { "name": ..., "artists": ... }
        songs_dict = json.loads(songs_json)
        song_count = len(songs_dict)  # number of songs

        # Fetch the playlist name from Spotify
        try:
            data = sp.playlist(playlist_id, fields="name")
            playlist_name = data["name"]
        except spotipy.exceptions.SpotifyException:
            # If there's an error (e.g. invalid or private), handle gracefully
            playlist_name = f"(Unable to retrieve name for ID={playlist_id})"

        print(f"{playlist_name} -> {song_count} songs")


# ----------------------- SPOTIFY PLAYLIST STUFF -----------------------

def extract_playlist_id(playlist_url: str) -> str:
    """Parse the Spotify playlist URL in a robust way."""
    parsed = urlparse(playlist_url)
    path_parts = parsed.path.split('/')
    # Typically: ['', 'playlist', '<PLAYLIST_ID>']
    if len(path_parts) > 2 and path_parts[1] == 'playlist':
        return path_parts[2]
    # If not recognized, just return the original or raise an error
    return playlist_url


def get_playlist_name(playlist_id: str) -> str:
    """Return the name of the playlist by ID (Spotipy calls)."""
    if not sp:
        raise RuntimeError("Spotify client not initialized. Call initialize_spotify first.")

    data = sp.playlist(playlist_id, fields="name")
    return data["name"]


def get_playlist_songs(playlist_id: str) -> dict:
    """
    Fetch all tracks from a Spotify playlist. 
    Returns a dict keyed by track URI, value = {"name": ..., "artists": ...}.
    """
    if not sp:
        raise RuntimeError("Spotify client not initialized. Call initialize_spotify first.")

    all_songs = {}
    results = sp.playlist_items(playlist_id, limit=100)
    
    while True:
        for item in results['items']:
            track = item['track']
            if not track:  # local/unavailable track
                continue
            uri = track['uri']
            name = track['name']
            artists = ", ".join(artist['name'] for artist in track['artists'])
            all_songs[uri] = {"name": name, "artists": artists}

        if results['next']:
            results = sp.next(results)
        else:
            break

    return all_songs


def track_all_user_playlists():
    """
    Track all playlists the user is the owner or co-collaborator of.
    Adds a snapshot of each playlist to the database.
    """
    if not sp:
        raise RuntimeError("Spotify client not initialized. Call initialize_spotify first.")

    user_id = get_current_user_id()
    playlists = sp.current_user_playlists(limit=50)
    
    while playlists:
        for playlist in playlists['items']:
            # Check if the user is the owner or a collaborator
            if playlist['owner']['id'] == user_id or playlist['collaborative']:
                playlist_id = playlist['id']
                print(f"Tracking playlist: {playlist['name']}")
                songs_dict = get_playlist_songs(playlist_id)
                store_songs(playlist_id, songs_dict)
        
        if playlists['next']:
            playlists = sp.next(playlists)
        else:
            break


def track_playlist_updates(playlist_id: str) -> dict:
    """
    1) Get current songs from Spotify,
    2) Compare w/ DB,
    3) Identify newly added URIs,
    4) Store the updated dict in DB,
    5) Return a dict of newly added songs.
    """
    current_songs = get_playlist_songs(playlist_id)
    previous_songs = get_stored_songs(playlist_id)
    
    # Store the fresh snapshot in DB
    store_songs(playlist_id, current_songs)

    # If we have nothing stored previously, there's no "new" difference to show
    if not previous_songs:
        print("New Playlist Detected")
        return {}

    # Identify newly added
    current_uris = set(current_songs.keys())
    previous_uris = set(previous_songs.keys())
    new_uris = current_uris - previous_uris
    new_songs = {uri: current_songs[uri] for uri in new_uris}

    return new_songs


def create_new_playlist(new_songs_dict: dict, user_id: str, playlist_name: str) -> str:
    """
    Create a new Spotify playlist w/ the given songs.
    Return the new playlist's Spotify URL.
    """
    if not sp:
        raise RuntimeError("Spotify client not initialized. Call initialize_spotify first.")

    new_playlist = sp.user_playlist_create(user=user_id, name=playlist_name, public=False)
    new_playlist_id = new_playlist['id']
    track_uris = list(new_songs_dict.keys())
    if track_uris:
        sp.playlist_add_items(playlist_id=new_playlist_id, items=track_uris)
    return new_playlist['external_urls']['spotify']


def delete_playlist_with_confirmation(playlist_url_or_id: str):
    """
    Ask user if they want to delete/unfollow the playlist. Then do so if yes.
    """
    if not sp:
        raise RuntimeError("Spotify client not initialized. Call initialize_spotify first.")

    playlist_id = extract_playlist_id(playlist_url_or_id)
    playlist_details = sp.playlist(playlist_id, fields="name,owner")
    playlist_name = playlist_details["name"]
    owner_id = playlist_details["owner"]["id"]

    print(f"You're about to unfollow playlist: '{playlist_name}' owned by {owner_id}.")
    response = input("Are you sure you want to continue? (yes/no): ")
    if response.strip().lower() in ("yes", "y"):
        sp.current_user_unfollow_playlist(playlist_id)
        print(f"Playlist '{playlist_name}' has been unfollowed.")
    else:
        print("Deletion canceled.")