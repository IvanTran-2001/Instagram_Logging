import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import os
from zoneinfo import ZoneInfo

# Load environment variables to get usernames
load_dotenv()
YOUR_USERNAME = os.getenv("INSTAGRAM_USERNAME", "unknown")
FRIEND_USERNAME = os.getenv("FRIEND_USERNAME", "unknown")

def convert_json_to_markdown(json_file):
    """Convert Instagram DM conversation JSON to readable Markdown format"""
    
    json_path = Path(json_file)
    
    if not json_path.exists():
        print(f"Error: File not found - {json_file}")
        return
    
    print(f"📖 Reading conversation from {json_path.name}...")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            messages = json.load(f)
    except json.JSONDecodeError:
        print("Error: Invalid JSON file")
        return
    except Exception as e:
        print(f"Error reading file: {e}")
        return
    
    # Create output markdown file in same folder as JSON
    output_path = json_path.parent / "conversation.md"
    
    print(f"✍️  Converting to Markdown...")
    
    # Count stats
    text_count = sum(1 for m in messages if m.get('type') == 'text')
    media_count = sum(1 for m in messages if m.get('type') in ['photo', 'video', 'multi_media', 'album', 'shared_album', 'shared_photo'])
    other_count = len(messages) - text_count - media_count
    
    with open(output_path, 'w', encoding='utf-8') as f:
        # Write header
        f.write(f"# Chat with {FRIEND_USERNAME}\n\n")
        f.write(f"**Total:** {len(messages)} | **Text:** {text_count} | **Media:** {media_count} | **Other:** {other_count}\n\n")
        f.write("---\n\n")
        
        # Reverse messages to go from oldest to newest
        messages_sorted = reversed(messages)
        
        # Write each message
        for msg in messages_sorted:
            user_id = msg.get('user', 'unknown')
            timestamp = msg.get('timestamp', 'N/A')
            msg_type = msg.get('type', 'unknown')
            
            # Determine if this is you or the client (fixed mapping)
            if user_id == "user_564826454":
                username = "Ivan"
            else:
                username = "Phuong Anh"
            
            # Format timestamp nicely (Australian format: DD/MM/YYYY HH:MM in Melbourne time)
            try:
                if timestamp and timestamp != 'N/A':
                    dt = datetime.fromisoformat(timestamp.replace('+00:00', '+00:00'))
                    # Convert UTC to Melbourne time (AEDT/AEST)
                    melbourne_tz = ZoneInfo('Australia/Melbourne')
                    dt_melbourne = dt.replace(tzinfo=ZoneInfo('UTC')).astimezone(melbourne_tz)
                    timestamp = dt_melbourne.strftime('%d/%m/%Y %H:%M')
            except:
                timestamp = "N/A"
            
            # Write message based on type
            if msg_type == 'text':
                content = msg.get('content', '(empty)').strip()
                # Check if content is short enough for one line
                if username == "Phuong Anh":
                    # Use blockquote for Phuong Anh
                    if len(content) < 60 and '\n' not in content:
                        f.write(f"> `{timestamp}` **{username}** {content}\n\n")
                    else:
                        f.write(f"> `{timestamp}` **{username}**\n> {content}\n\n")
                else:
                    # Ivan's messages (normal)
                    if len(content) < 60 and '\n' not in content:
                        f.write(f"`{timestamp}` **{username}** {content}\n\n")
                    else:
                        f.write(f"`{timestamp}` **{username}**\n{content}\n\n")
            
            elif msg_type == 'photo':
                photo_path = msg.get('photo_path', 'unknown')
                photo_name = Path(photo_path).name if photo_path else "unknown"
                if username == "Phuong Anh":
                    f.write(f"> `{timestamp}` **{username}** 📸 {photo_name}\n\n")
                else:
                    f.write(f"`{timestamp}` **{username}** 📸 {photo_name}\n\n")
            
            elif msg_type == 'video':
                video_path = msg.get('video_path', 'unknown')
                video_name = Path(video_path).name if video_path else "unknown"
                if username == "Phuong Anh":
                    f.write(f"> `{timestamp}` **{username}** 🎬 {video_name}\n\n")
                else:
                    f.write(f"`{timestamp}` **{username}** 🎬 {video_name}\n\n")
            
            elif msg_type == 'multi_media':
                media_items = msg.get('media_items', [])
                item_count = len(media_items)
                if username == "Phuong Anh":
                    f.write(f"> `{timestamp}` **{username}** 📸 {item_count} items:\n")
                    for item in media_items:
                        item_name = Path(item.get('path', '')).name
                        emoji = "🎬" if item.get('type') == 'video' else "📸"
                        f.write(f">   {emoji} {item_name}\n")
                    f.write("\n")
                else:
                    f.write(f"`{timestamp}` **{username}** 📸 {item_count} items:\n")
                    for item in media_items:
                        item_name = Path(item.get('path', '')).name
                        emoji = "🎬" if item.get('type') == 'video' else "📸"
                        f.write(f"  {emoji} {item_name}\n")
                    f.write("\n")
            
            elif msg_type == 'album':
                photo_paths = msg.get('photo_paths', [])
                if photo_paths:
                    if username == "Phuong Anh":
                        f.write(f"> `{timestamp}` **{username}** 📚 Album ({len(photo_paths)} photos):\n")
                        for photo_path in photo_paths:
                            photo_name = Path(photo_path).name
                            f.write(f">   📸 {photo_name}\n")
                        f.write("\n")
                    else:
                        f.write(f"`{timestamp}` **{username}** 📚 Album ({len(photo_paths)} photos):\n")
                        for photo_path in photo_paths:
                            photo_name = Path(photo_path).name
                            f.write(f"  📸 {photo_name}\n")
                        f.write("\n")
                else:
                    content = msg.get('content', '[album]')
                    if username == "Phuong Anh":
                        f.write(f"> `{timestamp}` **{username}** 📚 {content}\n\n")
                    else:
                        f.write(f"`{timestamp}` **{username}** 📚 {content}\n\n")
            
            elif msg_type == 'shared_album':
                photo_paths = msg.get('photo_paths', [])
                if username == "Phuong Anh":
                    f.write(f"> `{timestamp}` **{username}** 🔗 Shared Album ({len(photo_paths)} photos):\n")
                    for photo_path in photo_paths:
                        photo_name = Path(photo_path).name
                        f.write(f">   📸 {photo_name}\n")
                    f.write("\n")
                else:
                    f.write(f"`{timestamp}` **{username}** 🔗 Shared Album ({len(photo_paths)} photos):\n")
                    for photo_path in photo_paths:
                        photo_name = Path(photo_path).name
                        f.write(f"  📸 {photo_name}\n")
                    f.write("\n")
            
            elif msg_type == 'shared_photo':
                photo_path = msg.get('photo_path', 'unknown')
                photo_name = Path(photo_path).name if photo_path else "unknown"
                if username == "Phuong Anh":
                    f.write(f"> `{timestamp}` **{username}** 🔗 Shared: {photo_name}\n\n")
                else:
                    f.write(f"`{timestamp}` **{username}** 🔗 Shared: {photo_name}\n\n")
            
            elif msg_type == 'story_share':
                if username == "Phuong Anh":
                    f.write(f"> `{timestamp}` **{username}** 📖 Shared a story\n\n")
                else:
                    f.write(f"`{timestamp}` **{username}** 📖 Shared a story\n\n")
            
            elif msg_type == 'felix_share':
                if username == "Phuong Anh":
                    f.write(f"> `{timestamp}` **{username}** 🎬 Shared a reel\n\n")
                else:
                    f.write(f"`{timestamp}` **{username}** 🎬 Shared a reel\n\n")
            
            elif msg_type == 'voice_media':
                if username == "Phuong Anh":
                    f.write(f"> `{timestamp}` **{username}** 🎤 Voice message\n\n")
                else:
                    f.write(f"`{timestamp}` **{username}** 🎤 Voice message\n\n")
            
            elif msg_type == 'animated_media':
                if username == "Phuong Anh":
                    f.write(f"> `{timestamp}` **{username}** 🎆 GIF/animated media\n\n")
                else:
                    f.write(f"`{timestamp}` **{username}** 🎆 GIF/animated media\n\n")
            
            elif msg_type == 'link':
                content = msg.get('content', '[link]')
                url = msg.get('url', '')
                if username == "Phuong Anh":
                    f.write(f"> `{timestamp}` **{username}** 🔗 {content}\n")
                    if url:
                        f.write(f">   {url}\n")
                    f.write("\n")
                else:
                    f.write(f"`{timestamp}` **{username}** 🔗 {content}\n")
                    if url:
                        f.write(f"  {url}\n")
                    f.write("\n")
            
            else:
                # Catch-all for any other message type
                content = msg.get('content', f'[{msg_type}]')
                if username == "Phuong Anh":
                    f.write(f"> `{timestamp}` **{username}** {content}\n\n")
                else:
                    f.write(f"`{timestamp}` **{username}** {content}\n\n")
    
    print(f"✅ Done! Saved to: {output_path.name}")
    print(f"📊 {len(messages)} total | {text_count} text | {media_count} media | {other_count} other")


def find_latest_conversation():
    """Find the most recently created conversation folder"""
    data_dir = Path("data")
    
    if not data_dir.exists():
        print("Error: data/ directory not found")
        return None
    
    # Look for conversation_* folders
    conversation_folders = [d for d in data_dir.iterdir() if d.is_dir() and d.name.startswith("conversation_")]
    
    if not conversation_folders:
        print("Error: No conversation folders found in data/")
        return None
    
    # Sort by creation time, get the latest
    latest = sorted(conversation_folders, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    json_file = latest / "conversation.json"
    
    if json_file.exists():
        return json_file
    else:
        return None


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # User provided a file
        json_file = sys.argv[1]
    else:
        # Find latest conversation file
        json_file = find_latest_conversation()
        if json_file:
            print(f"Found: {json_file.name}")
        else:
            print("\nUsage: python view_conversation.py [path/to/conversation.json]")
            sys.exit(1)
    
    convert_json_to_markdown(json_file)
