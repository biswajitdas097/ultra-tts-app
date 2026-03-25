import streamlit as st
import os
import json
import uuid
import zipfile
import tempfile
from tts_engine import TTSEngine

st.set_page_config(page_title="Ultra TTS Generator Pro", layout="wide", page_icon="🎙️")

st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #1e1e2d 0%, #151521 100%);
    color: white;
}
.stButton>button {
    background-color: #2e5cff;
    color: white;
    border-radius: 8px;
    border: none;
    padding: 0.5rem 1rem;
    font-weight: 600;
}
.stButton>button:hover {
    background-color: #1a43d6;
}
</style>
""", unsafe_allow_html=True)

VOICE_OPTIONS_MALE = [
    "en-US-Journey-D", "en-US-Journey-J", "en-US-Casual-K", "en-US-Standard-B", 
    "en-US-Standard-D", "en-US-Standard-I", "en-US-Standard-J", "en-US-Wavenet-B", 
    "en-US-Wavenet-D", "en-US-Wavenet-I", "en-US-Wavenet-J", "en-US-Neural2-A", 
    "en-US-Neural2-D", "en-US-Neural2-I", "en-US-Neural2-J"
]

VOICE_OPTIONS_FEMALE = [
    "en-US-Journey-F", "en-US-Journey-O", "en-US-Standard-A", "en-US-Standard-C", 
    "en-US-Standard-E", "en-US-Standard-F", "en-US-Standard-G", "en-US-Standard-H", 
    "en-US-Wavenet-A", "en-US-Wavenet-C", "en-US-Wavenet-E", "en-US-Wavenet-F", 
    "en-US-Wavenet-G", "en-US-Wavenet-H", "en-US-Neural2-C"
]

def init_session():
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if 'output_dir' not in st.session_state:
        st.session_state.output_dir = os.path.join(tempfile.gettempdir(), f"tts_{st.session_state.session_id}")
        os.makedirs(st.session_state.output_dir, exist_ok=True)
    if 'generated_files' not in st.session_state:
        st.session_state.generated_files = []

init_session()

st.title("🎙️ Ultra TTS Generator Pro")
st.markdown("Generate long-form text-to-speech high quality audio using Google Cloud TTS.")

st.sidebar.header("⚙️ Configuration")
creds_file = st.sidebar.file_uploader("Upload GCP Service Account JSON", type=['json'])

if creds_file:
    try:
        creds_json = json.load(creds_file)
        st.session_state.creds_json = creds_json
        st.sidebar.success("Credentials Loaded Successfully!")
    except Exception as e:
        st.sidebar.error("Invalid JSON file.")

st.sidebar.subheader("Voice Settings")
gender = st.sidebar.radio("Voice Gender", ["Female", "Male"])
voice_choices = VOICE_OPTIONS_FEMALE if gender == "Female" else VOICE_OPTIONS_MALE
selected_voice = st.sidebar.selectbox("Select Voice Model", voice_choices)

speed = st.sidebar.slider("Speaking Rate (Speed)", min_value=0.25, max_value=4.0, value=1.0, step=0.1)
pitch = st.sidebar.slider("Pitch", min_value=-20.0, max_value=20.0, value=0.0, step=1.0)
style_emotion = st.sidebar.selectbox("Style/Emotion (Best on Journey models)", ["Neutral", "Happy", "Sad", "Calm", "Energetic"])
st.sidebar.info("Emotion is dynamically handled by Pitch/Speed configuration for standard voices or via 'Journey' models directly.")

script_input = st.text_area("📄 Paste your script here (Long-form supported):", height=250)
uploaded_script = st.file_uploader("Or upload a text file (.txt)", type=["txt"])
if uploaded_script:
    script_input = uploaded_script.read().decode('utf-8')

col1, col2 = st.columns(2)

if col1.button("🚀 Generate Full Audio"):
    if not hasattr(st.session_state, 'creds_json'):
        st.error("Please upload your Google Cloud credentials JSON first in the sidebar.")
    elif not script_input.strip():
        st.error("Script cannot be empty.")
    else:
        try:
            engine = TTSEngine(credentials_json=st.session_state.creds_json)
            with st.spinner("Segmenting script..."):
                segments = engine.split_script(script_input)
                st.info(f"Script split into {len(segments)} segments roughly 700 words each.")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(current, total):
                progress_bar.progress(current / total)
                status_text.text(f"Generation Progress: {current}/{total} segments completed.")

            st.session_state.generated_files = engine.generate_all_parallel(
                text_segments=segments,
                voice_name=selected_voice,
                speed=speed,
                pitch=pitch,
                output_dir=st.session_state.output_dir,
                progress_callback=update_progress
            )
            
            st.success("Generation Complete!")
        except Exception as e:
            st.error(f"Generation failed: {str(e)}")

if col2.button("▶️ Preview First Segment"):
    if not hasattr(st.session_state, 'creds_json'):
        st.error("Please upload your Google Cloud credentials JSON first.")
    elif not script_input.strip():
        st.error("Script cannot be empty.")
    else:
        try:
            engine = TTSEngine(credentials_json=st.session_state.creds_json)
            segments = engine.split_script(script_input)
            preview_text = segments[0] if segments else ""
            with st.spinner("Generating preview..."):
                preview_audio = engine.generate_segment(preview_text, selected_voice, speed, pitch)
                st.audio(preview_audio, format="audio/mp3")
        except Exception as e:
            st.error(f"Preview failed: {str(e)}")

st.divider()

if st.session_state.generated_files:
    st.subheader("📥 Downloads")
    d_col1, d_col2 = st.columns(2)
    
    with d_col1:
        if st.button("Merge & Prepare Single MP3"):
            with st.spinner("Merging audio files... This might take a minute depending on script length."):
                try:
                    merged_path = os.path.join(st.session_state.output_dir, "Full_Audio.mp3")
                    output_path = TTSEngine.merge_audio_files(st.session_state.generated_files, merged_path)
                    
                    with open(output_path, "rb") as f:
                        st.download_button("Download Single MP3", f, file_name="Full_TTS_Audio.mp3", mime="audio/mp3")
                except Exception as e:
                    st.error(f"Merge failed. Ensure ffmpeg is installed for pydub to work securely. Error: {str(e)}")
                    
    with d_col2:
        zip_path = os.path.join(st.session_state.output_dir, "All_Segments.zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file in st.session_state.generated_files:
                zipf.write(file, os.path.basename(file))
                
        with open(zip_path, "rb") as f:
            st.download_button("Download All Segments (ZIP)", f, file_name="All_Segments.zip", mime="application/zip")
