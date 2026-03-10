/**
 * Client-Side Audio Storage Service
 * Uses IndexedDB to store audio files locally in the browser
 * This allows audio files to persist across page reloads and tab switches
 */

const DB_NAME = 'AudioTranscriptionDB';
const DB_VERSION = 1;
const STORE_NAME = 'audioFiles';

class ClientAudioStorage {
  constructor() {
    this.db = null;
  }

  /**
   * Initialize IndexedDB
   */
  async init() {
    if (this.db) {
      return this.db;
    }

    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onerror = () => {
        console.error('[ClientAudioStorage] Failed to open IndexedDB:', request.error);
        reject(request.error);
      };

      request.onsuccess = () => {
        this.db = request.result;
        console.log('[ClientAudioStorage] IndexedDB initialized successfully');
        resolve(this.db);
      };

      request.onupgradeneeded = (event) => {
        console.log('[ClientAudioStorage] Upgrading database schema...');
        const db = event.target.result;

        // Create object store if it doesn't exist
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const objectStore = db.createObjectStore(STORE_NAME, { keyPath: 'id' });
          objectStore.createIndex('projectId', 'projectId', { unique: false });
          objectStore.createIndex('filename', 'filename', { unique: false });
          objectStore.createIndex('timestamp', 'timestamp', { unique: false });
          console.log('[ClientAudioStorage] Object store created');
        }
      };
    });
  }

  /**
   * Store an audio file
   * @param {string} id - Unique file ID
   * @param {string} projectId - Project ID
   * @param {File} file - Audio file to store
   * @param {object} metadata - Additional metadata
   */
  async storeFile(id, projectId, file, metadata = {}) {
    await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([STORE_NAME], 'readwrite');
      const objectStore = transaction.objectStore(STORE_NAME);

      const data = {
        id,
        projectId,
        file, // Store the File object directly
        filename: file.name,
        fileSize: file.size,
        fileType: file.type,
        timestamp: Date.now(),
        ...metadata
      };

      const request = objectStore.put(data);

      request.onsuccess = () => {
        console.log(`[ClientAudioStorage] Stored file: ${file.name} (ID: ${id})`);
        resolve(data);
      };

      request.onerror = () => {
        console.error('[ClientAudioStorage] Failed to store file:', request.error);
        reject(request.error);
      };
    });
  }

  /**
   * Retrieve an audio file by ID
   * @param {string} id - File ID
   * @returns {Promise<object|null>} File data with File object
   */
  async getFile(id) {
    await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([STORE_NAME], 'readonly');
      const objectStore = transaction.objectStore(STORE_NAME);
      const request = objectStore.get(id);

      request.onsuccess = () => {
        const result = request.result;
        if (result) {
          console.log(`[ClientAudioStorage] Retrieved file: ${result.filename} (ID: ${id})`);
        } else {
          console.log(`[ClientAudioStorage] File not found: ${id}`);
        }
        resolve(result || null);
      };

      request.onerror = () => {
        console.error('[ClientAudioStorage] Failed to retrieve file:', request.error);
        reject(request.error);
      };
    });
  }

  /**
   * Get all files for a project
   * @param {string} projectId - Project ID
   * @returns {Promise<Array>} Array of file data objects
   */
  async getProjectFiles(projectId) {
    await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([STORE_NAME], 'readonly');
      const objectStore = transaction.objectStore(STORE_NAME);
      const index = objectStore.index('projectId');
      const request = index.getAll(projectId);

      request.onsuccess = () => {
        console.log(`[ClientAudioStorage] Retrieved ${request.result.length} files for project ${projectId}`);
        resolve(request.result);
      };

      request.onerror = () => {
        console.error('[ClientAudioStorage] Failed to retrieve project files:', request.error);
        reject(request.error);
      };
    });
  }

  /**
   * Delete a file by ID
   * @param {string} id - File ID
   */
  async deleteFile(id) {
    await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([STORE_NAME], 'readwrite');
      const objectStore = transaction.objectStore(STORE_NAME);
      const request = objectStore.delete(id);

      request.onsuccess = () => {
        console.log(`[ClientAudioStorage] Deleted file: ${id}`);
        resolve();
      };

      request.onerror = () => {
        console.error('[ClientAudioStorage] Failed to delete file:', request.error);
        reject(request.error);
      };
    });
  }

  /**
   * Delete all files for a project
   * @param {string} projectId - Project ID
   */
  async deleteProjectFiles(projectId) {
    await this.init();

    const files = await this.getProjectFiles(projectId);
    const deletePromises = files.map(file => this.deleteFile(file.id));
    await Promise.all(deletePromises);
    console.log(`[ClientAudioStorage] Deleted ${files.length} files for project ${projectId}`);
  }

  /**
   * Get storage usage statistics
   * @returns {Promise<object>} Storage stats
   */
  async getStats() {
    await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([STORE_NAME], 'readonly');
      const objectStore = transaction.objectStore(STORE_NAME);
      const request = objectStore.getAll();

      request.onsuccess = () => {
        const files = request.result;
        const totalSize = files.reduce((sum, file) => sum + (file.fileSize || 0), 0);
        const stats = {
          totalFiles: files.length,
          totalSizeBytes: totalSize,
          totalSizeMB: (totalSize / (1024 * 1024)).toFixed(2),
          files: files.map(f => ({
            id: f.id,
            filename: f.filename,
            sizeKB: ((f.fileSize || 0) / 1024).toFixed(2),
            timestamp: new Date(f.timestamp).toISOString()
          }))
        };
        resolve(stats);
      };

      request.onerror = () => {
        console.error('[ClientAudioStorage] Failed to get stats:', request.error);
        reject(request.error);
      };
    });
  }

  /**
   * Check if a file exists
   * @param {string} id - File ID
   * @returns {Promise<boolean>}
   */
  async hasFile(id) {
    const file = await this.getFile(id);
    return file !== null;
  }
}

// Export singleton instance
const clientAudioStorage = new ClientAudioStorage();
export default clientAudioStorage;
