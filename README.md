# Instagram DM Logger

A Python program to automatically log all direct messages and media from a specific Instagram friend's conversation. Features incremental updates, album extraction, and intelligent early-stop logic for efficient syncing.

## Features

- ✅ **Incremental Updates** - Only fetches new messages since last run
- ✅ **Smart Early-Stop** - Stops fetching when reaching existing messages
- ✅ **All Message Types** - Text, photos, videos, reels, albums, stories, voice messages, links, GIFs
- ✅ **Album Extraction** - Properly extracts multiple photos from albums/carousels
- ✅ **Timezone Conversion** - Converts UTC to Melbourne time (AEDT/AEST)
- ✅ **Organized Storage** - Photos saved in subfolder with timestamped filenames
- ✅ **Newest First** - New messages prepended to top of JSON
- ✅ **Instagram Mobile API** - Reliable and fast (not web scraping)

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure credentials:**
   - Create a `.env` file in the project root
   - Add your Instagram credentials:
     ```
     INSTAGRAM_USERNAME=your_username
     INSTAGRAM_PASSWORD=your_password
     FRIEND_USERNAME=friend_username
     ```

3. **Run the program:**
   ```bash
   python main.py
   ```
   
   **First run**: Fetches entire conversation history (~40 minutes for 20k messages)
   
   **Update runs**: Only fetches new messages (seconds to minutes depending on new message count)

## Viewing Your Conversation

After `main.py` completes, convert the JSON to a readable Markdown file:

```bash
python view_conversation.py
```

This creates a `.md` file with:
- Full date/time in Melbourne timezone (Australian format)
- Your messages and your friend's messages clearly separated
- Photos listed with filenames
- Chronological order (oldest to newest)
- Compact formatting (short messages on one line, long ones expanded)

## Output

The program creates a timestamped conversation folder:

```
data/conversation_[friend]_[timestamp]/
├── conversation.json           # All messages (newest first)
└── photos/                     # All downloaded media
    ├── 20260109_141232_*.jpg  # Photos
    └── 20260109_141232_*.mp4  # Videos
```

**conversation.json** contains:
- All messages in chronological order (newest at top)
- Melbourne timezone timestamps
- Photo/video paths relative to conversation folder
- Message types: text, photo, video, multi_media, album, shared_album, story_share, voice_message, etc.

## File Structure

```
Instagram_Logging/
├── main.py                  # Main program (logs messages & downloads media)
├── view_conversation.py     # Converter (JSON to readable Markdown)
├── requirements.txt         # Python dependencies
├── .env                     # Your credentials (NOT tracked in git)
├── .gitignore              # Protects sensitive files
├── README.md               # This file
├── DOCUMENTATION.md        # Detailed technical documentation
├── data/                   # Conversation folders (gitignored)
│   └── conversation_*/
│       ├── conversation.json
│       └── photos/
├── logs/                   # Program logs (gitignored)
└── tests/                  # Test scripts (gitignored)
```

## Security Notes

- Never commit your `.env` file with real credentials
- The `.env` file is for local use only
- Consider using environment variables on production systems

## Troubleshooting

- **"Login failed"**: Check your credentials and 2FA is disabled or available
- **"User not found"**: Verify the friend's username is spelled correctly
- **No photos downloading**: Instagram may have restricted photo access; check logs
- **Program taking too long**: This is normal - Instagram requires 1-second delays between requests
- Check `logs/dm_logger_[date].log` for detailed error messages

## How It Works

### First Run
1. **Login**: Authenticates with Instagram
2. **Find Friend**: Searches for friend's user ID
3. **Fetch All Messages**: Downloads entire conversation history (up to 50,000 messages)
4. **Fetch Raw Data**: Gets additional API data for album extraction (batched)
5. **Process Messages**: Extracts text, downloads photos/videos/albums
6. **Save**: Writes to conversation.json in Melbourne timezone

### Update Runs
1. **Load Existing**: Reads conversation.json and finds newest message timestamp
2. **Smart Fetch**: Fetches in batches of 20 messages
3. **Early Stop**: Stops immediately when finding messages older than newest logged
4. **Filter New**: Only processes messages not already logged
5. **Prepend**: Adds new messages to top of JSON file

### Album Extraction
- Handles `visual_media` arrays (multiple photos in single message)
- Handles `generic_xma` (shared posts with 4+ photos)
- Handles `media_share` carousels (Instagram feed posts)
- Downloads all photos/videos from albums to photos/ subfolder

## Performance

- **First Run**: ~40 minutes for 20,000 messages (1-second delay per batch of 20)
- **Update Runs**: Seconds to minutes (stops at first overlap)
- **Memory**: Efficient - loads only new messages
- **Storage**: ~200 bytes per message; photos 100KB-1MB each

## Troubleshooting

- **"Login failed"**: Check your credentials in .env file
- **"User not found"**: Verify friend's username is correct
- **"No new messages"**: Working correctly - you're up to date!
- **Albums showing "[album - could not extract photos]"**: Old messages before raw data fetch was implemented
- **Timestamp parsing errors**: Instagram changed API format - check logs for details
- Check `logs/dm_logger_[date].log` for detailed diagnostics
