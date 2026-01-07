import os
import json
import logging
import time
import requests
import traceback
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from instagrapi import Client
from instagrapi.types import DirectMessage

# Load environment variables
load_dotenv()

# Setup logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / f"dm_logger_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Setup data directory
data_dir = Path("data")
data_dir.mkdir(exist_ok=True)


class InstagramDMLogger:
    def __init__(self):
        self.username = os.getenv("INSTAGRAM_USERNAME")
        self.password = os.getenv("INSTAGRAM_PASSWORD")
        self.friend_username = os.getenv("FRIEND_USERNAME")
        self.client = None
        self.message_count = 0
        self.photo_count = 0
        self.conversation_folder = None  # Will be set during run()
        
    def login(self):
        """Login to Instagram"""
        try:
            logger.info(f"Logging in as {self.username}...")
            self.client = Client()
            
            try:
                self.client.login(self.username, self.password)
                logger.info("Successfully logged in!")
                return True
            except Exception as e:
                if "challenge" in str(e).lower() or "two" in str(e).lower():
                    logger.info("Two-Factor Authentication detected!")
                    logger.info("Instagram is asking for a 2FA code...")
                    
                    # Prompt user for 2FA code
                    code = input("Enter your 2FA code: ")
                    
                    try:
                        # Try to complete the challenge with the code
                        self.client.login(self.username, self.password, verification_code=code)
                        logger.info("Successfully logged in with 2FA!")
                        return True
                    except Exception as e2:
                        logger.error(f"2FA verification failed: {e2}")
                        return False
                else:
                    raise e
                    
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False
    
    def get_friend_id(self):
        """Get the friend's user ID"""
        try:
            logger.info(f"Searching for user: {self.friend_username}")
            user = self.client.user_info_by_username(self.friend_username)
            logger.info(f"Found user ID: {user.pk}")
            return user.pk
        except Exception as e:
            logger.error(f"Failed to find user {self.friend_username}: {e}")
            return None
    
    def get_conversation(self, user_id, message_limit=50000):
        """Get all messages from conversation with friend"""
        try:
            logger.info(f"Fetching conversation with user ID: {user_id}")
            threads = self.client.direct_threads()
            
            for thread in threads:
                if user_id in [user.pk for user in thread.users]:
                    logger.info(f"Found conversation thread")
                    # Fetch messages with the specified limit
                    logger.info(f"Fetching up to {message_limit} messages (this may take a while)...")
                    self._fetch_all_messages_cursor(thread, message_limit)
                    return thread
            
            logger.warning("Conversation not found")
            return None
        except Exception as e:
            logger.error(f"Failed to get conversation: {e}")
            return None
    
    def _fetch_all_messages_cursor(self, thread, message_limit=50000):
        """Fetch messages using instagrapi's built-in direct_thread method"""
        try:
            # Get the correct thread ID attribute
            thread_id = thread.id if hasattr(thread, 'id') else thread.thread_id
            logger.info(f"Fetching up to {message_limit} messages from thread {thread_id}...")
            logger.info("Using instagrapi's built-in pagination...")
            
            # Use the built-in method which handles all pagination internally
            full_thread = self.client.direct_thread(thread_id, amount=message_limit)
            
            if full_thread and hasattr(full_thread, 'messages'):
                thread.messages = full_thread.messages
                logger.info(f"✓ Successfully loaded {len(thread.messages)} messages\n")
                return True
            else:
                logger.warning("No messages found in thread")
                return False
            
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def download_photo(self, media, message_index):
        """Download photo from message using thumbnail URL"""
        try:
            # DirectMessage media objects have thumbnail_url, not image_versions2
            if hasattr(media, 'thumbnail_url') and media.thumbnail_url:
                url = str(media.thumbnail_url)
                
                # Create unique filename with timestamp (milliseconds)
                filename = f"photo_{message_index}_{int(datetime.now().timestamp() * 1000)}.jpg"
                # Save to conversation folder
                filepath = self.conversation_folder / filename
                
                # Download directly from URL
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                logger.info(f"Downloaded photo: {filename}")
                return str(filepath)
            
            return None
        except Exception as e:
            logger.warning(f"Failed to download photo {message_index}: {e}")
            traceback.print_exc()
            return None
    
    def download_video(self, media, message_index):
        """Download video/reel from message using video URL"""
        try:
            if hasattr(media, 'video_url') and media.video_url:
                url = str(media.video_url)
                
                # Create unique filename with timestamp (milliseconds)
                filename = f"video_{message_index}_{int(datetime.now().timestamp() * 1000)}.mp4"
                # Save to conversation folder
                filepath = self.conversation_folder / filename
                
                # Download directly from URL
                response = requests.get(url, timeout=30)  # Videos take longer
                response.raise_for_status()
                
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                logger.info(f"Downloaded video: {filename} ({len(response.content)} bytes)")
                return str(filepath)
            
            return None
        except Exception as e:
            logger.warning(f"Failed to download video {message_index}: {e}")
            return None
    
    def process_messages(self, thread):
        """Process all messages from thread and write to file immediately"""
        try:
            logger.info("Processing messages and saving to file...")
            self.message_count = 0
            self.photo_count = 0
            
            messages = thread.messages if hasattr(thread, 'messages') else []
            
            if not messages:
                logger.warning("No messages to process")
                return False
            
            # Create conversation folder
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.conversation_folder = data_dir / f"conversation_{self.friend_username}_{timestamp}"
            self.conversation_folder.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Saving conversation to: {self.conversation_folder}\n")
            
            # Open file for writing JSON in the conversation folder
            filepath = self.conversation_folder / "conversation.json"
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("[\n")  # Start JSON array
                
                for idx, message in enumerate(messages):
                    self.message_count += 1
                    
                    # Get username efficiently
                    username = f"user_{message.user_id}" if hasattr(message, 'user_id') else "unknown"
                    
                    # Build message entry
                    message_entry = None
                    
                    # Check for text message
                    if hasattr(message, 'text') and message.text:
                        message_entry = {
                            "timestamp": str(message.timestamp) if hasattr(message, 'timestamp') else None,
                            "user": username,
                            "type": "text",
                            "content": message.text
                        }
                    
                    # Check for media
                    elif hasattr(message, 'media') and message.media:
                        media_type = self._determine_media_type(message.media)
                        
                        if media_type == "photo":
                            photo_path = self.download_photo(message.media, idx)
                            if photo_path:
                                message_entry = {
                                    "timestamp": str(message.timestamp) if hasattr(message, 'timestamp') else None,
                                    "user": username,
                                    "type": "photo",
                                    "photo_path": photo_path
                                }
                                self.photo_count += 1
                        elif media_type == "reel":
                            video_path = self.download_video(message.media, idx)
                            if video_path:
                                message_entry = {
                                    "timestamp": str(message.timestamp) if hasattr(message, 'timestamp') else None,
                                    "user": username,
                                    "type": "reel",
                                    "video_path": video_path
                                }
                                self.photo_count += 1  # Count as media item
                            else:
                                message_entry = {
                                    "timestamp": str(message.timestamp) if hasattr(message, 'timestamp') else None,
                                    "user": username,
                                    "type": "reel",
                                    "content": "(reel download failed)"
                                }
                        elif media_type == "video":
                            video_path = self.download_video(message.media, idx)
                            if video_path:
                                message_entry = {
                                    "timestamp": str(message.timestamp) if hasattr(message, 'timestamp') else None,
                                    "user": username,
                                    "type": "video",
                                    "video_path": video_path
                                }
                                self.photo_count += 1
                            else:
                                message_entry = {
                                    "timestamp": str(message.timestamp) if hasattr(message, 'timestamp') else None,
                                    "user": username,
                                    "type": "video",
                                    "content": "(video download failed)"
                                }
                    
                    # Write to file immediately if we have data
                    if message_entry:
                        json.dump(message_entry, f, ensure_ascii=False)
                        # Add comma between entries, but not after last one
                        if idx < len(messages) - 1:
                            f.write(",\n")
                        else:
                            f.write("\n")
                    
                    # Progress every 100 messages
                    if (idx + 1) % 100 == 0:
                        logger.info(f"Processed {self.message_count} messages...")
                
                f.write("]")  # End JSON array
            
            logger.info(f"✓ Processed {self.message_count} messages, downloaded {self.photo_count} media items")
            logger.info(f"Conversation folder: {self.conversation_folder}")
            logger.info(f"\n📁 All files saved to: {self.conversation_folder}")
            logger.info(f"   - conversation.json (all messages + media)")
            logger.info(f"   - photo_*.jpg (photos)")
            logger.info(f"   - video_*.mp4 (videos & reels)")
            logger.info(f"   - Run 'python view_conversation.py' to create conversation.md\n")
            return True
            
        except Exception as e:
            logger.error(f"Failed to process messages: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _determine_media_type(self, media):
        """Determine if media is a photo or reel"""
        try:
            if hasattr(media, 'media_type'):
                # 1 = Photo, 2 = Video, 8 = Album, 11 = Reel
                if media.media_type == 11:
                    return "reel"
                elif media.media_type == 1:
                    return "photo"
            
            # Fallback check
            if hasattr(media, 'video_duration'):
                return "reel"
            return "photo"
        except:
            return "photo"
    
    def save_conversation_data(self):
        """Data is already saved during processing, just log summary"""
        logger.info("All data has been saved to file")
    
    def run(self):
        """Main execution flow"""
        # Ask user how many messages to fetch
        print("\n📊 How many messages to fetch?")
        print("   Enter a number (e.g., 100, 1000)")
        print("   Enter -1 to fetch ALL messages (recommended for full backup)")
        
        try:
            message_limit = int(input("   Messages to fetch: "))
        except ValueError:
            print("❌ Invalid input! Using default of 1000 messages")
            message_limit = 1000
        
        if message_limit == -1:
            message_limit = 50000  # Instagram's practical limit
            print("📥 Fetching ALL messages (up to 50,000)\n")
        else:
            print(f"📥 Fetching {message_limit} messages\n")
        
        start_time = time.time()
        logger.info("=== Instagram DM Logger Started ===")
        logger.info(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Message limit: {message_limit}")
        
        login_start = time.time()
        if not self.login():
            return False
        login_time = time.time() - login_start
        logger.info(f"Login completed in {login_time:.2f} seconds\n")
        
        search_start = time.time()
        friend_id = self.get_friend_id()
        if not friend_id:
            return False
        search_time = time.time() - search_start
        logger.info(f"User search completed in {search_time:.2f} seconds\n")
        
        fetch_start = time.time()
        thread = self.get_conversation(friend_id, message_limit)
        if not thread:
            return False
        fetch_time = time.time() - fetch_start
        logger.info(f"Message fetching completed in {fetch_time:.2f} seconds\n")
        
        process_start = time.time()
        if self.process_messages(thread):
            process_time = time.time() - process_start
            logger.info(f"Message processing completed in {process_time:.2f} seconds\n")
            
            total_time = time.time() - start_time
            logger.info("=== Instagram DM Logger Completed ===")
            logger.info(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"\n--- TIMING SUMMARY ---")
            logger.info(f"Login: {login_time:.2f}s")
            logger.info(f"Search: {search_time:.2f}s")
            logger.info(f"Fetch: {fetch_time:.2f}s")
            logger.info(f"Process: {process_time:.2f}s")
            logger.info(f"TOTAL: {total_time:.2f}s ({total_time/60:.2f} minutes)")
            logger.info(f"-------------------\n")
            return True
        
        return False


if __name__ == "__main__":
    dm_logger = InstagramDMLogger()
    dm_logger.run()
