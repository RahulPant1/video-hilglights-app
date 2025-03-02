from flask import Flask, request, jsonify
import subprocess
import os
import re

app = Flask(__name__)

def get_video_id(url):
    """Extracts the video ID from a YouTube URL."""
    from urllib.parse import urlparse, parse_qs
    parsed_url = urlparse(url)
    if parsed_url.hostname in ('www.youtube.com', 'youtube.com', 'm.youtube.com'):
        query = parse_qs(parsed_url.query)
        return query.get('v', [None])[0]
    elif parsed_url.hostname == 'youtu.be':
        return parsed_url.path[1:]
    return None

def sanitize_filename(filename):
    """Removes invalid characters for file naming."""
    return re.sub(r'[\\/*?:"<>|]', '', filename)

def extract_plain_text(vtt_file, output_filename):
    """Extracts only the text from a .vtt subtitle file, removes repetitions, and saves to a file."""
    try:
        with open(vtt_file, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        text_lines = []
        seen_sentences = set()  # Track already seen lines

        for line in lines:
            # Remove formatting tags like <c>
            line = re.sub(r"<[^>]+>", "", line).strip()

            # Skip metadata and timestamps
            if "-->" in line or line.startswith(("WEBVTT", "Kind:", "Language:")):
                continue  

            # Avoid adding duplicate lines
            if line and line not in seen_sentences:
                text_lines.append(line)
                seen_sentences.add(line)

        cleaned_text = " ".join(text_lines)  # Convert to a single paragraph

        # Save cleaned transcript to a text file
        with open(output_filename, "w", encoding="utf-8") as output_file:
            output_file.write(cleaned_text)

        return cleaned_text
    except Exception as e:
        return f"Error parsing VTT file: {str(e)}"

def download_transcript(video_url):
    """Downloads YouTube captions and extracts text."""
    try:
        # Get video title
        title_command = ["yt-dlp", "--get-title", video_url]
        title_result = subprocess.run(title_command, capture_output=True, text=True)
        video_title = sanitize_filename(title_result.stdout.strip())

        if not video_title:
            return None, "Failed to retrieve video title"

        # Download transcript
        caption_command = [
            "yt-dlp", "--write-auto-sub", "--sub-lang", "en", "--skip-download",
            "--output", f"{video_title}", video_url
        ]
        subprocess.run(caption_command, check=True)

        # Check if subtitle file exists
        vtt_file = f"{video_title}.en.vtt"
        output_txt_file = f"{video_title}.txt"

        if os.path.exists(vtt_file):
            text_transcript = extract_plain_text(vtt_file, output_txt_file)
            return text_transcript, None
        return None, "Transcript file not found"
    
    except subprocess.CalledProcessError as e:
        return None, f"Error: {str(e)}"

@app.route('/get_transcript', methods=['POST'])
def get_transcript_route():
    """API endpoint to get YouTube transcript."""
    data = request.get_json()
    youtube_url = data.get('youtube_url')

    if not youtube_url:
        return jsonify({'error': 'YouTube URL is required'}), 400

    video_id = get_video_id(youtube_url)
    if not video_id:
        return jsonify({'error': 'Invalid YouTube URL'}), 400

    transcript_text, error = download_transcript(youtube_url)
    if transcript_text:
        return jsonify({'message': 'Transcript retrieved', 'transcript': transcript_text})
    return jsonify({'error': error}), 500

if __name__ == '__main__':
    app.run(debug=True)
