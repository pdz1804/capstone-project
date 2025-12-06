import { useState, useEffect, useCallback } from 'react'
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
  ChevronDown,
  ChevronUp,
  Trash2,
  RefreshCw,
  MessageSquare,
  Database,
  Layers,
  Sparkles,
  File,
  FileImage,
  Eye,
  X,
  Zap,
  BarChart3,
  Hash,
  AlertCircle,
  ArrowRight
} from 'lucide-react'

// API base URL - configurable via environment variable for deployment
const API_BASE = import.meta.env.VITE_API_URL 
  ? `${import.meta.env.VITE_API_URL}/api` 
  : '/api'

// File type icon helper
const getFileIcon = (type) => {
  const ext = type?.toLowerCase() || ''
  if (['.pdf', '.docx', '.doc', '.txt', '.md'].includes(ext)) return FileText
  if (['.png', '.jpg', '.jpeg', '.gif', '.webp'].includes(ext)) return FileImage
  return File
}

// Stage info with colors
const stageInfo = {
  'stage1_normalized': { label: 'Normalized', color: 'sky', step: 1 },
  'stage2_media_processed': { label: 'Media', color: 'cyan', step: 2 },
  'stage3_document_processed': { label: 'Chunked', color: 'blue', step: 3 },
  'stage4_rag_ready': { label: 'RAG Ready', color: 'indigo', step: 4 },
}

function App() {
  const [activeTab, setActiveTab] = useState('upload')
  const [files, setFiles] = useState({ input: [], processed: [], indexed: [] })
  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [searchLoading, setSearchLoading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(null)
  const [pipelineStatus, setPipelineStatus] = useState(null)
  const [expandedResults, setExpandedResults] = useState({})
  const [previewImage, setPreviewImage] = useState(null)
  const [processedFilter, setProcessedFilter] = useState('all')
  const [dataLoading, setDataLoading] = useState(true)
  const [pipelineConfig, setPipelineConfig] = useState(null)
  const [showConfig, setShowConfig] = useState(false)

  useEffect(() => {
    setDataLoading(true)
    Promise.all([fetchFiles(), fetchPipelineStatus(), fetchConfig()]).finally(() => setDataLoading(false))
    const interval = setInterval(fetchPipelineStatus, 5000)
    return () => clearInterval(interval)
  }, [])

  const fetchFiles = async () => {
    try {
      const response = await axios.get(`${API_BASE}/files`)
      setFiles(response.data)
    } catch (error) {
      console.error('Failed to fetch files:', error)
    }
  }

  const fetchPipelineStatus = async () => {
    try {
      const response = await axios.get(`${API_BASE}/status`)
      setPipelineStatus(response.data)
    } catch (error) {
      console.error('Failed to fetch status:', error)
    }
  }

  const fetchConfig = async () => {
    try {
      const response = await axios.get(`${API_BASE}/config`)
      setPipelineConfig(response.data)
    } catch (error) {
      console.error('Failed to fetch config:', error)
    }
  }

  const handleUpload = async (e) => {
    const uploadFiles = e.target.files
    if (!uploadFiles.length) return

    const formData = new FormData()
    for (let file of uploadFiles) {
      formData.append('files', file)
    }

    setUploadProgress({ uploading: true, progress: 0 })
    
    try {
      await axios.post(`${API_BASE}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          setUploadProgress({ uploading: true, progress })
        }
      })
      setUploadProgress({ uploading: false, success: true })
      fetchFiles()
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
      const dataTransfer = new DataTransfer()
      for (let file of dropFiles) {
        dataTransfer.items.add(file)
      }
      input.files = dataTransfer.files
      handleUpload({ target: { files: dataTransfer.files } })
    }
  }, [])

  const handleProcess = async () => {
    setLoading(true)
    try {
      const response = await axios.post(`${API_BASE}/process`)
      console.log('Process response:', response.data)
      await new Promise(r => setTimeout(r, 2000))
      fetchFiles()
      fetchPipelineStatus()
    } catch (error) {
      console.error('Processing failed:', error.response?.data || error.message)
      alert(`Processing failed: ${error.response?.data?.detail || error.message}`)
    }
    setLoading(false)
  }

  const handleIndex = async () => {
    setLoading(true)
    try {
      const response = await axios.post(`${API_BASE}/index`)
      console.log('Index response:', response.data)
      await new Promise(r => setTimeout(r, 2000))
      fetchFiles()
      fetchPipelineStatus()
    } catch (error) {
      console.error('Indexing failed:', error.response?.data || error.message)
      alert(`Indexing failed: ${error.response?.data?.detail || error.message}`)
    }
    setLoading(false)
  }

  const handleSearch = async () => {
    if (!query.trim()) return
    
    setSearchLoading(true)
    setResults(null)
    
    try {
      const response = await axios.post(`${API_BASE}/search`, { query, top_k: 10 })
      setResults(response.data)
    } catch (error) {
      console.error('Search failed:', error)
    }
    setSearchLoading(false)
  }

  const handleDeleteFile = async (filePath) => {
    try {
      await axios.delete(`${API_BASE}/files`, { data: { path: filePath } })
      fetchFiles()
    } catch (error) {
      console.error('Delete failed:', error)
    }
  }

  const toggleExpand = (id) => {
    setExpandedResults(prev => ({ ...prev, [id]: !prev[id] }))
  }

  // Group processed files by document source
  const processedByDoc = (files.processed && Array.isArray(files.processed)) ? files.processed.reduce((acc, file) => {
    const docName = file.name.replace(/\.(json|md|txt)$/, '').replace(/_stats$/, '')
    if (!acc[docName]) acc[docName] = { files: [], stages: new Set() }
    acc[docName].files.push(file)
    if (file.stage) acc[docName].stages.add(file.stage)
    return acc
  }, {}) : {}

  const filteredDocs = Object.entries(processedByDoc).filter(([_, doc]) => {
    if (processedFilter === 'all') return true
    return doc.stages && doc.stages.has(processedFilter)
  })

  const tabs = [
    { id: 'upload', label: 'Upload Files', icon: Upload },
    { id: 'processed', label: 'Processed Files', icon: Layers },
    { id: 'indexed', label: 'Indexed Files', icon: Database },
    { id: 'search', label: 'Search & Query', icon: Search },
  ]

  return (
    <div className="min-h-screen bg-gradient-to-br from-sky-50 via-white to-blue-50">
      {/* Decorative background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-sky-100 rounded-full opacity-40 blur-3xl"></div>
        <div className="absolute top-1/3 -left-32 w-72 h-72 bg-blue-100 rounded-full opacity-40 blur-3xl"></div>
        <div className="absolute -bottom-32 right-1/4 w-80 h-80 bg-cyan-100 rounded-full opacity-40 blur-3xl"></div>
      </div>

      {/* Header */}
      <header className="relative bg-white/80 backdrop-blur-xl border-b border-sky-100/50 sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="w-12 h-12 bg-gradient-to-br from-sky-400 to-blue-500 rounded-xl flex items-center justify-center shadow-lg shadow-sky-200/50">
                <Sparkles className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold bg-gradient-to-r from-sky-600 to-blue-600 bg-clip-text text-transparent">
                  RAG Pipeline
                </h1>
                <p className="text-xs text-slate-500">Multimodal Retrieval-Augmented Generation</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              {pipelineStatus && (
                <div className="flex items-center space-x-4 px-5 py-2.5 bg-gradient-to-r from-sky-50 to-blue-50 rounded-xl border border-sky-100 backdrop-blur-sm">
                  <div className="flex items-center space-x-2">
                    <div className={`w-2.5 h-2.5 rounded-full animate-pulse ${pipelineStatus.ready ? 'bg-emerald-400' : 'bg-amber-400'}`}></div>
                    <span className="text-sm font-medium text-slate-700">{pipelineStatus.indexed_docs} chunks</span>
                  </div>
                  {pipelineStatus.image_pages > 0 && (
                    <>
                      <div className="w-px h-5 bg-sky-200"></div>
                      <div className="flex items-center space-x-2">
                        <Image className="w-4 h-4 text-sky-500" />
                        <span className="text-sm font-medium text-slate-700">{pipelineStatus.image_pages} pages</span>
                      </div>
                    </>
                  )}
                </div>
              )}
              <button
                onClick={() => { fetchFiles(); fetchPipelineStatus(); }}
                className="p-2.5 text-slate-500 hover:text-sky-600 hover:bg-sky-50 rounded-lg transition-all duration-200"
              >
                <RefreshCw className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="relative max-w-7xl mx-auto px-4 py-6">
        {/* Tabs */}
        <div className="flex space-x-2 bg-white/60 backdrop-blur-sm p-1.5 rounded-xl mb-6 shadow-sm border border-sky-100/50">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center space-x-2 px-4 py-2.5 rounded-lg font-medium transition-all duration-300 ${
                activeTab === tab.id
                  ? 'bg-gradient-to-r from-sky-500 to-blue-500 text-white shadow-lg shadow-sky-200/50'
                  : 'text-slate-600 hover:text-sky-600 hover:bg-sky-50'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Show loading spinner if data hasn't loaded yet */}
        {dataLoading && (
          <div className="flex items-center justify-center py-20">
            <div className="text-center">
              <Loader2 className="w-12 h-12 animate-spin text-sky-500 mx-auto mb-3" />
              <p className="text-slate-500 font-medium">Loading data...</p>
            </div>
          </div>
        )}

        {/* Tab Content - Only show when data is loaded */}
        {!dataLoading && (
          <>
        {/* Upload Tab */}
        {activeTab === 'upload' && (
          <div className="space-y-6 animate-in fade-in slide-in-from-top-4 duration-500">
            {/* Upload Area */}
            <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-sm border border-sky-100 p-8 hover:shadow-lg hover:border-sky-200 transition-all duration-300">
              <h2 className="text-lg font-semibold text-slate-800 mb-6">Upload Documents</h2>
              <label className="block">
                <div 
                  className="border-2 border-dashed border-sky-300 rounded-2xl p-12 text-center hover:border-sky-500 hover:bg-sky-50/50 transition-all duration-300 cursor-pointer group"
                  onDrop={handleDrop}
                  onDragOver={(e) => e.preventDefault()}
                >
                  <div className="w-16 h-16 mx-auto mb-4 bg-gradient-to-br from-sky-100 to-blue-100 rounded-2xl flex items-center justify-center group-hover:scale-110 group-hover:from-sky-200 group-hover:to-blue-200 transition-all duration-300">
                    <Upload className="w-8 h-8 text-sky-500" />
                  </div>
                  <p className="text-slate-700 font-semibold mb-2">Drop files here or click to upload</p>
                  <p className="text-sm text-slate-400">PDF, DOCX, PPTX, TXT, images, videos and more</p>
                  <input
                    id="file-upload"
                    type="file"
                    multiple
                    onChange={handleUpload}
                    className="hidden"
                    accept=".pdf,.docx,.pptx,.txt,.md,.png,.jpg,.jpeg,.mp4,.avi,.mov"
                  />
                </div>
              </label>
              
              {uploadProgress && (
                <div className="mt-6 space-y-3">
                  {uploadProgress.uploading && (
                    <div className="flex items-center space-x-4 p-4 bg-sky-50 rounded-xl border border-sky-100">
                      <Loader2 className="w-5 h-5 animate-spin text-sky-500 flex-shrink-0" />
                      <div className="flex-1">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium text-slate-700">Uploading...</span>
                          <span className="text-sm font-bold text-sky-600">{uploadProgress.progress}%</span>
                        </div>
                        <div className="h-2.5 bg-sky-200 rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-gradient-to-r from-sky-400 to-blue-500 transition-all duration-300"
                            style={{ width: `${uploadProgress.progress}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  )}
                  {uploadProgress.success && (
                    <div className="flex items-center space-x-3 p-4 bg-emerald-50 rounded-xl border border-emerald-200">
                      <CheckCircle className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                      <span className="text-sm font-medium text-emerald-700">Upload complete!</span>
                    </div>
                  )}
                  {uploadProgress.error && (
                    <div className="flex items-center space-x-3 p-4 bg-red-50 rounded-xl border border-red-200">
                      <XCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
                      <span className="text-sm text-red-700">Upload failed: {uploadProgress.error}</span>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Input Files */}
            <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-sm border border-sky-100 p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-semibold text-slate-800 flex items-center space-x-3">
                  <FolderOpen className="w-5 h-5 text-sky-500" />
                  <span>Input Files</span>
                  <span className="px-3 py-1 bg-sky-100 text-sky-700 text-sm rounded-full font-semibold">
                    {files.input?.length || 0}
                  </span>
                </h2>
                <button
                  onClick={handleProcess}
                  disabled={loading || !files.input?.length}
                  className="px-6 py-2.5 bg-gradient-to-r from-sky-500 to-blue-500 text-white rounded-lg font-medium hover:shadow-lg hover:shadow-sky-200/50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2 transition-all duration-200 hover:scale-105 active:scale-95"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                  <span>Process</span>
                </button>
              </div>
              
              {files.input?.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-96 overflow-y-auto pr-2">
                  {files.input.map((file, idx) => {
                    const FileIcon = getFileIcon(file.type)
                    return (
                      <div key={idx} className="flex items-center justify-between p-4 bg-gradient-to-r from-slate-50 to-sky-50/50 rounded-xl border border-slate-100 hover:border-sky-200 hover:shadow-md transition-all duration-200 group">
                        <div className="flex items-center space-x-3">
                          <div className="w-10 h-10 bg-white rounded-lg flex items-center justify-center shadow-sm border border-slate-100">
                            <FileIcon className="w-5 h-5 text-sky-500" />
                          </div>
                          <div>
                            <p className="font-medium text-slate-800 text-sm truncate">{file.name}</p>
                            <p className="text-xs text-slate-400">{file.size}</p>
                          </div>
                        </div>
                        <button
                          onClick={() => handleDeleteFile(file.path)}
                          className="p-2 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-lg opacity-0 group-hover:opacity-100 transition-all duration-200"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div className="text-center py-12 text-slate-400">
                  <FolderOpen className="w-12 h-12 mx-auto mb-3 opacity-20" />
                  <p>No files uploaded yet</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Processed Files Tab */}
        {activeTab === 'processed' && (
          <div className="space-y-6 animate-in fade-in slide-in-from-top-4 duration-500">
            {/* Quick Action Panel */}
            <div className="bg-gradient-to-r from-blue-50 via-sky-50 to-cyan-50 backdrop-blur-sm rounded-2xl shadow-sm border border-sky-200 p-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-slate-800 mb-1">Pipeline Actions</h3>
                  <p className="text-sm text-slate-600">Manage document processing workflow</p>
                </div>
                <div className="flex items-center space-x-3">
                  <button
                    onClick={handleProcess}
                    disabled={loading || !files.input?.length}
                    className="px-6 py-2.5 bg-gradient-to-r from-sky-500 to-blue-500 text-white rounded-lg font-medium hover:shadow-lg hover:shadow-sky-200/50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2 transition-all duration-200 hover:scale-105 active:scale-95"
                  >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                    <span>Process Files</span>
                  </button>
                  <button
                    onClick={handleIndex}
                    disabled={loading}
                    className="px-6 py-2.5 bg-gradient-to-r from-indigo-500 to-purple-500 text-white rounded-lg font-medium hover:shadow-lg hover:shadow-indigo-200/50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2 transition-all duration-200 hover:scale-105 active:scale-95"
                  >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                    <span>Build Index</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Configuration Display */}
            {pipelineConfig?.key_settings && (
              <div className="bg-gradient-to-r from-slate-50 via-slate-50 to-stone-50 backdrop-blur-sm rounded-2xl shadow-sm border border-slate-200 p-6">
                <div className="flex items-center justify-between cursor-pointer" onClick={() => setShowConfig(!showConfig)}>
                  <div>
                    <h3 className="text-lg font-semibold text-slate-800 mb-1 flex items-center space-x-2">
                      <Database className="w-5 h-5" />
                      <span>Pipeline Configuration</span>
                    </h3>
                    <p className="text-sm text-slate-600">Current settings from config/default.yaml</p>
                  </div>
                  {showConfig ? <ChevronUp className="w-5 h-5 text-slate-500" /> : <ChevronDown className="w-5 h-5 text-slate-500" />}
                </div>
                
                {showConfig && (
                  <div className="mt-4 pt-4 border-t border-slate-200 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                    <div className="bg-white/60 rounded-lg p-3">
                      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Pipeline Mode</div>
                      <div className="text-sm font-medium text-slate-800">{pipelineConfig.key_settings.pipeline_mode}</div>
                    </div>
                    <div className="bg-white/60 rounded-lg p-3">
                      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">RAG Mode</div>
                      <div className="text-sm font-medium text-slate-800">{pipelineConfig.key_settings.rag_mode}</div>
                    </div>
                    <div className="bg-white/60 rounded-lg p-3">
                      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Processing</div>
                      <div className="text-sm font-medium text-slate-800">{pipelineConfig.key_settings.enable_processing ? '✓ Enabled' : '✗ Disabled'}</div>
                    </div>
                    <div className="bg-white/60 rounded-lg p-3">
                      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Retrieval</div>
                      <div className="text-sm font-medium text-slate-800">{pipelineConfig.key_settings.enable_retrieval ? '✓ Enabled' : '✗ Disabled'}</div>
                    </div>
                    <div className="bg-white/60 rounded-lg p-3">
                      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Generation</div>
                      <div className="text-sm font-medium text-slate-800">{pipelineConfig.key_settings.enable_generation ? '✓ Enabled' : '✗ Disabled'}</div>
                    </div>
                    <div className="bg-white/60 rounded-lg p-3">
                      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Image Retrieval</div>
                      <div className="text-sm font-medium text-slate-800">{pipelineConfig.key_settings.image_retrieval_enabled ? '✓ Enabled' : '✗ Disabled'}</div>
                    </div>
                    <div className="bg-white/60 rounded-lg p-3">
                      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">ColQwen Model</div>
                      <div className="text-sm font-medium text-slate-800 truncate">{pipelineConfig.key_settings.colqwen_model?.split('/')?.pop() || 'N/A'}</div>
                    </div>
                    <div className="bg-white/60 rounded-lg p-3">
                      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">ColQwen Quantization</div>
                      <div className="text-sm font-medium text-slate-800">{pipelineConfig.key_settings.colqwen_quantization || 'None'}</div>
                    </div>
                    <div className="bg-white/60 rounded-lg p-3 md:col-span-2 lg:col-span-1">
                      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Text Embedding</div>
                      <div className="text-sm font-medium text-slate-800 truncate">{pipelineConfig.key_settings.text_embedding_model?.split('-')?.pop() || 'N/A'}</div>
                    </div>
                  </div>
                )}
              </div>
            )}

        {/* Debug info */}
            {process.env.NODE_ENV === 'development' && (
              <div className="text-xs text-slate-400 bg-slate-50 p-2 rounded">
                Processed files: {files.processed?.length || 0} | Filtered docs: {filteredDocs.length}
              </div>
            )}
            <div className="flex items-center space-x-2 flex-wrap gap-2">
              <span className="text-sm font-medium text-slate-600">Filter:</span>
              <button
                onClick={() => setProcessedFilter('all')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  processedFilter === 'all' 
                    ? 'bg-sky-500 text-white shadow-lg shadow-sky-200/50' 
                    : 'bg-white/60 text-slate-600 border border-sky-100 hover:bg-sky-50'
                }`}
              >
                All ({files.processed?.length || 0})
              </button>
              {Object.entries(stageInfo).map(([stage, info]) => {
                const count = files.processed?.filter(f => f.stage === stage).length || 0
                if (count === 0) return null
                const activeColors = {
                  sky: 'bg-sky-500 text-white shadow-lg shadow-sky-200/50',
                  cyan: 'bg-cyan-500 text-white shadow-lg shadow-cyan-200/50',
                  blue: 'bg-blue-500 text-white shadow-lg shadow-blue-200/50',
                  indigo: 'bg-indigo-500 text-white shadow-lg shadow-indigo-200/50',
                }
                const inactiveColors = {
                  sky: 'bg-white/60 text-slate-600 border border-sky-100 hover:bg-sky-50',
                  cyan: 'bg-white/60 text-slate-600 border border-cyan-100 hover:bg-cyan-50',
                  blue: 'bg-white/60 text-slate-600 border border-blue-100 hover:bg-blue-50',
                  indigo: 'bg-white/60 text-slate-600 border border-indigo-100 hover:bg-indigo-50',
                }
                return (
                  <button
                    key={stage}
                    onClick={() => setProcessedFilter(stage)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                      processedFilter === stage ? activeColors[info.color] : inactiveColors[info.color]
                    }`}
                  >
                    {info.label} ({count})
                  </button>
                )
              })}
            </div>

            {/* Processing Pipeline Visual */}
            <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-sm border border-sky-100 p-6">
              <h3 className="text-lg font-semibold text-slate-800 mb-6">Processing Pipeline</h3>
              <div className="grid grid-cols-4 gap-4 mb-8">
                {Object.entries(stageInfo).map(([stage, info]) => {
                  const count = files.processed?.filter(f => f.stage === stage).length || 0
                  const colors = {
                    sky: 'from-sky-100 to-sky-50 text-sky-700 border-sky-200',
                    cyan: 'from-cyan-100 to-cyan-50 text-cyan-700 border-cyan-200',
                    blue: 'from-blue-100 to-blue-50 text-blue-700 border-blue-200',
                    indigo: 'from-indigo-100 to-indigo-50 text-indigo-700 border-indigo-200',
                  }
                  const colorSet = colors[info.color]
                  return (
                    <div key={stage} className={`bg-gradient-to-br ${colorSet} border p-4 rounded-xl text-center relative`}>
                      <div className="text-3xl font-bold mb-1">{count}</div>
                      <div className="text-xs font-medium">{info.label}</div>
                      {info.step < 4 && (
                        <ArrowRight className="absolute -right-8 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-300" />
                      )}
                    </div>
                  )
                })}
              </div>

              {/* Processed Files by Document */}
              {files.processed && files.processed.length > 0 ? (
                <div className="space-y-3 max-h-[500px] overflow-y-auto pr-2">
                  {filteredDocs.length > 0 ? (
                    filteredDocs.map(([docName, doc], idx) => {
                      const stages = doc.stages || new Set()
                      const stagesArray = Array.from(stages)
                      const maxStage = stagesArray.length > 0 ? Math.max(...stagesArray.map(s => stageInfo[s]?.step || 0)) : 0
                      const isExpanded = expandedResults[`doc-${idx}`]
                      return (
                        <div key={idx} className="border border-sky-100 rounded-xl overflow-hidden bg-white hover:shadow-md transition-all duration-200">
                          <button
                            onClick={() => toggleExpand(`doc-${idx}`)}
                            className="w-full p-4 flex items-center justify-between hover:bg-sky-50/50 transition-colors"
                          >
                            <div className="text-left flex-1">
                              <p className="font-medium text-slate-800">{docName}</p>
                              <div className="flex items-center space-x-2 mt-2">
                                {stagesArray.map(stage => {
                                  const info = stageInfo[stage] || { label: stage, color: 'sky' }
                                  const colorClasses = {
                                    sky: 'bg-sky-100 text-sky-700',
                                    cyan: 'bg-cyan-100 text-cyan-700',
                                    blue: 'bg-blue-100 text-blue-700',
                                    indigo: 'bg-indigo-100 text-indigo-700',
                                  }
                                  return (
                                    <span key={stage} className={`px-2.5 py-1 rounded-md text-xs font-medium ${colorClasses[info.color] || colorClasses.sky}`}>
                                      {info.label}
                                    </span>
                                  )
                                })}
                              </div>
                            </div>
                            {isExpanded ? (
                              <ChevronUp className="w-5 h-5 text-slate-400" />
                            ) : (
                              <ChevronDown className="w-5 h-5 text-slate-400" />
                            )}
                          </button>
                          {isExpanded && (
                            <div className="border-t border-slate-100 p-4 bg-slate-50/50 space-y-3">
                              {doc.files.map((file, fidx) => (
                                <div key={fidx} className="p-3 bg-white rounded-lg border border-slate-200">
                                  <div className="flex items-center justify-between mb-2">
                                    <p className="font-medium text-slate-800 text-sm">{file.name}</p>
                                    <span className="text-xs text-slate-400">{file.size}</span>
                                  </div>
                                  {file.preview && (
                                    <pre className="text-xs text-slate-600 bg-slate-50 p-2 rounded overflow-x-auto max-h-24 overflow-y-auto font-mono">
                                      {file.preview.substring(0, 200)}...
                                    </pre>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })
                  ) : (
                    <div className="text-center py-12 text-slate-400">
                      <AlertCircle className="w-12 h-12 mx-auto mb-3 opacity-20" />
                      <p>No files in selected filter</p>
                    </div>
                  )}
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

        {/* Indexed Files Tab */}
        {activeTab === 'indexed' && (
          <div className="space-y-6 animate-in fade-in slide-in-from-top-4 duration-500">
            {/* Index Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Text Index */}
              <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-sm border border-sky-100 p-8 hover:shadow-lg hover:border-sky-200 transition-all duration-300">
                <div className="flex items-center space-x-4 mb-6">
                  <div className="w-12 h-12 bg-gradient-to-br from-sky-100 to-blue-100 rounded-xl flex items-center justify-center">
                    <FileText className="w-6 h-6 text-sky-600" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-slate-800">Text Index</h3>
                    <p className="text-sm text-slate-400">BM25 + Dense Retrieval</p>
                  </div>
                </div>
                
                {pipelineStatus?.text_index ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="p-4 bg-gradient-to-br from-sky-50 to-cyan-50 rounded-xl border border-sky-100">
                        <div className="text-sm text-sky-600 font-medium mb-1">Chunks</div>
                        <p className="text-3xl font-bold text-sky-700">{pipelineStatus.text_index.chunks || 0}</p>
                      </div>
                      <div className="p-4 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl border border-blue-100">
                        <div className="text-sm text-blue-600 font-medium mb-1">Documents</div>
                        <p className="text-3xl font-bold text-blue-700">{pipelineStatus.text_index.docs || 0}</p>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {pipelineStatus.text_index.retrievers?.map((r, i) => (
                        <span key={i} className="px-3 py-1.5 bg-sky-100 text-sky-700 rounded-lg text-sm font-medium">
                          {r}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-6">
                    <AlertCircle className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                    <p className="text-slate-400 text-sm">No text index available</p>
                  </div>
                )}
              </div>

              {/* Image Index */}
              <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-sm border border-sky-100 p-8 hover:shadow-lg hover:border-sky-200 transition-all duration-300">
                <div className="flex items-center space-x-4 mb-6">
                  <div className="w-12 h-12 bg-gradient-to-br from-indigo-100 to-purple-100 rounded-xl flex items-center justify-center">
                    <Image className="w-6 h-6 text-indigo-600" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-slate-800">Image Index</h3>
                    <p className="text-sm text-slate-400">ColQwen Vision-Language</p>
                  </div>
                </div>
                
                {pipelineStatus?.image_index ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="p-4 bg-gradient-to-br from-indigo-50 to-purple-50 rounded-xl border border-indigo-100">
                        <div className="text-sm text-indigo-600 font-medium mb-1">Pages</div>
                        <p className="text-3xl font-bold text-indigo-700">{pipelineStatus.image_index.pages || 0}</p>
                      </div>
                      <div className="p-4 bg-gradient-to-br from-purple-50 to-pink-50 rounded-xl border border-purple-100">
                        <div className="text-sm text-purple-600 font-medium mb-1">PDFs</div>
                        <p className="text-3xl font-bold text-purple-700">{pipelineStatus.image_index.pdfs || 0}</p>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <span className="px-3 py-1.5 bg-indigo-100 text-indigo-700 rounded-lg text-sm font-medium">
                        ColQwen2
                      </span>
                      <span className="px-3 py-1.5 bg-purple-100 text-purple-700 rounded-lg text-sm font-medium">
                        8-bit Quantized
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-6">
                    <AlertCircle className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                    <p className="text-slate-400 text-sm">No image index available</p>
                  </div>
                )}
              </div>
            </div>

            {/* Indexed Files List */}
            <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-sm border border-sky-100 p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-semibold text-slate-800 flex items-center space-x-3">
                  <Database className="w-5 h-5 text-sky-500" />
                  <span>Indexed Documents</span>
                </h2>
                <button
                  onClick={handleIndex}
                  disabled={loading}
                  className="px-6 py-2.5 bg-gradient-to-r from-indigo-500 to-purple-500 text-white rounded-lg font-medium hover:shadow-lg hover:shadow-indigo-200/50 disabled:opacity-50 flex items-center space-x-2 transition-all duration-200 hover:scale-105 active:scale-95"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                  <span>Rebuild</span>
                </button>
              </div>

              {files.indexed?.length > 0 ? (
                <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
                  {files.indexed.map((file, idx) => (
                    <div 
                      key={idx} 
                      className={`p-4 rounded-xl border transition-all duration-200 hover:shadow-md ${
                        file.type === 'image' 
                          ? 'bg-gradient-to-r from-indigo-50 to-purple-50 border-indigo-100 hover:border-indigo-200' 
                          : 'bg-gradient-to-r from-sky-50 to-blue-50 border-sky-100 hover:border-sky-200'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                            file.type === 'image' ? 'bg-indigo-100' : 'bg-sky-100'
                          }`}>
                            {file.type === 'image' ? (
                              <Image className="w-5 h-5 text-indigo-600" />
                            ) : (
                              <FileText className="w-5 h-5 text-sky-600" />
                            )}
                          </div>
                          <div>
                            <p className="font-medium text-slate-800">{file.name}</p>
                            <p className="text-sm text-slate-400">
                              {file.type === 'image' 
                                ? `${file.pages} pages` 
                                : `${file.chunks} chunks`}
                            </p>
                          </div>
                        </div>
                        <span className={`px-3 py-1.5 rounded-lg text-sm font-medium ${
                          file.type === 'image' 
                            ? 'bg-indigo-100 text-indigo-700' 
                            : 'bg-sky-100 text-sky-700'
                        }`}>
                          {file.type === 'image' ? 'Vision' : 'Text'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12 text-slate-400">
                  <Database className="w-12 h-12 mx-auto mb-3 opacity-20" />
                  <p>No indexed documents</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Search Tab */}
        {activeTab === 'search' && (
          <div className="space-y-6 animate-in fade-in slide-in-from-top-4 duration-500">
            {/* Search Box */}
            <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-sm border border-sky-100 p-8 hover:shadow-lg hover:border-sky-200 transition-all duration-300">
              <h2 className="text-lg font-semibold text-slate-800 mb-6">Query Knowledge Base</h2>
              <div className="flex gap-3">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                  placeholder="Ask a question about your documents..."
                  className="flex-1 px-5 py-3 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent text-slate-700 placeholder-slate-400 transition-all duration-200"
                />
                <button
                  onClick={handleSearch}
                  disabled={searchLoading || !query.trim()}
                  className="px-8 py-3 bg-gradient-to-r from-sky-500 to-blue-500 text-white rounded-lg font-medium hover:shadow-lg hover:shadow-sky-200/50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2 transition-all duration-200 hover:scale-105 active:scale-95"
                >
                  {searchLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />}
                  <span>Search</span>
                </button>
              </div>
            </div>

            {/* Results */}
            {results && (
              <div className="space-y-6">
                {/* Generated Answer */}
                {results.answer && (
                  <div className="bg-gradient-to-br from-sky-50 to-blue-50 rounded-2xl shadow-sm border border-sky-100 p-8">
                    <h3 className="text-lg font-semibold mb-4 flex items-center space-x-3 text-slate-800">
                      <div className="w-8 h-8 bg-gradient-to-br from-sky-400 to-blue-500 rounded-lg flex items-center justify-center">
                        <MessageSquare className="w-4 h-4 text-white" />
                      </div>
                      <span>Answer</span>
                    </h3>
                    <p className="text-slate-700 whitespace-pre-wrap leading-relaxed">{results.answer}</p>
                  </div>
                )}

                {/* Text Results */}
                {results.text_results?.length > 0 && (
                  <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-sm border border-sky-100 p-6">
                    <h3 className="text-lg font-semibold mb-4 flex items-center space-x-3 text-slate-800">
                      <FileText className="w-5 h-5 text-sky-500" />
                      <span>Text Results</span>
                      <span className="ml-2 px-3 py-1 bg-sky-100 text-sky-700 text-sm rounded-full font-medium">
                        {results.text_results.length}
                      </span>
                    </h3>
                    <div className="space-y-3">
                      {results.text_results.map((result, idx) => (
                        <div key={idx} className="border border-sky-100 rounded-xl overflow-hidden hover:shadow-md transition-all duration-200">
                          <button
                            onClick={() => toggleExpand(`text-${idx}`)}
                            className="w-full p-4 flex items-center justify-between bg-gradient-to-r from-slate-50 to-sky-50/50 hover:to-sky-100/50 transition-colors"
                          >
                            <div className="flex items-center space-x-4 flex-1">
                              <span className="w-8 h-8 bg-gradient-to-br from-sky-400 to-blue-500 text-white rounded-lg flex items-center justify-center font-bold text-sm flex-shrink-0">
                                {idx + 1}
                              </span>
                              <div className="text-left">
                                <p className="font-medium text-slate-800 text-sm">{result.source || 'Document'}</p>
                                <div className="flex items-center space-x-2 mt-1.5">
                                  <span className="px-2 py-0.5 bg-sky-100 text-sky-700 text-xs rounded font-semibold">
                                    {result.score?.toFixed(4)}
                                  </span>
                                  {result.retrieval_type && (
                                    <span className="px-2 py-0.5 bg-slate-100 text-slate-600 text-xs rounded">
                                      {result.retrieval_type}
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                            {expandedResults[`text-${idx}`] ? (
                              <ChevronUp className="w-5 h-5 text-slate-400" />
                            ) : (
                              <ChevronDown className="w-5 h-5 text-slate-400" />
                            )}
                          </button>
                          {expandedResults[`text-${idx}`] && (
                            <div className="p-4 bg-white border-t border-sky-100">
                              <p className="text-slate-700 text-sm whitespace-pre-wrap mb-4">{result.text}</p>
                              {result.retrieval_info && (
                                <div className="flex items-center space-x-4 text-xs text-slate-500 border-t border-slate-100 pt-3">
                                  <span>BM25 Rank: #{result.retrieval_info.bm25_rank || '-'}</span>
                                  <span>Dense Rank: #{result.retrieval_info.dense_rank || '-'}</span>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Image Results */}
                {results.image_results?.length > 0 && (
                  <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-sm border border-indigo-100 p-6">
                    <h3 className="text-lg font-semibold mb-4 flex items-center space-x-3 text-slate-800">
                      <Image className="w-5 h-5 text-indigo-500" />
                      <span>Image Results</span>
                      <span className="ml-2 px-3 py-1 bg-indigo-100 text-indigo-700 text-sm rounded-full font-medium">
                        {results.image_results.length}
                      </span>
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                      {results.image_results.map((result, idx) => (
                        <div 
                          key={idx} 
                          className="group border border-indigo-100 rounded-xl overflow-hidden hover:shadow-lg hover:shadow-indigo-100/50 transition-all duration-300 hover:-translate-y-1 cursor-pointer bg-white"
                          onClick={() => setPreviewImage(result)}
                        >
                          <div className="aspect-[4/3] bg-gradient-to-br from-indigo-50 to-purple-50 relative overflow-hidden">
                            <img 
                              src={`${API_BASE}/pdf-page-image?pdf_name=${encodeURIComponent(result.source)}&page=${result.page}`}
                              alt={`Page ${result.page} of ${result.source}`}
                              className="w-full h-full object-cover"
                              onError={(e) => {
                                e.target.style.display = 'none'
                                e.target.nextSibling.style.display = 'flex'
                              }}
                            />
                            <div className="hidden items-center justify-center w-full h-full absolute inset-0">
                              <div className="text-center">
                                <Image className="w-10 h-10 text-indigo-300 mb-2 mx-auto" />
                                <p className="text-sm text-indigo-400 font-medium">Page {result.page}</p>
                              </div>
                            </div>
                            <div className="absolute inset-0 bg-indigo-900/0 group-hover:bg-indigo-900/10 transition-colors flex items-center justify-center">
                              <Eye className="w-8 h-8 text-white opacity-0 group-hover:opacity-100 transition-opacity drop-shadow-lg" />
                            </div>
                          </div>
                          <div className="p-3 bg-white">
                            <p className="font-medium text-sm text-slate-800 truncate">{result.source}</p>
                            <div className="flex items-center justify-between mt-2">
                              <span className="text-xs text-slate-400">Page {result.page}</span>
                              <span className="px-2 py-0.5 bg-indigo-100 text-indigo-700 text-xs font-bold rounded">
                                {result.score?.toFixed(2)}
                              </span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
          </>
        )}
      </div>

      {/* Image Preview Modal */}
      {previewImage && (
        <div 
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in duration-200"
          onClick={() => setPreviewImage(null)}
        >
          <div 
            className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-auto animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-6 border-b border-slate-100 sticky top-0 bg-white z-10">
              <div>
                <p className="font-semibold text-slate-800">{previewImage.source}</p>
                <p className="text-sm text-slate-400">Page {previewImage.page} • Score: {previewImage.score?.toFixed(4)}</p>
              </div>
              <button 
                onClick={() => setPreviewImage(null)}
                className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-slate-500" />
              </button>
            </div>
            <div className="p-6">
              <div className="bg-slate-50 rounded-xl overflow-hidden">
                <img 
                  src={`${API_BASE}/pdf-page-image?pdf_name=${encodeURIComponent(previewImage.source)}&page=${previewImage.page}`}
                  alt={`Page ${previewImage.page} of ${previewImage.source}`}
                  className="w-full h-auto"
                  onError={(e) => {
                    e.target.style.display = 'none'
                    e.target.nextSibling.style.display = 'flex'
                  }}
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

      <style>{`
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes slideInFromTop { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes zoomIn { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
        .animate-in { animation: fadeIn 0.3s ease-out; }
        .fade-in { animation: fadeIn 0.3s ease-out; }
        .slide-in-from-top-4 { animation: slideInFromTop 0.3s ease-out; }
        .zoom-in-95 { animation: zoomIn 0.2s ease-out; }
        .scrollbar-thin::-webkit-scrollbar { width: 6px; }
        .scrollbar-thin::-webkit-scrollbar-track { background: #f1f5f9; border-radius: 3px; }
        .scrollbar-thin::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
        .scrollbar-thin::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
      `}</style>
    </div>
  )
}

export default App
