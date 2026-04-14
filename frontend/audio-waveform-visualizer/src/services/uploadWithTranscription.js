/**
 * Upload With Transcription Service
 * Uploads audio file + pre-computed transcription data to server
 * Enables server-side assembly after client-side transcription
 * 
 * Backend endpoint: POST /api/projects/{project_id}/upload-with-transcription/
 * 
 * @see docs/frontend_wrok.md for full documentation
 */

import { getApiUrl } from '../config/api';

/**
 * Upload audio file with pre-computed transcription segments to server
 * 
 * @param {File} audioFile - The actual audio file to upload
 * @param {Object} transcriptionResult - The transcription result from client-side Whisper
 * @param {number} projectId - The project ID
 * @param {string} token - Authentication token
 * @param {Object} options - Optional metadata
 * @param {string} options.title - Title for the audio file
 * @param {number} options.orderIndex - Order index for the file
 * @param {function} options.onProgress - Progress callback (percent)
 * @returns {Promise<Object>} Server response with audio_file_id
 * 
 * @example
 * const result = await uploadWithTranscription(
 *   audioFile,
 *   transcriptionResult,
 *   projectId,
 *   token,
 *   {
 *     title: 'Chapter 1',
 *     orderIndex: 0,
 *     onProgress: (percent) => console.log(`${percent}% uploaded`)
 *   }
 * );
 * 
 * // result = {
 * //   success: true,
 * //   audio_file_id: 123,
 * //   filename: 'chapter_01.wav',
 * //   title: 'Chapter 1',
 * //   segments_count: 150,
 * //   words_count: 1250,
 * //   duration: 300.5,
 * //   status: 'transcribed'
 * // }
 */
export async function uploadWithTranscription(
  audioFile,
  transcriptionResult,
  projectId,
  token,
  options = {}
) {
  console.log('[UploadWithTranscription] Starting upload:', {
    filename: audioFile.name,
    fileSize: audioFile.size,
    projectId,
    segmentsCount: transcriptionResult.all_segments?.length
  });

  // Validate inputs
  if (!audioFile || !(audioFile instanceof File)) {
    throw new Error('audioFile must be a File object');
  }

  if (!transcriptionResult || !transcriptionResult.all_segments) {
    throw new Error('transcriptionResult must contain all_segments array');
  }

  if (!projectId) {
    throw new Error('projectId is required');
  }

  // Create FormData for multipart upload
  const formData = new FormData();

  // Add the actual audio file
  formData.append('audio_file', audioFile);

  // Format transcription segments for backend
  const segments = (transcriptionResult.all_segments || []).map(segment => ({
    text: segment.text || '',
    start: parseFloat(segment.start) || 0.0,
    end: parseFloat(segment.end) || 0.0,
    confidence: parseFloat(segment.confidence || 0.0),
    words: (segment.words || []).map(word => ({
      word: word.word || word.text || '',
      start: parseFloat(word.start) || 0.0,
      end: parseFloat(word.end) || 0.0,
      confidence: parseFloat(word.confidence || word.score || 0.0)
    }))
  }));

  console.log('[UploadWithTranscription] Formatted segments:', segments.length);

  // Add transcription data as JSON string
  formData.append('transcription_data', JSON.stringify(segments));

  // Add optional metadata
  if (options.title) {
    formData.append('title', options.title);
  } else {
    // Use filename as title if not provided
    formData.append('title', audioFile.name);
  }

  if (options.orderIndex !== undefined) {
    formData.append('order_index', options.orderIndex.toString());
  }

  // Build API URL
  const url = getApiUrl(`/api/projects/${projectId}/upload-with-transcription/`);
  console.log('[UploadWithTranscription] Uploading to:', url);

  try {
    // Create XMLHttpRequest for progress tracking
    const xhr = new XMLHttpRequest();

    const uploadPromise = new Promise((resolve, reject) => {
      // Track upload progress
      if (options.onProgress) {
        xhr.upload.addEventListener('progress', (event) => {
          if (event.lengthComputable) {
            const percentComplete = Math.round((event.loaded / event.total) * 100);
            console.log(`[UploadWithTranscription] Upload progress: ${percentComplete}%`);
            options.onProgress(percentComplete);
          }
        });
      }

      // Handle completion
      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const response = JSON.parse(xhr.responseText);
            console.log('[UploadWithTranscription] Upload successful:', response);
            resolve(response);
          } catch (error) {
            reject(new Error(`Failed to parse response: ${error.message}`));
          }
        } else {
          try {
            const errorData = JSON.parse(xhr.responseText);
            const errorMessage = errorData.error || errorData.detail || `Upload failed with status ${xhr.status}`;
            console.error('[UploadWithTranscription] Upload failed:', errorMessage);
            reject(new Error(errorMessage));
          } catch {
            reject(new Error(`Upload failed with status ${xhr.status}`));
          }
        }
      });

      // Handle errors
      xhr.addEventListener('error', () => {
        console.error('[UploadWithTranscription] Network error during upload');
        reject(new Error('Network error during upload'));
      });

      xhr.addEventListener('abort', () => {
        console.error('[UploadWithTranscription] Upload aborted');
        reject(new Error('Upload aborted'));
      });

      // Handle timeout
      xhr.addEventListener('timeout', () => {
        console.error('[UploadWithTranscription] Upload timeout');
        reject(new Error('Upload timeout - file may be too large'));
      });

      // Open connection
      xhr.open('POST', url);

      // Use httpOnly cookie for auth (withCredentials sends cookies cross-origin)
      xhr.withCredentials = true;

      // Set timeout (10 minutes for large files)
      xhr.timeout = 10 * 60 * 1000;

      // Send request
      xhr.send(formData);
    });

    const result = await uploadPromise;

    // Validate response
    if (!result.success) {
      throw new Error('Server returned success=false');
    }

    if (!result.audio_file_id) {
      throw new Error('Server did not return audio_file_id');
    }

    console.log('[UploadWithTranscription] Complete:', {
      audio_file_id: result.audio_file_id,
      filename: result.filename,
      segments_count: result.segments_count,
      duration: result.duration
    });

    return result;

  } catch (error) {
    console.error('[UploadWithTranscription] Error:', error);
    throw error;
  }
}

/**
 * Batch upload multiple files with transcriptions
 * Uploads files sequentially to avoid overwhelming the server
 * 
 * @param {Array} files - Array of {audioFile, transcriptionResult, metadata}
 * @param {number} projectId - The project ID
 * @param {string} token - Authentication token
 * @param {function} onFileProgress - Called for each file: (index, total, percent)
 * @param {function} onFileComplete - Called when each file completes: (index, result)
 * @returns {Promise<Array>} Array of upload results
 */
export async function batchUploadWithTranscription(
  files,
  projectId,
  token,
  onFileProgress = null,
  onFileComplete = null
) {
  console.log('[UploadWithTranscription] Batch upload started:', files.length, 'files');

  const results = [];

  for (let i = 0; i < files.length; i++) {
    const { audioFile, transcriptionResult, title, orderIndex } = files[i];

    console.log(`[UploadWithTranscription] Uploading file ${i + 1}/${files.length}:`, audioFile.name);

    try {
      const result = await uploadWithTranscription(
        audioFile,
        transcriptionResult,
        projectId,
        token,
        {
          title: title || audioFile.name,
          orderIndex: orderIndex !== undefined ? orderIndex : i,
          onProgress: (percent) => {
            if (onFileProgress) {
              onFileProgress(i, files.length, percent);
            }
          }
        }
      );

      results.push({ success: true, index: i, result });

      if (onFileComplete) {
        onFileComplete(i, result);
      }

    } catch (error) {
      console.error(`[UploadWithTranscription] Failed to upload file ${i}:`, error);
      results.push({ 
        success: false, 
        index: i, 
        error: error.message,
        filename: audioFile.name
      });

      if (onFileComplete) {
        onFileComplete(i, { error: error.message });
      }
    }
  }

  const successCount = results.filter(r => r.success).length;
  console.log(`[UploadWithTranscription] Batch upload complete: ${successCount}/${files.length} succeeded`);

  return results;
}

export default {
  uploadWithTranscription,
  batchUploadWithTranscription
};
