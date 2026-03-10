/**
 * Download Helper Utility
 * 
 * Provides functions to download various types of content:
 * - Text files (TXT, SRT, VTT)
 * - JSON files
 * - Audio files (WAV, MP3)
 */

class DownloadHelper {
  /**
   * Trigger a download of text content
   * @param {string} content - The text content to download
   * @param {string} filename - The filename for the download
   * @param {string} mimeType - MIME type (default: text/plain)
   */
  downloadAsText(content, filename, mimeType = 'text/plain') {
    const blob = new Blob([content], { type: `${mimeType};charset=utf-8` });
    this.downloadBlob(blob, filename);
  }

  /**
   * Download JSON data
   * @param {Object} data - The data to convert to JSON and download
   * @param {string} filename - The filename for the download
   * @param {boolean} pretty - Whether to pretty-print the JSON (default: true)
   */
  downloadAsJson(data, filename, pretty = true) {
    const jsonString = pretty ? JSON.stringify(data, null, 2) : JSON.stringify(data);
    this.downloadAsText(jsonString, filename, 'application/json');
  }

  /**
   * Download audio blob
   * @param {Blob} blob - The audio blob to download
   * @param {string} filename - The filename for the download
   */
  downloadAsAudio(blob, filename) {
    this.downloadBlob(blob, filename);
  }

  /**
   * Download a blob
   * @param {Blob} blob - The blob to download
   * @param {string} filename - The filename for the download
   */
  downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  /**
   * Convert transcription segments to plain text
   * @param {Array} segments - Transcription segments
   * @param {Object} options - Formatting options
   * @returns {string} Plain text transcription
   */
  segmentsToText(segments, options = {}) {
    const {
      includeTimestamps = false,
      separateLines = true,
      timestampFormat = 'seconds' // 'seconds' or 'timecode'
    } = options;

    let text = '';

    segments.forEach((seg, index) => {
      const segmentText = seg.text || '';
      
      if (includeTimestamps) {
        const start = seg.start_time ?? seg.start ?? 0;
        const end = seg.end_time ?? seg.end ?? 0;
        
        if (timestampFormat === 'timecode') {
          text += `[${this.formatTimecode(start)} --> ${this.formatTimecode(end)}] `;
        } else {
          text += `[${start.toFixed(2)}s - ${end.toFixed(2)}s] `;
        }
      }

      text += segmentText;
      
      if (separateLines) {
        text += '\n';
        if (includeTimestamps && index < segments.length - 1) {
          text += '\n'; // Extra line between timestamped segments
        }
      } else {
        text += ' ';
      }
    });

    return text.trim();
  }

  /**
   * Convert transcription segments to SRT subtitle format
   * @param {Array} segments - Transcription segments
   * @returns {string} SRT format text
   */
  segmentsToSRT(segments) {
    let srt = '';

    segments.forEach((seg, index) => {
      const start = seg.start_time ?? seg.start ?? 0;
      const end = seg.end_time ?? seg.end ?? 0;
      const text = seg.text || '';

      srt += `${index + 1}\n`;
      srt += `${this.formatSRTTimecode(start)} --> ${this.formatSRTTimecode(end)}\n`;
      srt += `${text}\n`;
      srt += '\n';
    });

    return srt;
  }

  /**
   * Convert transcription segments to VTT (WebVTT) subtitle format
   * @param {Array} segments - Transcription segments
   * @returns {string} VTT format text
   */
  segmentsToVTT(segments) {
    let vtt = 'WEBVTT\n\n';

    segments.forEach((seg, index) => {
      const start = seg.start_time ?? seg.start ?? 0;
      const end = seg.end_time ?? seg.end ?? 0;
      const text = seg.text || '';

      vtt += `${index + 1}\n`;
      vtt += `${this.formatVTTTimecode(start)} --> ${this.formatVTTTimecode(end)}\n`;
      vtt += `${text}\n`;
      vtt += '\n';
    });

    return vtt;
  }

  /**
   * Format seconds to SRT timecode (HH:MM:SS,mmm)
   */
  formatSRTTimecode(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    const milliseconds = Math.floor((seconds % 1) * 1000);

    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')},${String(milliseconds).padStart(3, '0')}`;
  }

  /**
   * Format seconds to VTT timecode (HH:MM:SS.mmm)
   */
  formatVTTTimecode(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    const milliseconds = Math.floor((seconds % 1) * 1000);

    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}.${String(milliseconds).padStart(3, '0')}`;
  }

  /**
   * Format seconds to simple timecode (MM:SS)
   */
  formatTimecode(seconds) {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }

  /**
   * Generate safe filename from text
   * @param {string} text - Original filename or text
   * @param {string} extension - File extension (without dot)
   * @returns {string} Safe filename
   */
  generateFilename(text, extension) {
    // Remove file extension if present
    const baseName = text.replace(/\.[^/.]+$/, '');
    
    // Replace unsafe characters
    const safeName = baseName
      .replace(/[^a-zA-Z0-9_\- ]/g, '_')
      .replace(/\s+/g, '_')
      .replace(/_+/g, '_')
      .substring(0, 200); // Limit length

    return `${safeName}.${extension}`;
  }

  /**
   * Download transcription in multiple formats
   * @param {Array} segments - Transcription segments
   * @param {string} baseFilename - Base filename (without extension)
   * @param {string} format - Format: 'txt', 'json', 'srt', 'vtt', 'txt-timestamps'
   */
  downloadTranscription(segments, baseFilename, format) {
    let content;
    let filename;

    switch (format.toLowerCase()) {
      case 'txt':
        content = this.segmentsToText(segments, { includeTimestamps: false, separateLines: true });
        filename = this.generateFilename(baseFilename, 'txt');
        this.downloadAsText(content, filename);
        break;

      case 'txt-timestamps':
        content = this.segmentsToText(segments, { includeTimestamps: true, separateLines: true, timestampFormat: 'timecode' });
        filename = this.generateFilename(baseFilename, 'txt');
        this.downloadAsText(content, filename);
        break;

      case 'json':
        const data = {
          filename: baseFilename,
          segments: segments,
          total_segments: segments.length,
          exported_at: new Date().toISOString()
        };
        filename = this.generateFilename(baseFilename, 'json');
        this.downloadAsJson(data, filename);
        break;

      case 'srt':
        content = this.segmentsToSRT(segments);
        filename = this.generateFilename(baseFilename, 'srt');
        this.downloadAsText(content, filename, 'text/plain');
        break;

      case 'vtt':
        content = this.segmentsToVTT(segments);
        filename = this.generateFilename(baseFilename, 'vtt');
        this.downloadAsText(content, filename, 'text/vtt');
        break;

      default:
        throw new Error(`Unsupported format: ${format}`);
    }

    console.log(`[DownloadHelper] Downloaded transcription as ${format}: ${filename}`);
  }
}

// Export singleton instance
const downloadHelper = new DownloadHelper();
export default downloadHelper;
