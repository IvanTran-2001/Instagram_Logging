import os
import json
import logging
import time
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from dotenv import load_dotenv
from instagrapi import Client
from dateutil import parser as date_parser

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
        self.conversation_folder = None
        self.photos_folder = None
        self.existing_messages = {}
        self.newest_message_timestamp = None
        self.raw_message_items = {}
        
    def login(self):
        """Login to Instagram"""
        try:
            logger.info(f"Logging in as {self.username}...")
            self.client = Client()
            self.client.login(self.username, self.password)
            logger.info("Successfully logged in!")
            return True
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
    
    def find_or_create_conversation_folder(self):
        """Find existing conversation folder or create a new one"""
        try:
            existing_folders = list(data_dir.glob(f"conversation_{self.friend_username}_*"))
            
            if existing_folders:
                self.conversation_folder = existing_folders[-1]
                logger.info(f"Found existing conversation folder: {self.conversation_folder.name}")
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.conversation_folder = data_dir / f"conversation_{self.friend_username}_{timestamp}"
                self.conversation_folder.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created new conversation folder: {self.conversation_folder.name}")
            
            # Create photos subfolder
            self.photos_folder = self.conversation_folder / "photos"
            self.photos_folder.mkdir(exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Failed to find or create conversation folder: {e}")
            return False
    
    def load_existing_messages(self):
        """Load existing messages from conversation.json"""
        try:
            json_path = self.conversation_folder / "conversation.json"
            
            if not json_path.exists():
                logger.info("No existing messages found")
                return []
            
            with open(json_path, 'r', encoding='utf-8') as f:
                messages = json.load(f)
            
            # Build lookup dict for duplicate detection
            newest_timestamp = None
            for msg in messages:
                timestamp_str = msg.get('timestamp')
                user = msg.get('user')
                msg_type = msg.get('type')
                
                # Parse timestamp for proper comparison
                if timestamp_str:
                    try:
                        from dateutil import parser
                        timestamp_dt = parser.parse(timestamp_str)
                        if newest_timestamp is None or timestamp_dt > newest_timestamp:
                            newest_timestamp = timestamp_dt
                    except:
                        # Fallback to string comparison
                        if newest_timestamp is None or timestamp_str > str(newest_timestamp):
                            newest_timestamp = timestamp_str
                
                # Create unique key for duplicate detection
                if msg_type == 'text':
                    content = msg.get('content', '')[:50]
                else:
                    content = f"media_{msg_type}"
                
                if timestamp_str and user:
                    key = f"{timestamp_str}_{user}_{content}"
                    self.existing_messages[key] = msg
            
            self.newest_message_timestamp = newest_timestamp
            logger.info(f"Loaded {len(messages)} existing messages")
            if newest_timestamp:
                logger.info(f"Newest message timestamp: {newest_timestamp}")
            
            return messages
            
        except Exception as e:
            logger.warning(f"Failed to load existing messages: {e}")
            return []
    
    def fetch_messages(self, user_id, is_first_run):
        """Fetch messages from Instagram with early-stop logic"""
        try:
            logger.info(f"Fetching conversation with user ID: {user_id}")
            threads = self.client.direct_threads()
            
            thread = None
            for t in threads:
                if user_id in [u.pk for u in t.users]:
                    thread = t
                    break
            
            if not thread:
                logger.warning("Conversation not found")
                return None
            
            logger.info("Found conversation thread")
            thread_id = thread.id if hasattr(thread, 'id') else thread.thread_id
            
            # Fetch in batches with early-stop logic
            all_messages = []
            
            if is_first_run:
                logger.info(f"First run - fetching all messages...")
                full_thread = self.client.direct_thread(thread_id, amount=50000)
                all_messages = full_thread.messages if hasattr(full_thread, 'messages') else []
                
                # Fetch raw data in batches for album extraction
                logger.info("Fetching raw data for albums/media...")
                cursor = None
                batch_num = 0
                while batch_num < 2500:  # 50k messages / 20 per batch
                    endpoint = f"direct_v2/threads/{thread_id}/"
                    params = {
                        "visual_message_return_type": "unseen",
                        "direction": "older",
                        "limit": 20
                    }
                    if cursor:
                        params['cursor'] = cursor
                    
                    try:
                        response = self.client.private_request(endpoint, params=params)
                        if 'thread' not in response or 'items' not in response['thread']:
                            break
                        
                        batch_items = response['thread']['items']
                        if not batch_items:
                            break
                        
                        # Store raw items
                        for item in batch_items:
                            if 'item_id' in item:
                                self.raw_message_items[item['item_id']] = item
                        
                        batch_num += 1
                        if batch_num % 100 == 0:
                            logger.info(f"  Fetched raw data batch {batch_num}...")
                        
                        cursor = response['thread'].get('oldest_cursor')
                        if not cursor:
                            break
                        
                        time.sleep(0.5)  # Rate limiting
                    except Exception as e:
                        logger.warning(f"Error fetching raw batch {batch_num}: {e}")
                        break
                
                logger.info(f"Loaded raw data for {len(self.raw_message_items)} messages")
            else:
                logger.info(f"Update run - fetching recent messages with early-stop...")
                
                # Fetch in batches of 20 (Instagram's default)
                cursor = None
                stop_fetching = False
                batch_count = 0
                max_batches = 100  # Safety limit
                new_item_ids = []  # Track new message IDs
                
                while not stop_fetching and batch_count < max_batches:
                    endpoint = f"direct_v2/threads/{thread_id}/"
                    params = {
                        "visual_message_return_type": "unseen",
                        "direction": "older",
                        "limit": 20
                    }
                    if cursor:
                        params['cursor'] = cursor
                    
                    response = self.client.private_request(endpoint, params=params)
                    
                    if 'thread' not in response or 'items' not in response['thread']:
                        break
                    
                    batch_items = response['thread']['items']
                    batch_count += 1
                    logger.info(f"  Batch {batch_count}: {len(batch_items)} messages")
                    
                    # Check each message and only keep new ones
                    for item in batch_items:
                        item_timestamp = item.get('timestamp')
                        item_id = item.get('item_id')
                        
                        if item_timestamp and self.newest_message_timestamp:
                            try:
                                from dateutil import parser
                                from datetime import datetime
                                
                                # Instagram timestamps are microseconds since epoch
                                if isinstance(item_timestamp, (int, float)):
                                    item_dt = datetime.fromtimestamp(item_timestamp / 1000000)
                                else:
                                    item_dt = parser.parse(str(item_timestamp))
                                
                                # Make both timezone-aware for comparison
                                if item_dt.tzinfo is None:
                                    from zoneinfo import ZoneInfo
                                    item_dt = item_dt.replace(tzinfo=ZoneInfo('UTC'))
                                
                                newest_tz_aware = self.newest_message_timestamp
                                if newest_tz_aware.tzinfo is None:
                                    newest_tz_aware = newest_tz_aware.replace(tzinfo=ZoneInfo('UTC'))
                                
                                # If this message is newer than our newest, keep it
                                if item_dt > newest_tz_aware:
                                    if item_id:
                                        new_item_ids.append(item_id)
                                        # Store raw items for album parsing
                                        self.raw_message_items[item_id] = item
                                else:
                                    # Found overlap, stop fetching
                                    logger.info(f"  ✓ Found overlap: API message {item_dt} <= newest logged {newest_tz_aware}")
                                    stop_fetching = True
                                    break
                            except Exception as e:
                                # Log parsing errors for debugging
                                logger.warning(f"  ⚠ Timestamp parsing error: {e} (timestamp: {item_timestamp})")
                                # Keep the message to be safe
                                if item_id:
                                    new_item_ids.append(item_id)
                                    self.raw_message_items[item_id] = item
                        else:
                            # No timestamp or no newest_message_timestamp, keep it
                            if item_id:
                                new_item_ids.append(item_id)
                                self.raw_message_items[item_id] = item
                    
                    # Get next cursor
                    cursor = response['thread'].get('oldest_cursor')
                    if not cursor:
                        break
                    
                    time.sleep(1)  # Rate limiting
                
                logger.info(f"  Found {len(new_item_ids)} new messages to process")
                
                # Convert to DirectMessage objects - fetch all messages and filter to new ones
                full_thread = self.client.direct_thread(thread_id, amount=20 * batch_count)
                all_fetched = full_thread.messages if hasattr(full_thread, 'messages') else []
                
                # Filter to only new messages based on item_ids
                all_messages = [msg for msg in all_fetched if msg.id in new_item_ids]
                logger.info(f"  Filtered to {len(all_messages)} new DirectMessage objects")
            
            # Also ensure raw data is loaded for albums
            try:
                if not self.raw_message_items:
                    endpoint = f"direct_v2/threads/{thread_id}/"
                    params = {
                        "visual_message_return_type": "unseen",
                        "direction": "older",
                        "limit": 100
                    }
                    raw_response = self.client.private_request(endpoint, params=params)
                    
                    if 'thread' in raw_response and 'items' in raw_response['thread']:
                        self.raw_message_items = {
                            item['item_id']: item 
                            for item in raw_response['thread']['items']
                        }
            except Exception as e:
                logger.warning(f"Could not fetch raw data for albums: {e}")
            
            logger.info(f"✓ Fetched {len(all_messages)} messages total\n")
            return all_messages
            
        except Exception as e:
            logger.error(f"Failed to fetch messages: {e}")
            return None
    
    def is_duplicate(self, message):
        """Check if message already exists"""
        timestamp = str(message.timestamp) if hasattr(message, 'timestamp') else None
        username = f"user_{message.user_id}" if hasattr(message, 'user_id') else "unknown"
        
        # Build content key
        if hasattr(message, 'text') and message.text:
            content = message.text[:50]
        elif hasattr(message, 'media') and message.media:
            content = "media_photo"  # Simplified
        elif hasattr(message, 'item_type') and message.item_type == 'generic_xma':
            content = "media_album"
        else:
            content = ""
        
        if timestamp and username:
            key = f"{timestamp}_{username}_{content}"
            return key in self.existing_messages
        
        return False
    
    def convert_to_melbourne_time(self, timestamp_str):
        """Convert UTC timestamp to Melbourne time"""
        if not timestamp_str:
            return None
        try:
            # Parse the timestamp
            dt = date_parser.parse(timestamp_str)
            # Convert to Melbourne timezone
            melbourne_dt = dt.astimezone(ZoneInfo('Australia/Melbourne'))
            return str(melbourne_dt)
        except Exception as e:
            logger.warning(f"Failed to convert timestamp {timestamp_str}: {e}")
            return timestamp_str
    
    def download_photo(self, url, index, message_timestamp=None):
        """Download a photo from URL"""
        try:
            # Use message timestamp if provided, otherwise use current time
            if message_timestamp:
                try:
                    from dateutil import parser
                    timestamp = parser.parse(message_timestamp)
                except:
                    timestamp = datetime.now()
            else:
                timestamp = datetime.now()
            
            timestamp_sort = timestamp.strftime('%Y%m%d_%H%M%S')
            timestamp_human = timestamp.strftime('%d-%b-%Y_%H-%M-%S')
            filename = f"{timestamp_sort}_{timestamp_human}_{index}.jpg"
            filepath = self.photos_folder / filename
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Downloaded: {filename}")
            # Return relative path for JSON
            return f"photos/{filename}"
        except Exception as e:
            logger.warning(f"Failed to download photo: {e}")
            return None
    
    def download_video(self, url, index, message_timestamp=None):
        """Download a video from URL"""
        try:
            # Use message timestamp if provided, otherwise use current time
            if message_timestamp:
                try:
                    from dateutil import parser
                    timestamp = parser.parse(message_timestamp)
                except:
                    timestamp = datetime.now()
            else:
                timestamp = datetime.now()
            
            timestamp_sort = timestamp.strftime('%Y%m%d_%H%M%S')
            timestamp_human = timestamp.strftime('%d-%b-%Y_%H-%M-%S')
            filename = f"{timestamp_sort}_{timestamp_human}_{index}.mp4"
            filepath = self.photos_folder / filename
            
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Downloaded: {filename}")
            # Return relative path for JSON
            return f"photos/{filename}"
        except Exception as e:
            logger.warning(f"Failed to download video: {e}")
            return None
    
    def process_message(self, message, index):
        """Process a single message and return its JSON entry"""
        username = f"user_{message.user_id}" if hasattr(message, 'user_id') else "unknown"
        timestamp_utc = str(message.timestamp) if hasattr(message, 'timestamp') else None
        timestamp = self.convert_to_melbourne_time(timestamp_utc)
        message_id = str(message.id) if hasattr(message, 'id') else None
        
        # Check raw data for visual_media (multiple photos/videos in one message)
        if message_id and message_id in self.raw_message_items:
            raw_item = self.raw_message_items[message_id]
            
            # Handle visual_media array (multiple photos sent together)
            if 'visual_media' in raw_item and raw_item['visual_media']:
                visual_media = raw_item['visual_media']
                if isinstance(visual_media, dict):
                    visual_media = [visual_media]
                
                media_paths = []
                for vm_idx, vm in enumerate(visual_media):
                    media_obj = vm.get('media', {})
                    
                    # Check for video
                    if 'video_versions' in media_obj and media_obj['video_versions']:
                        video_url = media_obj['video_versions'][0].get('url')
                        if video_url:
                            video_path = self.download_video(video_url, f"multi{index}_{vm_idx}", timestamp)
                            if video_path:
                                media_paths.append({"type": "video", "path": video_path})
                    # Check for photo
                    elif 'image_versions2' in media_obj and media_obj['image_versions2']:
                        candidates = media_obj['image_versions2'].get('candidates', [])
                        if candidates:
                            photo_url = candidates[0].get('url')
                            if photo_url:
                                photo_path = self.download_photo(photo_url, f"multi{index}_{vm_idx}", timestamp)
                                if photo_path:
                                    media_paths.append({"type": "photo", "path": photo_path})
                
                if media_paths:
                    return {
                        "timestamp": timestamp,
                        "user": username,
                        "type": "multi_media",
                        "media_items": media_paths,
                        "item_count": len(media_paths)
                    }, len(media_paths)
        
        # Text message
        if hasattr(message, 'text') and message.text:
            return {
                "timestamp": timestamp,
                "user": username,
                "type": "text",
                "content": message.text
            }, 0
        
        # Album/Carousel (generic_xma) - shared posts/reels
        elif hasattr(message, 'item_type') and message.item_type == 'generic_xma':
            album_paths = []
            
            if message_id and message_id in self.raw_message_items:
                raw_item = self.raw_message_items[message_id]
                if 'generic_xma' in raw_item and isinstance(raw_item['generic_xma'], list):
                    for xma_idx, xma in enumerate(raw_item['generic_xma']):
                        if 'preview_url_info' in xma and xma['preview_url_info']:
                            url = xma['preview_url_info'].get('url')
                            if url:
                                photo_path = self.download_photo(url, f"album{index}_{xma_idx}", timestamp)
                                if photo_path:
                                    album_paths.append(photo_path)
            
            if album_paths:
                return {
                    "timestamp": timestamp,
                    "user": username,
                    "type": "album",
                    "photo_paths": album_paths,
                    "item_count": len(album_paths)
                }, len(album_paths)
            else:
                # Log what we found for debugging
                if message_id and message_id in self.raw_message_items:
                    raw_item = self.raw_message_items[message_id]
                    logger.debug(f"Album message {message_id} structure: {list(raw_item.keys())}")
                else:
                    logger.debug(f"Album message {message_id} not found in raw_message_items")
                
                return {
                    "timestamp": timestamp,
                    "user": username,
                    "type": "album",
                    "content": "[album - could not extract photos]"
                }, 0
        
        # Media share (shared posts from feed)
        elif hasattr(message, 'item_type') and message.item_type == 'media_share':
            if message_id and message_id in self.raw_message_items:
                raw_item = self.raw_message_items[message_id]
                if 'media_share' in raw_item:
                    media = raw_item['media_share']
                    
                    # Check for carousel (multiple images)
                    if media.get('carousel_media'):
                        album_paths = []
                        for cm_idx, carousel_item in enumerate(media['carousel_media']):
                            if 'image_versions2' in carousel_item:
                                candidates = carousel_item['image_versions2'].get('candidates', [])
                                if candidates:
                                    url = candidates[0].get('url')
                                    if url:
                                        photo_path = self.download_photo(url, f"share{index}_{cm_idx}", timestamp)
                                        if photo_path:
                                            album_paths.append(photo_path)
                        
                        if album_paths:
                            return {
                                "timestamp": timestamp,
                                "user": username,
                                "type": "shared_album",
                                "photo_paths": album_paths,
                                "item_count": len(album_paths)
                            }, len(album_paths)
                    
                    # Single image share
                    elif 'image_versions2' in media:
                        candidates = media['image_versions2'].get('candidates', [])
                        if candidates:
                            url = candidates[0].get('url')
                            if url:
                                photo_path = self.download_photo(url, index, timestamp)
                                if photo_path:
                                    return {
                                        "timestamp": timestamp,
                                        "user": username,
                                        "type": "shared_photo",
                                        "photo_path": photo_path
                                    }, 1
            
            return {
                "timestamp": timestamp,
                "user": username,
                "type": "shared_media",
                "content": "[shared media - could not extract]"
            }, 0
        
        # Single photo
        elif hasattr(message, 'media') and message.media and hasattr(message.media, 'thumbnail_url') and message.media.thumbnail_url:
            url = str(message.media.thumbnail_url)
            photo_path = self.download_photo(url, index, timestamp)
            
            if photo_path:
                return {
                    "timestamp": timestamp,
                    "user": username,
                    "type": "photo",
                    "photo_path": photo_path
                }, 1
        
        # Video/Reel
        elif hasattr(message, 'media') and message.media and hasattr(message.media, 'video_url') and message.media.video_url:
            url = str(message.media.video_url)
            video_path = self.download_video(url, index, timestamp)
            
            if video_path:
                return {
                    "timestamp": timestamp,
                    "user": username,
                    "type": "video",
                    "video_path": video_path
                }, 1
        
        # Catch-all for any other message types (stories, voice messages, links, reactions, etc.)
        else:
            item_type = getattr(message, 'item_type', 'unknown')
            
            # Try to extract any useful information
            entry = {
                "timestamp": timestamp,
                "user": username,
                "type": item_type,
            }
            
            # Check for various possible content fields
            if hasattr(message, 'link') and message.link:
                entry["content"] = f"[link: {message.link.text if hasattr(message.link, 'text') else 'link'}]"
                entry["url"] = str(message.link.url) if hasattr(message.link, 'url') else None
            elif hasattr(message, 'animated_media') and message.animated_media:
                entry["content"] = "[animated media/GIF]"
            elif hasattr(message, 'voice_media') and message.voice_media:
                entry["content"] = "[voice message]"
            elif hasattr(message, 'story_share') and message.story_share:
                entry["content"] = "[story share]"
            elif hasattr(message, 'felix_share') and message.felix_share:
                entry["content"] = "[reel share]"
            elif hasattr(message, 'clip') and message.clip:
                entry["content"] = "[clip/reel]"
            elif hasattr(message, 'placeholder') and message.placeholder:
                entry["content"] = f"[{message.placeholder.message if hasattr(message.placeholder, 'message') else 'placeholder'}]"
            else:
                # Log unknown type for debugging
                logger.info(f"  Unknown message type '{item_type}' at index {index}")
                entry["content"] = f"[{item_type}]"
                # Store all available attributes for debugging
                entry["debug_attrs"] = [attr for attr in dir(message) if not attr.startswith('_')]
            
            return entry, 0
    
    def save_messages(self, existing_messages, new_message_entries):
        """Save all messages to JSON file with new messages at the top"""
        try:
            filepath = self.conversation_folder / "conversation.json"
            
            # Prepend new messages to the top (newest first)
            all_messages = new_message_entries + existing_messages
            logger.info(f"Preparing to save: {len(new_message_entries)} new + {len(existing_messages)} existing = {len(all_messages)} total")
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(all_messages, f, ensure_ascii=False, indent=2)
            
            # Verify the write
            with open(filepath, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
                actual_count = len(saved_data)
            
            logger.info(f"✓ Saved and verified {actual_count} total messages to file (newest at top)")
            
            if actual_count != len(all_messages):
                logger.error(f"⚠ Save mismatch! Expected {len(all_messages)} but file has {actual_count}")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Failed to save messages: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def run(self):
        """Main execution flow"""
        start_time = time.time()
        logger.info("=== Instagram DM Logger Started ===")
        logger.info(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Step 1: Find/create conversation folder
        if not self.find_or_create_conversation_folder():
            return False
        
        # Step 2: Load existing messages
        existing_messages = self.load_existing_messages()
        is_first_run = len(existing_messages) == 0
        logger.info("")
        
        # Step 3: Login
        login_start = time.time()
        if not self.login():
            return False
        login_time = time.time() - login_start
        logger.info(f"Login completed in {login_time:.2f} seconds\n")
        
        # Step 4: Get friend ID
        search_start = time.time()
        friend_id = self.get_friend_id()
        if not friend_id:
            return False
        search_time = time.time() - search_start
        logger.info(f"User search completed in {search_time:.2f} seconds\n")
        
        # Step 5: Fetch messages
        fetch_start = time.time()
        messages = self.fetch_messages(friend_id, is_first_run)
        if messages is None:
            return False
        fetch_time = time.time() - fetch_start
        logger.info(f"Message fetching completed in {fetch_time:.2f} seconds\n")
        
        # Step 6: Process new messages
        process_start = time.time()
        logger.info("Processing messages...")
        
        new_message_entries = []
        new_media_count = 0
        
        for idx, message in enumerate(messages):
            if self.is_duplicate(message):
                continue
            
            entry, media_count = self.process_message(message, len(existing_messages) + idx)
            if entry:
                new_message_entries.append(entry)
                new_media_count += media_count
            
            # Progress update every 50 messages
            if (idx + 1) % 50 == 0:
                logger.info(f"Processed {idx + 1}/{len(messages)} messages...")
        
        logger.info(f"Found {len(new_message_entries)} new messages\n")
        
        # Step 7: Save to file
        if new_message_entries:
            if not self.save_messages(existing_messages, new_message_entries):
                return False
        else:
            logger.info("No new messages to save")
        
        process_time = time.time() - process_start
        logger.info(f"Processing completed in {process_time:.2f} seconds\n")
        
        # Summary
        total_time = time.time() - start_time
        logger.info("=== Instagram DM Logger Completed ===")
        logger.info(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        logger.info(f"--- SUMMARY ---")
        logger.info(f"✓ New messages added: {len(new_message_entries)}")
        logger.info(f"✓ New media downloaded: {new_media_count}")
        logger.info(f"✓ Total messages: {len(existing_messages) + len(new_message_entries)}")
        logger.info(f"\n--- TIMING ---")
        logger.info(f"Login: {login_time:.2f}s")
        logger.info(f"Search: {search_time:.2f}s")
        logger.info(f"Fetch: {fetch_time:.2f}s")
        logger.info(f"Process: {process_time:.2f}s")
        logger.info(f"TOTAL: {total_time:.2f}s ({total_time/60:.2f} minutes)")
        logger.info(f"-------------------\n")
        
        return True


if __name__ == "__main__":
    dm_logger = InstagramDMLogger()
    dm_logger.run()
