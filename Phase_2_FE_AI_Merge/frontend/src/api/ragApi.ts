/**
 * Phase 2 merge backend — same contract as Phase_2_AI_SERVICE_FOLDER FastAPI.
 * Uses shared apiClient (Bearer + X-User-Id).
 */
import type { AxiosRequestConfig } from 'axios';
import apiClient from './client';
import type { FileItem } from '../App'; // type-only: no runtime cycle

/** Avoid sending default `Content-Type: application/json` on binary GETs (some stacks mishandle it). */
const blobGetConfig: Pick<AxiosRequestConfig, 'responseType' | 'transformRequest'> = {
  responseType: 'blob',
  transformRequest: [
    (_data, headers) => {
      if (headers && typeof (headers as { delete?: (k: string) => void }).delete === 'function') {
        (headers as { delete: (k: string) => void }).delete('Content-Type');
      }
      return _data;
    },
  ],
};

const EXT_MIME: Record<string, string> = {
  '.mp4': 'video/mp4',
  '.webm': 'video/webm',
  '.mov': 'video/quicktime',
  '.avi': 'video/x-msvideo',
  '.mkv': 'video/x-matroska',
  '.pdf': 'application/pdf',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.bmp': 'image/bmp',
  '.mp3': 'audio/mpeg',
  '.wav': 'audio/wav',
  '.aac': 'audio/aac',
  '.m4a': 'audio/mp4',
  '.flac': 'audio/flac',
  '.ogg': 'audio/ogg',
};

/** When the server returns `application/octet-stream`, rebuild the Blob with a real type so video/pdf/image play inline instead of downloading. */
export function coerceBlobForPreview(blob: Blob, fileName: string, headerMime?: string): Blob {
  const header = (headerMime || '').split(';')[0].trim().toLowerCase();
  if (header && header !== 'application/octet-stream') {
    if (!blob.type || blob.type === 'application/octet-stream') {
      return new Blob([blob], { type: header });
    }
    return blob;
  }
  const ext = fileName.includes('.') ? fileName.slice(fileName.lastIndexOf('.')).toLowerCase() : '';
  const t = EXT_MIME[ext];
  if (t) return new Blob([blob], { type: t });
  return blob;
}

export type FilesResponse = {
  input: Array<Record<string, unknown>>;
  processed: Array<Record<string, unknown>>;
  indexed: Array<Record<string, unknown>>;
};

export type FileWithMetadata = {
  file_name: string;
  name: string;
  path: string;
  size: string;
  type: string;
  modified?: string;
  storage?: string;
  status?: string;
  upload_time?: string | null;
  metadata_status?: string | null;
  metadata_error?: string | null;
  document_id?: string;
  processed_total_files?: number;
  processed_stage_counts?: Record<string, number>;
  indexed_text?: boolean;
  indexed_image?: boolean;
  index_status?: 'none' | 'text' | 'image' | 'all';
};

export type FilesWithMetadataResponse = {
  count: number;
  files: FileWithMetadata[];
  pipeline_stage_totals?: Record<string, number>;
  pipeline_document_count?: number;
};

export type ProcessedByFileResponse = {
  file_name: string;
  document_id?: string;
  display_name?: string;
  total_processed_files: number;
  stages: Array<{
    stage: string;
    file_count: number;
    files: Array<Record<string, unknown>>;
  }>;
};

export type FileMetadataDetailResponse = {
  file_name: string;
  file_path: string;
  storage?: string;
  processed_document_id?: string | null;
  processed_display_name?: string | null;
  processed_safe_name?: string | null;
  metadata?: Record<string, unknown> | null;
};

export async function getFiles(quick = false): Promise<FilesResponse> {
  const { data } = await apiClient.get<FilesResponse>('/files', { params: { quick } });
  return data;
}

export async function uploadFiles(fileList: File[]): Promise<void> {
  const form = new FormData();
  fileList.forEach((f) => form.append('files', f));
  await apiClient.post('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
}

export async function deleteFile(path: string): Promise<void> {
  await apiClient.delete('/files', { data: { path } });
}

export async function runProcess(
  force = false,
  selectedPaths: string[] = [],
  mode: 'standard' | 'fast' = 'standard'
): Promise<unknown> {
  const { data } = await apiClient.post(
    '/process',
    { selected_paths: selectedPaths, mode },
    { params: { force } }
  );
  return data;
}

export async function runIndex(
  force = false,
  selectedPaths: string[] = [],
  selectedNames: string[] = [],
  mode: 'standard' | 'fast' = 'standard'
): Promise<unknown> {
  const { data } = await apiClient.post(
    '/index',
    { selected_paths: selectedPaths, selected_names: selectedNames, mode },
    { params: { force } }
  );
  return data;
}

export async function runIndexText(
  force = false,
  selectedPaths: string[] = [],
  selectedNames: string[] = [],
  mode: 'standard' | 'fast' = 'standard'
): Promise<unknown> {
  const { data } = await apiClient.post(
    '/index/text',
    { selected_paths: selectedPaths, selected_names: selectedNames, mode },
    { params: { force } }
  );
  return data;
}

export async function runIndexImage(
  force = false,
  selectedPaths: string[] = [],
  selectedNames: string[] = [],
  mode: 'standard' | 'fast' = 'standard'
): Promise<unknown> {
  const { data } = await apiClient.post(
    '/index/image',
    { selected_paths: selectedPaths, selected_names: selectedNames, mode },
    { params: { force } }
  );
  return data;
}

export async function clearImageIndex(): Promise<unknown> {
  const { data } = await apiClient.post('/index/remove', { clear_image_index: true });
  return data;
}

export async function clearTextIndex(): Promise<unknown> {
  const { data } = await apiClient.post('/index/remove', { clear_text_index: true });
  return data;
}

export async function getProcessingStats(fresh = false): Promise<Record<string, unknown>> {
  const { data } = await apiClient.get('/status', { params: { fresh } });
  return data;
}

export async function getProcessedDocuments(preview = false): Promise<Record<string, unknown>> {
  const { data } = await apiClient.get('/processed-documents', { params: { preview } });
  return data;
}

export async function getProcessedFile(relPath: string): Promise<{ body: Blob; mediaType: string }> {
  const response = await apiClient.get('/processed-file', {
    params: { rel_path: relPath },
    ...blobGetConfig,
  });
  return {
    body: response.data,
    mediaType: response.headers['content-type'] || 'application/octet-stream',
  };
}

export async function getInputFile(fileName: string): Promise<{ body: Blob; mediaType: string }> {
  const response = await apiClient.get('/input-file', {
    params: { file_name: fileName },
    ...blobGetConfig,
  });
  return {
    body: response.data,
    mediaType: response.headers['content-type'] || 'application/octet-stream',
  };
}

export async function getInputFileUrl(
  fileName: string,
  expiresIn = 900
): Promise<{ url?: string | null; mode?: string; reason?: string; expires_in?: number }> {
  const { data } = await apiClient.get('/input-file-url', {
    params: {
      file_name: fileName,
      expires_in: expiresIn,
    },
  });
  return data;
}

export async function getFilesWithMetadata(): Promise<FilesWithMetadataResponse> {
  const { data } = await apiClient.get<FilesWithMetadataResponse>('/files-with-metadata');
  return data;
}

export async function getProcessedByFile(fileName: string): Promise<ProcessedByFileResponse> {
  const encoded = encodeURIComponent(fileName);
  const { data } = await apiClient.get<ProcessedByFileResponse>(`/files/${encoded}/processed`);
  return data;
}

export async function getFileMetadata(fileName: string): Promise<FileMetadataDetailResponse> {
  const encoded = encodeURIComponent(fileName);
  const { data } = await apiClient.get<FileMetadataDetailResponse>(`/file-metadata/${encoded}`);
  return data;
}

export async function getChunksByFile(fileName: string): Promise<{
  file_name: string;
  document_id?: string;
  loaded_from?: string | null;
  chunk_count: number;
  chunks: Array<Record<string, unknown>>;
}> {
  const encoded = encodeURIComponent(fileName);
  const { data } = await apiClient.get(`/files/${encoded}/chunks`);
  return data;
}

export async function searchRag(body: {
  query: string;
  top_k?: number;
  retriever_type?: string;
  include_images?: boolean;
  images_for_generation?: number;
  mode?: 'retrieval_only' | 'retrieval_generation';
  search_scope?: 'text' | 'image' | 'both';
  generation_model?: string | null;
  skip_reranker?: boolean;
}): Promise<{
  query: string;
  text_results: Array<Record<string, unknown>>;
  image_results: Array<Record<string, unknown>>;
  answer: string | null;
  contents?: Record<string, unknown>;
  mode?: string;
  search_scope?: string;
  generation?: Record<string, unknown>;
  telemetry?: {
    steps_ms?: Record<string, number>;
    tokens?: {
      input_total?: number;
      output_total?: number;
      provider_reported?: boolean;
    };
  };
}> {
  const { data } = await apiClient.post('/search', {
    query: body.query,
    top_k: body.top_k ?? 10,
    retriever_type: body.retriever_type ?? 'hybrid',
    include_images: body.include_images ?? true,
    images_for_generation: body.images_for_generation ?? 5,
    mode: body.mode ?? 'retrieval_generation',
    search_scope: body.search_scope ?? 'both',
    generation_model: body.generation_model ?? null,
    skip_reranker: body.skip_reranker ?? false,
  });
  return data;
}

export async function getGenerationModels(): Promise<{
  provider?: string;
  region?: string;
  configured_model?: string;
  models?: string[];
  error?: string;
}> {
  const { data } = await apiClient.get('/search/generation-models');
  return data;
}

export async function getSearchImagePreview(
  storageUri?: string,
  sourcePath?: string,
  page?: number
): Promise<{ body: Blob; mediaType: string }> {
  const response = await apiClient.get('/search/image-preview', {
    params: {
      ...(storageUri ? { storage_uri: storageUri } : {}),
      ...(!storageUri && sourcePath ? { source_path: sourcePath } : {}),
      ...(page && page > 0 ? { page } : {}),
    },
    responseType: 'blob',
  });
  return {
    body: response.data,
    mediaType: response.headers['content-type'] || 'application/octet-stream',
  };
}

export async function postSummary(payload: {
  focus_query?: string;
  depth?: string;
  document_id?: string | null;
  tone?: string;
  target_length?: string;
}): Promise<{ summary?: string; error?: string }> {
  const { data } = await apiClient.post('/insights/summary', payload);
  return data;
}

export async function postMcq(payload: {
  topic: string;
  num_questions: number;
  difficulty?: string;
  document_id?: string | null;
  question_style?: string;
  include_explanations?: boolean;
}): Promise<{ questions?: unknown[]; error?: string; raw?: string }> {
  const { data } = await apiClient.post('/insights/mcq', payload);
  return data;
}

export async function postRoadmap(payload: {
  student_profile: string;
  goals: string;
  document_id?: string | null;
}): Promise<{ roadmap?: string; error?: string }> {
  const { data } = await apiClient.post('/insights/learning-roadmap', payload);
  return data;
}

export type QuizResultRow = {
  attempt_id: string;
  user_id: string;
  score: number;
  total: number;
  file_id?: number | null;
  document_id?: string | null;
  quiz_topic?: string | null;
  created_at: string;
};

export async function getQuizResults(limit = 200): Promise<{ items: QuizResultRow[] }> {
  const { data } = await apiClient.get('/quiz-results', { params: { limit } });
  return { items: (data?.items || []) as QuizResultRow[] };
}

export async function postQuizResult(payload: {
  score: number;
  total: number;
  file_id?: number | null;
  document_id?: string | null;
  quiz_topic?: string;
}): Promise<{ item?: QuizResultRow }> {
  const { data } = await apiClient.post('/quiz-results', payload);
  return data;
}

function normPath(s: string): string {
  return s.replace(/\\/g, '/').toLowerCase();
}

/** True if any text-index source string refers to this input file (paths vary by pipeline). */
function inputMatchesIndexedSource(fileName: string, documentFolder: string, textIndexed: Array<Record<string, unknown>>): boolean {
  const fn = normPath(fileName);
  const fold = normPath(documentFolder);
  for (const ir of textIndexed) {
    const src = normPath(String((ir as { name?: string }).name || ''));
    if (!src) continue;
    if (src.includes(fn) || src.endsWith(fn)) return true;
    if (fold.length >= 2 && (src.includes(`/${fold}/`) || src.endsWith(`/${fold}`) || src.includes(fold))) {
      return true;
    }
    const lastSeg = src.split('/').pop() || '';
    if (lastSeg && (fn.includes(lastSeg) || lastSeg.includes(fold))) return true;
  }
  return false;
}

/** Map GET /api/files input + indexed rows → UI FileItem list */
export function mapFilesToFileItems(data: FilesResponse): FileItem[] {
  const indexed = data.indexed || [];
  const textIndexed = indexed.filter((r) => (r as { type?: string }).type !== 'image');

  return (data.input || []).map((row, idx) => {
    const name = String((row as { name?: string }).name || 'file');
    const path = String((row as { path?: string }).path || '');
    const ext = String((row as { type?: string }).type || '').toLowerCase();
    const sizeStr = String((row as { size?: string }).size || '0 B');
    const modified = String((row as { modified?: string }).modified || '');
    const id = stableIdFromPath(path || `${name}-${idx}`);

    const documentFolder = name.replace(/\.[^/.]+$/, '') || name;
    const inIndex = inputMatchesIndexedSource(name, documentFolder, textIndexed);

    const type = extToFileType(name, ext);

    return {
      id,
      name,
      type,
      size: sizeStr,
      rawSize: parseHumanSize(sizeStr),
      status: inIndex ? 'indexed' : 'uploaded',
      date: modified.slice(0, 10) || new Date().toISOString().slice(0, 10),
      storagePath: path,
      documentFolder,
    };
  });
}

/** Map GET /api/files-with-metadata rows -> UI FileItem list */
export function mapFilesWithMetadataToFileItems(data: FilesWithMetadataResponse): FileItem[] {
  return (data.files || []).map((row, idx) => {
    const name = String(row.name || row.file_name || `file-${idx}`);
    const path = String(row.path || '');
    const sizeStr = String(row.size || '0 B');
    const id = stableIdFromPath(path || `${name}-${idx}`);
    const documentFolder = String(row.document_id || '').trim() || name.replace(/\.[^/.]+$/, '') || name;
    const metadataStatus = String(row.status || row.metadata_status || 'uploaded').toLowerCase();
    const status: FileItem['status'] =
      metadataStatus === 'indexed'
        ? 'indexed'
        : metadataStatus === 'processed'
          ? 'processed'
          : metadataStatus === 'failed'
            ? 'failed'
            : metadataStatus === 'processing'
              ? 'processing'
              : 'uploaded';

    return {
      id,
      name,
      type: extToFileType(name, String(row.type || '')),
      size: sizeStr,
      rawSize: parseHumanSize(sizeStr),
      status,
      indexStatus: (row.index_status as any) || undefined,
      date: String(row.upload_time || row.modified || '').slice(0, 10) || new Date().toISOString().slice(0, 10),
      storagePath: path,
      documentFolder,
    };
  });
}

function stableIdFromPath(p: string): number {
  let h = 0;
  for (let i = 0; i < p.length; i++) h = (Math.imul(31, h) + p.charCodeAt(i)) | 0;
  return Math.abs(h) || 1;
}

function parseHumanSize(s: string): number {
  const m = /^([\d.]+)\s*(B|KB|MB|GB)$/i.exec(s.trim());
  if (!m) return 0;
  const n = parseFloat(m[1]);
  const u = m[2].toUpperCase();
  const mul = u === 'GB' ? 1024 ** 3 : u === 'MB' ? 1024 ** 2 : u === 'KB' ? 1024 : 1;
  return Math.round(n * mul);
}

function extToFileType(fileName: string, extFromApi: string): FileItem['type'] {
  const ext = (extFromApi || fileName.slice(fileName.lastIndexOf('.'))).toLowerCase();
  if (['.mp4', '.webm', '.mov', '.avi', '.mkv'].includes(ext)) return 'video';
  if (['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'].includes(ext)) return 'image';
  if (['.mp3', '.wav', '.aac', '.m4a', '.flac', '.ogg'].includes(ext)) return 'audio';
  if (ext === '.pdf') return 'pdf';
  if (['.xlsx', '.xls', '.csv', '.xlsm'].includes(ext)) return 'spreadsheet';
  return 'document';
}
