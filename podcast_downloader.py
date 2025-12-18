#!/usr/bin/env python3
"""
Podcast RSS Feed Downloader
Downloads all episodes from a podcast RSS feed, extracts metadata,
and organizes them into folders.

Usage: python podcast_downloader.py <RSS_FEED_URL>
"""

import os
import sys
import re
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, unquote
from html import unescape
from datetime import datetime
import json
import argparse
import time

# Namespace definitions commonly used in podcast RSS feeds
NAMESPACES = {
    'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd',
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'atom': 'http://www.w3.org/2005/Atom',
    'googleplay': 'http://www.google.com/schemas/play-podcasts/1.0',
    'podcast': 'https://podcastindex.org/namespace/1.0',
    'rawvoice': 'http://www.rawvoice.com/rawvoiceRssModule/',
    'media': 'http://search.yahoo.com/mrss/',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'sy': 'http://purl.org/rss/1.0/modules/syndication/',
}


def sanitize_filename(filename):
    """Remove or replace invalid characters for filenames."""
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')
    # Replace multiple spaces with single space
    filename = re.sub(r'\s+', ' ', filename)
    # Trim whitespace
    filename = filename.strip()
    # Limit length
    if len(filename) > 200:
        filename = filename[:200]
    return filename


def get_text(element, xpath, namespaces=None, default=''):
    """Safely extract text from an XML element."""
    if element is None:
        return default
    
    found = element.find(xpath, namespaces)
    if found is not None and found.text:
        return unescape(found.text.strip())
    return default


def get_attr(element, xpath, attr, namespaces=None, default=''):
    """Safely extract attribute from an XML element."""
    if element is None:
        return default
    
    found = element.find(xpath, namespaces)
    if found is not None:
        return found.get(attr, default)
    return default


def parse_duration(duration_str):
    """Parse duration string (HH:MM:SS or seconds) to readable format."""
    if not duration_str:
        return ''
    
    # If it's already in HH:MM:SS format
    if ':' in duration_str:
        return duration_str
    
    # If it's in seconds
    try:
        total_seconds = int(duration_str)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    except ValueError:
        return duration_str


def get_show_metadata(channel):
    """Extract show-level metadata from the RSS feed channel."""
    show_data = {
        'title': get_text(channel, 'title'),
        'description': get_text(channel, 'description'),
        'link': get_text(channel, 'link'),
        'language': get_text(channel, 'language'),
        'copyright': get_text(channel, 'copyright'),
        'last_build_date': get_text(channel, 'lastBuildDate'),
        'pub_date': get_text(channel, 'pubDate'),
        'generator': get_text(channel, 'generator'),
        'managing_editor': get_text(channel, 'managingEditor'),
        'webmaster': get_text(channel, 'webMaster'),
        
        # iTunes specific
        'itunes_author': get_text(channel, 'itunes:author', NAMESPACES),
        'itunes_subtitle': get_text(channel, 'itunes:subtitle', NAMESPACES),
        'itunes_summary': get_text(channel, 'itunes:summary', NAMESPACES),
        'itunes_owner_name': get_text(channel, 'itunes:owner/itunes:name', NAMESPACES),
        'itunes_owner_email': get_text(channel, 'itunes:owner/itunes:email', NAMESPACES),
        'itunes_image': get_attr(channel, 'itunes:image', 'href', NAMESPACES),
        'itunes_explicit': get_text(channel, 'itunes:explicit', NAMESPACES),
        'itunes_type': get_text(channel, 'itunes:type', NAMESPACES),
        'itunes_keywords': get_text(channel, 'itunes:keywords', NAMESPACES),
        'itunes_new_feed_url': get_text(channel, 'itunes:new-feed-url', NAMESPACES),
        
        # Categories
        'itunes_categories': [],
        
        # Google Play
        'googleplay_author': get_text(channel, 'googleplay:author', NAMESPACES),
        'googleplay_description': get_text(channel, 'googleplay:description', NAMESPACES),
        'googleplay_image': get_attr(channel, 'googleplay:image', 'href', NAMESPACES),
        'googleplay_explicit': get_text(channel, 'googleplay:explicit', NAMESPACES),
        
        # Standard image
        'image_url': get_text(channel, 'image/url'),
        'image_title': get_text(channel, 'image/title'),
        'image_link': get_text(channel, 'image/link'),
        
        # Raw Voice
        'rawvoice_rating': get_text(channel, 'rawvoice:rating', NAMESPACES),
        'rawvoice_location': get_text(channel, 'rawvoice:location', NAMESPACES),
        'rawvoice_frequency': get_text(channel, 'rawvoice:frequency', NAMESPACES),
    }
    
    # Get categories
    for category in channel.findall('itunes:category', NAMESPACES):
        cat_text = category.get('text', '')
        if cat_text:
            show_data['itunes_categories'].append(cat_text)
            # Check for subcategories
            for subcat in category.findall('itunes:category', NAMESPACES):
                subcat_text = subcat.get('text', '')
                if subcat_text:
                    show_data['itunes_categories'].append(f"  └─ {subcat_text}")
    
    return show_data


def get_episode_metadata(item):
    """Extract episode-level metadata from an RSS item."""
    episode_data = {
        'title': get_text(item, 'title'),
        'description': get_text(item, 'description'),
        'link': get_text(item, 'link'),
        'guid': get_text(item, 'guid'),
        'guid_is_permalink': get_attr(item, 'guid', 'isPermaLink'),
        'pub_date': get_text(item, 'pubDate'),
        'author': get_text(item, 'author'),
        'comments': get_text(item, 'comments'),
        
        # Enclosure (media file)
        'enclosure_url': get_attr(item, 'enclosure', 'url'),
        'enclosure_length': get_attr(item, 'enclosure', 'length'),
        'enclosure_type': get_attr(item, 'enclosure', 'type'),
        
        # iTunes specific
        'itunes_title': get_text(item, 'itunes:title', NAMESPACES),
        'itunes_author': get_text(item, 'itunes:author', NAMESPACES),
        'itunes_subtitle': get_text(item, 'itunes:subtitle', NAMESPACES),
        'itunes_summary': get_text(item, 'itunes:summary', NAMESPACES),
        'itunes_duration': parse_duration(get_text(item, 'itunes:duration', NAMESPACES)),
        'itunes_explicit': get_text(item, 'itunes:explicit', NAMESPACES),
        'itunes_episode': get_text(item, 'itunes:episode', NAMESPACES),
        'itunes_season': get_text(item, 'itunes:season', NAMESPACES),
        'itunes_episode_type': get_text(item, 'itunes:episodeType', NAMESPACES),
        'itunes_image': get_attr(item, 'itunes:image', 'href', NAMESPACES),
        'itunes_keywords': get_text(item, 'itunes:keywords', NAMESPACES),
        'itunes_block': get_text(item, 'itunes:block', NAMESPACES),
        
        # Content encoded (full HTML description)
        'content_encoded': get_text(item, 'content:encoded', NAMESPACES),
        
        # Google Play
        'googleplay_description': get_text(item, 'googleplay:description', NAMESPACES),
        'googleplay_explicit': get_text(item, 'googleplay:explicit', NAMESPACES),
        'googleplay_image': get_attr(item, 'googleplay:image', 'href', NAMESPACES),
        
        # Podcast 2.0 namespace
        'podcast_transcript': get_attr(item, 'podcast:transcript', 'url', NAMESPACES),
        'podcast_chapters': get_attr(item, 'podcast:chapters', 'url', NAMESPACES),
        
        # DC namespace
        'dc_creator': get_text(item, 'dc:creator', NAMESPACES),
    }
    
    return episode_data


def download_file(url, filepath, retries=3, chunk_size=8192):
    """Download a file with progress indication and retry logic."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f"\r  Downloading: {percent:.1f}% ({downloaded}/{total_size} bytes)", end='')
            
            print()  # New line after download complete
            return True
            
        except requests.RequestException as e:
            print(f"\n  Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                print(f"  Retrying in 5 seconds...")
                time.sleep(5)
    
    return False


def save_metadata_file(metadata, filepath):
    """Save metadata to a formatted text file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("PODCAST EPISODE METADATA\n")
        f.write("=" * 80 + "\n\n")
        
        # Basic info
        f.write("BASIC INFORMATION\n")
        f.write("-" * 40 + "\n")
        f.write(f"Title: {metadata.get('title', 'N/A')}\n")
        if metadata.get('itunes_title'):
            f.write(f"iTunes Title: {metadata.get('itunes_title')}\n")
        f.write(f"Publication Date: {metadata.get('pub_date', 'N/A')}\n")
        f.write(f"Author: {metadata.get('author') or metadata.get('itunes_author') or 'N/A'}\n")
        f.write(f"Link: {metadata.get('link', 'N/A')}\n")
        f.write(f"GUID: {metadata.get('guid', 'N/A')}\n")
        f.write("\n")
        
        # Episode info
        f.write("EPISODE DETAILS\n")
        f.write("-" * 40 + "\n")
        f.write(f"Season Number: {metadata.get('itunes_season') or 'N/A'}\n")
        f.write(f"Episode Number: {metadata.get('itunes_episode') or 'N/A'}\n")
        f.write(f"Episode Type: {metadata.get('itunes_episode_type') or 'full'}\n")
        f.write(f"Duration: {metadata.get('itunes_duration') or 'N/A'}\n")
        f.write(f"Explicit: {metadata.get('itunes_explicit') or 'N/A'}\n")
        f.write("\n")
        
        # Media file info
        f.write("MEDIA FILE\n")
        f.write("-" * 40 + "\n")
        f.write(f"URL: {metadata.get('enclosure_url', 'N/A')}\n")
        f.write(f"Type: {metadata.get('enclosure_type', 'N/A')}\n")
        file_size = metadata.get('enclosure_length', '')
        if file_size:
            try:
                size_mb = int(file_size) / (1024 * 1024)
                f.write(f"Size: {size_mb:.2f} MB ({file_size} bytes)\n")
            except ValueError:
                f.write(f"Size: {file_size}\n")
        f.write("\n")
        
        # Artwork
        f.write("ARTWORK\n")
        f.write("-" * 40 + "\n")
        f.write(f"Episode Image (iTunes): {metadata.get('itunes_image') or 'N/A'}\n")
        f.write(f"Episode Image (Google Play): {metadata.get('googleplay_image') or 'N/A'}\n")
        f.write("\n")
        
        # Subtitle/Summary
        f.write("SUBTITLE\n")
        f.write("-" * 40 + "\n")
        f.write(f"{metadata.get('itunes_subtitle') or 'N/A'}\n")
        f.write("\n")
        
        # Keywords
        if metadata.get('itunes_keywords'):
            f.write("KEYWORDS\n")
            f.write("-" * 40 + "\n")
            f.write(f"{metadata.get('itunes_keywords')}\n")
            f.write("\n")
        
        # Description (with HTML preserved)
        f.write("DESCRIPTION\n")
        f.write("-" * 40 + "\n")
        f.write(f"{metadata.get('description') or 'N/A'}\n")
        f.write("\n")
        
        # Content encoded (full HTML show notes)
        if metadata.get('content_encoded'):
            f.write("CONTENT ENCODED (Show Notes)\n")
            f.write("-" * 40 + "\n")
            f.write(f"{metadata.get('content_encoded')}\n")
            f.write("\n")
        
        # iTunes Summary (with HTML preserved)
        if metadata.get('itunes_summary'):
            f.write("ITUNES SUMMARY\n")
            f.write("-" * 40 + "\n")
            f.write(f"{metadata.get('itunes_summary')}\n")
            f.write("\n")
        
        # Google Play Description (with HTML preserved)
        if metadata.get('googleplay_description'):
            f.write("GOOGLE PLAY DESCRIPTION\n")
            f.write("-" * 40 + "\n")
            f.write(f"{metadata.get('googleplay_description')}\n")
            f.write("\n")
        
        # Transcript/Chapters links
        if metadata.get('podcast_transcript') or metadata.get('podcast_chapters'):
            f.write("ADDITIONAL RESOURCES\n")
            f.write("-" * 40 + "\n")
            if metadata.get('podcast_transcript'):
                f.write(f"Transcript URL: {metadata.get('podcast_transcript')}\n")
            if metadata.get('podcast_chapters'):
                f.write(f"Chapters URL: {metadata.get('podcast_chapters')}\n")
            f.write("\n")
        
        # Raw JSON metadata for programmatic access
        f.write("\n" + "=" * 80 + "\n")
        f.write("RAW METADATA (JSON)\n")
        f.write("=" * 80 + "\n")
        f.write(json.dumps(metadata, indent=2, ensure_ascii=False))


def save_show_metadata(show_data, output_dir):
    """Save show-level metadata to a file."""
    filepath = os.path.join(output_dir, "SHOW_INFO.txt")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("PODCAST SHOW INFORMATION\n")
        f.write("=" * 80 + "\n\n")
        
        f.write("BASIC INFORMATION\n")
        f.write("-" * 40 + "\n")
        f.write(f"Title: {show_data.get('title', 'N/A')}\n")
        f.write(f"Author: {show_data.get('itunes_author') or 'N/A'}\n")
        f.write(f"Website: {show_data.get('link', 'N/A')}\n")
        f.write(f"Language: {show_data.get('language', 'N/A')}\n")
        f.write(f"Copyright: {show_data.get('copyright', 'N/A')}\n")
        f.write(f"Show Type: {show_data.get('itunes_type') or 'episodic'}\n")
        f.write(f"Explicit: {show_data.get('itunes_explicit') or 'N/A'}\n")
        f.write("\n")
        
        f.write("OWNER INFORMATION\n")
        f.write("-" * 40 + "\n")
        f.write(f"Owner Name: {show_data.get('itunes_owner_name') or 'N/A'}\n")
        f.write(f"Owner Email: {show_data.get('itunes_owner_email') or 'N/A'}\n")
        f.write("\n")
        
        f.write("CATEGORIES\n")
        f.write("-" * 40 + "\n")
        if show_data.get('itunes_categories'):
            for cat in show_data['itunes_categories']:
                f.write(f"{cat}\n")
        else:
            f.write("N/A\n")
        f.write("\n")
        
        f.write("ARTWORK\n")
        f.write("-" * 40 + "\n")
        f.write(f"iTunes Image: {show_data.get('itunes_image') or 'N/A'}\n")
        f.write(f"Standard Image: {show_data.get('image_url') or 'N/A'}\n")
        f.write(f"Google Play Image: {show_data.get('googleplay_image') or 'N/A'}\n")
        f.write("\n")
        
        f.write("KEYWORDS\n")
        f.write("-" * 40 + "\n")
        f.write(f"{show_data.get('itunes_keywords') or 'N/A'}\n")
        f.write("\n")
        
        f.write("DESCRIPTION\n")
        f.write("-" * 40 + "\n")
        f.write(f"{show_data.get('description', 'N/A')}\n")
        f.write("\n")
        
        if show_data.get('itunes_summary'):
            f.write("ITUNES SUMMARY\n")
            f.write("-" * 40 + "\n")
            f.write(f"{show_data.get('itunes_summary')}\n")
            f.write("\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("RAW METADATA (JSON)\n")
        f.write("=" * 80 + "\n")
        f.write(json.dumps(show_data, indent=2, ensure_ascii=False))
    
    return filepath


def download_artwork(url, output_dir, filename="show_artwork"):
    """Download podcast artwork."""
    if not url:
        return None
    
    try:
        # Determine extension from URL or content type
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()
        
        if '.png' in path:
            ext = '.png'
        elif '.jpg' in path or '.jpeg' in path:
            ext = '.jpg'
        else:
            ext = '.jpg'  # Default to jpg
        
        filepath = os.path.join(output_dir, f"{filename}{ext}")
        
        if download_file(url, filepath):
            return filepath
    except Exception as e:
        print(f"  Warning: Could not download artwork: {e}")
    
    return None


def main():
    parser = argparse.ArgumentParser(
        description='Download all episodes from a podcast RSS feed',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python podcast_downloader.py https://example.com/feed.xml
  python podcast_downloader.py https://example.com/feed.xml -o ~/Podcasts
  python podcast_downloader.py https://example.com/feed.xml --metadata-only
  python podcast_downloader.py https://example.com/feed.xml --start 1 --end 10
        """
    )
    parser.add_argument('feed_url', help='URL of the podcast RSS feed')
    parser.add_argument('-o', '--output', default='.', help='Output directory (default: current directory)')
    parser.add_argument('--metadata-only', action='store_true', help='Only download metadata, skip audio files')
    parser.add_argument('--start', type=int, default=1, help='Start from episode number (default: 1)')
    parser.add_argument('--end', type=int, default=None, help='End at episode number (default: all)')
    parser.add_argument('--skip-artwork', action='store_true', help='Skip downloading artwork')
    
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print("PODCAST RSS FEED DOWNLOADER")
    print(f"{'='*60}\n")
    
    # Fetch RSS feed
    print(f"Fetching RSS feed: {args.feed_url}")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(args.feed_url, headers=headers, timeout=30)
        response.raise_for_status()
        feed_content = response.content
    except requests.RequestException as e:
        print(f"Error fetching feed: {e}")
        sys.exit(1)
    
    # Parse RSS feed
    print("Parsing RSS feed...")
    try:
        # Register namespaces to preserve them
        for prefix, uri in NAMESPACES.items():
            ET.register_namespace(prefix, uri)
        
        root = ET.fromstring(feed_content)
        channel = root.find('channel')
        
        if channel is None:
            print("Error: Invalid RSS feed - no channel element found")
            sys.exit(1)
    except ET.ParseError as e:
        print(f"Error parsing feed: {e}")
        sys.exit(1)
    
    # Get show metadata
    show_data = get_show_metadata(channel)
    show_title = sanitize_filename(show_data['title']) or 'Podcast'
    print(f"Found podcast: {show_data['title']}")
    
    # Create output directory
    output_dir = os.path.join(args.output, show_title)
    os.makedirs(output_dir, exist_ok=True)
    print(f"Output directory: {output_dir}")
    
    # Save show metadata
    print("\nSaving show information...")
    save_show_metadata(show_data, output_dir)
    
    # Download show artwork
    if not args.skip_artwork and show_data.get('itunes_image'):
        print("Downloading show artwork...")
        download_artwork(show_data['itunes_image'], output_dir, "show_artwork")
    
    # Get all episodes
    items = channel.findall('item')
    total_episodes = len(items)
    print(f"\nFound {total_episodes} episodes in feed")
    
    if total_episodes == 0:
        print("No episodes found!")
        sys.exit(0)
    
    # Determine range
    start_idx = max(0, args.start - 1)
    end_idx = args.end if args.end else total_episodes
    end_idx = min(end_idx, total_episodes)
    
    print(f"Processing episodes {args.start} to {end_idx}")
    print(f"\n{'='*60}\n")
    
    # Process episodes (reverse order to start with oldest = episode 1)
    items_reversed = list(reversed(items))
    
    for idx, item in enumerate(items_reversed[start_idx:end_idx], start=args.start):
        episode_data = get_episode_metadata(item)
        
        # Get episode title
        ep_title = episode_data.get('title') or episode_data.get('itunes_title') or f'Episode {idx}'
        ep_title_clean = sanitize_filename(ep_title)
        
        # Create folder name: "1 - Episode Title"
        folder_name = f"{idx} - {ep_title_clean}"
        episode_dir = os.path.join(output_dir, folder_name)
        
        print(f"Episode {idx}/{end_idx}: {ep_title}")
        
        # Create episode directory
        os.makedirs(episode_dir, exist_ok=True)
        
        # Save metadata
        metadata_file = os.path.join(episode_dir, "metadata.txt")
        save_metadata_file(episode_data, metadata_file)
        print(f"  ✓ Saved metadata")
        
        # Download audio file
        if not args.metadata_only and episode_data.get('enclosure_url'):
            audio_url = episode_data['enclosure_url']
            
            # Determine filename
            parsed_url = urlparse(audio_url)
            audio_filename = os.path.basename(unquote(parsed_url.path))
            
            # If filename is empty or weird, create one
            if not audio_filename or len(audio_filename) < 4:
                audio_ext = '.mp3'
                enc_type = episode_data.get('enclosure_type', '')
                if 'mp4' in enc_type or 'm4a' in enc_type:
                    audio_ext = '.m4a'
                elif 'ogg' in enc_type:
                    audio_ext = '.ogg'
                audio_filename = f"{ep_title_clean}{audio_ext}"
            
            audio_path = os.path.join(episode_dir, audio_filename)
            
            # Check if file already exists
            if os.path.exists(audio_path):
                print(f"  ⏭ Audio file already exists, skipping")
            else:
                print(f"  Downloading: {audio_filename}")
                if download_file(audio_url, audio_path):
                    print(f"  ✓ Downloaded audio")
                else:
                    print(f"  ✗ Failed to download audio")
        
        # Download episode artwork if different from show artwork
        if not args.skip_artwork and episode_data.get('itunes_image'):
            ep_artwork = episode_data['itunes_image']
            if ep_artwork != show_data.get('itunes_image'):
                download_artwork(ep_artwork, episode_dir, "episode_artwork")
        
        print()
    
    print(f"{'='*60}")
    print("DOWNLOAD COMPLETE!")
    print(f"{'='*60}")
    print(f"\nAll files saved to: {output_dir}")
    print(f"Total episodes processed: {end_idx - start_idx + 1}")


if __name__ == '__main__':
    main()