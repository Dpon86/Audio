import whisper
from pydub import AudioSegment
import tkinter as tk
from tkinter import messagebox, Listbox, END

# --- Transcribe audio and get segments ---
model = whisper.load_model("base")
result = model.transcribe("yourfile.wav")
segments = result["segments"]  # Each segment has 'text', 'start', 'end'

# --- GUI to display segments and select for deletion ---
class SegmentEditor(tk.Tk):
    def __init__(self, segments):
        super().__init__()
        self.title("Audio Segment Editor")
        self.geometry("600x400")
        self.segments = segments
        self.to_delete = []

        self.listbox = Listbox(self, selectmode=tk.MULTIPLE, width=80)
        for i, seg in enumerate(segments):
            display = f"{i+1}: [{seg['start']:.2f}s - {seg['end']:.2f}s] {seg['text']}"
            self.listbox.insert(END, display)
        self.listbox.pack(pady=10, fill=tk.BOTH, expand=True)

        self.delete_btn = tk.Button(self, text="Delete Selected Segments", command=self.delete_segments)
        self.delete_btn.pack(pady=10)

    def delete_segments(self):
        selected_indices = self.listbox.curselection()
        self.to_delete = [self.segments[i] for i in selected_indices]
        self.destroy()

# Launch GUI and get segments to delete
app = SegmentEditor(segments)
app.mainloop()
segments_to_delete = app.to_delete

# --- Remove selected segments from audio ---
if segments_to_delete:
    audio = AudioSegment.from_wav("yourfile.wav")
    # Convert times to milliseconds and sort by start time
    delete_ranges = sorted([(int(seg['start']*1000), int(seg['end']*1000)) for seg in segments_to_delete])
    # Remove segments in reverse order to keep indices correct
    for start, end in reversed(delete_ranges):
        audio = audio[:start] + audio[end:]
    audio.export("edited.wav", format="wav")
    print("Edited audio saved as 'edited.wav'.")
else:
    print("No segments selected for deletion.")