"""
Debug script to test photo downloading from Instagram DM
"""
import json
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
import os
from instagrapi import Client
import requests

# Create test folder with timestamp inside data/ directory
data_dir = Path("data")
data_dir.mkdir(exist_ok=True)

test_folder = data_dir / f"test_download_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
test_folder.mkdir(exist_ok=True)

# Load credentials
load_dotenv()
username = os.getenv("INSTAGRAM_USERNAME")
password = os.getenv("INSTAGRAM_PASSWORD")
friend_username = os.getenv("FRIEND_USERNAME")

print(f"🔍 Testing photo download from conversation with {friend_username}\n")
print(f"📁 Saving to: {test_folder}\n")

# Step 1: Login
print("1️⃣ Logging in...")
client = Client()
try:
    client.login(username, password)
    print("✅ Login successful\n")
except Exception as e:
    print(f"❌ Login failed: {e}\n")
    exit(1)

# Step 2: Get friend ID
print("2️⃣ Finding friend ID...")
try:
    user = client.user_info_by_username(friend_username)
    friend_id = user.pk
    print(f"✅ Found friend ID: {friend_id}\n")
except Exception as e:
    print(f"❌ Failed to find friend: {e}\n")
    exit(1)

# Step 3: Get conversation
print("3️⃣ Finding conversation thread...")
try:
    threads = client.direct_threads()
    thread = None
    for t in threads:
        if friend_id in [u.pk for u in t.users]:
            thread = t
            break
    
    if not thread:
        print(f"❌ Conversation not found\n")
        exit(1)
    
    print(f"✅ Found conversation thread\n")
except Exception as e:
    print(f"❌ Failed to find conversation: {e}\n")
    exit(1)

# Step 4: Fetch messages (only first 100 for speed)
print("4️⃣ Fetching first 100 messages (for speed)...")
try:
    thread_id = thread.id if hasattr(thread, 'id') else thread.thread_id
    full_thread = client.direct_thread(thread_id, amount=100)  # Only 100 messages, not 50000
    messages = full_thread.messages if hasattr(full_thread, 'messages') else []
    print(f"✅ Fetched {len(messages)} messages\n")
except Exception as e:
    print(f"❌ Failed to fetch messages: {e}\n")
    exit(1)

# Step 5: Find ALL photo messages
print("5️⃣ Looking for photo messages...")
photo_messages = []
for idx, msg in enumerate(messages):  # Check all fetched messages (should be ~100)
    if hasattr(msg, 'media') and msg.media:
        media = msg.media
        # Check if it's a photo
        if hasattr(media, 'media_type') and media.media_type == 1:
            photo_messages.append((idx, msg))
            print(f"   Found photo at message index {idx}")

if not photo_messages:
    print("❌ No photo messages found in first 100 messages\n")
    exit(1)

print(f"✅ Found {len(photo_messages)} photo messages\n")

# Step 6: Download ALL photos
print("6️⃣ Downloading all photos...\n")
downloaded_count = 0

for msg_idx, photo_message in photo_messages:
    media = photo_message.media
    print(f"📸 Processing photo {downloaded_count + 1}/{len(photo_messages)}...")
    
    if hasattr(media, 'thumbnail_url') and media.thumbnail_url:
        url = str(media.thumbnail_url)
        print(f"   URL: {url[:60]}...")
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Save it with timestamp-based filename
            filename = f"photo_{int(datetime.now().timestamp() * 1000)}.jpg"
            filepath = test_folder / filename
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            print(f"   ✅ Downloaded: {filepath} ({len(response.content)} bytes)\n")
            downloaded_count += 1
            
        except Exception as e:
            print(f"   ❌ Failed: {e}\n")
    else:
        print(f"   ❌ No thumbnail URL available\n")

print(f"✅ Download complete! Downloaded {downloaded_count}/{len(photo_messages)} photos")
