/**
 * Client-Side Transcription Service
 * Uses Whisper model via transformers.js to process audio in the browser
 * This reduces server load and allows users to process audio on their own hardware
 */

import { pipeline } from '@xenova/transformers';

class ClientSideTranscriptionService {
  constructor() {
    this.transcriber = null;
    this.modelLoaded = false;
    this.isLoading = false;
  }

  /**
   * Initialize the Whisper model
   * Downloads model to browser cache (39MB for tiny, 75MB for base)
   * @param {string} modelSize - 'tiny', 'base', 'small' (default: 'tiny' for speed)
   * @param {function} onProgress - Callback for download progress
   */
  async initialize(modelSize = 'tiny', onProgress = null) {
    if (this.modelLoaded) {
      return this.transcriber;
    }

    if (this.isLoading) {
      // Wait for existing initialization
      while (this.isLoading) {
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      return this.transcriber;
    }

    this.isLoading = true;

    try {
      const modelName = `Xenova/whisper-${modelSize}.en`;
      
      this.transcriber = await pipeline(
        'automatic-speech-recognition',
        modelName,
        {
          progress_callback: (progress) => {
            if (onProgress && progress.status) {
              const percent = progress.progress || 0;
              const status = progress.status;
              onProgress({ 
                percent: Math.round(percent), 
                status,
                message: `${status}: ${Math.round(percent)}%`
              });
            }
          }
        }
      );

      this.modelLoaded = true;
      this.isLoading = false;
      return this.transcriber;
    } catch (error) {
      this.isLoading = false;
      console.error('Failed to load Whisper model:', error);
      throw new Error(`Model loading failed: ${error.message}`);
    }
  }

  /**
   * Transcribe audio file in the browser
   * @param {File} audioFile - The audio file to transcribe
   * @param {object} options - Transcription options
   * @param {function} onProgress - Progress callback
   * @returns {Promise<object>} Transcription result with segments
   */
  async transcribe(audioFile, options = {}, onProgress = null) {
    if (!this.modelLoaded) {
      throw new Error('Model not loaded. Call initialize() first.');
    }

    try {
      // Read audio file as ArrayBuffer
      const arrayBuffer = await audioFile.arrayBuffer();
      
      // Convert to format expected by transformers.js
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
      
      // Extract audio data (mono, 16kHz as expected by Whisper)
      const audioData = this.resampleAndConvertToMono(audioBuffer);

      // Transcribe with timestamps
      onProgress?.({ status: 'transcribing', percent: 10, message: 'Transcribing audio...' });
      
      const result = await this.transcriber(audioData, {
        chunk_length_s: 30, // Process in 30-second chunks
        stride_length_s: 5, // 5-second overlap
        return_timestamps: true,
        ...options
      });

      onProgress?.({ status: 'processing', percent: 90, message: 'Processing segments...' });

      // Convert to format matching server response
      const segments = this.formatSegments(result);

      onProgress?.({ status: 'complete', percent: 100, message: 'Complete!' });

      return {
        all_segments: segments,
        text: result.text,
        repetitive_groups: [],
        potential_repetitive_groups: []
      };
    } catch (error) {
      console.error('Transcription error:', error);
      throw new Error(`Transcription failed: ${error.message}`);
    }
  }

  /**
   * Resample audio to 16kHz mono (required by Whisper)
   */
  resampleAndConvertToMono(audioBuffer) {
    const sampleRate = 16000; // Whisper expects 16kHz
    const numberOfChannels = audioBuffer.numberOfChannels;
    const length = audioBuffer.length;
    const resampleLength = Math.floor(length * sampleRate / audioBuffer.sampleRate);
    
    // Get mono channel data
    let monoData = new Float32Array(resampleLength);
    
    if (numberOfChannels === 1) {
      monoData = this.resampleBuffer(audioBuffer.getChannelData(0), resampleLength);
    } else {
      // Mix down to mono
      const leftChannel = audioBuffer.getChannelData(0);
      const rightChannel = audioBuffer.getChannelData(1);
      const mixed = new Float32Array(length);
      
      for (let i = 0; i < length; i++) {
        mixed[i] = (leftChannel[i] + rightChannel[i]) / 2;
      }
      
      monoData = this.resampleBuffer(mixed, resampleLength);
    }
    
    return monoData;
  }

  /**
   * Simple linear resampling
   */
  resampleBuffer(buffer, targetLength) {
    if (buffer.length === targetLength) {
      return buffer;
    }

    const result = new Float32Array(targetLength);
    const ratio = buffer.length / targetLength;

    for (let i = 0; i < targetLength; i++) {
      const sourceIndex = i * ratio;
      const index = Math.floor(sourceIndex);
      const frac = sourceIndex - index;

      if (index + 1 < buffer.length) {
        result[i] = buffer[index] * (1 - frac) + buffer[index + 1] * frac;
      } else {
        result[i] = buffer[index];
      }
    }

    return result;
  }

  /**
   * Format segments to match server API format
   */
  formatSegments(result) {
    if (!result.chunks || result.chunks.length === 0) {
      return [];
    }

    return result.chunks.map((chunk, index) => ({
      id: index,
      start: chunk.timestamp[0] || 0,
      end: chunk.timestamp[1] || 0,
      text: chunk.text.trim(),
      speaker: null // Client-side doesn't do speaker diarization
    }));
  }

  /**
   * Check if browser supports required features
   */
  static isSupported() {
    const hasAudioContext = !!(window.AudioContext || window.webkitAudioContext);
    const hasArrayBuffer = typeof ArrayBuffer !== 'undefined';
    const hasFloat32Array = typeof Float32Array !== 'undefined';
    
    return hasAudioContext && hasArrayBuffer && hasFloat32Array;
  }

  /**
   * Get estimated model download size
   */
  static getModelSize(modelSize = 'tiny') {
    const sizes = {
      'tiny': 39,   // MB
      'base': 75,   // MB
      'small': 244, // MB
    };
    return sizes[modelSize] || sizes['tiny'];
  }
}

// Singleton instance
const transcriptionService = new ClientSideTranscriptionService();

export default transcriptionService;
export { ClientSideTranscriptionService };
