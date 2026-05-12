from flask import Flask, render_template, request, redirect, url_for
from youtube_transcript_api import YouTubeTranscriptApi
from langchain_google_genai import ChatGoogleGenerativeAI
import googleapiclient.discovery
import os
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize AI model and YouTube API using your keys from .env
model = ChatGoogleGenerativeAI(model='gemini-2.5-flash-lite')
api_key = os.getenv('GOOGLE_API_KEY')
api_key_yt = os.getenv('YOUTUBE_API_KEY')
youtube = googleapiclient.discovery.build('youtube', 'v3', developerKey=api_key_yt)

# A simple temporary database to hold transcripts and summaries in memory
video_database = {}

@app.route('/', methods=['GET'])
def index():
    # Show the homepage where users enter the link
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    link = request.form['video_url']
    
    # 1. Slice video_id from the yt link (Your logic)
    if '&' in link:
        end_index = link.index('&')
    else:
        end_index = None
    
    try:
        video_id = link[link.index('v=')+2:end_index]
    except ValueError:
        video_id = link.split('/')[-1].split('?')[0] # Backup logic for short links
        
    # 2. Fetch the subtitle
    yt_api = YouTubeTranscriptApi()
    transcript_list = yt_api.fetch(video_id, languages=['en','en-IN','hi'])
    full_text = ' '.join([d['text'] for d in transcript_list.to_raw_data()])

    # 3. Get Video details using YouTube API (Your logic)
    req = youtube.videos().list(part='snippet', id=video_id)
    response = req.execute()
    
    title = 'Video Summary'
    thumbnail_url = ''
    links_list = []
    
    if 'items' in response and len(response['items']) > 0:
        video_snippet = response['items'][0]['snippet']
        title = video_snippet.get('title', 'Video Summary')
        description = video_snippet.get('description', '')
        
        thumbnails = video_snippet.get('thumbnails', {})
        thumbnail_url = thumbnails.get('maxres', {}).get('url', '') or thumbnails.get('high', {}).get('url', '')
        
        link_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
        links_list = re.findall(link_pattern, description)

    # 4. Prompt for generating summary
    prompt1 = f'Create a concise, well-structured, and attractive summary of the following text: {full_text}. Use clear sections or bullet points. Do not use markdown code blocks.'
    result = model.invoke(prompt1)
    summary = result.content

    # 5. Save all this data temporarily in our dictionary using the video_id as the key
    video_database[video_id] = {
        'title': title,
        'thumbnail_url': thumbnail_url,
        'summary': summary,
        'links_list': links_list,
        'full_text': full_text
    }

    # Redirect the user to the video page
    return redirect(url_for('video_page', video_id=video_id))

@app.route('/video/<video_id>', methods=['GET', 'POST'])
def video_page(video_id):
    # Retrieve the saved data for this video
    data = video_database.get(video_id)
    
    if not data:
        return "Video data not found. Please try submitting the link again."

    ai_answer = ""

    # If the user submits a question from the form on this page
    if request.method == 'POST':
        user_question = request.form['question']
        
        # Ask Gemini using the saved full_text transcript
        prompt2 = f"Here is a video transcript: {data['full_text']}\n\nAnswer this question accurately based only on the transcript: {user_question}"
        result = model.invoke(prompt2)
        ai_answer = result.content

    # Render the Jinja2 template with Tailwind CSS
    return render_template('video.html', data=data, ai_answer=ai_answer)

if __name__ == '__main__':
    app.run(debug=True)