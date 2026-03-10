/**
 * Client-Side Audio Assembly Service
 * 
 * Removes duplicate segments from audio files entirely in the browser.
 * Uses Web Audio API to process and reassemble audio without server upload.
 * 
 * Features:
 * - Load audio file into AudioBuffer
 * - Remove marked segments (duplicates)
 * - Stitch remaining segments together
 * - Export as WAV blob
 * - Progress tracking
 */

class ClientAudioAssembly {
  constructor() {
    this.audioContext = null;
    this.lastAssembledBlob = null;
    this.lastAssemblyInfo = null;
  }

  /**
   * Initialize AudioContext (lazy initialization)
   */
  getAudioContext() {
    if (!this.audioContext) {
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    return this.audioContext;
  }

  /**
   * Load audio file into AudioBuffer
   * @param {File|Blob} audioFile - The audio file to load
   * @returns {Promise<AudioBuffer>} Decoded audio buffer
   */
  async loadAudioFile(audioFile) {
    const arrayBuffer = await audioFile.arrayBuffer();
    const audioContext = this.getAudioContext();
    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
    return audioBuffer;
  }

  /**
   * Extract a time segment from an AudioBuffer
   * @param {AudioBuffer} sourceBuffer - Source audio buffer
   * @param {number} startTime - Start time in seconds
   * @param {number} endTime - End time in seconds
   * @returns {AudioBuffer} New buffer containing only the segment
   */
  extractSegment(sourceBuffer, startTime, endTime) {
    const audioContext = this.getAudioContext();
    const sampleRate = sourceBuffer.sampleRate;
    const numberOfChannels = sourceBuffer.numberOfChannels;
    
    const startSample = Math.floor(startTime * sampleRate);
    const endSample = Math.floor(endTime * sampleRate);
    const segmentLength = endSample - startSample;

    // Create new buffer for this segment
    const segmentBuffer = audioContext.createBuffer(
      numberOfChannels,
      segmentLength,
      sampleRate
    );

    // Copy audio data for each channel
    for (let channel = 0; channel < numberOfChannels; channel++) {
      const sourceData = sourceBuffer.getChannelData(channel);
      const segmentData = segmentBuffer.getChannelData(channel);
      
      for (let i = 0; i < segmentLength; i++) {
        segmentData[i] = sourceData[startSample + i];
      }
    }

    return segmentBuffer;
  }

  /**
   * Concatenate multiple AudioBuffers into one
   * @param {AudioBuffer[]} buffers - Array of audio buffers to concatenate
   * @returns {AudioBuffer} Combined audio buffer
   */
  concatenateBuffers(buffers) {
    if (buffers.length === 0) {
      throw new Error('No buffers to concatenate');
    }

    const audioContext = this.getAudioContext();
    const sampleRate = buffers[0].sampleRate;
    const numberOfChannels = buffers[0].numberOfChannels;
    
    // Calculate total length
    const totalLength = buffers.reduce((sum, buffer) => sum + buffer.length, 0);

    // Create combined buffer
    const combinedBuffer = audioContext.createBuffer(
      numberOfChannels,
      totalLength,
      sampleRate
    );

    // Copy each buffer's data
    let offset = 0;
    for (const buffer of buffers) {
      for (let channel = 0; channel < numberOfChannels; channel++) {
        const sourceData = buffer.getChannelData(channel);
        const destData = combinedBuffer.getChannelData(channel);
        
        destData.set(sourceData, offset);
      }
      offset += buffer.length;
    }

    return combinedBuffer;
  }

  /**
   * Convert AudioBuffer to WAV blob
   * @param {AudioBuffer} audioBuffer - The audio buffer to convert
   * @returns {Blob} WAV file blob
   */
  audioBufferToWav(audioBuffer) {
    const numberOfChannels = audioBuffer.numberOfChannels;
    const sampleRate = audioBuffer.sampleRate;
    const format = 1; // PCM
    const bitDepth = 16;

    const bytesPerSample = bitDepth / 8;
    const blockAlign = numberOfChannels * bytesPerSample;

    const data = [];
    for (let channel = 0; channel < numberOfChannels; channel++) {
      data.push(audioBuffer.getChannelData(channel));
    }

    const interleaved = this.interleave(data);
    const dataLength = interleaved.length * bytesPerSample;
    const buffer = new ArrayBuffer(44 + dataLength);
    const view = new DataView(buffer);

    // Write WAV header
    this.writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + dataLength, true);
    this.writeString(view, 8, 'WAVE');
    this.writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true); // fmt chunk size
    view.setUint16(20, format, true);
    view.setUint16(22, numberOfChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * blockAlign, true); // byte rate
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, bitDepth, true);
    this.writeString(view, 36, 'data');
    view.setUint32(40, dataLength, true);

    // Write audio data
    this.floatTo16BitPCM(view, 44, interleaved);

    return new Blob([buffer], { type: 'audio/wav' });
  }

  /**
   * Interleave multiple channel data arrays
   */
  interleave(channelData) {
    const length = channelData[0].length;
    const numberOfChannels = channelData.length;
    const result = new Float32Array(length * numberOfChannels);

    let offset = 0;
    for (let i = 0; i < length; i++) {
      for (let channel = 0; channel < numberOfChannels; channel++) {
        result[offset++] = channelData[channel][i];
      }
    }

    return result;
  }

  /**
   * Convert float samples to 16-bit PCM
   */
  floatTo16BitPCM(view, offset, input) {
    for (let i = 0; i < input.length; i++, offset += 2) {
      const s = Math.max(-1, Math.min(1, input[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
  }

  /**
   * Write string to DataView
   */
  writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }

  /**
   * Assemble audio by removing specified segments
   * 
   * @param {File|Blob} audioFile - Original audio file
   * @param {Array} segments - All transcription segments with timing info
   * @param {Array} segmentsToRemove - Array of segment IDs to remove (duplicates)
   * @param {Function} progressCallback - Progress callback(current, total, status)
   * @returns {Promise<Object>} { blob, duration, removedCount, keptCount }
   */
  async assembleAudio(audioFile, segments, segmentsToRemove, progressCallback = null) {
    console.log('[ClientAudioAssembly] Starting audio assembly');
    console.log(`[ClientAudioAssembly] Total segments: ${segments.length}`);
    console.log(`[ClientAudioAssembly] Segments to remove: ${segmentsToRemove.length}`);

    const reportProgress = (current, total, status) => {
      if (progressCallback) {
        progressCallback(current, total, status);
      }
    };

    try {
      // Step 1: Load audio file
      reportProgress(0, 4, 'Loading audio file...');
      const audioBuffer = await this.loadAudioFile(audioFile);
      console.log(`[ClientAudioAssembly] Audio loaded: ${audioBuffer.duration.toFixed(2)}s, ${audioBuffer.numberOfChannels} channels, ${audioBuffer.sampleRate}Hz`);

      // Step 2: Identify segments to keep
      reportProgress(1, 4, 'Identifying segments to keep...');
      const segmentsToRemoveSet = new Set(segmentsToRemove);
      const segmentsToKeep = segments.filter(seg => !segmentsToRemoveSet.has(seg.id));
      
      // Sort by start time
      segmentsToKeep.sort((a, b) => {
        const aStart = a.start_time ?? a.start ?? 0;
        const bStart = b.start_time ?? b.start ?? 0;
        return aStart - bStart;
      });

      console.log(`[ClientAudioAssembly] Segments to keep: ${segmentsToKeep.length}`);

      if (segmentsToKeep.length === 0) {
        throw new Error('No segments to keep - cannot create empty audio file');
      }

      // Step 3: Extract audio segments
      reportProgress(2, 4, `Extracting ${segmentsToKeep.length} audio segments...`);
      const audioSegments = [];
      
      for (let i = 0; i < segmentsToKeep.length; i++) {
        const seg = segmentsToKeep[i];
        const startTime = seg.start_time ?? seg.start ?? 0;
        const endTime = seg.end_time ?? seg.end ?? 0;

        // Ensure times are within audio bounds
        const clampedStart = Math.max(0, Math.min(startTime, audioBuffer.duration));
        const clampedEnd = Math.max(clampedStart, Math.min(endTime, audioBuffer.duration));

        if (clampedEnd > clampedStart) {
          const segmentBuffer = this.extractSegment(audioBuffer, clampedStart, clampedEnd);
          audioSegments.push(segmentBuffer);
        }

        if (i % 10 === 0) {
          reportProgress(2, 4, `Extracted ${i + 1}/${segmentsToKeep.length} segments...`);
          // Allow UI to update
          await new Promise(resolve => setTimeout(resolve, 0));
        }
      }

      console.log(`[ClientAudioAssembly] Extracted ${audioSegments.length} audio segments`);

      // Step 4: Concatenate segments
      reportProgress(3, 4, 'Stitching audio together...');
      const assembledBuffer = this.concatenateBuffers(audioSegments);
      console.log(`[ClientAudioAssembly] Assembled audio: ${assembledBuffer.duration.toFixed(2)}s`);

      // Step 5: Convert to WAV blob
      reportProgress(4, 4, 'Encoding to WAV format...');
      const wavBlob = this.audioBufferToWav(assembledBuffer);
      
      const assemblyInfo = {
        originalDuration: audioBuffer.duration,
        assembledDuration: assembledBuffer.duration,
        removedDuration: audioBuffer.duration - assembledBuffer.duration,
        totalSegments: segments.length,
        removedCount: segmentsToRemove.length,
        keptCount: segmentsToKeep.length,
        sampleRate: audioBuffer.sampleRate,
        numberOfChannels: audioBuffer.numberOfChannels,
        fileSizeBytes: wavBlob.size,
        timestamp: new Date().toISOString()
      };

      this.lastAssembledBlob = wavBlob;
      this.lastAssemblyInfo = assemblyInfo;

      console.log('[ClientAudioAssembly] Assembly complete');
      console.log('[ClientAudioAssembly] Info:', assemblyInfo);

      reportProgress(4, 4, 'Complete!');

      return {
        blob: wavBlob,
        duration: assembledBuffer.duration,
        removedCount: segmentsToRemove.length,
        keptCount: segmentsToKeep.length,
        info: assemblyInfo
      };

    } catch (error) {
      console.error('[ClientAudioAssembly] Assembly error:', error);
      throw error;
    }
  }

  /**
   * Get last assembled blob (cached)
   */
  getLastAssembledBlob() {
    return this.lastAssembledBlob;
  }

  /**
   * Get last assembly info (cached)
   */
  getLastAssemblyInfo() {
    return this.lastAssemblyInfo;
  }

  /**
   * Clear cached data
   */
  clearCache() {
    this.lastAssembledBlob = null;
    this.lastAssemblyInfo = null;
  }

  /**
   * Close audio context to free resources
   */
  cleanup() {
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
    this.clearCache();
  }

  /**
   * Format duration in seconds as MM:SS
   */
  formatDuration(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }

  /**
   * Format file size in bytes to human-readable string
   */
  formatFileSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
}

// Export singleton instance
const clientAudioAssembly = new ClientAudioAssembly();
export default clientAudioAssembly;
