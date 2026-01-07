# Instagram DM Logger - Complete Learning Guide

This document explains **everything** about how this program works, from start to finish.

---

## Table of Contents
1. [What This Program Does](#what-this-program-does)
2. [How Instagram Works](#how-instagram-works)
3. [Program Flow](#program-flow)
4. [Code Breakdown](#code-breakdown)
5. [API & Pagination](#api--pagination)
6. [Data Storage](#data-storage)

---

## What This Program Does

This program:
1. **Logs into your Instagram account** using your username and password
2. **Finds a specific friend's direct messages**
3. **Downloads ALL messages** from your conversation with that friend (from first message to most recent)
4. **Downloads all photos** from the conversation
5. **Saves everything to files** on your computer (messages as JSON, photos in a folder)
6. **Skips reels** (doesn't download video reels)

### Why would you want this?

- **Backup**: Save important conversations permanently
- **Archive**: Keep memories without relying on Instagram
- **Search**: Easily find old messages in a local file
- **Privacy**: Own your data instead of trusting Instagram

---

## How Instagram Works

### Instagram API vs Scraping

This program uses **Instagram's Private API**, not scraping.

**What's the difference?**

| Method | What it does | How it works |
|--------|------------|------------|
| **Scraping** | Reads the HTML website code | Opens Instagram website, reads HTML like a browser, extracts data |
| **API Access** | Asks Instagram directly for data | Sends special requests to Instagram's servers, receives JSON data back |

**This program uses API Access** because:
- ✅ Faster than scraping
- ✅ More reliable
- ✅ Gets real data directly from Instagram
- ✅ Uses what Instagram's mobile app uses

### How the API Works

Think of it like ordering food:

1. **You (the client)** → Send request to Instagram's server: "Give me messages from thread 123"
2. **Instagram's server** → Processes your request
3. **Instagram's server** → Sends back JSON data: `{"messages": [...]}`
4. **You** → Process the data and save it

Every API request is just HTTP (the same protocol websites use), but instead of returning HTML (website code), it returns **JSON** (structured data).

### Example API Request

```
GET https://i.instagram.com/api/v1/direct_v2/threads/340282366841710301949128122292511813703/
Headers: 
  - Authentication token (proves it's you)
  - User agent (says you're Instagram mobile app)

Instagram responds with:
{
  "thread": {
    "items": [
      {"text": "hey!", "timestamp": 1234567890},
      {"text": "how are you?", "timestamp": 1234567891}
    ],
    "oldest_cursor": "abc123def456"
  }
}
```

---

## Program Flow

### Step-by-Step Execution

```
START
  ↓
[1] LOGIN
    - Read username & password from .env file
    - Send login request to Instagram API
    - Instagram sends back authentication token
    - If 2FA enabled: Ask you for 2FA code → Send to Instagram
    ↓
[2] SEARCH
    - Take friend's username from .env (e.g., "melanie.ig_")
    - Ask Instagram: "What's the user ID for melanie.ig_?"
    - Instagram responds: "user ID is 2130174857"
    ↓
[3] FIND CONVERSATION
    - Ask Instagram: "Get me all my DM threads"
    - Instagram returns list of all conversations
    - Find the one that includes user ID 2130174857
    ↓
[4] FETCH ALL MESSAGES (Main Work)
    - Ask Instagram: "Get me messages from this thread"
    - Instagram returns 20 newest messages + a "cursor"
    - [Wait 1 second]
    - Ask Instagram again: "Get me older messages using this cursor"
    - Instagram returns next 20 messages + new cursor
    - [Wait 1 second]
    - Repeat until cursor = None (reached the beginning)
    ↓
[5] PROCESS MESSAGES
    - For each message:
      - Extract text or photo
      - If photo: Download it
      - If reel: Skip it
      - Save to JSON file
    ↓
[6] SAVE DATA
    - Save all messages as JSON
    - Organize photos in data folder
    ↓
END
```

### Timeline Example

Say you have a 5-day conversation with 100 messages:

```
Time Logged                  Flow
2026-01-07 18:49:05        [1] LOGIN (10 seconds)
2026-01-07 18:49:15        [2] SEARCH (9 seconds)
2026-01-07 18:49:24        [3] FIND CONVERSATION (1 second)
2026-01-07 18:49:25        [4] FETCH ALL MESSAGES (start)
  - Request 1: Get newest 20 messages (2 sec)
  - Wait 1 second
  - Request 2: Get next 20 messages (2 sec)
  - Wait 1 second
  - ... repeat 5 times total ...
2026-01-07 18:49:50        [4] FETCH COMPLETE (25 seconds total)
2026-01-07 18:49:51        [5] PROCESS MESSAGES (1 second)
2026-01-07 18:49:52        [6] SAVE DATA (1 second)
2026-01-07 18:49:52        DONE! Total: ~50 seconds
```

---

## Code Breakdown

### 1. Setting Up (Imports & Configuration)

```python
import os                      # Read files and environment variables
import json                    # Save/load data as JSON
import logging                 # Print status messages
import time                    # Add delays
from datetime import datetime  # Get current time
from pathlib import Path       # Handle file paths
from dotenv import load_dotenv # Read .env file
from instagrapi import Client  # Instagram API library
```

**What each does:**
- `os`: Lets us read the `.env` file with your credentials
- `json`: Converts Python data to text format for saving
- `logging`: Shows you what the program is doing (in console and log files)
- `time`: Adds 1-second delays between API requests
- `datetime`: Records when messages were sent
- `Path`: Makes file paths work on all computers (Windows/Mac/Linux)
- `load_dotenv`: Reads your .env file securely
- `Client`: The actual Instagram API tool from instagrapi library

### 2. The InstagramDMLogger Class

A class is like a "container" that holds everything related to one task. Think of it like a toolbox:

```python
class InstagramDMLogger:
    """This is the toolbox for logging Instagram messages"""
    
    def __init__(self):
        self.username = os.getenv("INSTAGRAM_USERNAME")
        self.password = os.getenv("INSTAGRAM_PASSWORD")
        self.client = None              # Will hold Instagram connection
        self.conversation_data = []     # Will hold all messages
```

---

### 3. Login Function

```python
def login(self):
    """Login to Instagram"""
    try:
        self.client = Client()  # Create Instagram connection
        self.client.login(self.username, self.password)
        logger.info("Successfully logged in!")
        return True
    except Exception as e:
        if "challenge" in str(e).lower():
            logger.info("2FA needed - asking for code...")
            code = input("Enter your 2FA code: ")
            self.client.login(self.username, self.password, 
                            verification_code=code)
            return True
        else:
            logger.error(f"Login failed: {e}")
            return False
```

**How it works:**

1. Create a new "Instagram client" (like opening Instagram on your phone)
2. Send username and password to Instagram's servers
3. If successful: Instagram says "OK, you're logged in! Here's your token"
4. Save that token in `self.client` (use it for future requests)
5. If 2FA needed: Ask you for the code, send it again

**What happens behind the scenes:**

```
You                          Instagram Server
  |                               |
  |-- username + password ------->|
  |<----- "Need 2FA code" --------|
  |-- 2FA code ------------------>|
  |<----- "OK! Here's your token" |
```

---

### 4. Get Friend ID Function

```python
def get_friend_id(self):
    """Get the friend's user ID"""
    logger.info(f"Searching for user: {self.friend_username}")
    user = self.client.user_info_by_username(self.friend_username)
    logger.info(f"Found user ID: {user.pk}")
    return user.pk  # pk = primary key (unique ID number)
```

**Why do we need the ID?**

- Instagram internally uses **numbers** to identify users, not usernames
- Usernames can change, but IDs never change
- So we convert "melanie.ig_" → "2130174857" first

---

### 5. Get Conversation Function

```python
def get_conversation(self, user_id):
    """Get all messages from conversation with friend"""
    logger.info(f"Fetching conversation with user ID: {user_id}")
    threads = self.client.direct_threads()
    
    for thread in threads:
        # Check if this thread includes our friend
        if user_id in [user.pk for user in thread.users]:
            logger.info("Found conversation thread")
            logger.info("Fetching ALL messages from history...")
            self._fetch_all_messages_cursor(thread)
            return thread
    
    logger.warning("Conversation not found")
    return None
```

**What it does:**

1. Ask Instagram: "Give me all my DM conversations"
2. Loop through each conversation
3. Check if this conversation includes our friend's ID
4. When found: Fetch all messages from this thread
5. Return the thread with all messages

---

### 6. Fetch All Messages (The Core Function)

This is the most important part:

```python
def _fetch_all_messages_cursor(self, thread):
    """Fetch all messages using cursor-based pagination"""
    try:
        thread_id = thread.id  # Get the conversation ID
        logger.info(f"Fetching all messages from thread {thread_id}...")
        
        # Request up to 50,000 messages
        # instagrapi handles pagination automatically
        full_thread = self.client.direct_thread(thread_id, amount=50000)
        
        if full_thread and hasattr(full_thread, 'messages'):
            thread.messages = full_thread.messages
            logger.info(f"Loaded {len(thread.messages)} messages")
            return True
    except Exception as e:
        logger.error(f"Error fetching messages: {e}")
        return False
```

**What is pagination?**

Pagination means "getting data in chunks instead of all at once"

**Why?**

- If Instagram returns 100,000 messages at once = huge file, slow
- If Instagram returns 20 messages at a time = smaller chunks, faster
- Like reading a book: one page at a time, not the whole book at once

**How cursor works:**

```
1st Request:
  GET /thread/123/?limit=20
  Response: {
    items: [msg1, msg2, ..., msg20],
    oldest_cursor: "abc123"  ← Remember this!
  }

2nd Request:
  GET /thread/123/?cursor=abc123&limit=20
  Response: {
    items: [msg21, msg22, ..., msg40],
    oldest_cursor: "def456"  ← New cursor!
  }

3rd Request:
  GET /thread/123/?cursor=def456&limit=20
  Response: {
    items: [msg41, msg42, ..., msg60],
    oldest_cursor: null  ← No more messages!
  }

Stop! No cursor = we've reached the beginning
```

---

### 7. Process Messages Function

```python
def process_messages(self, thread):
    """Process all messages from thread"""
    try:
        logger.info("Processing messages...")
        message_count = 0
        photo_count = 0
        
        messages = thread.messages if hasattr(thread, 'messages') else []
        
        for idx, message in enumerate(messages):
            message_count += 1
            
            # Get username
            username = "unknown"
            if hasattr(message, 'user_id'):
                username = f"user_{message.user_id}"
            
            # Log text messages
            if hasattr(message, 'text') and message.text:
                logger.info(f"[{username}] {message.text}")
                self.conversation_data.append({
                    "timestamp": str(message.timestamp),
                    "user": username,
                    "type": "text",
                    "content": message.text
                })
            
            # Handle media (photos only, skip reels)
            if hasattr(message, 'media') and message.media:
                media_type = self._determine_media_type(message.media)
                
                if media_type == "photo":
                    logger.info(f"[{username}] Photo")
                    photo_path = self.download_photo(message.media, idx)
                    self.conversation_data.append({
                        "timestamp": str(message.timestamp),
                        "user": username,
                        "type": "photo",
                        "photo_path": photo_path
                    })
                    photo_count += 1
        
        logger.info(f"Processed {message_count} messages")
        logger.info(f"Downloaded {photo_count} photos")
        return True
    except Exception as e:
        logger.error(f"Failed to process messages: {e}")
        return False
```

**What it does:**

1. Loop through each message
2. Check what type it is (text, photo, reel)
3. For text: Save directly to JSON
4. For photos: Download the file AND save reference in JSON
5. For reels: Skip them completely

---

### 8. Download Photo Function

```python
def download_photo(self, media, message_index):
    """Download photo from message"""
    try:
        if hasattr(media, 'image_versions2'):
            # Download the actual image file
            response = self.client.download_photo(media)
            
            # Create unique filename with timestamp
            timestamp = datetime.now().timestamp()
            filename = f"photo_{message_index}_{timestamp}.jpg"
            filepath = data_dir / filename
            
            # Save to data folder
            with open(filepath, 'wb') as f:
                f.write(response)
            
            logger.info(f"Downloaded photo: {filename}")
            return str(filepath)
    except Exception as e:
        logger.warning(f"Failed to download photo: {e}")
        return None
```

**What it does:**

1. Get the photo URL from the message
2. Download the actual image file
3. Save it to `data/` folder with a unique name
4. Return the file path (so we can reference it in JSON)

---

### 9. Save to JSON

```python
def save_conversation_data(self):
    """Save all conversation data to JSON"""
    try:
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"conversation_{self.friend_username}_{timestamp}.json"
        filepath = data_dir / filename
        
        # Save all conversation data to JSON file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.conversation_data, f, indent=2, 
                     ensure_ascii=False)
        
        logger.info(f"Conversation data saved to {filepath}")
        return True
    except Exception as e:
        logger.error(f"Failed to save: {e}")
        return False
```

**What JSON looks like:**

```json
[
  {
    "timestamp": "2026-01-07 07:18:38.386555+00:00",
    "user": "user_564826454",
    "type": "text",
    "content": "chilling hahha"
  },
  {
    "timestamp": "2026-01-07 07:18:32.940024+00:00",
    "user": "user_2130174857",
    "type": "text",
    "content": "what u doing"
  }
]
```

**Why JSON?**

- ✅ Human-readable (you can open and read it)
- ✅ Machine-readable (programs can parse it)
- ✅ Structured (organized data)
- ✅ Standard format (works everywhere)

---

## API & Pagination

### Understanding Rate Limiting

**Rate limiting** = Instagram limiting how fast you can make requests

**Why?**

- If you make 1000 requests per second = Instagram thinks you're a bot
- Instagram blocks you to protect their servers
- Real users can only make so many requests per second

**How instagrapi handles it:**

- Adds **1-second delay** between requests automatically
- This makes requests look "human" (like a real person slowly scrolling)
- Instead of: Request, Request, Request (instant)
- It does: Request, Wait 1s, Request, Wait 1s, Request

### Pagination Limits

**Instagram's limitations:**
- Returns 20 messages per request (not configurable)
- Some accounts may not have all history available
- Deleted messages don't appear
- Very old messages might not be accessible

**Time calculation:**

```
If you have 1000 messages:
  1000 messages / 20 per request = 50 requests
  50 requests * 1 second delay = 50 seconds minimum
  + Network/response time = ~2 minutes total

If you have 5000 messages:
  5000 / 20 = 250 requests
  250 * 1 = 250 seconds
  + overhead = ~5 minutes total
```

---

## Data Storage

### File Structure

```
Instagram_Logging/
├── main.py                                    # Main program
├── requirements.txt                           # What to install
├── .env                                       # Your credentials (SECRET!)
├── .env.example                              # Template
├── README.md                                 # Usage guide
├── DOCUMENTATION.md                          # This file
│
├── data/
│   ├── conversation_melanie.ig__20260107_184911.json    # All messages
│   ├── photo_0_1234567.jpg                  # Downloaded photo 1
│   ├── photo_1_1234568.jpg                  # Downloaded photo 2
│   └── photo_2_1234569.jpg                  # Downloaded photo 3
│
└── logs/
    └── dm_logger_20260107.log                # What the program did
```

### JSON File Format

```json
[
  {
    "timestamp": "2026-01-07 07:18:38.386555+00:00",  // When sent
    "user": "user_564826454",                         // Who sent it
    "type": "text",                                   // Message type
    "content": "chilling hahha"                       // The message
  },
  {
    "timestamp": "2026-01-07 07:17:51.247510+00:00",
    "user": "user_2130174857",
    "type": "photo",
    "photo_path": "data/photo_5_1234567.jpg"
  },
  {
    "timestamp": "2026-01-07 07:17:47.919987+00:00",
    "user": "user_2130174857",
    "type": "reel",
    "content": "(reel skipped)"
  }
]
```

### How to Use the JSON File

**Open with any text editor:**
- Notepad, VS Code, Sublime Text, etc.
- Just open `conversation_melanie.ig__20260107_184911.json`

**Search for messages:**
- Ctrl+F to find text
- Search for "pizza" to find all messages about pizza

**Load into Python:**

```python
import json

with open("data/conversation_melanie.ig__20260107_184911.json") as f:
    messages = json.load(f)

for msg in messages:
    print(f"{msg['user']}: {msg['content']}")
```

**Load into Excel:**
- Open the JSON file in Excel (it will parse the data)
- Create a spreadsheet with all messages

---

## Security & Privacy

### Why .env File?

**NEVER put credentials in the code:**

❌ Bad:
```python
username = "_ivan_tran_"
password = "Bdeajfh19203"
```

✅ Good:
```python
from dotenv import load_dotenv
import os
username = os.getenv("INSTAGRAM_USERNAME")
password = os.getenv("INSTAGRAM_PASSWORD")
```

**Why?**

- If you upload to GitHub: Your password is exposed
- If someone gets access to your computer: Only .env is visible, not the code
- You can change password without changing code

### Data Privacy

Your data is stored **locally on your computer**:
- ✅ Nobody can see your messages except you
- ✅ Instagram can't see that you logged them
- ✅ You own the data completely
- ✅ Safe from Instagram deletions

---

## Common Questions

### Q: Is this legal?

A: Using your own account to log your own messages is legal. Reading terms of service: Instagram allows automated access via official APIs for personal use.

### Q: Will Instagram ban me?

A: Very unlikely if:
- You only log messages with 1 friend
- You run it occasionally (not 24/7)
- You use official library (instagrapi)

Avoid:
- Logging thousands of accounts
- Making 1000s of requests per minute
- Selling the data

### Q: How do I find message count?

A: After running, check the log message:
```
✓ Successfully loaded 1,523 messages from complete history
```

Then calculate: `1,523 / 20 messages per request * 1 second = ~76 seconds`

### Q: Can I log multiple friends?

A: Yes! Duplicate the program or add a loop to run it for multiple usernames.

### Q: What if I get rate limited?

A: Instagram might slow you down or block temporarily. Just wait an hour and try again.

### Q: Can I download videos?

A: Currently skips them. To enable: Modify `_determine_media_type()` function.

---

## Learning Resources

If you want to understand more:

1. **Python Basics**
   - Variables, loops, functions: codecademy.com

2. **APIs**
   - How APIs work: youtube.com (search "REST API explained")

3. **JSON**
   - json.org - Learn JSON format

4. **Instagram API**
   - Instagrapi GitHub: github.com/subzeroid/instagrapi
   - Source code shows how everything works

---

**That's it!** You now understand how the entire program works from start to finish. Happy logging! 📱💾
