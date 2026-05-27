import { useState, useEffect, useCallback, useMemo } from 'react'
import axios from 'axios'
import {
  Upload,
  Search,
  FileText,
  Image,
  FolderOpen,
  Loader2,
  CheckCircle,
  XCircle,
  Trash2,
  RefreshCw,
  Database,
  Layers,
  Sparkles,
  File,
  FileImage,
  X,
  Zap,
  Hash,
  AlertCircle,
  ArrowRight,
  Lightbulb,
  Eye,
} from 'lucide-react'

// Components
import SearchBar from './components/SearchBar'
import AnswerPanel from './components/AnswerPanel'
import CitationCard from './components/CitationCard'
import ImageCitation from './components/ImageCitation'
import SettingsPanel from './components/SettingsPanel'
import InsightsPanel from './components/InsightsPanel'
import ProcessedFilePreviewModal from './components/ProcessedFilePreviewModal'
import { getApiBase } from './apiBase'

// API base   see apiBase.js (avoids VITE_API_URL=http://host:8000 missing /api)
const API_BASE = getApiBase()

/** Merge newly uploaded rows into input list (keyed by path). */
function mergeInputByPath(existing, incoming) {
  const map = new Map((existing || []).map((f) => [f.path, f]))
  for (const f of incoming || []) {
    map.set(f.path, f)
  }
  return Array.from(map.values())
}

// File type icon helper
const getFileIcon = (type) => {
  const ext = type?.toLowerCase() || ''
  if (['.pdf', '.docx', '.doc', '.txt', '.md'].includes(ext)) return FileText
  if (['.png', '.jpg', '.jpeg', '.gif', '.webp'].includes(ext)) return FileImage
  return File
}

// Stage info with colors   stage3 is full-doc markdown (Docling), not index “chunks” (those come from Build Index).
const stageInfo = {
  'stage1_normalized': {
    label: 'Normalized',
    color: 'sky',
    step: 1,
    blurb: 'Original uploads and normalized PDF copies.',
  },
  'stage2_media_processed': {
    label: 'Media',
    color: 'cyan',
    step: 2,
    blurb: 'Extracted images, transcripts, and media metadata.',
  },
  'stage3_document_processed': {
    label: 'Document markdown',
    color: 'blue',
    step: 3,
    blurb:
      'Structured markdown per document (e.g. Docling output). These are not retrieval chunks   chunking happens when you Build Index.',
  },
  'stage4_rag_ready': {
    label: 'RAG-ready bundle',
    color: 'indigo',
    step: 4,
    blurb:
      'Consolidated folder per doc for indexing (MD, PDF, extras). Header “Chunks” counts indexed segments, not one-to-one with files here.',
  },
}

const STAGE_ORDER_LIST = Object.keys(stageInfo)

/** When GET /api/processed-documents fails or returns empty, rebuild from flat /api/files rows (same as pre-snapshot UI). */
function buildLegacyProcessedLayout(processedFiles, inputFileCount) {
  if (!Array.isArray(processedFiles) || processedFiles.length === 0) return null

  const emptyStages = () =>
    Object.fromEntries(STAGE_ORDER_LIST.map((s) => [s, { file_count: 0, files: [] }]))

  const stage_totals = Object.fromEntries(STAGE_ORDER_LIST.map((s) => [s, 0]))
  const byDoc = {}

  for (const f of processedFiles) {
    const st = STAGE_ORDER_LIST.includes(f.stage) ? f.stage : null
    const targetStage = st || 'stage1_normalized'
    if (STAGE_ORDER_LIST.includes(targetStage)) {
      stage_totals[targetStage] = (stage_totals[targetStage] || 0) + 1
    }

    const docName = String(f.name || 'file')
      .replace(/\.(json|md|txt)$/i, '')
      .replace(/_stats$/, '')

    if (!byDoc[docName]) {
      byDoc[docName] = {
        id: docName,
        display_name: docName,
        total_files: 0,
        stages: emptyStages(),
      }
    }
    const rel = st ? `${st}/${f.name}` : String(f.name || '')
    const row = {
      name: f.name,
      relative_path: rel,
      path: f.path,
      size: f.size,
      modified: f.modified,
      type: f.type,
      storage: f.storage,
      ...(f.preview ? { preview: f.preview } : {}),
    }
    byDoc[docName].stages[targetStage].files.push(row)
    byDoc[docName].total_files++
  }

  for (const d of Object.values(byDoc)) {
    for (const s of STAGE_ORDER_LIST) {
      d.stages[s].file_count = d.stages[s].files.length
    }
  }

  const documents = Object.values(byDoc)
  return {
    input_file_count: inputFileCount ?? 0,
    artifact_count: processedFiles.length,
    document_count: documents.length,
    stage_order: STAGE_ORDER_LIST,
    stage_totals,
    root_files: [],
    documents,
    _fallback: true,
  }
}

function shouldUseLegacyProcessedSnapshot(apiLayout, flatProcessedLength) {
  if (flatProcessedLength === 0) return false
  if (apiLayout == null) return true
  const hasApiData =
    (apiLayout.artifact_count ?? 0) > 0 ||
    (Array.isArray(apiLayout.documents) && apiLayout.documents.length > 0)
  return !hasApiData
}

function App() {
  // ── State ──────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState('upload')
  const [files, setFiles] = useState({ input: [], processed: [], indexed: [] })
  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [searchLoading, setSearchLoading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(null)
  const [pipelineStatus, setPipelineStatus] = useState(null)
  const [previewImage, setPreviewImage] = useState(null)
  const [processedFilter, setProcessedFilter] = useState('all')
  const [dataLoading, setDataLoading] = useState(true)
  const [pipelineConfig, setPipelineConfig] = useState(null)
  const [showConfig, setShowConfig] = useState(false)
  const [processingStats, setProcessingStats] = useState(null)
  const [expandedCitations, setExpandedCitations] = useState({})
  const [expandedCitationMetadata, setExpandedCitationMetadata] = useState({})
  const [expandedCitationContent, setExpandedCitationContent] = useState({})
  const [processedLayout, setProcessedLayout] = useState(null)
  const [processedLayoutError, setProcessedLayoutError] = useState(null)
  const [selectedProcessedDocId, setSelectedProcessedDocId] = useState(null)
  const [processedPreviewFile, setProcessedPreviewFile] = useState(null)

  const fetchProcessedLayout = useCallback(async () => {
    try {
      const r = await axios.get(`${API_BASE}/processed-documents`)
      setProcessedLayout(r.data)
      setProcessedLayoutError(null)
    } catch (e) {
      console.error('processed-documents:', e)
      setProcessedLayout(null)
      setProcessedLayoutError(e.response?.data?.detail || e.message || 'Request failed')
    }
  }, [])

  const fetchPipelineStatus = useCallback(async (fresh = false) => {
    try {
      const r = await axios.get(`${API_BASE}/status`, { params: fresh ? { fresh: true } : {} })
      setPipelineStatus(r.data)
    } catch (e) {
      console.error('Failed to fetch status:', e)
    }
  }, [])

  const processedDisplay = useMemo(() => {
    const flat = files.processed || []
    const n = flat.length
    const api = processedLayout
    if (shouldUseLegacyProcessedSnapshot(api, n)) {
      return buildLegacyProcessedLayout(flat, files.input?.length ?? 0)
    }
    return api
  }, [processedLayout, files.processed, files.input])

  // ── Effects ────────────────────────────────────────────
  useEffect(() => {
    setDataLoading(true)
    Promise.all([
      fetchFiles(),
      fetchPipelineStatus(false),
      fetchConfig(),
      fetchProcessingStats(),
      fetchProcessedLayout(),
    ]).finally(() => setDataLoading(false))

    let interval = null
    const startPolling = () => {
      if (interval) clearInterval(interval)
      // Server caches /api/status (Qdrant); 60s polling is enough for a dashboard ticker.
      interval = setInterval(() => fetchPipelineStatus(false), 60000)
    }
    const stopPolling = () => { if (interval) { clearInterval(interval); interval = null } }
    startPolling()

    const handleVisibilityChange = () => {
      if (document.hidden) { stopPolling() } else { fetchPipelineStatus(false); startPolling() }
    }
    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => { stopPolling(); document.removeEventListener('visibilitychange', handleVisibilityChange) }
  }, [fetchProcessedLayout, fetchPipelineStatus])

  useEffect(() => {
    const docs = processedDisplay?.documents
    if (!docs?.length) {
      setSelectedProcessedDocId(null)
      return
    }
    const ids = docs.map((d) => d.id)
    setSelectedProcessedDocId((cur) => (cur && ids.includes(cur) ? cur : ids[0]))
  }, [processedDisplay])

  // ── API Calls ──────────────────────────────────────────
  const fetchFiles = async (quick = false) => {
    try {
      const r = await axios.get(`${API_BASE}/files`, { params: quick ? { quick: 1 } : {} })
      if (quick) {
        setFiles((prev) => ({ ...prev, input: r.data.input || [] }))
      } else {
        setFiles(r.data)
      }
    } catch (e) {
      console.error('Failed to fetch files:', e)
    }
  }

  const fetchConfig = async () => {
    try { const r = await axios.get(`${API_BASE}/config`); setPipelineConfig(r.data) }
    catch (e) { console.error('Failed to fetch config:', e) }
  }

  const fetchProcessingStats = async () => {
    try { const r = await axios.get(`${API_BASE}/processing-stats`); setProcessingStats(r.data) }
    catch (e) { console.error('Failed to fetch processing stats:', e) }
  }

  const handleUpload = async (e) => {
    const uploadFiles = e.target.files
    if (!uploadFiles.length) return
    const formData = new FormData()
    for (let file of uploadFiles) formData.append('files', file)
    setUploadProgress({ uploading: true, progress: 0 })
    try {
      // Do not set Content-Type manually   axios must add the multipart boundary.
      const r = await axios.post(`${API_BASE}/upload`, formData, {
        onUploadProgress: (p) =>
          setUploadProgress({ uploading: true, progress: Math.round((p.loaded * 100) / p.total) }),
      })
      setUploadProgress({ uploading: false, success: true })
      if (r.data?.files?.length) {
        setFiles((prev) => ({ ...prev, input: mergeInputByPath(prev.input, r.data.files) }))
      } else {
        await fetchFiles(true)
      }
      setTimeout(() => setUploadProgress(null), 2000)
    } catch (error) {
      setUploadProgress({ uploading: false, error: error.message })
    }
  }

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    const dropFiles = e.dataTransfer.files
    if (dropFiles.length) {
      const input = document.getElementById('file-upload')
      const dt = new DataTransfer()
      for (let f of dropFiles) dt.items.add(f)
      input.files = dt.files
      handleUpload({ target: { files: dt.files } })
    }
  }, [])

  const refreshAfterAction = () => {
    fetchFiles()
    fetchPipelineStatus(true)
    fetchProcessingStats()
    fetchProcessedLayout()
  }

  const handleProcess = async () => {
    setLoading(true)
    try {
      await axios.post(`${API_BASE}/process`)
      await new Promise(r => setTimeout(r, 2000))
      refreshAfterAction()
    } catch (error) {
      console.error('Processing failed:', error.response?.data || error.message)
      alert(`Processing failed: ${error.response?.data?.detail || error.message}`)
    }
    setLoading(false)
  }

  const handleIndex = async () => {
    setLoading(true)
    try {
      await axios.post(`${API_BASE}/index?force=true`)
      await new Promise(r => setTimeout(r, 2000))
      refreshAfterAction()
    } catch (error) {
      console.error('Indexing failed:', error.response?.data || error.message)
      alert(`Indexing failed: ${error.response?.data?.detail || error.message}`)
    }
    setLoading(false)
  }

  const handleRebuildSpecificIndex = async (indexType) => {
    setLoading(true)
    try {
      await axios.post(`${API_BASE}/index/${indexType}?force=true`)
      await new Promise(r => setTimeout(r, 2000))
      refreshAfterAction()
    } catch (error) {
      console.error(`${indexType} index rebuild failed:`, error.response?.data || error.message)
      alert(`${indexType.charAt(0).toUpperCase() + indexType.slice(1)} index rebuild failed: ${error.response?.data?.detail || error.message}`)
    }
    setLoading(false)
  }

  const handleRemoveTextFromIndex = async (textSource) => {
    if (!textSource || !window.confirm('Remove this source from the text index (Qdrant + documents.json + BM25)?')) return
    setLoading(true)
    try {
      const r = await axios.post(`${API_BASE}/index/remove`, { text_source: textSource })
      const tr = r.data?.results?.text
      alert(
        tr
          ? `Removed ${tr.removed_qdrant_points ?? 0} Qdrant points, ${tr.removed_documents_json_chunks ?? 0} chunks from documents.json.`
          : 'Remove completed.',
      )
      await new Promise((x) => setTimeout(x, 500))
      refreshAfterAction()
    } catch (error) {
      console.error('Remove from index failed:', error.response?.data || error.message)
      alert(`Remove from index failed: ${error.response?.data?.detail || error.message}`)
    }
    setLoading(false)
  }

  const handleClearImageIndex = async () => {
    if (!window.confirm('Clear the entire vision index (all ColQwen pages in Qdrant)?')) return
    setLoading(true)
    try {
      const r = await axios.post(`${API_BASE}/index/remove`, { clear_image_index: true })
      const ir = r.data?.results?.image
      alert(
        ir?.cleared_collection
          ? `Image index cleared (had ${ir.previous_point_count ?? 0} pages).`
          : 'Request completed.',
      )
      await new Promise((x) => setTimeout(x, 500))
      refreshAfterAction()
    } catch (error) {
      console.error('Clear image index failed:', error.response?.data || error.message)
      alert(`Clear image index failed: ${error.response?.data?.detail || error.message}`)
    }
    setLoading(false)
  }

  const handleSearch = async () => {
    if (!query.trim()) return
    setSearchLoading(true)
    setResults(null)
    try {
      const r = await axios.post(`${API_BASE}/search`, {
        query,
        top_k: 10,
        retriever_type: 'hybrid',
        include_images: true,
        images_for_generation: 5,
      })
      setResults(r.data)
    } catch (error) {
      console.error('Search failed:', error)
      alert(`Search failed: ${error.response?.data?.detail || error.message || 'Unknown error'}`)
    }
    setSearchLoading(false)
  }

  const handleDeleteFile = async (filePath) => {
    try {
      await axios.delete(`${API_BASE}/files`, { data: { path: filePath } })
      await fetchFiles(true)
    }
    catch (e) { console.error('Delete failed:', e) }
  }

  // ── Helpers ────────────────────────────────────────────
  const toggleCitationExpand = (citationId) => setExpandedCitations(prev => ({ ...prev, [citationId]: !prev[citationId] }))
  const toggleCitationMetadata = (citationId) => setExpandedCitationMetadata(prev => ({ ...prev, [citationId]: !prev[citationId] }))

  const handleCitationClick = (e, href) => {
    const match = href.match(/#(chunk|image)-(\d+)-(\d+)/)
    if (!match) return

    e.preventDefault()
    e.stopPropagation()
    const [, type, fileNum, chunkNum] = match
    const citationId = `${type}-${fileNum}-${chunkNum}`

    if (activeTab !== 'search') {
      setActiveTab('search')
      setTimeout(() => handleCitationClick(e, href), 100)
      return
    }

    // Find citation key from results
    let citationKey = null
    if (results?.contents) {
      const expectedKey = type === 'image' ? `[2.${chunkNum}]` : `[${fileNum}.${chunkNum}]`
      if (results.contents[expectedKey]) {
        citationKey = expectedKey
      } else {
        for (const [key, value] of Object.entries(results.contents)) {
          if (value?.id === citationId) { citationKey = key; break }
        }
      }
    }

    // Expand citation
    if (citationKey) {
      setExpandedCitations(prev => ({ ...prev, [citationKey]: true }))
    }

    // Scroll helpers
    const waitForEl = (selector, cb, max = 10, attempt = 0) => {
      const el = typeof selector === 'string' ? document.querySelector(selector) : selector()
      if (el) cb(el)
      else if (attempt < max) setTimeout(() => waitForEl(selector, cb, max, attempt + 1), 100)
    }

    waitForEl('#citations-section', (section) => {
      section.scrollIntoView({ behavior: 'smooth', block: 'start' })
      setTimeout(() => {
        waitForEl(`#${citationId}`, (el) => {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' })
          el.style.boxShadow = '0 0 0 3px rgba(59, 130, 246, 0.5)'
          el.style.transition = 'box-shadow 0.3s ease'
          setTimeout(() => { el.style.boxShadow = 'none' }, 2000)
        }, 20)
      }, 500)
    }, 20)
  }

  // ── Derived Data ───────────────────────────────────────
  const documentsForFilter = useMemo(() => {
    const docs = processedDisplay?.documents || []
    if (processedFilter === 'all') return docs
    return docs.filter((d) => (d.stages?.[processedFilter]?.file_count || 0) > 0)
  }, [processedDisplay, processedFilter])

  const selectedProcessedDoc = useMemo(() => {
    if (!documentsForFilter.length) return null
    const hit = documentsForFilter.find((d) => d.id === selectedProcessedDocId)
    return hit || documentsForFilter[0]
  }, [documentsForFilter, selectedProcessedDocId])

  const tabs = [
    { id: 'upload', label: 'Upload Files', icon: Upload },
    { id: 'processed', label: 'Processed Files', icon: Layers },
    { id: 'indexed', label: 'Indexed Files', icon: Database },
    { id: 'search', label: 'Search & Query', icon: Search },
    { id: 'insights', label: 'Insights', icon: Lightbulb },
  ]

  // ── Render ─────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-sky-50">
      {/* Decorative background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-sky-200/20 rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute top-1/3 -left-40 w-80 h-80 bg-blue-200/20 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }}></div>
        <div className="absolute -bottom-40 right-1/4 w-96 h-96 bg-sky-200/20 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '2s' }}></div>
      </div>

      {/* Header */}
      <header className="relative glass-strong border-b border-sky-100/60 sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-6 py-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-5">
              <div className="w-14 h-14 bg-sky-500 rounded-2xl flex items-center justify-center shadow-lg shadow-sky-200/50 ring-2 ring-white/50">
                <Sparkles className="w-7 h-7 text-white" />
              </div>
              <div>
                <h1 className="text-3xl font-bold text-sky-600 tracking-tight">Educational RAG AI Service</h1>
                <p className="text-sm text-slate-500 font-medium mt-0.5">Qdrant + hybrid search · SageMaker-ready ColQwen</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              {pipelineStatus && (
                <div className="flex items-center space-x-5 px-6 py-3 bg-white/80 backdrop-blur-md rounded-2xl border border-sky-100/60 shadow-sm card-shadow">
                  <div className="flex items-center space-x-3">
                    <div className={`w-3 h-3 rounded-full animate-pulse ${pipelineStatus.ready ? 'bg-emerald-500 shadow-lg shadow-emerald-200' : 'bg-amber-500 shadow-lg shadow-amber-200'}`}></div>
                    <div>
                      <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Chunks</span>
                      <p className="text-lg font-bold text-slate-800">{pipelineStatus.indexed_docs || 0}</p>
                    </div>
                  </div>
                  {pipelineStatus.image_pages > 0 && (
                    <>
                      <div className="w-px h-8 bg-sky-200"></div>
                      <div className="flex items-center space-x-3">
                        <div className="w-8 h-8 bg-indigo-100 rounded-lg flex items-center justify-center">
                          <Image className="w-4 h-4 text-indigo-600" />
                        </div>
                        <div>
                          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Pages</span>
                          <p className="text-lg font-bold text-slate-800">{pipelineStatus.image_pages}</p>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              )}
              <button
                onClick={() => { fetchFiles(); fetchPipelineStatus(true); fetchProcessedLayout() }}
                className="p-3 text-slate-500 hover:text-sky-600 hover:bg-sky-50 rounded-xl transition-all duration-200 hover:scale-110 active:scale-95"
                title="Refresh"
              >
                <RefreshCw className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="relative max-w-7xl mx-auto px-6 py-8 z-10">
        {/* Tabs */}
        <div className="flex space-x-3 glass p-2 rounded-2xl mb-8 card-shadow">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center space-x-2.5 px-5 py-3 rounded-xl font-semibold text-sm transition-all duration-300 ${activeTab === tab.id
                  ? 'bg-sky-500 text-white shadow-lg shadow-sky-200/50 scale-105'
                  : 'text-slate-600 hover:text-sky-600 hover:bg-white/60'
                }`}
            >
              <tab.icon className={`w-4.5 h-4.5 ${activeTab === tab.id ? 'text-white' : 'text-slate-500'}`} />
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Loading spinner */}
        {dataLoading && (
          <div className="flex items-center justify-center py-32">
            <div className="text-center animate-in zoom-in-95">
              <div className="relative">
                <div className="w-16 h-16 border-4 border-sky-100 border-t-sky-500 rounded-full animate-spin mx-auto mb-4"></div>
                <Sparkles className="w-6 h-6 text-sky-500 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
              </div>
              <p className="text-slate-600 font-semibold text-lg">Loading pipeline data...</p>
              <p className="text-slate-400 text-sm mt-2">Please wait</p>
            </div>
          </div>
        )}

        {!dataLoading && (
          <>
            {/* ━━━ Upload Tab ━━━ */}
            {activeTab === 'upload' && (
              <div className="space-y-8 animate-in fade-in slide-in-from-top-4">
                {/* Upload Area */}
                <div className="glass-strong rounded-3xl card-shadow card-shadow-hover p-10">
                  <div className="flex items-center space-x-3 mb-8">
                    <div className="w-10 h-10 bg-sky-500 rounded-xl flex items-center justify-center shadow-lg shadow-sky-200/50">
                      <Upload className="w-5 h-5 text-white" />
                    </div>
                    <div>
                      <h2 className="text-2xl font-bold text-slate-800">Upload Documents</h2>
                      <p className="text-sm text-slate-500 mt-0.5">Add files to process and index</p>
                    </div>
                  </div>
                  <label className="block">
                    <div
                      className="border-2 border-dashed border-sky-300/60 rounded-3xl p-16 text-center hover:border-sky-400 hover:bg-sky-50/50 transition-all duration-300 group relative overflow-hidden"
                      onDrop={handleDrop}
                      onDragOver={(e) => e.preventDefault()}
                    >
                      <div className="absolute inset-0 bg-sky-500/0 group-hover:bg-sky-500/5 transition-all duration-500"></div>
                      <div className="relative z-10">
                        <div className="w-20 h-20 mx-auto mb-6 bg-sky-100 rounded-3xl flex items-center justify-center group-hover:scale-110 group-hover:rotate-3 group-hover:bg-sky-200 transition-all duration-500 shadow-lg shadow-sky-200/30">
                          <Upload className="w-10 h-10 text-sky-500 group-hover:text-sky-600 transition-colors" />
                        </div>
                        <p className="text-slate-700 font-bold text-lg mb-2 group-hover:text-sky-700 transition-colors">Drop files here or click to upload</p>
                        <p className="text-sm text-slate-500 group-hover:text-slate-600 transition-colors">PDF, DOCX, PPTX, TXT, images, videos and more</p>
                      </div>
                      <input id="file-upload" type="file" multiple onChange={handleUpload} className="hidden" accept=".pdf,.docx,.pptx,.txt,.md,.png,.jpg,.jpeg,.mp4,.avi,.mov,.xlsx,.doc,.xls,.ppt" />
                    </div>
                  </label>

                  {uploadProgress && (
                    <div className="mt-8 space-y-4 animate-in slide-in-from-bottom">
                      {uploadProgress.uploading && (
                        <div className="flex items-center space-x-5 p-5 bg-sky-50 rounded-2xl border-2 border-sky-200/60 card-shadow">
                          <div className="relative">
                            <Loader2 className="w-6 h-6 animate-spin text-sky-500 flex-shrink-0" />
                          </div>
                          <div className="flex-1">
                            <div className="flex items-center justify-between mb-3">
                              <span className="text-sm font-bold text-slate-700">Uploading files...</span>
                              <span className="text-lg font-bold text-sky-600">{uploadProgress.progress}%</span>
                            </div>
                            <div className="h-3 bg-white/80 rounded-full overflow-hidden shadow-inner">
                              <div className="h-full bg-sky-500 transition-all duration-500 shadow-lg shadow-sky-300/50" style={{ width: `${uploadProgress.progress}%` }} />
                            </div>
                          </div>
                        </div>
                      )}
                      {uploadProgress.success && (
                        <div className="flex items-center space-x-4 p-5 bg-emerald-50 rounded-2xl border-2 border-emerald-200/60 card-shadow animate-in zoom-in-95">
                          <div className="w-10 h-10 bg-emerald-500 rounded-xl flex items-center justify-center shadow-lg shadow-emerald-200/50">
                            <CheckCircle className="w-6 h-6 text-white" />
                          </div>
                          <span className="text-sm font-bold text-emerald-700">Upload complete!</span>
                        </div>
                      )}
                      {uploadProgress.error && (
                        <div className="flex items-center space-x-4 p-5 bg-red-50 rounded-2xl border-2 border-red-200/60 card-shadow animate-in zoom-in-95">
                          <div className="w-10 h-10 bg-red-500 rounded-xl flex items-center justify-center shadow-lg shadow-red-200/50">
                            <XCircle className="w-6 h-6 text-white" />
                          </div>
                          <span className="text-sm font-bold text-red-700">Upload failed: {uploadProgress.error}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Input Files List */}
                <div className="glass-strong rounded-3xl card-shadow p-8">
                  <div className="flex items-center justify-between mb-8">
                    <div className="flex items-center space-x-4">
                      <div className="w-12 h-12 bg-sky-100 rounded-2xl flex items-center justify-center shadow-sm">
                        <FolderOpen className="w-6 h-6 text-sky-600" />
                      </div>
                      <div>
                        <h2 className="text-xl font-bold text-slate-800 flex items-center space-x-3">
                          <span>Input Files</span>
                          <span className="px-4 py-1.5 bg-sky-500 text-white text-sm rounded-full font-bold shadow-lg shadow-sky-200/50">{files.input?.length || 0}</span>
                        </h2>
                        <p className="text-sm text-slate-500 mt-1">Files ready for processing</p>
                      </div>
                    </div>
                    <button onClick={handleProcess} disabled={loading || !files.input?.length}
                      className="px-8 py-3.5 bg-sky-500 text-white rounded-xl font-bold hover:shadow-xl hover:shadow-sky-200/50 disabled:opacity-50 flex items-center space-x-2.5 transition-all duration-300 hover:scale-105 active:scale-95 disabled:hover:scale-100">
                      {loading ? (<><Loader2 className="w-5 h-5 animate-spin" /><span>Processing...</span></>) : (<><Zap className="w-5 h-5" /><span>Process</span></>)}
                    </button>
                  </div>

                  {files.input?.length > 0 ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-h-96 overflow-y-auto pr-2 scrollbar-thin">
                      {files.input.map((file, idx) => {
                        const FileIcon = getFileIcon(file.type)
                        return (
                          <div key={idx} className="flex items-center justify-between p-5 bg-white rounded-2xl border-2 border-slate-100 hover:border-sky-200 hover:shadow-lg card-shadow-hover transition-all duration-300 group animate-in fade-in" style={{ animationDelay: `${idx * 50}ms` }}>
                            <div className="flex items-center space-x-4 flex-1 min-w-0">
                              <div className="w-12 h-12 bg-sky-100 rounded-xl flex items-center justify-center shadow-sm border border-sky-200/50 flex-shrink-0">
                                <FileIcon className="w-6 h-6 text-sky-600" />
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="font-bold text-slate-800 text-sm truncate">{file.name}</p>
                                <p className="text-xs text-slate-500 font-medium mt-1">{file.size}</p>
                              </div>
                            </div>
                            <button onClick={() => handleDeleteFile(file.path)} className="p-2.5 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-xl opacity-0 group-hover:opacity-100 transition-all duration-200 ml-3 flex-shrink-0" title="Delete file">
                              <Trash2 className="w-5 h-5" />
                            </button>
                          </div>
                        )
                      })}
                    </div>
                  ) : (
                    <div className="text-center py-16 text-slate-400 animate-in fade-in">
                      <div className="w-20 h-20 mx-auto mb-4 bg-slate-100 rounded-3xl flex items-center justify-center opacity-50">
                        <FolderOpen className="w-10 h-10 text-slate-400" />
                      </div>
                      <p className="font-semibold text-lg text-slate-500">No files uploaded yet</p>
                      <p className="text-sm text-slate-400 mt-2">Upload files to get started</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ━━━ Processed Files Tab ━━━ */}
            {activeTab === 'processed' && (
              <div className="space-y-6 animate-in fade-in slide-in-from-top-4 duration-500">
                {/* Pipeline Actions */}
                <div className="bg-sky-50 backdrop-blur-sm rounded-2xl shadow-sm border border-sky-200 p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-lg font-semibold text-slate-800 mb-1">Pipeline Actions</h3>
                      <p className="text-sm text-slate-600">Manage document processing workflow</p>
                    </div>
                    <div className="flex items-center space-x-3">
                      <button onClick={handleProcess} disabled={loading || !files.input?.length}
                        className="px-6 py-2.5 bg-sky-500 text-white rounded-lg font-medium hover:shadow-lg hover:shadow-sky-200/50 disabled:opacity-50 flex items-center space-x-2 transition-all duration-200 hover:scale-105 active:scale-95">
                        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                        <span>Process Files</span>
                      </button>
                      <button onClick={handleIndex} disabled={loading}
                        className="px-6 py-2.5 bg-indigo-500 text-white rounded-lg font-medium hover:shadow-lg hover:shadow-indigo-200/50 disabled:opacity-50 flex items-center space-x-2 transition-all duration-200 hover:scale-105 active:scale-95">
                        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                        <span>Build Index</span>
                      </button>
                    </div>
                  </div>
                </div>

                {/* Settings Panel (Stats + Config) */}
                <SettingsPanel
                  pipelineConfig={pipelineConfig}
                  showConfig={showConfig}
                  setShowConfig={setShowConfig}
                  processingStats={processingStats}
                />

                {(processedLayoutError || processedDisplay?._fallback) && (
                  <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950 shadow-sm">
                    <p className="font-semibold text-amber-900">Processed view fallback</p>
                    <p className="mt-1 text-amber-900/90">
                      {processedLayoutError
                        ? `Could not load GET /api/processed-documents (${processedLayoutError}). `
                        : 'The structured snapshot reported no artifacts while the file list still has items, or the API is outdated. '}
                      Showing a grouped view built from GET /api/files. Use the refresh button after restarting the backend so
                      <code className="mx-1 rounded bg-amber-100/80 px-1 font-mono text-xs">/api/processed-documents</code>
                      is available.
                    </p>
                  </div>
                )}

                {/* Counts   aligned with storage layout (users/…/processing) */}
                <div className="flex flex-wrap gap-3">
                  <div className="px-4 py-3 rounded-xl bg-white border border-sky-100 shadow-sm">
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Input files</p>
                    <p className="text-2xl font-bold text-sky-700">{processedDisplay?.input_file_count ?? files.input?.length ?? 0}</p>
                    <p className="text-[10px] text-slate-400 mt-1 leading-snug">In input/ (uploads)</p>
                  </div>
                  <div className="px-4 py-3 rounded-xl bg-white border border-sky-100 shadow-sm">
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Document groups</p>
                    <p className="text-2xl font-bold text-blue-700">{processedDisplay?.document_count ?? 0}</p>
                    {processedDisplay?.named_document_folders != null &&
                      processedDisplay.named_document_folders !== processedDisplay.document_count && (
                        <p className="text-[10px] text-slate-400 mt-1 leading-snug">
                          {processedDisplay.named_document_folders} named folder{processedDisplay.named_document_folders === 1 ? '' : 's'} + pipeline-wide
                        </p>
                      )}
                    <p className="text-[10px] text-slate-400 mt-1 leading-snug">Matches sidebar rows</p>
                  </div>
                  <div className="px-4 py-3 rounded-xl bg-white border border-indigo-100 shadow-sm">
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Processing artifacts</p>
                    <p className="text-2xl font-bold text-indigo-700">{processedDisplay?.artifact_count ?? 0}</p>
                    <p className="text-[10px] text-slate-400 mt-1 leading-snug">All files under processing/</p>
                  </div>
                </div>
                {processedDisplay?.count_hints && (
                  <div className="rounded-xl border border-slate-200/80 bg-slate-50/90 px-4 py-3 text-xs text-slate-600 space-y-2 max-w-4xl">
                    <p>
                      <span className="font-semibold text-slate-700">Stage cards: </span>
                      {processedDisplay.count_hints.stage_totals}
                    </p>
                    <p>
                      <span className="font-semibold text-slate-700">Document groups: </span>
                      {processedDisplay.count_hints.document_groups}
                    </p>
                  </div>
                )}

                {/* Filter Buttons */}
                <div className="flex items-center space-x-2 flex-wrap gap-2">
                  <span className="text-sm font-medium text-slate-600">Filter:</span>
                  <button
                    type="button"
                    onClick={() => setProcessedFilter('all')}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${processedFilter === 'all' ? 'bg-sky-500 text-white shadow-lg shadow-sky-200/50' : 'bg-white/60 text-slate-600 border border-sky-100 hover:bg-sky-50'}`}
                  >
                    All ({processedDisplay?.artifact_count ?? files.processed?.length ?? 0})
                  </button>
                  {Object.entries(stageInfo).map(([stage, info]) => {
                    const count = processedDisplay?.stage_totals?.[stage] ?? 0
                    if (count === 0) return null
                    const active = { sky: 'bg-sky-500 text-white shadow-lg shadow-sky-200/50', cyan: 'bg-cyan-500 text-white shadow-lg shadow-cyan-200/50', blue: 'bg-blue-500 text-white shadow-lg shadow-blue-200/50', indigo: 'bg-indigo-500 text-white shadow-lg shadow-indigo-200/50' }
                    const inactive = { sky: 'bg-white/60 text-slate-600 border border-sky-100 hover:bg-sky-50', cyan: 'bg-white/60 text-slate-600 border border-cyan-100 hover:bg-cyan-50', blue: 'bg-white/60 text-slate-600 border border-blue-100 hover:bg-blue-50', indigo: 'bg-white/60 text-slate-600 border border-indigo-100 hover:bg-indigo-50' }
                    return (
                      <button key={stage} type="button" onClick={() => setProcessedFilter(stage)}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${processedFilter === stage ? active[info.color] : inactive[info.color]}`}>
                        {info.label} ({count})
                      </button>
                    )
                  })}
                </div>

                {/* Processing Pipeline Visual + master–detail */}
                <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-sm border border-sky-100 p-6">
                  <h3 className="text-lg font-semibold text-slate-800">Processing Pipeline</h3>
                  <p className="text-xs text-slate-500 mt-1 mb-6 leading-relaxed">
                    Folders follow{' '}
                    <code className="rounded bg-slate-100 px-1 font-mono text-[11px]">stage1_normalized</code>
                    {' → '}
                    <code className="rounded bg-slate-100 px-1 font-mono text-[11px]">stage4_rag_ready</code>
                    . Numbers below count <span className="font-medium text-slate-600">files on disk</span>. The header{' '}
                    <span className="font-medium text-slate-600">Chunks</span> value is how many text segments were written to the
                    index (after chunking)   usually much larger than a single stage-3 <code className="font-mono text-[11px]">.md</code>{' '}
                    per document.
                  </p>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
                    {Object.entries(stageInfo).map(([stage, info]) => {
                      const count = processedDisplay?.stage_totals?.[stage] ?? 0
                      const colors = { sky: 'bg-sky-100 text-sky-700 border-sky-200', cyan: 'bg-cyan-100 text-cyan-700 border-cyan-200', blue: 'bg-blue-100 text-blue-700 border-blue-200', indigo: 'bg-indigo-100 text-indigo-700 border-indigo-200' }
                      return (
                        <div key={stage} className={`${colors[info.color]} border p-4 rounded-xl text-center relative`}>
                          <div className="text-3xl font-bold mb-1">{count}</div>
                          <div className="text-xs font-medium">{info.label}</div>
                          {info.step < 4 && <ArrowRight className="hidden sm:block absolute -right-5 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-300" />}
                        </div>
                      )
                    })}
                  </div>

                  {(processedDisplay?.artifact_count ?? 0) > 0 || (files.processed?.length ?? 0) > 0 ? (
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                      <div className="lg:col-span-4 space-y-2 max-h-[min(560px,70vh)] overflow-y-auto pr-1">
                        <p className="text-sm font-semibold text-slate-600 mb-2">Your documents</p>
                        {documentsForFilter.length > 0 ? (
                          documentsForFilter.map((doc) => {
                            const active = selectedProcessedDoc?.id === doc.id
                            const badges = (processedDisplay?.stage_order || Object.keys(stageInfo)).filter((st) => (doc.stages?.[st]?.file_count || 0) > 0)
                            return (
                              <button
                                key={doc.id}
                                type="button"
                                onClick={() => setSelectedProcessedDocId(doc.id)}
                                className={`w-full text-left p-4 rounded-xl border transition-all ${active ? 'border-sky-400 bg-sky-50 ring-2 ring-sky-300/60 shadow-md' : 'border-slate-200 bg-white hover:border-sky-200 hover:shadow-sm'}`}
                              >
                                <p className="font-semibold text-slate-800 truncate" title={doc.display_name || doc.id}>{doc.display_name || doc.id}</p>
                                <p className="text-xs text-slate-500 mt-1">{doc.total_files ?? 0} files</p>
                                <div className="flex flex-wrap gap-1 mt-2">
                                  {badges.map((st) => {
                                    const inf = stageInfo[st] || { label: st, color: 'sky' }
                                    const cc = { sky: 'bg-sky-100 text-sky-800', cyan: 'bg-cyan-100 text-cyan-800', blue: 'bg-blue-100 text-blue-800', indigo: 'bg-indigo-100 text-indigo-800' }
                                    return (
                                      <span key={st} className={`px-2 py-0.5 rounded text-[10px] font-medium ${cc[inf.color] || cc.sky}`}>{inf.label}</span>
                                    )
                                  })}
                                </div>
                              </button>
                            )
                          })
                        ) : (
                          <div className="text-center py-8 text-slate-400 text-sm">
                            <AlertCircle className="w-10 h-10 mx-auto mb-2 opacity-30" />
                            No documents match this filter
                          </div>
                        )}
                      </div>
                      <div className="lg:col-span-8 min-h-[320px]">
                        {processedDisplay?.root_files?.length > 0 && (
                          <div className="mb-6 p-4 rounded-xl bg-slate-50 border border-slate-200">
                            <h4 className="text-sm font-semibold text-slate-700 mb-2">Workspace root files</h4>
                            <ul className="text-xs text-slate-600 space-y-2 font-mono break-all">
                              {processedDisplay.root_files.map((f, i) => (
                                <li key={i} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-100 bg-white px-2 py-2">
                                  <span>
                                    {f.relative_path} <span className="text-slate-400">({f.size})</span>
                                  </span>
                                  <button
                                    type="button"
                                    onClick={() => setProcessedPreviewFile(f)}
                                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-semibold text-sky-600 bg-sky-50 hover:bg-sky-100 border border-sky-100 shrink-0"
                                  >
                                    <Eye className="w-3.5 h-3.5" />
                                    Preview
                                  </button>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {selectedProcessedDoc ? (
                          <div className="space-y-5">
                            <div className="flex items-center justify-between gap-2 border-b border-slate-100 pb-3">
                              <h4 className="text-lg font-bold text-slate-800 truncate">{selectedProcessedDoc.display_name || selectedProcessedDoc.id}</h4>
                              <span className="text-sm text-slate-500 shrink-0">{selectedProcessedDoc.total_files} files</span>
                            </div>
                            {(processedDisplay?.stage_order || Object.keys(stageInfo)).map((stageKey) => {
                              const stData = selectedProcessedDoc.stages?.[stageKey]
                              if (!stData?.files?.length) return null
                              const info = stageInfo[stageKey] || { label: stageKey, color: 'sky' }
                              const headColors = { sky: 'border-sky-200 bg-sky-50/80', cyan: 'border-cyan-200 bg-cyan-50/80', blue: 'border-blue-200 bg-blue-50/80', indigo: 'border-indigo-200 bg-indigo-50/80' }
                              return (
                                <div key={stageKey} className={`rounded-xl border ${headColors[info.color] || headColors.sky} overflow-hidden`}>
                                  <div className="px-4 py-2 border-b border-white/60 flex justify-between items-start gap-3">
                                    <div className="min-w-0">
                                      <span className="text-sm font-bold text-slate-800">{info.label}</span>
                                      {info.blurb ? (
                                        <p className="text-[11px] text-slate-500 mt-1 leading-snug">{info.blurb}</p>
                                      ) : null}
                                    </div>
                                    <span className="text-xs text-slate-500 shrink-0">{stData.files.length} files</span>
                                  </div>
                                  <ul className="p-3 space-y-2 max-h-72 overflow-y-auto bg-white/90">
                                    {stData.files.map((f, i) => (
                                      <li key={i} className="text-sm rounded-lg border border-slate-100 p-3 bg-white">
                                        <div className="flex justify-between gap-2 items-start">
                                          <span className="font-medium text-slate-800 truncate min-w-0">{f.name}</span>
                                          <div className="flex items-center gap-2 shrink-0">
                                            <button
                                              type="button"
                                              onClick={() => setProcessedPreviewFile(f)}
                                              className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-semibold text-sky-600 bg-sky-50 hover:bg-sky-100 border border-sky-100"
                                            >
                                              <Eye className="w-3.5 h-3.5" />
                                              Preview
                                            </button>
                                            <span className="text-xs text-slate-400 whitespace-nowrap">{f.modified}</span>
                                          </div>
                                        </div>
                                        <p className="text-xs text-slate-500 mt-1 break-all font-mono">{f.relative_path}</p>
                                        <div className="flex justify-between mt-1 text-xs text-slate-400">
                                          <span>{f.size}</span>
                                          <span>{f.type || ' '}</span>
                                        </div>
                                        {f.preview ? (
                                          <pre className="mt-2 text-xs text-slate-600 bg-slate-50 p-2 rounded max-h-28 overflow-auto whitespace-pre-wrap">{f.preview}</pre>
                                        ) : null}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )
                            })}
                          </div>
                        ) : (
                          <div className="flex flex-col items-center justify-center py-16 text-slate-400">
                            <Layers className="w-14 h-14 mb-3 opacity-25" />
                            <p className="font-medium">Select a document</p>
                            <p className="text-sm mt-1 text-center max-w-sm">Choose a folder on the left to see normalized → RAG-ready files in order.</p>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="text-center py-12 text-slate-400">
                      <Layers className="w-12 h-12 mx-auto mb-3 opacity-20" />
                      <p>No processed files yet</p>
                      <p className="text-sm mt-2">Upload files and run processing to see results here</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ━━━ Indexed Files Tab ━━━ */}
            {activeTab === 'indexed' && (
              <div className="space-y-6 animate-in fade-in slide-in-from-top-4 duration-500">
                {/* Index Stats Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Text Index */}
                  <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-sm border border-sky-100 p-8 hover:shadow-lg hover:border-sky-200 transition-all duration-300">
                    <div className="flex items-center space-x-4 mb-6">
                      <div className="w-12 h-12 bg-sky-100 rounded-xl flex items-center justify-center"><FileText className="w-6 h-6 text-sky-600" /></div>
                      <div><h3 className="font-semibold text-slate-800">Text Index</h3><p className="text-sm text-slate-400">BM25 + Qdrant dense + hybrid</p></div>
                    </div>
                    {pipelineStatus?.text_index ? (
                      <div className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                          <div className="p-4 bg-sky-50 rounded-xl border border-sky-100"><div className="text-sm text-sky-600 font-medium mb-1">Chunks</div><p className="text-3xl font-bold text-sky-700">{pipelineStatus.text_index.chunks || 0}</p></div>
                          <div className="p-4 bg-blue-50 rounded-xl border border-blue-100"><div className="text-sm text-blue-600 font-medium mb-1">Documents</div><p className="text-3xl font-bold text-blue-700">{pipelineStatus.text_index.docs || 0}</p></div>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {pipelineStatus.text_index.retrievers?.map((r, i) => <span key={i} className="px-3 py-1.5 bg-sky-100 text-sky-700 rounded-lg text-sm font-medium">{r}</span>)}
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-6"><AlertCircle className="w-8 h-8 mx-auto mb-2 text-slate-300" /><p className="text-slate-400 text-sm">No text index available</p></div>
                    )}
                  </div>

                  {/* Image Index */}
                  <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-sm border border-sky-100 p-8 hover:shadow-lg hover:border-sky-200 transition-all duration-300">
                    <div className="flex items-center space-x-4 mb-6">
                      <div className="w-12 h-12 bg-indigo-100 rounded-xl flex items-center justify-center"><Image className="w-6 h-6 text-indigo-600" /></div>
                      <div><h3 className="font-semibold text-slate-800">Image Index</h3><p className="text-sm text-slate-400">ColQwen → Qdrant (MaxSim)</p></div>
                    </div>
                    {pipelineStatus?.image_index ? (
                      <div className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                          <div className="p-4 bg-indigo-50 rounded-xl border border-indigo-100"><div className="text-sm text-indigo-600 font-medium mb-1">Pages</div><p className="text-3xl font-bold text-indigo-700">{pipelineStatus.image_index.pages || 0}</p></div>
                          <div className="p-4 bg-purple-50 rounded-xl border border-purple-100"><div className="text-sm text-purple-600 font-medium mb-1">Vector DB</div><p className="text-lg font-bold text-purple-700 leading-tight">{pipelineStatus.image_index.vector_store || 'qdrant'}</p></div>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <span className="px-3 py-1.5 bg-indigo-100 text-indigo-700 rounded-lg text-sm font-medium">ColQwen</span>
                          <span className="px-3 py-1.5 bg-purple-100 text-purple-700 rounded-lg text-sm font-medium">MaxSim</span>
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-6"><AlertCircle className="w-8 h-8 mx-auto mb-2 text-slate-300" /><p className="text-slate-400 text-sm">No image index available</p></div>
                    )}
                  </div>
                </div>

                {/* Indexed Files List */}
                <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-sm border border-sky-100 p-6">
                  <div className="flex items-center justify-between mb-6">
                    <h2 className="text-lg font-semibold text-slate-800 flex items-center space-x-3">
                      <Database className="w-5 h-5 text-sky-500" /><span>Indexed Documents</span>
                    </h2>
                    <div className="flex items-center space-x-2">
                      <button onClick={() => handleRebuildSpecificIndex('text')} disabled={loading}
                        className="px-4 py-2.5 bg-sky-500 text-white rounded-lg font-medium hover:shadow-lg hover:shadow-sky-200/50 disabled:opacity-50 flex items-center space-x-2 transition-all duration-200 hover:scale-105 active:scale-95" title="Rebuild text index only">
                        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}<span>Rebuild Text</span>
                      </button>
                      <button onClick={() => handleRebuildSpecificIndex('image')} disabled={loading}
                        className="px-4 py-2.5 bg-indigo-500 text-white rounded-lg font-medium hover:shadow-lg hover:shadow-indigo-200/50 disabled:opacity-50 flex items-center space-x-2 transition-all duration-200 hover:scale-105 active:scale-95" title="Rebuild image index only">
                        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}<span>Rebuild Image</span>
                      </button>
                      <button onClick={handleIndex} disabled={loading}
                        className="px-4 py-2.5 bg-slate-600 text-white rounded-lg font-medium hover:shadow-lg hover:shadow-slate-200/50 disabled:opacity-50 flex items-center space-x-2 transition-all duration-200 hover:scale-105 active:scale-95" title="Rebuild all indexes">
                        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}<span>Rebuild All</span>
                      </button>
                    </div>
                  </div>

                  {files.indexed?.length > 0 ? (
                    <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
                      {files.indexed.map((file, idx) => (
                        <div key={idx} className={`p-4 rounded-xl border transition-all duration-200 hover:shadow-md ${file.type === 'image' ? 'bg-indigo-50 border-indigo-100 hover:border-indigo-200' : 'bg-sky-50 border-sky-100 hover:border-sky-200'}`}>
                          <div className="flex items-center justify-between gap-3">
                            <div className="flex items-center space-x-3 min-w-0 flex-1">
                              <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${file.type === 'image' ? 'bg-indigo-100' : 'bg-sky-100'}`}>
                                {file.type === 'image' ? <Image className="w-5 h-5 text-indigo-600" /> : <FileText className="w-5 h-5 text-sky-600" />}
                              </div>
                              <div className="min-w-0">
                                <p className="font-medium text-slate-800 break-all">{file.name}</p>
                                <p className="text-sm text-slate-400">{file.type === 'image' ? `${file.pages} pages` : `${file.chunks} chunks`}</p>
                              </div>
                            </div>
                            <div className="flex items-center gap-2 flex-shrink-0">
                              {file.type === 'text' && (
                                <button
                                  type="button"
                                  onClick={() => handleRemoveTextFromIndex(file.name)}
                                  disabled={loading}
                                  className="p-2.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-xl transition-colors disabled:opacity-40"
                                  title="Remove this source from text index (Qdrant + BM25)"
                                >
                                  <Trash2 className="w-5 h-5" />
                                </button>
                              )}
                              {file.type === 'image' && (
                                <button
                                  type="button"
                                  onClick={handleClearImageIndex}
                                  disabled={loading}
                                  className="px-3 py-1.5 text-sm font-medium text-red-700 bg-red-50 hover:bg-red-100 rounded-lg border border-red-100 disabled:opacity-40"
                                  title="Remove all pages from vision index"
                                >
                                  Clear vision index
                                </button>
                              )}
                              <span className={`px-3 py-1.5 rounded-lg text-sm font-medium ${file.type === 'image' ? 'bg-indigo-100 text-indigo-700' : 'bg-sky-100 text-sky-700'}`}>
                                {file.type === 'image' ? 'Vision' : 'Text'}
                              </span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-12 text-slate-400">
                      <Database className="w-12 h-12 mx-auto mb-3 opacity-20" /><p>No indexed documents</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ━━━ Search Tab ━━━ */}
            {activeTab === 'search' && (
              <div className="space-y-6 animate-in fade-in slide-in-from-top-4 duration-500">
                <SearchBar query={query} setQuery={setQuery} onSearch={handleSearch} searchLoading={searchLoading} />

                {results && (
                  <div className="space-y-6">
                    <AnswerPanel answer={results.answer} onCitationClick={handleCitationClick} />

                    {/* Citations */}
                    {results.contents && Object.keys(results.contents).length > 0 && (
                      <div id="citations-section" className="bg-white rounded-2xl shadow-sm border border-sky-100 p-8">
                        <h3 className="text-lg font-semibold mb-6 flex items-center space-x-3 text-slate-800">
                          <Hash className="w-5 h-5 text-sky-500" /><span>Citations</span>
                        </h3>

                        {/* Text Citations */}
                        {Object.entries(results.contents).filter(([, v]) => v.type === 'text').length > 0 && (
                          <div className="mb-8">
                            <h4 className="text-md font-semibold mb-4 text-slate-700 flex items-center space-x-2">
                              <FileText className="w-4 h-4 text-sky-500" /><span>Text Chunks</span>
                            </h4>
                            <div className="space-y-3">
                              {Object.entries(results.contents).filter(([, v]) => v.type === 'text').map(([citationKey, citation]) => (
                                <CitationCard
                                  key={citationKey}
                                  citationKey={citationKey}
                                  citation={citation}
                                  expanded={expandedCitations[citationKey]}
                                  onToggle={toggleCitationExpand}
                                  metadataExpanded={expandedCitationMetadata[citationKey]}
                                  onToggleMetadata={toggleCitationMetadata}
                                  contentExpanded={expandedCitationContent[citationKey]}
                                  onExpandContent={(key) => setExpandedCitationContent(prev => ({ ...prev, [key]: true }))}
                                />
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Image Citations */}
                        {Object.entries(results.contents).filter(([, v]) => v.type === 'image').length > 0 && (
                          <div>
                            <h4 className="text-md font-semibold mb-4 text-slate-700 flex items-center space-x-2">
                              <Image className="w-4 h-4 text-indigo-500" /><span>Images</span>
                            </h4>
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                              {Object.entries(results.contents).filter(([, v]) => v.type === 'image').map(([citationKey, citation]) => (
                                <ImageCitation
                                  key={citationKey}
                                  citationKey={citationKey}
                                  citation={citation}
                                  expanded={expandedCitations[citationKey]}
                                  onToggle={toggleCitationExpand}
                                  metadataExpanded={expandedCitationMetadata[citationKey]}
                                  onToggleMetadata={toggleCitationMetadata}
                                  apiBase={API_BASE}
                                />
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'insights' && (
              <InsightsPanel apiBase={API_BASE} processedLayout={processedDisplay} />
            )}
          </>
        )}
      </div>

      {/* Image Preview Modal */}
      {processedPreviewFile && (
        <ProcessedFilePreviewModal
          file={processedPreviewFile}
          apiBase={API_BASE}
          onClose={() => setProcessedPreviewFile(null)}
        />
      )}

      {previewImage && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in duration-200" onClick={() => setPreviewImage(null)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-auto animate-in zoom-in-95 duration-200" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between p-6 border-b border-slate-100 sticky top-0 bg-white z-10">
              <div>
                <p className="font-semibold text-slate-800">{previewImage.source}</p>
                <p className="text-sm text-slate-400">Page {previewImage.page} &bull; Score: {previewImage.score?.toFixed(4)}</p>
              </div>
              <button onClick={() => setPreviewImage(null)} className="p-2 hover:bg-slate-100 rounded-lg transition-colors">
                <X className="w-5 h-5 text-slate-500" />
              </button>
            </div>
            <div className="p-6">
              <div className="bg-slate-50 rounded-xl overflow-hidden">
                <img
                  src={`${API_BASE}/pdf-page-image?pdf_name=${encodeURIComponent(previewImage.source)}&page=${previewImage.page}`}
                  alt={`Page ${previewImage.page} of ${previewImage.source}`}
                  className="w-full h-auto"
                  onError={(e) => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'flex' }}
                />
                <div className="hidden items-center justify-center min-h-96 text-slate-400">
                  <div className="text-center">
                    <Image className="w-16 h-16 mx-auto mb-3 opacity-30" />
                    <p>Image preview not available</p>
                    <p className="text-sm mt-1">PDF rendering requires pdf2image + poppler</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
