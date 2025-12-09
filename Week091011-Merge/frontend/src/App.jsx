import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import remarkGfm from 'remark-gfm'
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
  const [processingStats, setProcessingStats] = useState(null)
  const [expandedCitations, setExpandedCitations] = useState({})
  const [expandedCitationMetadata, setExpandedCitationMetadata] = useState({})
  const [expandedCitationContent, setExpandedCitationContent] = useState({})

  useEffect(() => {
    setDataLoading(true)
    Promise.all([fetchFiles(), fetchPipelineStatus(), fetchConfig(), fetchProcessingStats()]).finally(() => setDataLoading(false))
    
    // Smart polling: only poll when tab is visible, and less frequently (30 seconds)
    let interval = null
    
    const startPolling = () => {
      if (interval) clearInterval(interval)
      interval = setInterval(fetchPipelineStatus, 30000) // 30 seconds instead of 5
    }
    
    const stopPolling = () => {
      if (interval) {
        clearInterval(interval)
        interval = null
      }
    }
    
    // Start polling initially
    startPolling()
    
    // Stop polling when tab is hidden, resume when visible
    const handleVisibilityChange = () => {
      if (document.hidden) {
        stopPolling()
      } else {
        // Refresh immediately when tab becomes visible, then resume polling
        fetchPipelineStatus()
        startPolling()
      }
    }
    
    document.addEventListener('visibilitychange', handleVisibilityChange)
    
    return () => {
      stopPolling()
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
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

  const fetchProcessingStats = async () => {
    try {
      const response = await axios.get(`${API_BASE}/processing-stats`)
      setProcessingStats(response.data)
    } catch (error) {
      console.error('Failed to fetch processing stats:', error)
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
      fetchProcessingStats()
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
      fetchProcessingStats()
    } catch (error) {
      console.error('Indexing failed:', error.response?.data || error.message)
      alert(`Indexing failed: ${error.response?.data?.detail || error.message}`)
    }
    setLoading(false)
  }

  const handleRebuildSpecificIndex = async (indexType) => {
    setLoading(true)
    try {
      const response = await axios.post(`${API_BASE}/index/${indexType}`)
      console.log(`${indexType} index rebuild response:`, response.data)
      await new Promise(r => setTimeout(r, 2000))
      fetchFiles()
      fetchPipelineStatus()
      fetchProcessingStats()
    } catch (error) {
      console.error(`${indexType} index rebuild failed:`, error.response?.data || error.message)
      alert(`${indexType.charAt(0).toUpperCase() + indexType.slice(1)} index rebuild failed: ${error.response?.data?.detail || error.message}`)
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

  const toggleCitationExpand = (citationId) => {
    setExpandedCitations(prev => ({ ...prev, [citationId]: !prev[citationId] }))
  }

  const toggleCitationMetadata = (citationId) => {
    setExpandedCitationMetadata(prev => ({ ...prev, [citationId]: !prev[citationId] }))
  }

  const scrollToCitation = (citationId) => {
    // Try to find the element by ID
    const element = document.getElementById(citationId)
    if (element) {
      // Scroll to the element
      element.scrollIntoView({ behavior: 'smooth', block: 'center' })
      // Highlight the citation briefly with a box shadow
      element.style.transition = 'box-shadow 0.3s ease'
      element.style.boxShadow = '0 0 0 4px rgba(56, 189, 248, 0.4)'
      setTimeout(() => {
        element.style.boxShadow = ''
      }, 2000)
    } else {
      console.warn(`Citation element not found: ${citationId}`)
    }
  }

  const handleCitationClick = (e, href) => {
    console.log('handleCitationClick called with href:', href)
    console.log('Current activeTab:', activeTab)
    console.log('Current results:', results)
    
    // Check if it's a citation link (chunk-X-Y or image-X-Y)
    const match = href.match(/#(chunk|image)-(\d+)-(\d+)/)
    console.log('Match result:', match)
    if (match) {
      e.preventDefault()
      e.stopPropagation()
      const [, type, fileNum, chunkNum] = match
      const citationId = `${type}-${fileNum}-${chunkNum}`
      console.log('Citation ID:', citationId)
      
      // Switch to search tab if not already there
      if (activeTab !== 'search') {
        console.log('Switching to search tab...')
        setActiveTab('search')
        // Wait for tab switch to complete
        setTimeout(() => {
          handleCitationClick(e, href) // Recursive call after tab switch
        }, 100)
        return
      }
      
      // Find the citation key from results.contents
      // Backend format: key is "[1.1]", value.id is "chunk-1-1"
      let citationKey = null
      if (results && results.contents) {
        console.log('Results.contents exists, keys:', Object.keys(results.contents))
        // Extract citation number from ID (e.g., "chunk-1-1" -> "[1.1]")
        const idMatch = citationId.match(/(chunk|image)-(\d+)-(\d+)/)
        if (idMatch) {
          const [, type, fileNum, chunkNum] = idMatch
          // For text chunks: [1.1], [1.2], etc.
          // For images: [2.1], [2.2], etc.
          const expectedKey = type === 'image' ? `[2.${chunkNum}]` : `[${fileNum}.${chunkNum}]`
          console.log(`Looking for citation key: ${expectedKey} (from ID: ${citationId})`)
          
          // Try the expected key format first
          if (results.contents[expectedKey]) {
            citationKey = expectedKey
            console.log('Found citation key:', citationKey)
          } else {
            // Fallback: search by ID match
            console.log('Expected key not found, searching by ID match...')
            for (const [key, value] of Object.entries(results.contents)) {
              console.log(`Checking key: ${key}, value.id: ${value?.id}`)
              if (value?.id === citationId) {
                citationKey = key
                console.log('Found citation key by ID match:', citationKey)
                break
              }
            }
          }
        }
        
        if (!citationKey) {
          console.warn('Citation key not found for ID:', citationId)
          console.warn('Available contents keys:', Object.keys(results.contents))
          if (results.contents) {
            console.warn('Contents structure:', Object.entries(results.contents).map(([k, v]) => ({
              key: k,
              id: v?.id,
              type: v?.type
            })))
          }
        }
      } else {
        console.warn('Results or results.contents is null/undefined')
        console.warn('Results:', results)
      }
      
      // Expand the citation FIRST, before scrolling
      if (citationKey) {
        if (!expandedCitations[citationKey]) {
          console.log('Expanding citation:', citationKey)
          toggleCitationExpand(citationKey)
        }
        // Force expansion immediately
        setExpandedCitations(prev => ({ ...prev, [citationKey]: true }))
      }
      
      // Function to wait for element and scroll
      const waitForElementAndScroll = (selector, callback, maxAttempts = 10, attempt = 0) => {
        const element = typeof selector === 'string' ? document.querySelector(selector) : selector()
        if (element) {
          callback(element)
        } else if (attempt < maxAttempts) {
          setTimeout(() => waitForElementAndScroll(selector, callback, maxAttempts, attempt + 1), 100)
        } else {
          console.warn(`Element not found after ${maxAttempts} attempts:`, selector)
        }
      }
      
      // Scroll to citations section first, then to specific citation
      // Wait for citations section to appear
      waitForElementAndScroll('#citations-section', (citationsSection) => {
        console.log('Found citations section, scrolling...')
        citationsSection.scrollIntoView({ behavior: 'smooth', block: 'start' })
        
        // Then scroll to specific citation after DOM updates
        setTimeout(() => {
          console.log('Scrolling to citation:', citationId)
          waitForElementAndScroll(`#${citationId}`, (element) => {
            console.log('Found citation element, scrolling...')
            element.scrollIntoView({ behavior: 'smooth', block: 'center' })
            // Highlight
            element.style.boxShadow = '0 0 0 3px rgba(59, 130, 246, 0.5)'
            element.style.transition = 'box-shadow 0.3s ease'
            setTimeout(() => {
              element.style.boxShadow = 'none'
            }, 2000)
          }, 20, 0) // Try up to 2 seconds
        }, 500)
      }, 20, 0) // Try up to 2 seconds
    } else {
      console.warn('No match found for href:', href)
    }
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
    <div className="min-h-screen bg-sky-50">
      {/* Enhanced decorative background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-sky-200/20 rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute top-1/3 -left-40 w-80 h-80 bg-blue-200/20 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }}></div>
        <div className="absolute -bottom-40 right-1/4 w-96 h-96 bg-sky-200/20 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '2s' }}></div>
      </div>

      {/* Modern Header */}
      <header className="relative glass-strong border-b border-sky-100/60 sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-6 py-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-5">
              <div className="w-14 h-14 bg-sky-500 rounded-2xl flex items-center justify-center shadow-lg shadow-sky-200/50 ring-2 ring-white/50">
                <Sparkles className="w-7 h-7 text-white" />
              </div>
              <div>
                <h1 className="text-3xl font-bold text-sky-600 tracking-tight">
                  RAG Pipeline
                </h1>
                <p className="text-sm text-slate-500 font-medium mt-0.5">Multimodal Retrieval-Augmented Generation</p>
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
                onClick={() => { fetchFiles(); fetchPipelineStatus(); }}
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
        {/* Modern Tabs */}
        <div className="flex space-x-3 glass p-2 rounded-2xl mb-8 card-shadow">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center space-x-2.5 px-5 py-3 rounded-xl font-semibold text-sm transition-all duration-300 ${
                activeTab === tab.id
                  ? 'bg-sky-500 text-white shadow-lg shadow-sky-200/50 scale-105'
                  : 'text-slate-600 hover:text-sky-600 hover:bg-white/60'
              }`}
            >
              <tab.icon className={`w-4.5 h-4.5 ${activeTab === tab.id ? 'text-white' : 'text-slate-500'}`} />
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Enhanced loading spinner */}
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

        {/* Tab Content - Only show when data is loaded */}
        {!dataLoading && (
          <>
        {/* Upload Tab */}
        {activeTab === 'upload' && (
          <div className="space-y-8 animate-in fade-in slide-in-from-top-4">
            {/* Modern Upload Area */}
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
                <div className="mt-8 space-y-4 animate-in slide-in-from-bottom">
                  {uploadProgress.uploading && (
                    <div className="flex items-center space-x-5 p-5 bg-sky-50 rounded-2xl border-2 border-sky-200/60 card-shadow">
                      <div className="relative">
                        <Loader2 className="w-6 h-6 animate-spin text-sky-500 flex-shrink-0" />
                        <div className="absolute inset-0 w-6 h-6 border-2 border-sky-200 border-t-transparent rounded-full animate-spin"></div>
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between mb-3">
                          <span className="text-sm font-bold text-slate-700">Uploading files...</span>
                          <span className="text-lg font-bold text-sky-600">{uploadProgress.progress}%</span>
                        </div>
                        <div className="h-3 bg-white/80 rounded-full overflow-hidden shadow-inner">
                          <div 
                            className="h-full bg-sky-500 transition-all duration-500 shadow-lg shadow-sky-300/50"
                            style={{ width: `${uploadProgress.progress}%` }}
                          />
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

            {/* Modern Input Files Section */}
            <div className="glass-strong rounded-3xl card-shadow p-8">
              <div className="flex items-center justify-between mb-8">
                <div className="flex items-center space-x-4">
                  <div className="w-12 h-12 bg-sky-100 rounded-2xl flex items-center justify-center shadow-sm">
                    <FolderOpen className="w-6 h-6 text-sky-600" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-slate-800 flex items-center space-x-3">
                      <span>Input Files</span>
                      <span className="px-4 py-1.5 bg-sky-500 text-white text-sm rounded-full font-bold shadow-lg shadow-sky-200/50">
                        {files.input?.length || 0}
                      </span>
                    </h2>
                    <p className="text-sm text-slate-500 mt-1">Files ready for processing</p>
                  </div>
                </div>
                <button
                  onClick={handleProcess}
                  disabled={loading || !files.input?.length}
                  className="px-8 py-3.5 bg-sky-500 text-white rounded-xl font-bold hover:shadow-xl hover:shadow-sky-200/50 disabled:opacity-50 flex items-center space-x-2.5 transition-all duration-300 hover:scale-105 active:scale-95 disabled:hover:scale-100"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      <span>Processing...</span>
                    </>
                  ) : (
                    <>
                      <Zap className="w-5 h-5" />
                      <span>Process</span>
                    </>
                  )}
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
                        <button
                          onClick={() => handleDeleteFile(file.path)}
                          className="p-2.5 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-xl opacity-0 group-hover:opacity-100 transition-all duration-200 ml-3 flex-shrink-0"
                          title="Delete file"
                        >
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

        {/* Processed Files Tab */}
        {activeTab === 'processed' && (
          <div className="space-y-6 animate-in fade-in slide-in-from-top-4 duration-500">
            {/* Quick Action Panel */}
            <div className="bg-sky-50 backdrop-blur-sm rounded-2xl shadow-sm border border-sky-200 p-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-slate-800 mb-1">Pipeline Actions</h3>
                  <p className="text-sm text-slate-600">Manage document processing workflow</p>
                </div>
                <div className="flex items-center space-x-3">
                  <button
                    onClick={handleProcess}
                    disabled={loading || !files.input?.length}
                    className="px-6 py-2.5 bg-sky-500 text-white rounded-lg font-medium hover:shadow-lg hover:shadow-sky-200/50 disabled:opacity-50 flex items-center space-x-2 transition-all duration-200 hover:scale-105 active:scale-95"
                  >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                    <span>Process Files</span>
                  </button>
                  <button
                    onClick={handleIndex}
                    disabled={loading}
                    className="px-6 py-2.5 bg-indigo-500 text-white rounded-lg font-medium hover:shadow-lg hover:shadow-indigo-200/50 disabled:opacity-50 flex items-center space-x-2 transition-all duration-200 hover:scale-105 active:scale-95"
                  >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                    <span>Build Index</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Processing Stats Display */}
            {processingStats && (
              <div className="glass-strong rounded-3xl card-shadow p-8">
                <h3 className="text-xl font-bold text-slate-800 mb-6 flex items-center space-x-3">
                  <BarChart3 className="w-6 h-6 text-sky-500" />
                  <span>Processing Statistics</span>
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                  <div className="bg-white rounded-xl p-4 border border-sky-100">
                    <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Total Input Files</div>
                    <div className="text-2xl font-bold text-sky-600">{processingStats.total_input_files || 0}</div>
                  </div>
                  <div className="bg-white rounded-xl p-4 border border-sky-100">
                    <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Total Output Files</div>
                    <div className="text-2xl font-bold text-sky-600">{processingStats.total_output_files || 0}</div>
                  </div>
                  <div className="bg-white rounded-xl p-4 border border-sky-100">
                    <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Normalized</div>
                    <div className="text-2xl font-bold text-sky-600">{processingStats.stages?.normalization?.normalized_files || 0}</div>
                  </div>
                  <div className="bg-white rounded-xl p-4 border border-sky-100">
                    <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Processed</div>
                    <div className="text-2xl font-bold text-sky-600">{processingStats.stages?.document_processing?.processed_files || 0}</div>
                  </div>
                </div>
                {processingStats.stages && (
                  <div className="space-y-4">
                    <div className="bg-white rounded-xl p-4 border border-sky-100">
                      <h4 className="font-semibold text-slate-800 mb-3">Stage Details</h4>
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-slate-600">Normalization:</span>
                          <span className="font-medium text-slate-800">{processingStats.stages.normalization?.normalized_files || 0} files</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-600">Media Processing:</span>
                          <span className="font-medium text-slate-800">{processingStats.stages.media_processing?.processed_files || 0} files</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-600">Document Processing:</span>
                          <span className="font-medium text-slate-800">{processingStats.stages.document_processing?.processed_files || 0} files</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-600">Consolidation:</span>
                          <span className="font-medium text-slate-800">{processingStats.stages.consolidation?.total_documents || 0} documents</span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Configuration Display */}
            {pipelineConfig?.key_settings && (
              <div className="bg-slate-50 backdrop-blur-sm rounded-2xl shadow-sm border border-slate-200 p-6">
                <div className="flex items-center justify-between" onClick={() => setShowConfig(!showConfig)}>
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
                    sky: 'bg-sky-100 text-sky-700 border-sky-200',
                    cyan: 'bg-cyan-100 text-cyan-700 border-cyan-200',
                    blue: 'bg-blue-100 text-blue-700 border-blue-200',
                    indigo: 'bg-indigo-100 text-indigo-700 border-indigo-200',
                  }
                  const colorSet = colors[info.color]
                  return (
                    <div key={stage} className={`${colorSet} border p-4 rounded-xl text-center relative`}>
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
                  <div className="w-12 h-12 bg-sky-100 rounded-xl flex items-center justify-center">
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
                      <div className="p-4 bg-sky-50 rounded-xl border border-sky-100">
                        <div className="text-sm text-sky-600 font-medium mb-1">Chunks</div>
                        <p className="text-3xl font-bold text-sky-700">{pipelineStatus.text_index.chunks || 0}</p>
                      </div>
                      <div className="p-4 bg-blue-50 rounded-xl border border-blue-100">
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
                  <div className="w-12 h-12 bg-indigo-100 rounded-xl flex items-center justify-center">
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
                      <div className="p-4 bg-indigo-50 rounded-xl border border-indigo-100">
                        <div className="text-sm text-indigo-600 font-medium mb-1">Pages</div>
                        <p className="text-3xl font-bold text-indigo-700">{pipelineStatus.image_index.pages || 0}</p>
                      </div>
                      <div className="p-4 bg-purple-50 rounded-xl border border-purple-100">
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
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => handleRebuildSpecificIndex('text')}
                    disabled={loading}
                    className="px-4 py-2.5 bg-sky-500 text-white rounded-lg font-medium hover:shadow-lg hover:shadow-sky-200/50 disabled:opacity-50 flex items-center space-x-2 transition-all duration-200 hover:scale-105 active:scale-95"
                    title="Rebuild text index only"
                  >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                    <span>Rebuild Text</span>
                  </button>
                  <button
                    onClick={() => handleRebuildSpecificIndex('image')}
                    disabled={loading}
                    className="px-4 py-2.5 bg-indigo-500 text-white rounded-lg font-medium hover:shadow-lg hover:shadow-indigo-200/50 disabled:opacity-50 flex items-center space-x-2 transition-all duration-200 hover:scale-105 active:scale-95"
                    title="Rebuild image index only"
                  >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                    <span>Rebuild Image</span>
                  </button>
                  <button
                    onClick={handleIndex}
                    disabled={loading}
                    className="px-4 py-2.5 bg-slate-600 text-white rounded-lg font-medium hover:shadow-lg hover:shadow-slate-200/50 disabled:opacity-50 flex items-center space-x-2 transition-all duration-200 hover:scale-105 active:scale-95"
                    title="Rebuild all indexes"
                  >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                    <span>Rebuild All</span>
                  </button>
                </div>
              </div>

              {files.indexed?.length > 0 ? (
                <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
                  {files.indexed.map((file, idx) => (
                    <div 
                      key={idx} 
                      className={`p-4 rounded-xl border transition-all duration-200 hover:shadow-md ${
                        file.type === 'image' 
                          ? 'bg-indigo-50 border-indigo-100 hover:border-indigo-200' 
                          : 'bg-sky-50 border-sky-100 hover:border-sky-200'
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
            {/* Modern Search Box */}
            <div className="glass-strong rounded-3xl card-shadow p-10">
              <div className="flex items-center space-x-3 mb-8">
                <div className="w-12 h-12 bg-sky-500 rounded-2xl flex items-center justify-center shadow-lg shadow-sky-200/50">
                  <Search className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-slate-800">Query Knowledge Base</h2>
                  <p className="text-sm text-slate-500 mt-0.5">Search across your indexed documents</p>
                </div>
              </div>
              <div className="flex gap-4">
                <div className="flex-1 relative">
                  <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                    placeholder="Ask a question about your documents..."
                    className="w-full px-6 py-4 bg-white border-2 border-slate-200 rounded-2xl focus:outline-none focus:ring-4 focus:ring-sky-200/50 focus:border-sky-400 text-slate-700 placeholder-slate-400 font-medium transition-all duration-200 shadow-sm"
                  />
                  <div className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-300">
                    <Search className="w-5 h-5" />
                  </div>
                </div>
                <button
                  onClick={handleSearch}
                  disabled={searchLoading || !query.trim()}
                  className="px-10 py-4 bg-sky-500 text-white rounded-2xl font-bold hover:shadow-xl hover:shadow-sky-200/50 disabled:opacity-50 flex items-center space-x-2.5 transition-all duration-300 hover:scale-105 active:scale-95 disabled:hover:scale-100"
                >
                  {searchLoading ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      <span>Searching...</span>
                    </>
                  ) : (
                    <>
                      <Search className="w-5 h-5" />
                      <span>Search</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Results */}
            {results && (
              <div className="space-y-6">
                {/* Generated Answer */}
                {results.answer && (
                  <div className="bg-sky-50 rounded-2xl shadow-sm border border-sky-100 p-8">
                    <h3 className="text-lg font-semibold mb-4 flex items-center space-x-3 text-slate-800">
                      <div className="w-8 h-8 bg-sky-500 rounded-lg flex items-center justify-center">
                        <MessageSquare className="w-4 h-4 text-white" />
                      </div>
                      <span>Answer</span>
                    </h3>
                    <div className="prose prose-sky max-w-none text-slate-700">
                      <ReactMarkdown
                        remarkPlugins={[remarkMath, remarkGfm]}
                        rehypePlugins={[rehypeKatex]}
                        components={{
                          p: ({node, ...props}) => <p className="mb-4 leading-relaxed text-slate-700" {...props} />,
                          h1: ({node, ...props}) => <h1 className="text-3xl font-bold mb-4 mt-6 text-slate-900 first:mt-0" {...props} />,
                          h2: ({node, ...props}) => <h2 className="text-2xl font-bold mb-3 mt-5 text-slate-900" {...props} />,
                          h3: ({node, ...props}) => <h3 className="text-xl font-semibold mb-2 mt-4 text-slate-900" {...props} />,
                          ul: ({node, ...props}) => <ul className="list-disc pl-6 mb-4 space-y-2" {...props} />,
                          ol: ({node, ...props}) => <ol className="list-decimal pl-6 mb-4 space-y-2" {...props} />,
                          li: ({node, ...props}) => <li className="leading-relaxed" {...props} />,
                          code: ({node, inline, className, children, ...props}) => {
                            const match = /language-(\w+)/.exec(className || '')
                            const isMath = className?.includes('math') || className?.includes('katex')
                            
                            if (inline) {
                              return (
                                <code className="bg-slate-100 px-1.5 py-0.5 rounded text-sm font-mono text-slate-800" {...props}>
                                  {children}
                                </code>
                              )
                            }
                            return (
                              <code className="block bg-slate-900 text-slate-100 p-4 rounded-lg overflow-x-auto text-sm font-mono mb-4" {...props}>
                                {children}
                              </code>
                            )
                          },
                          pre: ({node, ...props}) => <pre className="bg-slate-900 text-slate-100 p-4 rounded-lg overflow-x-auto mb-4" {...props} />,
                          blockquote: ({node, ...props}) => <blockquote className="border-l-4 border-sky-300 pl-4 italic text-slate-600 my-4" {...props} />,
                          a: ({node, href, children, ...props}) => {
                            // Handle citation links - replace markdown hyperref with just citation reference
                            if (href && (href.startsWith('#chunk-') || href.startsWith('#image-'))) {
                              // Extract citation reference from children
                              let citationRef = children
                              if (typeof children === 'string') {
                                citationRef = children.match(/\[[\d.]+\]/)?.[0] || children
                              } else if (Array.isArray(children)) {
                                const text = children.map(c => typeof c === 'string' ? c : '').join('')
                                citationRef = text.match(/\[[\d.]+\]/)?.[0] || text || children
                              }
                              
                              return (
                                <a 
                                  href={href}
                                  onClick={(e) => {
                                    e.preventDefault()
                                    e.stopPropagation()
                                    console.log('Citation clicked:', href)
                                    handleCitationClick(e, href)
                                  }}
                                  className="text-sky-600 hover:text-sky-700 underline font-semibold cursor-pointer inline-block hover:bg-sky-50 px-1 rounded"
                                  style={{ textDecoration: 'underline' }}
                                  {...props}
                                >
                                  {citationRef}
                                </a>
                              )
                            }
                            return <a className="text-sky-600 hover:text-sky-700 underline" href={href} {...props}>{children}</a>
                          },
                          strong: ({node, ...props}) => <strong className="font-bold text-slate-900" {...props} />,
                          em: ({node, ...props}) => <em className="italic" {...props} />,
                          table: ({node, ...props}) => <table className="min-w-full border-collapse border border-slate-300 my-4" {...props} />,
                          thead: ({node, ...props}) => <thead className="bg-slate-100" {...props} />,
                          tbody: ({node, ...props}) => <tbody {...props} />,
                          tr: ({node, ...props}) => <tr className="border-b border-slate-200" {...props} />,
                          th: ({node, ...props}) => <th className="border border-slate-300 px-4 py-2 text-left font-semibold text-slate-900" {...props} />,
                          td: ({node, ...props}) => <td className="border border-slate-300 px-4 py-2 text-slate-700" {...props} />,
                        }}
                      >
                        {results.answer}
                      </ReactMarkdown>
                    </div>
                  </div>
                )}

                {/* Citations Section */}
                {results.contents && Object.keys(results.contents).length > 0 && (
                  <div id="citations-section" className="bg-white rounded-2xl shadow-sm border border-sky-100 p-8">
                    <h3 className="text-lg font-semibold mb-6 flex items-center space-x-3 text-slate-800">
                      <Hash className="w-5 h-5 text-sky-500" />
                      <span>Citations</span>
                    </h3>
                    
                    {/* Text Citations */}
                    {Object.entries(results.contents)
                      .filter(([key, value]) => value.type === 'text')
                      .length > 0 && (
                      <div className="mb-8">
                        <h4 className="text-md font-semibold mb-4 text-slate-700 flex items-center space-x-2">
                          <FileText className="w-4 h-4 text-sky-500" />
                          <span>Text Chunks</span>
                        </h4>
                        <div className="space-y-3">
                          {Object.entries(results.contents)
                            .filter(([key, value]) => value.type === 'text')
                            .map(([citationKey, citation]) => (
                              <div
                                key={citationKey}
                                id={citation.id}
                                className="border border-sky-100 rounded-xl overflow-hidden hover:shadow-md transition-all duration-200 bg-white"
                              >
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    toggleCitationExpand(citationKey)
                                  }}
                                  className="w-full p-4 flex items-center justify-between bg-sky-50 hover:bg-sky-100 transition-colors"
                                >
                                  <div className="flex items-center space-x-3 flex-1 text-left">
                                    <span className="px-3 py-1 bg-sky-500 text-white rounded-lg font-semibold text-sm flex-shrink-0">
                                      {citationKey}
                                    </span>
                                    <div className="flex-1 min-w-0">
                                      <p className="font-medium text-slate-800 text-sm truncate">{citation.filename}</p>
                                      <p className="text-xs text-slate-500 mt-1">Score: {citation.score?.toFixed(4) || 'N/A'}</p>
                                    </div>
                                  </div>
                                  {expandedCitations[citationKey] ? (
                                    <ChevronUp className="w-5 h-5 text-slate-400 flex-shrink-0" />
                                  ) : (
                                    <ChevronDown className="w-5 h-5 text-slate-400 flex-shrink-0" />
                                  )}
                                </button>
                                
                                {expandedCitations[citationKey] && (
                                  <div className="p-4 bg-white border-t border-sky-100">
                                    {/* Content Preview/Full */}
                                    <div className="mb-4">
                                      {(() => {
                                        const fullText = citation.full_text || citation.text || ''
                                        const previewText = citation.text || ''
                                        // Check if full_text exists and is different from preview text, or if content is longer than 200 chars
                                        const hasMoreContent = (citation.full_text && citation.full_text.length > previewText.length) || 
                                                               (fullText.length > 200 && previewText.length <= 200) ||
                                                               (previewText.includes('...') && citation.full_text)
                                        
                                        console.log(`Citation ${citationKey}: fullText length=${fullText.length}, previewText length=${previewText.length}, hasMoreContent=${hasMoreContent}`)
                                        
                                        if (expandedCitationContent[citationKey] || !hasMoreContent) {
                                          return (
                                            <p className="text-slate-700 text-sm whitespace-pre-wrap leading-relaxed">
                                              {fullText}
                                            </p>
                                          )
                                        } else {
                                          return (
                                            <div>
                                              <p className="text-slate-700 text-sm whitespace-pre-wrap leading-relaxed">
                                                {previewText}
                                              </p>
                                              <button
                                                onClick={(e) => {
                                                  e.stopPropagation()
                                                  setExpandedCitationContent(prev => ({ ...prev, [citationKey]: true }))
                                                }}
                                                className="mt-3 text-sky-600 hover:text-sky-700 text-sm font-semibold flex items-center space-x-2 px-3 py-1.5 rounded-lg hover:bg-sky-50 transition-colors border border-sky-200 bg-white"
                                              >
                                                <span>View More Content</span>
                                                <ChevronDown className="w-4 h-4" />
                                              </button>
                                            </div>
                                          )
                                        }
                                      })()}
                                    </div>
                                    
                                    {/* Metadata Toggle Button - ALWAYS VISIBLE */}
                                    <div className="border-t border-slate-200 pt-3 mt-3">
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation()
                                          toggleCitationMetadata(citationKey)
                                        }}
                                        className="w-full flex items-center justify-between text-sm text-slate-600 hover:text-slate-800 py-2.5 px-3 rounded-lg hover:bg-slate-50 transition-colors border border-slate-200 hover:border-sky-300 bg-white"
                                      >
                                        <span className="font-semibold flex items-center space-x-2">
                                          <Hash className="w-4 h-4 text-sky-500" />
                                          <span>View Metadata</span>
                                        </span>
                                        {expandedCitationMetadata[citationKey] ? (
                                          <ChevronUp className="w-4 h-4 text-slate-500" />
                                        ) : (
                                          <ChevronDown className="w-4 h-4 text-slate-500" />
                                        )}
                                      </button>
                                      
                                      {expandedCitationMetadata[citationKey] && (
                                        <div className="mt-3 pt-3 border-t border-slate-100 text-xs text-slate-600 space-y-2 bg-slate-50 rounded-lg p-3">
                                          <div className="flex justify-between items-start">
                                            <span className="font-semibold text-slate-700">Filename:</span>
                                            <span className="text-right ml-4 break-words max-w-[60%]">{citation.filename}</span>
                                          </div>
                                          <div className="flex justify-between items-start">
                                            <span className="font-semibold text-slate-700">Hybrid Score:</span>
                                            <span className="text-right ml-4">{citation.score?.toFixed(4) || 'N/A'}</span>
                                          </div>
                                          {citation.retrieval_info && (
                                            <>
                                              <div className="border-t border-slate-200 pt-2 mt-2">
                                                <div className="font-semibold text-slate-700 mb-1">Raw Scores:</div>
                                                {citation.retrieval_info.bm25_score !== null && citation.retrieval_info.bm25_score !== undefined && (
                                                  <div className="flex justify-between items-start mt-1">
                                                    <span className="text-slate-600">BM25 (raw):</span>
                                                    <span className="text-right ml-4 font-mono">{citation.retrieval_info.bm25_score?.toFixed(4) || 'N/A'}</span>
                                                  </div>
                                                )}
                                                {citation.retrieval_info.bm25_score_normalized !== null && citation.retrieval_info.bm25_score_normalized !== undefined && (
                                                  <div className="flex justify-between items-start mt-1">
                                                    <span className="text-slate-600">BM25 (normalized):</span>
                                                    <span className="text-right ml-4 font-mono">{citation.retrieval_info.bm25_score_normalized?.toFixed(4) || 'N/A'}</span>
                                                  </div>
                                                )}
                                                {citation.retrieval_info.dense_score !== null && citation.retrieval_info.dense_score !== undefined && (
                                                  <div className="flex justify-between items-start mt-1">
                                                    <span className="text-slate-600">Dense (raw):</span>
                                                    <span className="text-right ml-4 font-mono">{citation.retrieval_info.dense_score?.toFixed(4) || 'N/A'}</span>
                                                  </div>
                                                )}
                                                {citation.retrieval_info.bm25_rank && (
                                                  <div className="flex justify-between items-start mt-1">
                                                    <span className="text-slate-600">BM25 Rank:</span>
                                                    <span className="text-right ml-4">#{citation.retrieval_info.bm25_rank}</span>
                                                  </div>
                                                )}
                                                {citation.retrieval_info.dense_rank && (
                                                  <div className="flex justify-between items-start mt-1">
                                                    <span className="text-slate-600">Dense Rank:</span>
                                                    <span className="text-right ml-4">#{citation.retrieval_info.dense_rank}</span>
                                                  </div>
                                                )}
                                              </div>
                                            </>
                                          )}
                                          <div className="flex justify-between items-start">
                                            <span className="font-semibold text-slate-700">Citation ID:</span>
                                            <span className="font-mono text-right ml-4">{citation.id}</span>
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                )}
                              </div>
                            ))}
                        </div>
                      </div>
                    )}

                    {/* Image Citations */}
                    {Object.entries(results.contents)
                      .filter(([key, value]) => value.type === 'image')
                      .length > 0 && (
                      <div>
                        <h4 className="text-md font-semibold mb-4 text-slate-700 flex items-center space-x-2">
                          <Image className="w-4 h-4 text-indigo-500" />
                          <span>Images</span>
                        </h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                          {Object.entries(results.contents)
                            .filter(([key, value]) => value.type === 'image')
                            .map(([citationKey, citation]) => (
                              <div
                                key={citationKey}
                                id={citation.id}
                                className="border border-indigo-100 rounded-xl overflow-hidden hover:shadow-lg transition-all duration-200 bg-white"
                              >
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    toggleCitationExpand(citationKey)
                                  }}
                                  className="w-full"
                                >
                                  <div className="aspect-[4/3] bg-indigo-50 relative overflow-hidden">
                                    <img
                                      src={`${API_BASE}/pdf-page-image?pdf_name=${encodeURIComponent(citation.source)}&page=${citation.page}`}
                                      alt={`Page ${citation.page} of ${citation.source}`}
                                      className="w-full h-full object-cover"
                                      onError={(e) => {
                                        e.target.style.display = 'none'
                                        if (e.target.nextSibling) {
                                          e.target.nextSibling.style.display = 'flex'
                                        }
                                      }}
                                    />
                                    <div className="hidden items-center justify-center w-full h-full absolute inset-0">
                                      <div className="text-center">
                                        <Image className="w-10 h-10 text-indigo-300 mb-2 mx-auto" />
                                        <p className="text-sm text-indigo-400 font-medium">Page {citation.page}</p>
                                      </div>
                                    </div>
                                    <div className="absolute top-2 right-2 px-2 py-1 bg-indigo-500 text-white rounded text-xs font-semibold">
                                      {citationKey}
                                    </div>
                                  </div>
                                </button>
                                
                                {expandedCitations[citationKey] && (
                                  <div className="p-4 bg-white border-t border-indigo-100">
                                    <div className="mb-3">
                                      <p className="text-sm font-medium text-slate-800 mb-1">{citation.source}</p>
                                      <p className="text-xs text-slate-500">Page {citation.page}</p>
                                    </div>
                                    
                                    {/* Metadata Toggle Button */}
                                    <div className="border-t border-slate-200 pt-3 mt-3">
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation()
                                          toggleCitationMetadata(citationKey)
                                        }}
                                        className="w-full flex items-center justify-between text-sm text-slate-600 hover:text-slate-800 py-2.5 px-3 rounded-lg hover:bg-slate-50 transition-colors border border-slate-200 hover:border-indigo-300"
                                      >
                                        <span className="font-semibold flex items-center space-x-2">
                                          <Hash className="w-4 h-4 text-indigo-500" />
                                          <span>View Metadata</span>
                                        </span>
                                        {expandedCitationMetadata[citationKey] ? (
                                          <ChevronUp className="w-4 h-4 text-slate-500" />
                                        ) : (
                                          <ChevronDown className="w-4 h-4 text-slate-500" />
                                        )}
                                      </button>
                                      
                                      {expandedCitationMetadata[citationKey] && (
                                        <div className="mt-3 pt-3 border-t border-slate-100 text-xs text-slate-600 space-y-2 bg-slate-50 rounded-lg p-3">
                                          <div className="flex justify-between items-start">
                                            <span className="font-semibold text-slate-700">Source:</span>
                                            <span className="text-right ml-4 truncate max-w-[60%]">{citation.source}</span>
                                          </div>
                                          <div className="flex justify-between items-start">
                                            <span className="font-semibold text-slate-700">Page:</span>
                                            <span className="text-right ml-4">{citation.page}</span>
                                          </div>
                                          <div className="flex justify-between items-start">
                                            <span className="font-semibold text-slate-700">Score:</span>
                                            <span className="text-right ml-4">{citation.score?.toFixed(4) || 'N/A'}</span>
                                          </div>
                                          <div className="flex justify-between items-start">
                                            <span className="font-semibold text-slate-700">Citation ID:</span>
                                            <span className="font-mono text-right ml-4">{citation.id}</span>
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                )}
                              </div>
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

    </div>
  )
}

export default App
