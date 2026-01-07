# Instagram DM Logger

A Python program to automatically log all direct messages and photos from a specific Instagram friend's conversation. Downloads entire message history, saves as JSON, and creates a beautifully formatted Markdown view of the conversation.

## Features

- ✅ Logs **all** text messages (entire conversation history)
- ✅ Downloads all photos from the conversation
- ✅ Skips reels automatically
- ✅ Saves conversation data as JSON (streaming write - efficient memory usage)
- ✅ Creates readable Markdown view of conversation with timestamps
- ✅ Comprehensive logging to file and console
- ✅ Instagram mobile API (not scraping) - reliable and fast

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure credentials:**
   - Copy `.env.example` to `.env`
   - Edit `.env` with your Instagram credentials:
     ```
     INSTAGRAM_USERNAME=your_username
     INSTAGRAM_PASSWORD=your_password
     FRIEND_USERNAME=friend_username
     ```

3. **Run the program:**
   ```bash
   python main.py
   ```
   
   This will take approximately 20-35 minutes depending on conversation size (due to Instagram's 1-second API rate limiting for safety).

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

- **JSON Data**: `data/conversation_[friend]_[timestamp].json` - Raw message data
- **Markdown View**: `data/conversation_[friend]_[timestamp].md` - Human-readable format
- **Photos**: `data/photo_[index]_[timestamp].jpg` - All downloaded photos
- **Logs**: `logs/dm_logger_[date].log` - Program execution logs

## File Structure

```
Instagram_Logging/
├── main.py                  # Main program (logs messages & downloads photos)
├── view_conversation.py     # Converter (JSON to readable Markdown)
├── requirements.txt         # Python dependencies
├── .env                     # Your credentials (create from .env.example)
├── .env.example             # Template for credentials
├── README.md                # This file
├── DOCUMENTATION.md         # Detailed explanation of how everything works
├── data/                    # Downloaded photos and conversation files
│   ├── conversation_*.json  # Raw message data
│   ├── conversation_*.md    # Readable conversation view
│   └── photo_*.jpg          # Downloaded photos
└── logs/                    # Log files
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

1. **Login**: Authenticates with Instagram using your credentials
2. **Find Friend**: Searches for the friend's user ID by username
3. **Fetch Messages**: Downloads entire message history using cursor-based pagination (20 messages per API request)
4. **Download Photos**: Saves all photos to `data/` folder
5. **Save Data**: Writes messages to JSON file as they're processed (stream writing)
6. **Convert (Optional)**: Use `view_conversation.py` to create a readable Markdown view

## Performance

- **Speed**: ~30 minutes for 40,000 messages (due to Instagram's 1-second safety delay)
- **Memory**: Efficient streaming processing - doesn't load all messages into RAM
- **Storage**: Each message is ~200 bytes; photos depend on size (typically 100KB-1MB each)

## Security Notes

- Never commit your `.env` file with real credentials
- The `.env` file is for local use only
- Consider using environment variables on production systems

## Troubleshooting

- If you get "Login failed", check your credentials
- If "User not found", verify the friend's username
- Check `logs/` for detailed error messages

## Future Improvements

- Add support for scrolling through older conversations
- Add filtering by date range
- Add support for other media types (videos, documents)
- Add scheduling for continuous monitoring
