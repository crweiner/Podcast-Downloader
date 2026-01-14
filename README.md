# Podcast RSS Feed Downloader

A Python script that downloads all episodes from a podcast RSS feed, extracts metadata, and organizes everything into neatly structured folders.

## Features

- Downloads all MP3/audio files from any podcast RSS feed (including LibSyn)
- Extracts comprehensive metadata (title, description, duration, episode number, etc.)
- Preserves HTML formatting in descriptions (links, formatting, etc.)
- Organizes episodes into numbered folders
- Downloads show and episode artwork
- Supports resuming interrupted downloads (skips existing files)
- Configurable episode range

## Installation

### Prerequisites
- Python 3.7 or higher
- pip (usually comes with Python)

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/a8cteam51/Podcast-Downloader.git
   cd podcast-downloader
   ```

2. **Create a virtual environment:**
   
   On macOS/Linux:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
   
   On Windows:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Deactivating the Virtual Environment

When you're done, deactivate the virtual environment:
```bash
deactivate
```

### Troubleshooting

- **Python version issues:** Ensure you're using Python 3.7+ by running `python3 --version` (or `python --version` on Windows)
- **Permission errors:** If you get permission errors, you may be installing globally. Always use a virtual environment.
- **Import errors:** Make sure the virtual environment is activated (you should see `(venv)` in your terminal prompt)

## Usage:

### Download entire podcast

`python3 podcast_downloader.py "https://example.com/feed.xml"`

### Specify output directory

`python3 podcast_downloader.py "https://example.com/feed.xml" -o ~/Podcasts`

### Download only metadata (no audio files)

`python3 podcast_downloader.py "https://example.com/feed.xml" --metadata-only`

### Download specific episode range

`python3 podcast_downloader.py "https://example.com/feed.xml" --start 1 --end 10`

### Skip artwork downloads

`python3 podcast_downloader.py "https://example.com/feed.xml" --skip-artwork`

## Output structure:

```sql
Podcast Name/
├── SHOW_INFO.txt
├── show_artwork.jpg
├── 1 - First Episode Title/
│   ├── metadata.txt
│   └── episode.mp3
├── 2 - Second Episode Title/
│   ├── metadata.txt
│   └── episode.mp3
└── ...
```

## Metatata captured:

Show-level: Title, author, description, categories, artwork, language, copyright, owner info, keywords

Episode-level: Title, description (with HTML), publication date, duration, season/episode numbers, episode type, artwork, enclosure URL/size/type, keywords, transcript URL, chapters URL

## Options:

| Flag | Description |
| ---- | ----------- |
| `-o, --output` | Output directory (default: current directory) |
| `--metadata-only` | Skip audio downloads, only save metadata |
| `--start N` | Start from episode number N |
| `--end N` | Stop at episode number N |
| `--skip-artwork` | Skip downloading artwork images |


## License: 
MIT