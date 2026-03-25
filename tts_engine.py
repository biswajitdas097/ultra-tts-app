import os
import re
import json
from google.oauth2 import service_account
from google.cloud import texttospeech
import concurrent.futures
from pydub import AudioSegment

class TTSEngine:
    def __init__(self, credentials_json=None):
        if credentials_json:
            try:
                if isinstance(credentials_json, str):
                    creds_dict = json.loads(credentials_json)
                else:
                    creds_dict = credentials_json
                self.credentials = service_account.Credentials.from_service_account_info(creds_dict)
                self.client = texttospeech.TextToSpeechClient(credentials=self.credentials)
            except Exception as e:
                raise ValueError(f"Invalid credentials provided: {e}")
        else:
            self.client = texttospeech.TextToSpeechClient()

    def split_script(self, script, max_words=700):
        """Split script into segments by sentences, max `max_words` per segment."""
        sentences = re.split(r'(?<=[.!?]) +', script)
        chunks = []
        current_chunk = []
        current_word_count = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            words_in_sentence = len(sentence.split())
            if current_word_count + words_in_sentence > max_words and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_word_count = words_in_sentence
            else:
                current_chunk.append(sentence)
                current_word_count += words_in_sentence
                
        if current_chunk:
            chunks.append(" ".join(current_chunk))
            
        return chunks

    def generate_segment(self, text, voice_name, speed=1.0, pitch=0.0):
        """Generate audio for a single text segment using Google Cloud TTS."""
        synthesis_input = texttospeech.SynthesisInput(text=text)

        language_code = "-".join(voice_name.split("-")[:2])
        
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=speed,
            pitch=pitch
        )

        response = self.client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        return response.audio_content

    def generate_all_parallel(self, text_segments, voice_name, speed, pitch, output_dir, max_workers=5, progress_callback=None):
        """Generate audio for all segments in parallel and save to files."""
        os.makedirs(output_dir, exist_ok=True)
        results = []
        
        def process_segment(index, text):
            filename = os.path.join(output_dir, f"segment_{index + 1}.mp3")
            if os.path.exists(filename):
                return filename
                
            audio_content = self.generate_segment(text, voice_name, speed, pitch)
            with open(filename, "wb") as out:
                out.write(audio_content)
            return filename

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(process_segment, i, text): i 
                for i, text in enumerate(text_segments)
            }
            
            completed = 0
            for future in concurrent.futures.as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    filename = future.result()
                    results.append((index, filename))
                except Exception as exc:
                    print(f"Segment {index + 1} generated an exception: {exc}")
                    raise exc
                
                completed += 1
                if progress_callback:
                    progress_callback(completed, len(text_segments))

        results.sort(key=lambda x: x[0])
        return [filename for _, filename in results]

    @staticmethod
    def merge_audio_files(mp3_files, output_filename="merged_output.mp3"):
        """Merge multiple MP3 files into a single MP3 file using pydub."""
        if not mp3_files:
            return None
        
        combined = AudioSegment.empty()
        for mp3_file in mp3_files:
            segment = AudioSegment.from_mp3(mp3_file)
            combined += segment
            
        combined.export(output_filename, format="mp3")
        return output_filename
