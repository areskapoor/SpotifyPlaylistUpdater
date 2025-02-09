# Spotify Playlist Downloader & Updater

A tool for DJs and music enthusiasts to **track Spotify playlists** and **download newly added songs** in MP3 format via Telegram. This makes it easy to keep your local music library up-to-date with the latest additions, saving you time and confusion.

---

## Features

1. **Automatic Playlist Tracking**  
   - Monitors a given Spotify playlist and detects newly added songs.

2. **Selective Download via Telegram**  
   - Only new songs get downloaded to avoid redownloading your entire playlist.

3. **Easy Integration**  
   - Uses the Telegram [@deezload2bot] or similar to perform downloads and manage them.

4. **Minimal Setup**  
   - Just provide your **Spotify** and **Telegram** credentials in a `.env` file.

---

## How It Works

1. **Check a Spotify Playlist**  
   - The app looks up your playlist and compares it to any previously stored version in a local SQLite database.

2. **Identify Newly Added Songs**  
   - If new songs are found, the tool can automatically create a temporary playlist with just those new tracks.

3. **Send the Playlist Link to Telegram Bot**  
   - The tool leverages a Telegram bot to fetch and download MP3 files.

4. **Download MP3 Files**  
   - The songs are saved locally in a `downloads/` directory, organized by playlist name.

---

## Installation & Setup

### 1. Clone or Download this Repository

```bash
git clone https://github.com/YourUsername/spotify-playlist-downloader.git
cd spotify-playlist-downloader
```

### 2. Create and Activate a Virtual Environment (Optional but Recommended)

```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate     # On Windows
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Set Up Your .env File
Create a file named .env in the project’s root directory. It needs to contain:

```ini
Copy
Edit
# Spotify credentials
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret

# Telegram credentials
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
PHONE_NUMBER=your_phone_number  # if you're using user-based sessions
BOT_TOKEN=your_bot_token        # if needed (you may not need both)
```
- Spotify Client ID & Client Secret: You can get these from the Spotify Developer Dashboard.
- Telegram API ID & API Hash: Obtain them by creating an app on my.telegram.org.
- Phone Number: If you are using Pyrogram in user mode (not as a bot).
- Bot Token: If you are using a Telegram bot account instead of a user session.

### 5. Usage
Run the main script:

```bash
python main.py
```
You’ll be asked to log in to both Spotify (via OAuth) and Telegram (via a phone code or bot token). Once authenticated:

1. Enter a Spotify playlist link when prompted.
2. The tool will check your database to see if it’s a new playlist or if it has been tracked before.
3. If it’s a new playlist, it stores the entire playlist in the database but doesn’t download anything automatically.
4. If it finds newly added songs:
5. It creates a temp playlist with those new songs.
6. It sends that playlist link to Telegram for downloading.
7. After the download is complete, it can optionally delete the temp playlist to keep your Spotify tidy.

### 6. Where Do Songs Download?
All MP3 files are saved into a downloads/ directory under a subfolder named after the playlist. For example:

downloads/
── My Playlist Name/
    ── Artist1 - Song1.mp3
    ── Artist2 - Song2.mp3
    ...

## Contributing
Pull requests and issues are welcome! If you find a bug or have a feature request, please open an issue in this repository.

Happy DJing! If you run into any problems, please open an issue or reach out. Enjoy your streamlined workflow for managing and downloading newly added Spotify tracks.