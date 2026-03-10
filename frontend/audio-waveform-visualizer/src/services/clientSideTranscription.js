/**
 * Client-Side Transcription Service
 * Uses Whisper model via transformers.js to process audio in the browser
 * This reduces server load and allows users to process audio on their own hardware
 */

import { pipeline, env } from '@xenova/transformers';

// Configure transformers.js environment
console.log('[ClientTranscription] Configuring transformers.js environment...');

// Explicitly use jsdelivr CDN
env.backends.onnx.wasm.wasmPaths = 'https://cdn.jsdelivr.net/npm/@xenova/transformers@2.17.2/dist/';
env.remotes = {
  'models': 'https://huggingface.co/',
};

env.allowRemoteModels = true;
env.allowLocalModels = false;
env.useBrowserCache = true;

console.log('[ClientTranscription] Environment configured:', {
  allowRemoteModels: env.allowRemoteModels,
  allowLocalModels: env.allowLocalModels,
  useBrowserCache: env.useBrowserCache,
  wasmPaths: env.backends?.onnx?.wasm?.wasmPaths,
  remotes: env.remotes
});

class ClientSideTranscriptionService {
  constructor() {
    this.transcriber = null;
    this.modelLoaded = false;
    this.isLoading = false;
    console.log('[ClientTranscription] Service initialized');
  }

  /**
   * Initialize the Whisper model
   * Downloads model to browser cache (39MB for tiny, 75MB for base)
   * @param {string} modelSize - 'tiny', 'base', 'small' (default: 'tiny' for speed)
   * @param {function} onProgress - Callback for download progress
   */
  async initialize(modelSize = 'tiny', onProgress = null) {
    console.log('[ClientTranscription] Initialize called with modelSize:', modelSize);
    
    if (this.modelLoaded) {
      console.log('[ClientTranscription] Model already loaded, returning existing transcriber');
      return this.transcriber;
    }

    if (this.isLoading) {
      console.log('[ClientTranscription] Model currently loading, waiting...');
      // Wait for existing initialization
      while (this.isLoading) {
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      return this.transcriber;
    }

    this.isLoading = true;
    console.log('[ClientTranscription] Starting model initialization...');

    // Intercept fetch to log URLs
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
      console.log('[ClientTranscription] Fetching URL:', args[0]);
      return originalFetch.apply(this, args);
    };

    try {
      const modelName = `Xenova/whisper-${modelSize}.en`;
      console.log('[ClientTranscription] Loading model:', modelName);
      console.log('[ClientTranscription] Environment settings:', {
        allowRemoteModels: env.allowRemoteModels,
        allowLocalModels: env.allowLocalModels
      });
      
      this.transcriber = await pipeline(
        'automatic-speech-recognition',
        modelName,
        {
          progress_callback: (progress) => {
            console.log('[ClientTranscription] Download progress:', progress);
            if (onProgress && progress.status) {
              const percent = progress.progress || 0;
              const status = progress.status;
              console.log(`[ClientTranscription] Progress: ${status} ${Math.round(percent)}%`);
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
      window.fetch = originalFetch; // Restore original fetch
      console.log('[ClientTranscription] Model loaded successfully!');
      return this.transcriber;
    } catch (error) {
      this.isLoading = false;
      window.fetch = originalFetch; // Restore original fetch
      console.error('[ClientTranscription] Failed to load Whisper model:', error);
      console.error('[ClientTranscription] Error stack:', error.stack);
      console.error('[ClientTranscription] Error details:', {
        message: error.message,
        name: error.name,
        cause: error.cause
      });
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
    console.log('[ClientTranscription] transcribe() called with file:', audioFile?.name);
    
    if (!this.modelLoaded) {
      console.error('[ClientTranscription] Model not loaded!');
      throw new Error('Model not loaded. Call initialize() first.');
    }

    try {
      console.log('[ClientTranscription] Reading audio file...');
      // Read audio file as ArrayBuffer
      const arrayBuffer = await audioFile.arrayBuffer();
      console.log('[ClientTranscription] ArrayBuffer size:', arrayBuffer.byteLength, 'bytes');
      
      // Convert to format expected by transformers.js
      console.log('[ClientTranscription] Creating AudioContext...');
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      console.log('[ClientTranscription] Decoding audio data...');
      const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
      const audioDuration = audioBuffer.duration;
      console.log('[ClientTranscription] Audio decoded:', audioDuration, 'seconds');
      
      // Extract audio data (mono, 16kHz as expected by Whisper)
      console.log('[ClientTranscription] Resampling to 16kHz mono...');
      const audioData = this.resampleAndConvertToMono(audioBuffer);
      console.log('[ClientTranscription] Resampled data length:', audioData.length);

      // Estimate processing time (Whisper tiny processes at ~0.5-1x real-time)
      const estimatedMinutes = Math.ceil(audioDuration / 60);
      const estimatedTimeMin = Math.ceil(estimatedMinutes * 0.5);
      const estimatedTimeMax = Math.ceil(estimatedMinutes * 2);
      console.log(`[ClientTranscription] Audio duration: ${estimatedMinutes} minutes`);
      console.log(`[ClientTranscription] Estimated processing time: ${estimatedTimeMin}-${estimatedTimeMax} minutes`);
      
      onProgress?.({ 
        status: 'transcribing', 
        percent: 10, 
        message: `Transcribing ${estimatedMinutes} min audio (estimated ${estimatedTimeMin}-${estimatedTimeMax} min)...`,
        audioDuration,
        estimatedTimeMin,
        estimatedTimeMax
      });

      // Transcribe with timestamps and progress callback
      console.log('[ClientTranscription] Starting transcription...');
      const startTime = Date.now();
      let lastProgressUpdate = startTime;
      
      const result = await this.transcriber(audioData, {
        chunk_length_s: 30, // Process in 30-second chunks
        stride_length_s: 5, // 5-second overlap
        return_timestamps: true,
        callback_function: (progressData) => {
          // Update progress periodically (every 2 seconds max)
          const now = Date.now();
          if (now - lastProgressUpdate > 2000) {
            const elapsed = (now - startTime) / 1000 / 60; // minutes
            const percentComplete = Math.min(90, 10 + (progressData?.progress || 0) * 0.8);
            console.log(`[ClientTranscription] Progress: ${percentComplete.toFixed(1)}% (${elapsed.toFixed(1)} min elapsed)`);
            onProgress?.({ 
              status: 'transcribing', 
              percent: Math.round(percentComplete), 
              message: `Processing... ${elapsed.toFixed(1)} min elapsed`,
              elapsed
            });
            lastProgressUpdate = now;
          }
        },
        ...options
      });

      const totalElapsed = (Date.now() - startTime) / 1000 / 60;
      console.log(`[ClientTranscription] Transcription complete in ${totalElapsed.toFixed(1)} minutes! Result:`, result);
      onProgress?.({ status: 'processing', percent: 90, message: 'Processing segments...' });

      // Convert to format matching server response
      const segments = this.formatSegments(result);
      console.log('[ClientTranscription] Formatted', segments.length, 'segments');

      onProgress?.({ status: 'complete', percent: 100, message: 'Complete!' });

      return {
        all_segments: segments,
        text: result.text,
        repetitive_groups: [],
        potential_repetitive_groups: []
      };
    } catch (error) {
      console.error('[ClientTranscription] Transcription error:', error);
      console.error('[ClientTranscription] Error name:', error.name);
      console.error('[ClientTranscription] Error message:', error.message);
      console.error('[ClientTranscription] Error stack:', error.stack);
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
