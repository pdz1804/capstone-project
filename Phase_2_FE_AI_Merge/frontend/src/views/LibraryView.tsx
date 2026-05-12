import React, { useState, useRef, useEffect } from 'react';
import {
  UploadCloud,
  FileText,
  Video,
  Image as ImageIcon,
  MoreVertical,
  CheckCircle2,
  AlertCircle,
  Search,
  Filter,
  Loader2,
  Trash2,
  Download,
  ChevronDown,
  ChevronUp,
  LayoutGrid,
  List,
  Edit2,
  Eye,
  X,
  Music,
  File,
  Play,
  Layers,
} from 'lucide-react';
import { FileItem } from '../App';
import {
  coerceBlobForPreview,
  deleteFile,
  getFileMetadata,
  getInputFile,
  getInputFileUrl,
  runIndex,
  runProcess,
  uploadFiles,
} from '../api/ragApi';
import { Document, Page, pdfjs } from 'react-pdf';
import { AdminTablePagination } from '../components/admin/AdminTableControls';

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface LibraryViewProps {
  files: FileItem[];
  filesTotal: number;
  filesLoading: boolean;
  setFiles: React.Dispatch<React.SetStateAction<FileItem[]>>;
  onRefreshFiles: (params?: {
    skip?: number;
    limit?: number;
    query?: string;
    type?: string;
    status?: string;
    sort_by?: 'name' | 'size' | 'date' | 'status' | 'type';
    sort_dir?: 'asc' | 'desc';
    cache_bust?: boolean;
  }) => Promise<{ count: number } | void>;
  controlMode?: 'upload' | 'process' | 'index';
}

type PipelineJobMode = 'process' | 'index';

type PipelineProgressState = {
  mode: PipelineJobMode;
  targetNames: string[];
  total: number;
  completed: number;
  percent: number;
};

const PROCESS_PROGRESS_POLL_MS = 5000;
const INDEX_PROGRESS_POLL_MS = 10000;

export default function LibraryView({
  files,
  filesTotal,
  filesLoading,
  setFiles,
  onRefreshFiles,
  controlMode = 'upload'
}: LibraryViewProps) {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const formatBytes = (bytes: number) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const formatMs = (value: unknown) => {
    const n = typeof value === 'number' ? value : Number(value);
    if (!Number.isFinite(n)) return '-';
    if (n >= 1000) return `${(n / 1000).toFixed(1)}s`;
    return `${Math.round(n)}ms`;
  };

  // Enhanced Management State
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState('all');
  const [sortBy, setSortBy] = useState<'date' | 'name' | 'size'>('date');
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [selectedFiles, setSelectedFiles] = useState<number[]>([]);
  const [activeDropdown, setActiveDropdown] = useState<number | null>(null);
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');
  const [renamingFileId, setRenamingFileId] = useState<number | null>(null);
  const [newName, setNewName] = useState('');
  const [previewFile, setPreviewFile] = useState<any | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [numPages, setNumPages] = useState<number>(0);
  const [pdfPageWidth, setPdfPageWidth] = useState<number>(900);
  const [textContent, setTextContent] = useState<string | null>(null);
  const [remotePreview, setRemotePreview] = useState<
    | { kind: 'none' }
    | { kind: 'blob'; url: string; mime: string }
    | { kind: 'text'; content: string }
    | { kind: 'html'; content: string }
    | { kind: 'office'; iframeSrc: string; sourceUrl: string }
  >({ kind: 'none' });
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [metadataFileName, setMetadataFileName] = useState<string | null>(null);
  const [metadataDetail, setMetadataDetail] = useState<Record<string, unknown> | null>(null);
  const [metadataLoading, setMetadataLoading] = useState(false);
  const [pipelineMode, setPipelineMode] = useState<'standard' | 'fast'>('standard');
  const [pipelineBusy, setPipelineBusy] = useState<'idle' | 'process' | 'index'>('idle');
  const [pipelineProgress, setPipelineProgress] = useState<PipelineProgressState | null>(null);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<{ current: number; total: number } | null>(null);
  const [lastIndexResult, setLastIndexResult] = useState<Record<string, any> | null>(null);
  const pipelineBusyRef = useRef<'idle' | 'process' | 'index'>('idle');
  const pipelinePollRef = useRef<number | null>(null);
  const pipelinePollInFlightRef = useRef(false);
  const pipelineJobTokenRef = useRef(0);
  const pdfContainerRef = useRef<HTMLDivElement | null>(null);
  const [deletingIds, setDeletingIds] = useState<Set<number>>(new Set());
  const [bulkDeleteProgress, setBulkDeleteProgress] = useState<{ current: number; total: number } | null>(null);

  const refreshCurrentPage = (cacheBust = false) =>
    onRefreshFiles({
      skip: (page - 1) * pageSize,
      limit: pageSize,
      query: searchTerm.trim() || undefined,
      type: filterType === 'all' ? undefined : filterType,
      sort_by: sortBy,
      sort_dir: sortOrder,
      cache_bust: cacheBust,
    });

  const setPipelineBusySafe = (next: 'idle' | 'process' | 'index') => {
    pipelineBusyRef.current = next;
    setPipelineBusy(next);
  };

  const computePipelineProgress = (
    mode: PipelineJobMode,
    targetNames: string[],
    snapshot: FileItem[]
  ): PipelineProgressState => {
    const normalizedTargets = Array.from(
      new Set(
        targetNames
          .map((name) => String(name || '').trim().toLowerCase())
          .filter(Boolean)
      )
    );

    const byName = new Map(snapshot.map((row) => [String(row.name || '').trim().toLowerCase(), row]));

    const completed = normalizedTargets.reduce((acc, key) => {
      const row = byName.get(key);
      if (!row) return acc;
      if (mode === 'process') {
        return acc + (row.status === 'processed' || row.status === 'indexed' ? 1 : 0);
      }
      return acc + (row.status === 'indexed' || (row.indexStatus && row.indexStatus !== 'none') ? 1 : 0);
    }, 0);

    const total = normalizedTargets.length;
    const percent = total > 0 ? Math.min(100, Math.round((completed / total) * 100)) : 0;

    return {
      mode,
      targetNames: normalizedTargets,
      total,
      completed,
      percent,
    };
  };

  const stopPipelinePolling = () => {
    if (pipelinePollRef.current !== null) {
      window.clearInterval(pipelinePollRef.current);
      pipelinePollRef.current = null;
    }
    pipelinePollInFlightRef.current = false;
  };

  const startPipelinePolling = (token: number, mode: PipelineJobMode) => {
    stopPipelinePolling();

    const pollOnce = () => {
      if (pipelineBusyRef.current === 'idle') return;
      if (pipelineJobTokenRef.current !== token) return;
      if (pipelinePollInFlightRef.current) return;

      pipelinePollInFlightRef.current = true;
      void refreshCurrentPage(true)
        .catch(() => undefined)
        .finally(() => {
          pipelinePollInFlightRef.current = false;
        });
    };

    pollOnce();
    const intervalMs = mode === 'index' ? INDEX_PROGRESS_POLL_MS : PROCESS_PROGRESS_POLL_MS;
    pipelinePollRef.current = window.setInterval(pollOnce, intervalMs);
  };

  useEffect(() => {
    return () => {
      stopPipelinePolling();
    };
  }, []);

  useEffect(() => {
    setPipelineProgress((prev) => {
      if (!prev || pipelineBusy === 'idle') return prev;
      const next = computePipelineProgress(prev.mode, prev.targetNames, files);
      return {
        ...prev,
        total: next.total,
        completed: next.completed,
        percent: next.percent,
      };
    });
  }, [files, pipelineBusy]);

  useEffect(() => {
    if (pipelineBusy === 'idle' || !pipelineProgress) return;
    if (pipelineProgress.total > 0 && pipelineProgress.completed >= pipelineProgress.total) {
      stopPipelinePolling();
    }
  }, [pipelineBusy, pipelineProgress]);

  useEffect(() => {
    const updateWidth = () => {
      const container = pdfContainerRef.current;
      if (!container) return;
      const next = Math.max(320, Math.floor(container.clientWidth - 32));
      setPdfPageWidth(next);
    };
    updateWidth();
    window.addEventListener('resize', updateWidth);
    return () => window.removeEventListener('resize', updateWidth);
  }, [previewFile, remotePreview.kind, previewUrl]);

  useEffect(() => {
    let localUrlToRevoke: string | null = null;
    let remoteObjectUrlToRevoke: string | null = null;
    let cancelled = false;

    setPreviewUrl(null);
    setNumPages(0);
    setTextContent(null);
    setRemotePreview({ kind: 'none' });
    setPreviewLoading(false);
    setPreviewError(null);

    if (!previewFile) {
      return;
    }

    if (previewFile.originalFile) {
      const url = URL.createObjectURL(previewFile.originalFile);
      localUrlToRevoke = url;
      setPreviewUrl(url);

      if (previewFile.originalFile.type === 'text/plain') {
        fetch(url)
          .then((res) => res.text())
          .then((txt) => {
            if (!cancelled) setTextContent(txt);
          })
          .catch(() => {
            if (!cancelled) setTextContent(null);
          });
      }
    } else {
      setPreviewLoading(true);
      void (async () => {
        try {
          const nameLower = String(previewFile.name || '').toLowerCase();
          const ext = nameLower.includes('.') ? nameLower.slice(nameLower.lastIndexOf('.')) : '';
          const officeExt = ['.ppt', '.pptx', '.xls', '.xlsx', '.doc', '.docx'];
          const isPdfExt = ext === '.pdf';

          if (officeExt.includes(ext)) {
            const u = await getInputFileUrl(previewFile.name, 900, { viewer: 'office' });
            if (cancelled) return;
            if (!u?.url) throw new Error('Office preview URL is not available for this file.');
            setRemotePreview({
              kind: 'office',
              iframeSrc: `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(u.url)}`,
              sourceUrl: u.url,
            });
            return;
          }

          // Fast path for remote PDFs: avoid proxying full bytes through backend.
          if (isPdfExt) {
            try {
              const u = await getInputFileUrl(previewFile.name, 900);
              if (cancelled) return;
              if (u?.url) {
                const pdfMime = (u.content_type || 'application/pdf').split(';')[0].trim().toLowerCase() || 'application/pdf';
                setRemotePreview({ kind: 'blob', url: u.url, mime: pdfMime });
                return;
              }
            } catch {
              // Fallback to byte fetch path below.
            }
          }

          const { body, mediaType } = await getInputFile(previewFile.name);
          if (cancelled) return;

          const mime = (mediaType || '').split(';')[0].trim().toLowerCase();
          const textish =
            mime.startsWith('text/') ||
            mime === 'application/json' ||
            /\.(txt|md|csv|json|log)$/i.test(nameLower);

          if (mime === 'text/html' || ext === '.html' || ext === '.htm') {
            const html = await body.text();
            if (cancelled) return;
            setRemotePreview({ kind: 'html', content: html });
            return;
          }

          if (textish && mime !== 'application/pdf') {
            const txt = await body.text();
            if (cancelled) return;
            setRemotePreview({ kind: 'text', content: txt });
            return;
          }

          const coerced = coerceBlobForPreview(body, previewFile.name, mediaType);
          const objectUrl = URL.createObjectURL(coerced);
          remoteObjectUrlToRevoke = objectUrl;
          setRemotePreview({
            kind: 'blob',
            url: objectUrl,
            mime: coerced.type || mime || 'application/octet-stream',
          });
        } catch (e) {
          if (cancelled) return;
          if (previewFile.type === 'pdf' || String(previewFile.name || '').toLowerCase().endsWith('.pdf')) {
            try {
              const u = await getInputFileUrl(previewFile.name, 900);
              if (cancelled) return;
              if (u?.url) {
                setRemotePreview({ kind: 'blob', url: u.url, mime: 'application/pdf' });
                setPreviewError(null);
                return;
              }
            } catch {
              // fall through
            }
          }
          setRemotePreview({ kind: 'none' });
          setPreviewError(e instanceof Error ? e.message : 'Could not load file for preview.');
        } finally {
          if (!cancelled) setPreviewLoading(false);
        }
      })();
    }

    return () => {
      cancelled = true;
      if (localUrlToRevoke) URL.revokeObjectURL(localUrlToRevoke);
      if (remoteObjectUrlToRevoke) URL.revokeObjectURL(remoteObjectUrlToRevoke);
    };
  }, [previewFile]);

  const handleDownload = async (file: any) => {
    if (file.originalFile) {
      const url = URL.createObjectURL(file.originalFile);
      const a = document.createElement('a');
      a.href = url;
      a.download = file.name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } else {
      try {
        const u = await getInputFileUrl(file.name, 900);
        if (u?.url) {
          const a = document.createElement('a');
          a.href = u.url;
          a.target = '_blank';
          a.rel = 'noreferrer';
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          return;
        }
      } catch {
        // Fall through to blob download.
      }

      try {
        const { body, mediaType } = await getInputFile(file.name);
        const coerced = coerceBlobForPreview(body, file.name, mediaType);
        const url = URL.createObjectURL(coerced);
        const a = document.createElement('a');
        a.href = url;
        a.download = file.name;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      } catch (e) {
        alert(e instanceof Error ? e.message : 'Download failed');
      }
    }
  };

  const handleViewMetadata = async (file: FileItem) => {
    setMetadataFileName(file.name);
    setMetadataLoading(true);
    setMetadataDetail(null);
    setActiveDropdown(null);
    try {
      const data = await getFileMetadata(file.name);
      setMetadataDetail(data as unknown as Record<string, unknown>);
    } catch (e) {
      console.error(e);
      setMetadataDetail({
        error: e instanceof Error ? e.message : 'Failed to load metadata',
      });
    } finally {
      setMetadataLoading(false);
    }
  };

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = () => {
      setActiveDropdown(null);
      setIsFilterOpen(false);
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, []);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      void onRefreshFiles({
        skip: (page - 1) * pageSize,
        limit: pageSize,
        query: searchTerm.trim() || undefined,
        type: filterType === 'all' ? undefined : filterType,
        sort_by: sortBy,
        sort_dir: sortOrder,
      });
    }, 250);
    return () => window.clearTimeout(handle);
  }, [filterType, onRefreshFiles, page, pageSize, searchTerm, sortBy, sortOrder]);

  const processNewFiles = async (fileList: FileList | File[]) => {
    const arr = Array.from(fileList);
    if (arr.length === 0) return;
    setUploadBusy(true);
    setUploadProgress({ current: 0, total: arr.length });
    try {
      if (arr.length === 1) {
        await uploadFiles(arr);
        setUploadProgress({ current: 1, total: 1 });
      } else {
        let count = 0;
        // Batch upload 5 at a time
        const batchSize = 5;
        for (let i = 0; i < arr.length; i += batchSize) {
          const batch = arr.slice(i, i + batchSize);
          await uploadFiles(batch);
          count += batch.length;
          setUploadProgress({ current: Math.min(count, arr.length), total: arr.length });
        }
      }
      await refreshCurrentPage(true);
    } catch (e) {
      console.error(e);
      alert(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      setUploadBusy(false);
      setUploadProgress(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleRunProcess = async () => {
    if (pipelineBusyRef.current !== 'idle') return;

    let selectedRows = files.filter((f) => selectedFiles.includes(f.id));
    if (selectedRows.length === 0 && selectedFiles.length > 0) {
      selectedRows = filteredAndSortedFiles.filter((f) => selectedFiles.includes(f.id));
    }
    if (selectedRows.length === 0) {
      alert('No selected files resolved for processing. Please re-select the file(s) and try again.');
      return;
    }

    const selectedPaths = selectedRows
      .map((f) => f.storagePath)
      .filter((p): p is string => Boolean(p));
    const targetNames = selectedRows.map((f) => f.name).filter(Boolean);
    const initialProgress = computePipelineProgress('process', targetNames, files);

    setPipelineBusySafe('process');
    setPipelineProgress(initialProgress);
    const token = ++pipelineJobTokenRef.current;
    startPipelinePolling(token, 'process');

    try {
      await runProcess(false, selectedPaths, pipelineMode);
      await refreshCurrentPage(true);
    } catch (e) {
      console.error(e);
      alert(e instanceof Error ? e.message : 'Process failed');
    } finally {
      stopPipelinePolling();
      setPipelineBusySafe('idle');
      setPipelineProgress(null);
    }
  };

  const handleRunIndex = async () => {
    if (pipelineBusyRef.current !== 'idle') return;

    let selectedRows = files.filter((f) => selectedFiles.includes(f.id));
    // Fallback to currently rendered rows if list ids drift after refresh/sort.
    if (selectedRows.length === 0 && selectedFiles.length > 0) {
      selectedRows = filteredAndSortedFiles.filter((f) => selectedFiles.includes(f.id));
    }
    if (selectedRows.length === 0) {
      alert('No selected files resolved for indexing. Please re-select the file and try again.');
      return;
    }

    const selectedPaths = selectedRows
      .map((f) => f.storagePath)
      .filter((p): p is string => Boolean(p));
    const selectedNames = selectedRows.map((f) => f.name).filter(Boolean);
    const initialProgress = computePipelineProgress('index', selectedNames, files);

    setPipelineBusySafe('index');
    setPipelineProgress(initialProgress);
    const token = ++pipelineJobTokenRef.current;
    startPipelinePolling(token, 'index');

    try {
      const result = await runIndex(false, selectedPaths, selectedNames, pipelineMode);
      setLastIndexResult(result as Record<string, any>);
      await refreshCurrentPage(true);
    } catch (e) {
      console.error(e);
      alert(e instanceof Error ? e.message : 'Index failed');
    } finally {
      stopPipelinePolling();
      setPipelineBusySafe('idle');
      setPipelineProgress(null);
    }
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files.length > 0) {
      void processNewFiles(event.target.files);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processNewFiles(e.dataTransfer.files);
    }
  };

  // File Management Actions
  const handleRename = (id: number, newName: string) => {
    if (newName.trim()) {
      setFiles(files.map(f => f.id === id ? { ...f, name: newName.trim() } : f));
    }
    setRenamingFileId(null);
    setNewName('');
    setActiveDropdown(null);
  };

  const handleDelete = async (id: number) => {
    const row = files.find((f) => f.id === id);
    if (!row) return;
    const confirmed = window.confirm(`Delete "${row.name}"?\n\nThis action cannot be undone.`);
    if (!confirmed) {
      setActiveDropdown(null);
      return;
    }
    const path = row?.storagePath;
    setDeletingIds((prev) => new Set([...prev, id]));
    setActiveDropdown(null);
    if (!path) {
      setFiles(files.filter((f) => f.id !== id));
      setSelectedFiles(selectedFiles.filter((selectedId) => selectedId !== id));
      setDeletingIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      return;
    }
    try {
      await deleteFile(path);
      await refreshCurrentPage(true);
    } catch (e) {
      console.error(e);
      alert(e instanceof Error ? e.message : 'Delete failed');
    } finally {
      setSelectedFiles(selectedFiles.filter((selectedId) => selectedId !== id));
      setDeletingIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  const handleBulkDelete = async () => {
    const toRemove = files.filter((f) => selectedFiles.includes(f.id));
    if (toRemove.length === 0) return;
    const confirmed = window.confirm(
      `Delete ${toRemove.length} selected file(s)?\n\nThis action cannot be undone.`
    );
    if (!confirmed) return;
    setDeletingIds(new Set(toRemove.map((f) => f.id)));
    setBulkDeleteProgress({ current: 0, total: toRemove.length });
    try {
      for (let i = 0; i < toRemove.length; i++) {
        const f = toRemove[i];
        if (f.storagePath) await deleteFile(f.storagePath);
        setBulkDeleteProgress({ current: i + 1, total: toRemove.length });
      }
      await refreshCurrentPage(true);
    } catch (e) {
      console.error(e);
      alert(e instanceof Error ? e.message : 'Bulk delete failed');
    } finally {
      setSelectedFiles([]);
      setDeletingIds(new Set());
      setBulkDeleteProgress(null);
    }
  };

  const toggleSelection = (id: number) => {
    setSelectedFiles(prev => prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]);
  };

  const handleSort = (column: 'date' | 'name' | 'size') => {
    setPage(1);
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortOrder(column === 'name' ? 'asc' : 'desc');
    }
  };

  // Derived State: rows are filtered/sorted/paginated by GET /api/files-with-metadata.
  const filteredAndSortedFiles = files;
  const totalFileRows = Math.max(filesTotal || 0, files.length);
  const totalPages = Math.max(1, Math.ceil(totalFileRows / Math.max(1, pageSize)));

  useEffect(() => {
    setPage((current) => Math.min(Math.max(1, current), totalPages));
  }, [totalPages]);

  const toggleAll = () => {
    if (selectedFiles.length === filteredAndSortedFiles.length && filteredAndSortedFiles.length > 0) {
      setSelectedFiles([]);
    } else {
      setSelectedFiles(filteredAndSortedFiles.map(f => f.id));
    }
  };

  const SortIcon = ({ column }: { column: 'date' | 'name' | 'size' }) => {
    if (sortBy !== column) return null;
    return sortOrder === 'asc' ? <ChevronUp className="w-4 h-4 inline ml-1" /> : <ChevronDown className="w-4 h-4 inline ml-1" />;
  };

  const isPdfPreview =
    !!previewFile &&
    (
      previewFile.type === 'pdf' ||
      previewFile.originalFile?.type === 'application/pdf' ||
      (remotePreview.kind === 'blob' && remotePreview.mime === 'application/pdf')
    );

  const usePdfViewportLayout = isPdfPreview && !previewLoading && !previewError;
  const useFullBleedStatusLayout = previewLoading || !!previewError;
  const isRemoteSignedPdfPreview =
    isPdfPreview &&
    remotePreview.kind === 'blob' &&
    remotePreview.mime === 'application/pdf' &&
    /^https?:\/\//i.test(remotePreview.url);

  const getPdfSrc = () => {
    if (previewUrl) return previewUrl;
    if (remotePreview.kind === 'blob') return remotePreview.url;
    return '';
  };

  const openPreviewInNewTab = () => {
    if (remotePreview.kind === 'office') {
      window.open(remotePreview.sourceUrl, '_blank', 'noopener,noreferrer');
      return;
    }
    const src = getPdfSrc() || previewUrl || (remotePreview.kind === 'blob' ? remotePreview.url : '');
    if (!src) return;
    window.open(src, '_blank', 'noopener,noreferrer');
  };

  return (
    <div className="w-full space-y-7 pb-12">
      {/* Upload/Pipeline/Index Control Section */}
      {controlMode === 'upload' && (
        <div
          className={`border-2 border-dashed rounded-2xl p-12 text-center transition-colors ${isDragging ? 'border-sky-500 bg-sky-50' : 'border-slate-300 bg-white hover:border-sky-400 hover:bg-slate-50'
            }`}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          onClick={() => void refreshCurrentPage(true)}
        >
          <div className="w-16 h-16 bg-sky-100 text-sky-600 rounded-full flex items-center justify-center mx-auto mb-4">
            <UploadCloud className="w-8 h-8" />
          </div>
          <h3 className="text-xl font-semibold text-slate-900 mb-2">Upload Educational Content</h3>
          <p className="text-slate-500 max-w-md mx-auto mb-6">
            Drag and drop your video lectures, PDFs, presentations, or spreadsheets here.
            BK-MInD will automatically process, transcribe, and index them for RAG.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <input
              type="file"
              multiple
              className="hidden"
              ref={fileInputRef}
              onChange={handleFileUpload}
            />
            <button
              type="button"
              disabled={uploadBusy}
              onClick={() => {
                void refreshCurrentPage(true);
                fileInputRef.current?.click();
              }}
              className="px-6 py-2.5 bg-sky-600 text-white rounded-lg font-medium hover:bg-sky-700 transition-colors disabled:opacity-50"
            >
              {uploadBusy && uploadProgress !== null
                ? `Uploading… ${uploadProgress.current}/${uploadProgress.total}`
                : uploadBusy
                ? 'Uploading…'
                : 'Browse Files'}
            </button>
          </div>
          <p className="mt-4 text-center text-xs text-slate-500 max-w-xl mx-auto">
            Upload sends files to the API <code className="bg-slate-100 px-1 rounded">POST /api/upload</code>. After uploading, go to the <span className="font-semibold text-sky-600">Run Pipeline</span> tab to process your files.
          </p>
          <div className="mt-8 flex items-center justify-center gap-6 text-xs text-slate-400 flex-wrap">
            <span className="flex items-center gap-1.5"><Video className="w-4 h-4" /> MP4, AVI, MOV</span>
            <span className="flex items-center gap-1.5"><FileText className="w-4 h-4" /> PDF, DOCX, PPTX</span>
            <span className="flex items-center gap-1.5"><FileText className="w-4 h-4" /> XLSX, CSV</span>
            <span className="flex items-center gap-1.5"><ImageIcon className="w-4 h-4" /> PNG, JPG</span>
            <span className="flex items-center gap-1.5"><Music className="w-4 h-4" /> MP3, WAV, AAC</span>
          </div>
        </div>
      )}

      {(controlMode === 'process' || controlMode === 'index') && (
        <div className="bg-white rounded-2xl border border-sky-100 shadow-[0_16px_36px_-28px_rgba(14,165,233,0.55)] p-8">
          <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.5fr)_auto] items-center gap-8 xl:gap-12">
            <div className="space-y-2 text-center xl:text-left">
              <h3 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2 justify-center md:justify-start">
                {controlMode === 'process' ? <><Play className="w-5 h-5 text-sky-600" /> Pipeline Control</> : <><Layers className="w-5 h-5 text-emerald-600" /> Vector Index Control</>}
              </h3>
              <p className="text-slate-500 font-medium leading-relaxed xl:max-w-2xl">
                {controlMode === 'process'
                  ? 'Select staged files from the library below to start transcription and insight extraction.'
                  : 'Select processed files to build the semantic search index.'}
              </p>
              <p className="text-xs text-slate-600 xl:max-w-2xl">
                {controlMode === 'process'
                  ? 'Estimated time: 3 - 5s per page.'
                  : 'Estimated time: 7s per page.'}
              </p>
              <p className="text-xs text-amber-700 xl:max-w-2xl">
                Note: Actual processing time can vary depending on the number of active users currently using the system.
              </p>
              <p className="text-xs text-slate-500 xl:max-w-2xl">
                Uploading only places files in staged state. Run Pipeline first to move files to <span className="font-semibold">Processed</span>, then Build Index to make them searchable in Knowledge Explorer and visible as chunks in Lecture Viewer.
              </p>
            </div>

            <div className="flex flex-wrap items-center justify-center xl:justify-end gap-4">
              <div className="flex items-center gap-2 px-4 py-2.5 bg-slate-50 rounded-xl border border-slate-200">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Mode</span>
                <select
                  value={pipelineMode}
                  onChange={(e) => setPipelineMode(e.target.value as 'standard' | 'fast')}
                  className="bg-transparent border-none text-sm font-bold text-slate-900 focus:ring-0 p-0 pr-8 cursor-pointer"
                  disabled={pipelineBusy !== 'idle'}
                >
                  <option value="standard">Standard</option>
                  <option value="fast">Fast</option>
                </select>
              </div>

              {controlMode === 'process' ? (
                <button
                  type="button"
                  disabled={pipelineBusy !== 'idle' || selectedFiles.length === 0}
                  onClick={() => void handleRunProcess()}
                  className="flex items-center gap-3 px-8 py-3.5 bg-sky-600 text-white rounded-xl font-bold hover:bg-sky-700 transition-all disabled:opacity-50 shadow-lg shadow-sky-100 hover:-translate-y-0.5 active:translate-y-0"
                >
                  {pipelineBusy === 'process' ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5" />}
                  {pipelineBusy === 'process'
                    ? `Processing… ${pipelineProgress?.mode === 'process' ? `${pipelineProgress.completed}/${pipelineProgress.total}` : ''}`.trim()
                    : `Run Pipeline (${selectedFiles.length})`}
                </button>
              ) : (
                <button
                  type="button"
                  disabled={pipelineBusy !== 'idle' || selectedFiles.length === 0}
                  onClick={() => void handleRunIndex()}
                  className="flex items-center gap-3 px-8 py-3.5 bg-emerald-600 text-white rounded-xl font-bold hover:bg-emerald-700 transition-all disabled:opacity-50 shadow-lg shadow-emerald-100 hover:-translate-y-0.5 active:translate-y-0"
                >
                  {pipelineBusy === 'index' ? <Loader2 className="w-5 h-5 animate-spin" /> : <Layers className="w-5 h-5" />}
                  {pipelineBusy === 'index'
                    ? `Indexing… ${pipelineProgress?.mode === 'index' ? `${pipelineProgress.completed}/${pipelineProgress.total}` : ''}`.trim()
                    : `Build Vector Index (${selectedFiles.length})`}
                </button>
              )}
            </div>
          </div>

          {pipelineBusy !== 'idle' && pipelineProgress && (
            <div className="mt-6 rounded-xl border border-sky-100 bg-sky-50/70 p-4">
              <div className="flex items-center justify-between gap-3 text-xs font-semibold text-slate-700">
                <span>{pipelineProgress.mode === 'process' ? 'Pipeline progress' : 'Index progress'}</span>
                <span>
                  {pipelineProgress.completed}/{pipelineProgress.total} ({pipelineProgress.percent}%)
                </span>
              </div>
              <div className="mt-2 w-full h-2 rounded-full bg-sky-100 overflow-hidden">
                <div
                  className={`h-full transition-all duration-500 ${pipelineProgress.mode === 'process' ? 'bg-sky-500' : 'bg-emerald-500'}`}
                  style={{ width: `${pipelineProgress.percent}%` }}
                />
              </div>
              <p className="mt-2 text-[11px] text-slate-500">
                {pipelineProgress.mode === 'process'
                  ? 'Tracking selected files as they move from Uploaded to Processed/Indexed.'
                  : 'Tracking selected files as they move to Indexed status.'}
              </p>
            </div>
          )}
        </div>
      )}

      {controlMode === 'index' && lastIndexResult && (
        <div className="rounded-2xl border border-emerald-100 bg-white p-4 shadow-[0_12px_26px_-22px_rgba(16,185,129,0.45)]">
          <div className="mb-3 flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            <h3 className="text-sm font-bold uppercase tracking-tight text-slate-800">Last Index Timing</h3>
          </div>
          {lastIndexResult.artifact_path && (
            <p className="mb-3 break-all rounded-md bg-slate-50 px-2 py-1 text-xs text-slate-500">
              Saved JSON: {lastIndexResult.artifact_path}
            </p>
          )}
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            {[
              ['Wall total', formatMs(lastIndexResult.results?.timings_ms?.total_ms)],
              ['Text index', formatMs(lastIndexResult.results?.timings_ms?.text_total_ms)],
              ['Text embed', formatMs(lastIndexResult.results?.timings_ms?.text_embed_ms)],
              ['Text upsert', formatMs(lastIndexResult.results?.text?.timings_ms?.qdrant_upsert_ms)],
              ['Image index', formatMs(lastIndexResult.results?.timings_ms?.image_total_ms)],
              ['Image embed', formatMs(lastIndexResult.results?.timings_ms?.image_embed_ms)],
              ['Image render', formatMs(lastIndexResult.results?.image?.timings_ms?.render_pages_ms)],
              ['Image upsert', formatMs(lastIndexResult.results?.image?.timings_ms?.qdrant_upsert_ms)],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg border border-emerald-100 bg-emerald-50/40 px-3 py-2">
                <p className="text-[10px] font-bold uppercase tracking-tight text-emerald-800">{label}</p>
                <p className="text-base font-black text-slate-900">{value}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* File List Section */}
      <div className="bg-white rounded-2xl border border-sky-100 shadow-[0_16px_36px_-28px_rgba(14,165,233,0.55)] overflow-hidden">
        <div className="p-4 border-b border-sky-100 flex items-center justify-between bg-sky-50/40">
          <div className="flex items-center gap-4">
            <h3 className="text-lg font-semibold text-slate-900">Content Library</h3>
            {selectedFiles.length > 0 && (
              <div className="flex items-center gap-3 px-3 py-1.5 bg-sky-50 border border-sky-100 rounded-lg">
                <span className="text-sm font-medium text-sky-700">{selectedFiles.length} selected</span>
                <div className="w-px h-4 bg-sky-200"></div>
                <button
                  onClick={handleBulkDelete}
                  disabled={bulkDeleteProgress !== null}
                  className={`text-sm font-medium flex items-center gap-1 transition-colors ${
                    bulkDeleteProgress !== null
                      ? 'text-amber-600 cursor-wait'
                      : 'text-red-600 hover:text-red-700'
                  }`}
                >
                  {bulkDeleteProgress !== null ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Deleting {bulkDeleteProgress.current}/{bulkDeleteProgress.total}
                    </>
                  ) : (
                    <>
                      <Trash2 className="w-4 h-4" /> Delete
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search files..."
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value);
                  setPage(1);
                }}
                className="pl-9 pr-4 py-2 border border-sky-100 bg-white rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 w-64"
              />
            </div>
            <div className="flex bg-slate-100 p-1 rounded-lg">
              <button
                onClick={() => setViewMode('list')}
                className={`p-1.5 rounded-md transition-colors ${viewMode === 'list' ? 'bg-white shadow-sm text-sky-600' : 'text-slate-500 hover:text-slate-700'}`}
                title="List View"
              >
                <List className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode('grid')}
                className={`p-1.5 rounded-md transition-colors ${viewMode === 'grid' ? 'bg-white shadow-sm text-sky-600' : 'text-slate-500 hover:text-slate-700'}`}
                title="Grid View"
              >
                <LayoutGrid className="w-4 h-4" />
              </button>
            </div>
            <div className="relative">
              <button
                onClick={(e) => { e.stopPropagation(); setIsFilterOpen(!isFilterOpen); setActiveDropdown(null); }}
                className={`p-2 border rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${filterType !== 'all' ? 'bg-sky-50 border-sky-200 text-sky-700' : 'border-slate-300 text-slate-600 hover:bg-slate-50'
                  }`}
              >
                <Filter className="w-4 h-4" />
                {filterType === 'all' ? 'Filter' : filterType.charAt(0).toUpperCase() + filterType.slice(1)}
              </button>
              {isFilterOpen && (
                <div className="absolute right-0 mt-2 w-48 bg-white rounded-xl shadow-lg border border-slate-200 py-1 z-10" onClick={e => e.stopPropagation()}>
                  {['all', 'document', 'pdf', 'video', 'image', 'spreadsheet', 'audio'].map(type => (
                    <button
                      key={type}
                      onClick={() => { setFilterType(type); setPage(1); setIsFilterOpen(false); }}
                      className={`w-full text-left px-4 py-2 text-sm hover:bg-slate-50 ${filterType === type ? 'text-sky-600 font-medium bg-sky-50/50' : 'text-slate-700'}`}
                    >
                      {type === 'all' ? 'All Types' : type.charAt(0).toUpperCase() + type.slice(1)}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {viewMode === 'list' ? (
          <div className="overflow-x-auto min-h-[300px]">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="bg-sky-50/60 text-slate-500 font-medium border-b border-sky-100">
                <tr>
                  <th className="px-6 py-4 w-12">
                    <input
                      type="checkbox"
                      checked={selectedFiles.length === filteredAndSortedFiles.length && filteredAndSortedFiles.length > 0}
                      onChange={toggleAll}
                      className="rounded border-slate-300 text-sky-600 focus:ring-sky-500"
                    />
                  </th>
                  <th className="px-6 py-4 cursor-pointer hover:text-slate-700 select-none" onClick={() => handleSort('name')}>
                    File Name <SortIcon column="name" />
                  </th>
                  <th className="px-6 py-4">Type</th>
                  <th className="px-6 py-4 cursor-pointer hover:text-slate-700 select-none" onClick={() => handleSort('size')}>
                    Size <SortIcon column="size" />
                  </th>
                  <th className="px-6 py-4 cursor-pointer hover:text-slate-700 select-none" onClick={() => handleSort('date')}>
                    Date Added <SortIcon column="date" />
                  </th>
                  <th className="px-6 py-4">Status</th>
                  <th className="px-6 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filesLoading ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-slate-500">
                      <Loader2 className="w-5 h-5 animate-spin inline-block mr-2 text-sky-600" />
                      Loading files...
                    </td>
                  </tr>
                ) : filteredAndSortedFiles.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-slate-500">
                      No files found matching your criteria.
                    </td>
                  </tr>
                ) : (
                  filteredAndSortedFiles.map((file) => (
                    <tr
                      key={file.id}
                      className={`transition-colors group hover:bg-sky-50/40 ${selectedFiles.includes(file.id) ? 'bg-sky-50/30' : ''}`}
                    >
                      <td className="px-6 py-4">
                        <input
                          type="checkbox"
                          checked={selectedFiles.includes(file.id)}
                          onChange={() => toggleSelection(file.id)}
                          className="rounded border-slate-300 text-sky-600 focus:ring-sky-500"
                        />
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className={`p-2 rounded-lg ${file.type === 'video' ? 'bg-sky-100 text-sky-600' :
                            file.type === 'document' ? 'bg-blue-100 text-blue-600' :
                              file.type === 'pdf' ? 'bg-red-100 text-red-600' :
                                file.type === 'spreadsheet' ? 'bg-emerald-100 text-emerald-600' :
                                  file.type === 'audio' ? 'bg-purple-100 text-purple-600' :
                                    'bg-amber-100 text-amber-600'
                            }`}>
                            {file.type === 'video' ? <Video className="w-4 h-4" /> :
                              file.type === 'document' ? <FileText className="w-4 h-4" /> :
                                file.type === 'pdf' ? <File className="w-4 h-4" /> :
                                  file.type === 'spreadsheet' ? <FileText className="w-4 h-4" /> :
                                    file.type === 'audio' ? <Music className="w-4 h-4" /> :
                                      <ImageIcon className="w-4 h-4" />}
                          </div>
                          <div>
                            {renamingFileId === file.id ? (
                              <input
                                type="text"
                                value={newName}
                                onChange={(e) => setNewName(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') handleRename(file.id, newName);
                                  if (e.key === 'Escape') setRenamingFileId(null);
                                }}
                                autoFocus
                                className="w-full px-2 py-1 text-sm border border-sky-300 rounded focus:outline-none focus:ring-2 focus:ring-sky-500"
                                onBlur={() => handleRename(file.id, newName)}
                                onClick={e => e.stopPropagation()}
                              />
                            ) : (
                              <p
                                className="font-medium truncate max-w-[250px] cursor-pointer hover:text-sky-600 text-slate-900"
                                title={file.name}
                                onClick={() => setPreviewFile(file)}
                              >
                                {file.name}
                              </p>
                            )}
                            <p className="text-xs mt-0.5 text-slate-400">
                              {file.duration && `Duration: ${file.duration}`}
                              {file.pages && `Pages: ${file.pages}`}
                              {file.rows && `Rows: ${file.rows}`}
                              {file.resolution && `Res: ${file.resolution}`}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 capitalize">{file.type}</td>
                      <td className="px-6 py-4 whitespace-nowrap">{file.size}</td>
                      <td className="px-6 py-4 whitespace-nowrap">{file.date}</td>
                      <td className="px-6 py-4">
                        <div className="flex flex-wrap items-center gap-2">
                        {file.status === 'indexed' && (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            {file.indexStatus === 'all'
                              ? 'Indexed (All)'
                              : file.indexStatus === 'text'
                                ? 'Indexed (Text)'
                                : file.indexStatus === 'image'
                                  ? 'Indexed (Image)'
                                  : 'Indexed'}
                          </span>
                        )}
                        {file.status === 'uploading' && (
                          <div className="flex flex-col gap-1.5 w-48">
                            <div className="flex items-center justify-between">
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-medium bg-blue-100 text-blue-700">
                                <UploadCloud className="w-3 h-3 animate-bounce" />
                                Uploading {file.progress}%
                              </span>
                              <span className="text-[10px] text-slate-500">{file.timeRemaining}s left</span>
                            </div>
                            <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                              <div className="h-full bg-blue-500 rounded-full transition-all duration-300" style={{ width: `${file.progress}%` }}></div>
                            </div>
                            <div className="text-[10px] text-slate-400 text-right">
                              {formatBytes(file.uploadedBytes)} / {formatBytes(file.rawSize)}
                            </div>
                          </div>
                        )}
                        {file.status === 'uploaded' && (
                          <span
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-800 cursor-default"
                            title="Uploaded to storage. Click “Run pipeline (process)”, then “Build index” on the server."
                          >
                            Uploaded
                          </span>
                        )}
                        {file.status === 'processed' && (
                          <span
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-sky-100 text-sky-800 cursor-default"
                            title="Processing is done. Build index to make this searchable."
                          >
                            Processed
                          </span>
                        )}
                        {file.status === 'processing' && (
                          <div className="flex items-center gap-2">
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-sky-100 text-sky-700">
                              <div className="w-3.5 h-3.5 border-2 border-sky-600 border-t-transparent rounded-full animate-spin"></div>
                              Processing
                            </span>
                            {typeof file.progress === 'number' && (
                              <span className="text-xs text-slate-500">{file.progress}%</span>
                            )}
                          </div>
                        )}
                        {file.status === 'failed' && (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">
                            <AlertCircle className="w-3.5 h-3.5" />
                            Failed
                          </span>
                        )}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-right relative">
                        <button
                          onClick={(e) => { e.stopPropagation(); setActiveDropdown(activeDropdown === file.id ? null : file.id); setIsFilterOpen(false); }}
                          className={`p-1.5 rounded-lg transition-all ${activeDropdown === file.id ? 'bg-slate-200 text-slate-800' : 'text-slate-400 hover:text-slate-600 hover:bg-slate-100 opacity-0 group-hover:opacity-100'}`}
                        >
                          <MoreVertical className="w-5 h-5" />
                        </button>

                        {activeDropdown === file.id && (
                          <div className="absolute right-8 top-10 w-40 bg-white rounded-xl shadow-lg border border-slate-200 py-1 z-10" onClick={e => e.stopPropagation()}>
                            {/* <button onClick={() => setPreviewFile(file)} className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2">
                              <Eye className="w-4 h-4" /> Preview
                            </button> */}
                            <button onClick={() => { setRenamingFileId(file.id); setNewName(file.name); setActiveDropdown(null); }} className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2">
                              <Edit2 className="w-4 h-4" /> Rename
                            </button>
                            <button onClick={() => { void handleDownload(file); setActiveDropdown(null); }} className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2">
                              <Download className="w-4 h-4" /> Download
                            </button>
                            <button onClick={() => void handleViewMetadata(file)} className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2">
                              <Eye className="w-4 h-4" /> View metadata
                            </button>
                            <div className="h-px bg-slate-100 my-1"></div>
                            <button
                              onClick={() => handleDelete(file.id)}
                              disabled={deletingIds.has(file.id)}
                              className={`w-full text-left px-4 py-2 text-sm flex items-center gap-2 transition-colors ${
                                deletingIds.has(file.id)
                                  ? 'text-amber-600 bg-amber-50 cursor-wait'
                                  : 'text-red-600 hover:bg-red-50'
                              }`}
                            >
                              {deletingIds.has(file.id) ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : (
                                <Trash2 className="w-4 h-4" />
                              )}
                              {deletingIds.has(file.id) ? 'Deleting...' : 'Delete'}
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-6 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6 min-h-[300px]">
            {filesLoading ? (
              <div className="col-span-full text-center text-slate-500 py-12">
                <Loader2 className="w-5 h-5 animate-spin inline-block mr-2 text-sky-600" />
                Loading files...
              </div>
            ) : filteredAndSortedFiles.length === 0 ? (
              <div className="col-span-full text-center text-slate-500 py-12">
                No files found matching your criteria.
              </div>
            ) : (
              filteredAndSortedFiles.map((file) => (
                <div
                  key={file.id}
                  className={`relative group border rounded-xl p-4 transition-all ${
                    selectedFiles.includes(file.id)
                      ? 'border-sky-500 bg-sky-50/30'
                      : 'border-sky-100 hover:border-sky-300 hover:shadow-md bg-white'
                  }`}
                >
                  <div className="absolute top-3 left-3 z-10">
                    <input
                      type="checkbox"
                      checked={selectedFiles.includes(file.id)}
                      onChange={() => toggleSelection(file.id)}
                      className="rounded border-slate-300 text-sky-600 focus:ring-sky-500 opacity-0 group-hover:opacity-100 transition-opacity"
                      style={{ opacity: selectedFiles.includes(file.id) ? 1 : undefined }}
                    />
                  </div>
                  <div className="absolute top-2 right-2 z-10">
                    <button
                      onClick={(e) => { e.stopPropagation(); setActiveDropdown(activeDropdown === file.id ? null : file.id); setIsFilterOpen(false); }}
                      className={`p-1.5 rounded-lg transition-all ${activeDropdown === file.id ? 'bg-slate-200 text-slate-800' : 'text-slate-400 hover:text-slate-600 hover:bg-slate-100 opacity-0 group-hover:opacity-100'}`}
                    >
                      <MoreVertical className="w-5 h-5" />
                    </button>
                    {activeDropdown === file.id && (
                      <div className="absolute right-0 top-8 w-40 bg-white rounded-xl shadow-lg border border-slate-200 py-1 z-20" onClick={e => e.stopPropagation()}>
                        <button onClick={() => setPreviewFile(file)} className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2">
                          <Eye className="w-4 h-4" /> Preview
                        </button>
                        <button onClick={() => { setRenamingFileId(file.id); setNewName(file.name); setActiveDropdown(null); }} className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2">
                          <Edit2 className="w-4 h-4" /> Rename
                        </button>
                        <button onClick={() => { void handleDownload(file); setActiveDropdown(null); }} className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2">
                          <Download className="w-4 h-4" /> Download
                        </button>
                        <button onClick={() => void handleViewMetadata(file)} className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2">
                          <Eye className="w-4 h-4" /> View metadata
                        </button>
                        <div className="h-px bg-slate-100 my-1"></div>
                        <button
                          onClick={() => handleDelete(file.id)}
                          disabled={deletingIds.has(file.id)}
                          className={`w-full text-left px-4 py-2 text-sm flex items-center gap-2 transition-colors ${
                            deletingIds.has(file.id)
                              ? 'text-amber-600 bg-amber-50 cursor-wait'
                              : 'text-red-600 hover:bg-red-50'
                          }`}
                        >
                          {deletingIds.has(file.id) ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Trash2 className="w-4 h-4" />
                          )}
                          {deletingIds.has(file.id) ? 'Deleting...' : 'Delete'}
                        </button>
                      </div>
                    )}
                  </div>

                  <div className="flex flex-col items-center text-center mt-2 cursor-pointer" onClick={() => setPreviewFile(file)}>
                    <div className={`w-16 h-16 rounded-2xl flex items-center justify-center mb-4 ${file.type === 'video' ? 'bg-sky-100 text-sky-600' :
                      file.type === 'document' ? 'bg-blue-100 text-blue-600' :
                        file.type === 'pdf' ? 'bg-red-100 text-red-600' :
                          file.type === 'spreadsheet' ? 'bg-emerald-100 text-emerald-600' :
                            file.type === 'audio' ? 'bg-purple-100 text-purple-600' :
                              'bg-amber-100 text-amber-600'
                      }`}>
                      {file.type === 'video' ? <Video className="w-8 h-8" /> :
                        file.type === 'document' ? <FileText className="w-8 h-8" /> :
                          file.type === 'pdf' ? <File className="w-8 h-8" /> :
                            file.type === 'spreadsheet' ? <FileText className="w-8 h-8" /> :
                              file.type === 'audio' ? <Music className="w-8 h-8" /> :
                                <ImageIcon className="w-8 h-8" />}
                    </div>

                    {renamingFileId === file.id ? (
                      <div className="w-full px-2" onClick={e => e.stopPropagation()}>
                        <input
                          type="text"
                          value={newName}
                          onChange={(e) => setNewName(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleRename(file.id, newName);
                            if (e.key === 'Escape') setRenamingFileId(null);
                          }}
                          autoFocus
                          className="w-full px-2 py-1 text-sm border border-sky-300 rounded focus:outline-none focus:ring-2 focus:ring-sky-500 text-center"
                          onBlur={() => handleRename(file.id, newName)}
                        />
                      </div>
                    ) : (
                      <h4
                        className="font-medium text-sm line-clamp-2 mb-1 px-2 hover:text-sky-600 text-slate-900"
                        title={file.name}
                      >
                        {file.name}
                      </h4>
                    )}

                    <div className="text-xs flex items-center gap-2 mt-2 text-slate-500">
                      <span>{file.size}</span>
                      <span>•</span>
                      <span>{file.date}</span>
                    </div>

                    <div className="mt-3">
                      <div className="flex flex-wrap justify-center gap-1.5">
                      {file.status === 'indexed' && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-100 text-emerald-700">
                          <CheckCircle2 className="w-3 h-3" /> {file.indexStatus === 'all'
                            ? 'Indexed All'
                            : file.indexStatus === 'text'
                              ? 'Indexed Text'
                              : file.indexStatus === 'image'
                                ? 'Indexed Image'
                                : 'Indexed'}
                        </span>
                      )}
                      {file.status === 'uploading' && (
                        <div className="flex flex-col gap-1 w-full">
                          <div className="flex items-center justify-between">
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-100 text-blue-700">
                              <UploadCloud className="w-3 h-3 animate-bounce" /> Uploading
                            </span>
                            <span className="text-[10px] text-slate-500">{file.progress}%</span>
                          </div>
                          <div className="w-full h-1 bg-slate-100 rounded-full overflow-hidden mt-1">
                            <div className="h-full bg-blue-500 rounded-full transition-all duration-300" style={{ width: `${file.progress}%` }}></div>
                          </div>
                          <div className="flex justify-between text-[9px] text-slate-400 mt-0.5">
                            <span>{formatBytes(file.uploadedBytes)} / {formatBytes(file.rawSize)}</span>
                            <span>{file.timeRemaining}s left</span>
                          </div>
                        </div>
                      )}
                      {file.status === 'uploaded' && (
                        <span
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-100 text-amber-800"
                          title="Run Process, then Build index"
                        >
                          Uploaded
                        </span>
                      )}
                      {file.status === 'processed' && (
                        <span
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-sky-100 text-sky-800"
                          title="Processed. Run Build index to index this file."
                        >
                          Processed
                        </span>
                      )}
                      {file.status === 'processing' && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-sky-100 text-sky-700">
                          <Loader2 className="w-3 h-3 animate-spin" /> Processing
                          {typeof file.progress === 'number' ? ` ${file.progress}%` : ''}
                        </span>
                      )}
                      {file.status === 'failed' && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-red-100 text-red-700">
                          <AlertCircle className="w-3 h-3" /> Failed
                        </span>
                      )}
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
        <div className="border-t border-slate-100 px-4 py-3">
          <AdminTablePagination
            page={page}
            pageSize={pageSize}
            totalItems={totalFileRows}
            onPageChange={(next) => setPage(Math.min(Math.max(1, next), totalPages))}
            onPageSizeChange={(nextSize) => {
              setPageSize(nextSize);
              setPage(1);
            }}
            itemLabel="files"
          />
        </div>
      </div>

      {/* Preview Modal */}
      {previewFile && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm" onClick={() => setPreviewFile(null)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-5xl max-h-[92vh] flex flex-col overflow-hidden border border-sky-100" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b border-sky-100 bg-sky-50/40">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${previewFile.type === 'video' ? 'bg-sky-100 text-sky-600' :
                  previewFile.type === 'document' ? 'bg-blue-100 text-blue-600' :
                    previewFile.type === 'pdf' ? 'bg-red-100 text-red-600' :
                      previewFile.type === 'spreadsheet' ? 'bg-emerald-100 text-emerald-600' :
                        previewFile.type === 'audio' ? 'bg-purple-100 text-purple-600' :
                          'bg-amber-100 text-amber-600'
                  }`}>
                  {previewFile.type === 'video' ? <Video className="w-5 h-5" /> :
                    previewFile.type === 'document' ? <FileText className="w-5 h-5" /> :
                      previewFile.type === 'pdf' ? <File className="w-5 h-5" /> :
                        previewFile.type === 'spreadsheet' ? <FileText className="w-5 h-5" /> :
                          previewFile.type === 'audio' ? <Music className="w-5 h-5" /> :
                            <ImageIcon className="w-5 h-5" />}
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900">{previewFile.name}</h3>
                  <p className="text-xs text-slate-500">{previewFile.size} • Added {previewFile.date}</p>
                </div>
              </div>
              <button
                onClick={() => setPreviewFile(null)}
                className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                aria-label="Close preview modal"
                title="Close preview"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div
              className={`flex-1 bg-sky-50/40 min-h-[420px] ${usePdfViewportLayout
                ? 'p-0 overflow-hidden'
                : useFullBleedStatusLayout
                  ? 'p-0 overflow-hidden'
                  : 'p-8 flex items-center justify-center overflow-y-auto'
                }`}
            >
              {/* Preview Content */}
              {previewLoading ? (
                <div className="w-full h-full min-h-[420px] bg-white/90 border border-sky-100 flex flex-col items-center justify-center text-center p-8">
                  <Loader2 className="w-8 h-8 animate-spin text-sky-600 mb-4" />
                  <p className="text-sm text-slate-600">Loading preview...</p>
                </div>
              ) : previewError ? (
                <div className="w-full h-full min-h-[420px] bg-white/90 border border-red-200 flex flex-col items-center justify-center text-center p-8">
                  <AlertCircle className="w-10 h-10 text-red-500 mb-4" />
                  <p className="text-sm text-red-700 mb-2">Cannot preview this file.</p>
                  <p className="text-xs text-slate-500 max-w-lg">{previewError}</p>
                </div>
              ) : (previewUrl || remotePreview.kind === 'blob') && (
                (previewFile.type === 'image' || (remotePreview.kind === 'blob' && remotePreview.mime.startsWith('image/')))
              ) ? (
                <img
                  src={previewUrl || (remotePreview.kind === 'blob' ? remotePreview.url : '')}
                  alt={previewFile.name}
                  className="max-w-full max-h-full object-contain rounded-xl shadow-lg"
                />
              ) : (previewUrl || remotePreview.kind === 'blob') && previewFile.type === 'video' ? (
                <video
                  src={previewUrl || (remotePreview.kind === 'blob' ? remotePreview.url : '')}
                  controls
                  className="w-full max-w-2xl aspect-video rounded-xl shadow-lg bg-black"
                />
              ) : (previewUrl || remotePreview.kind === 'blob') && previewFile.type === 'audio' ? (
                <div className="w-full max-w-2xl bg-white rounded-xl shadow-lg border border-slate-200 p-12 flex flex-col items-center justify-center text-center">
                  <div className="w-24 h-24 bg-purple-100 rounded-full flex items-center justify-center mb-8 shadow-inner">
                    <Music className="w-12 h-12 text-purple-600" />
                  </div>
                  <audio src={previewUrl || (remotePreview.kind === 'blob' ? remotePreview.url : '')} controls className="w-full" />
                </div>
              ) : isRemoteSignedPdfPreview ? (
                <iframe
                  title={`PDF: ${previewFile.name}`}
                  src={remotePreview.url}
                  className="w-full h-full min-h-[620px] max-h-[75vh] border-0 bg-white"
                />
              ) : isPdfPreview ? (
                <div
                  ref={pdfContainerRef}
                  className="w-full h-full min-h-[620px] max-h-[75vh] overflow-y-auto bg-sky-100/50 flex flex-col items-center p-5"
                >
                  <Document
                    file={getPdfSrc()}
                    onLoadSuccess={({ numPages: pages }) => setNumPages(pages)}
                    onLoadError={() => setPreviewError('PDF preview failed to render. You can still open/download the original file.')}
                    loading={
                      <div className="w-full max-w-3xl rounded-2xl border border-sky-100 bg-white px-8 py-16 text-center shadow-sm">
                        <Loader2 className="w-8 h-8 animate-spin text-sky-600 mx-auto mb-4" />
                        <p className="text-sm text-slate-600">Loading PDF preview...</p>
                        <button
                          type="button"
                          onClick={openPreviewInNewTab}
                          className="mt-4 px-3 py-2 text-xs font-semibold rounded-lg border border-sky-200 text-sky-700 hover:bg-sky-50"
                        >
                          Open original in new tab
                        </button>
                      </div>
                    }
                    className="flex flex-col items-center gap-4"
                  >
                    {Array.from({ length: numPages || 0 }, (_, index) => (
                      <div key={`page_${index + 1}`} className="shadow-md bg-white">
                        <Page
                          pageNumber={index + 1}
                          width={pdfPageWidth}
                          renderTextLayer={false}
                          renderAnnotationLayer={false}
                        />
                      </div>
                    ))}
                  </Document>
                </div>
              ) : textContent || remotePreview.kind === 'text' ? (
                <div className="w-full h-full min-h-[600px] max-h-[70vh] overflow-y-auto bg-white rounded-xl shadow-lg p-8 border border-slate-200 text-left">
                  <pre className="whitespace-pre-wrap font-mono text-sm text-slate-800">
                    {remotePreview.kind === 'text' ? remotePreview.content : textContent || 'Loading text...'}
                  </pre>
                </div>
              ) : remotePreview.kind === 'html' ? (
                <div className="w-full h-full min-h-[600px] max-h-[70vh] overflow-hidden bg-white rounded-xl shadow-lg border border-slate-200">
                  <iframe
                    title={`HTML: ${previewFile.name}`}
                    srcDoc={remotePreview.content}
                    sandbox=""
                    className="w-full h-full border-0"
                  />
                </div>
              ) : remotePreview.kind === 'office' ? (
                <div className="w-full h-full min-h-[600px] max-h-[70vh] overflow-hidden bg-white rounded-xl shadow-lg border border-slate-200">
                  <div className="px-4 py-2 border-b border-slate-200 bg-slate-50/80 flex items-center justify-between gap-3">
                    <p className="text-xs text-slate-500">Office online preview</p>
                    <a
                      href={remotePreview.sourceUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs font-semibold text-sky-700 hover:text-sky-800"
                    >
                      Open original file
                    </a>
                  </div>
                  <iframe
                    title={`Office: ${previewFile.name}`}
                    src={remotePreview.iframeSrc}
                    className="w-full h-full border-0"
                  />
                </div>
              ) : previewFile.type === 'video' ? (
                <div className="w-full max-w-2xl aspect-video bg-slate-900 rounded-xl flex items-center justify-center shadow-lg relative overflow-hidden">
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="w-16 h-16 bg-white/20 backdrop-blur-md rounded-full flex items-center justify-center cursor-pointer hover:bg-white/30 transition-colors">
                      <div className="w-0 h-0 border-t-8 border-t-transparent border-l-[14px] border-l-white border-b-8 border-b-transparent ml-1"></div>
                    </div>
                  </div>
                  <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/60 to-transparent">
                    <div className="h-1 bg-white/30 rounded-full overflow-hidden">
                      <div className="h-full bg-sky-500 w-1/3"></div>
                    </div>
                  </div>
                </div>
              ) : previewFile.type === 'audio' ? (
                <div className="w-full max-w-2xl bg-white rounded-xl shadow-lg border border-slate-200 p-12 flex flex-col items-center justify-center text-center">
                  <div className="w-24 h-24 bg-purple-100 rounded-full flex items-center justify-center mb-8 shadow-inner">
                    <Music className="w-12 h-12 text-purple-600" />
                  </div>
                  <div className="w-full h-12 bg-slate-100 rounded-full flex items-center px-4">
                    <div className="w-4 h-4 bg-purple-600 rounded-full"></div>
                    <div className="flex-1 h-1 bg-slate-300 mx-4 rounded-full"></div>
                    <div className="text-xs text-slate-500 font-mono">0:00 / 0:00</div>
                  </div>
                </div>
              ) : previewFile.type === 'image' ? (
                <div className="w-full max-w-2xl aspect-video bg-slate-200 rounded-xl flex items-center justify-center shadow-lg overflow-hidden border border-slate-300">
                  <ImageIcon className="w-24 h-24 text-slate-400" />
                </div>
              ) : (
                <div className="w-full max-w-2xl bg-white rounded-xl shadow-lg border border-slate-200 p-12 min-h-[400px] flex flex-col items-center justify-center text-center">
                  <div className="w-20 h-20 bg-slate-100 rounded-full flex items-center justify-center mb-6">
                    <FileText className="w-10 h-10 text-slate-400" />
                  </div>
                  <h3 className="text-xl font-semibold text-slate-900 mb-2">Preview Not Available</h3>
                  <p className="text-slate-500 max-w-md mb-8">
                    This file type cannot be previewed in the browser. Please download the file to view its contents.
                  </p>
                  <button
                    onClick={() => void handleDownload(previewFile)}
                    className="px-6 py-3 text-sm font-medium text-white bg-sky-600 rounded-xl hover:bg-sky-700 transition-colors flex items-center gap-2 shadow-sm"
                  >
                    <Download className="w-5 h-5" />
                    Download File
                  </button>
                </div>
              )}
            </div>
            <div className="p-4 border-t border-sky-100 bg-white flex justify-end gap-3">
              <button
                type="button"
                onClick={openPreviewInNewTab}
                className="px-4 py-2 text-sm font-medium text-sky-700 bg-sky-50 border border-sky-200 rounded-lg hover:bg-sky-100 transition-colors"
              >
                Open Preview
              </button>
              <button onClick={() => void handleDownload(previewFile)} className="px-4 py-2 text-sm font-medium text-white bg-sky-600 rounded-lg hover:bg-sky-700 transition-colors flex items-center gap-2">
                <Download className="w-4 h-4" /> Download Original
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Metadata Modal */}
      {metadataFileName && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm" onClick={() => setMetadataFileName(null)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-3xl max-h-[85vh] flex flex-col overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b border-slate-200">
              <div>
                <h3 className="text-base font-semibold text-slate-900">File metadata</h3>
                <p className="text-xs text-slate-500 mt-0.5">{metadataFileName}</p>
              </div>
              <button
                onClick={() => setMetadataFileName(null)}
                className="p-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg"
                aria-label="Close metadata modal"
                title="Close metadata"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 overflow-auto">
              {metadataLoading ? (
                <div className="flex items-center gap-2 text-slate-500 text-sm">
                  <Loader2 className="w-4 h-4 animate-spin" /> Loading metadata...
                </div>
              ) : (
                <pre className="text-xs leading-5 whitespace-pre-wrap break-all bg-slate-50 border border-slate-200 rounded-xl p-4 text-slate-700">
                  {JSON.stringify(metadataDetail, null, 2)}
                </pre>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
