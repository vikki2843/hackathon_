from flask import Flask, request, jsonify,render_template
import os
from google.cloud import storage, speech_v1p1beta1 as speech, translate_v2 as translate, texttospeech
from moviepy.editor import *

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

# Set up Google Cloud credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "C:/Users/paivi/OneDrive/Desktop/Haackathon_2.0/hackathon-399515-5efe51419b00.json"

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/upload', methods=['POST'])
def upload_file():
    # Check if video file is in request
    if 'video' not in request.files:
        return jsonify({'error': 'No video file in request'}), 400

    video = request.files['video']
    language = request.form.get('language')
    voiceType = request.form.get('voiceType')

    if video.filename == '':
        return jsonify({'error': 'No video file selected'}), 400

    video_path = os.path.join(app.config['UPLOAD_FOLDER'], video.filename)
    video.save(video_path)

    # Process video here (Translate and dub)
    translated_video_url = translate_and_dub_video(video_path, language, voiceType)

    return jsonify({'video_url': translated_video_url})

def upload_to_gcs(file_path, bucket_name):
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(os.path.basename(file_path))
    blob.upload_from_filename(file_path)
    return blob.public_url

def download_from_gcs(blob_url, destination):
    storage_client = storage.Client()
    bucket = storage_client.bucket(blob_url.split('/')[2])
    blob = bucket.blob('/'.join(blob_url.split('/')[3:]))
    blob.download_to_filename(destination)

def extract_audio_from_video(video_path, audio_path):
    video = VideoFileClip(video_path)
    audio = video.audio
    audio.write_audiofile(audio_path)

def speech_to_text(audio_path, language_code):
    client = speech.SpeechClient()
    with open(audio_path, 'rb') as audio_file:
        content = audio_file.read()

    audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=44100,
        language_code=language_code
    )
    response = client.recognize(config=config, audio=audio)

    return ''.join([result.alternatives[0].transcript for result in response.results])

def translate_text(text, target_language):
    client = translate.Client()
    result = client.translate(text, target_language=target_language)
    return result['translatedText']

def text_to_speech(text, language_code, voice_type):
    client = texttospeech.TextToSpeechClient()

    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        ssml_gender=texttospeech.SsmlVoiceGender[voice_type]
    )
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)

    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )

    # Save audio to file
    with open("output.mp3", "wb") as out:
        out.write(response.audio_content)

    return "output.mp3"

def merge_audio_to_video(video_path, audio_path, output_path):
    video = VideoFileClip(video_path)
    audio = AudioFileClip(audio_path)
    final_video = video.set_audio(audio)
    final_video.write_videofile(output_path)

def translate_and_dub_video(video_path, language, voiceType):
    # Step 1: Extract audio
    audio_path = "extracted_audio.wav"
    extract_audio_from_video(video_path, audio_path)

    # Step 2: Convert audio to text
    text = speech_to_text(audio_path, "en-US")  # Assuming source is English

    # Step 3: Translate text
    translated_text = translate_text(text, language)

    # Step 4: Convert translated text to audio
    dubbed_audio_path = text_to_speech(translated_text, language, voiceType)

    # Step 5: Combine audio with video
    output_video_path = "translated_video.mp4"
    merge_audio_to_video(video_path, dubbed_audio_path, output_video_path)

    return output_video_path

if __name__ == '__main__':
    app.run(debug=True)
