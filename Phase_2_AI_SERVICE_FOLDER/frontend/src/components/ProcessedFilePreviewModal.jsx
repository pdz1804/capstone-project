import { useEffect, useRef, useState } from 'react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Download, Eye, FileText, Loader2, X } from 'lucide-react'

function getExtension(file) {
  const t = (file?.type || '').replace(/^\./, '').toLowerCase()
  if (t) return t
  const n = file?.name || ''
  const i = n.lastIndexOf('.')
  return i >= 0 ? n.slice(i + 1).toLowerCase() : ''
}

function isProbablyTextExt(ext) {
  return [
    'md',
    'txt',
    'csv',
    'log',
    'xml',
    'yaml',
    'yml',
    'html',
    'htm',
    'css',
    'py',
    'ts',
    'tsx',
    'jsx',
    'js',
    'java',
    'c',
    'h',
    'cpp',
    'go',
    'rs',
    'sh',
    'env',
    'ini',
    'toml',
    'sql',
  ].includes(ext)
}

function isImageExt(ext) {
  return ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'ico'].includes(ext)
}

function isVideoExt(ext) {
  return ['mp4', 'webm', 'ogv'].includes(ext)
}

/**
 * Modal: fetch GET /api/processed-file?rel_path=… and render by type (markdown, JSON, text, PDF, image, video).
 */
export default function ProcessedFilePreviewModal({ file, apiBase, onClose }) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [textContent, setTextContent] = useState(null)
  const [jsonFormatted, setJsonFormatted] = useState(null)
  const [blobUrl, setBlobUrl] = useState(null)
  const [kind, setKind] = useState(null)
  const objectUrlRef = useRef(null)

  useEffect(() => {
    if (!file?.relative_path) return undefined

    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current)
      objectUrlRef.current = null
    }

    let cancelled = false
    const ext = getExtension(file)

    const run = async () => {
      setLoading(true)
      setError(null)
      setTextContent(null)
      setJsonFormatted(null)
      setBlobUrl(null)
      setKind(null)

      try {
        const tryTextFirst = ext === 'json' || isProbablyTextExt(ext)

        if (tryTextFirst) {
          const r = await axios.get(`${apiBase}/processed-file`, {
            params: { rel_path: file.relative_path },
            responseType: 'text',
            transformResponse: [(d) => d],
          })
          if (cancelled) return
          const raw = r.data
          if (ext === 'json') {
            try {
              setJsonFormatted(JSON.stringify(JSON.parse(raw), null, 2))
              setKind('json')
            } catch {
              setTextContent(raw)
              setKind('text')
            }
          } else if (ext === 'md') {
            setTextContent(raw)
            setKind('md')
          } else {
            setTextContent(raw)
            setKind('text')
          }
          return
        }

        const r = await axios.get(`${apiBase}/processed-file`, {
          params: { rel_path: file.relative_path },
          responseType: 'blob',
        })
        if (cancelled) return

        const blob = r.data
        const ct = (r.headers['content-type'] || '').split(';')[0].trim().toLowerCase()

        if (ct.startsWith('text/') || ct === 'application/json' || ct === 'application/xml') {
          const t = await blob.text()
          if (ct === 'application/json' || ext === 'json') {
            try {
              setJsonFormatted(JSON.stringify(JSON.parse(t), null, 2))
              setKind('json')
            } catch {
              setTextContent(t)
              setKind('text')
            }
          } else if (ext === 'md' || ct.includes('markdown')) {
            setTextContent(t)
            setKind('md')
          } else {
            setTextContent(t)
            setKind('text')
          }
          return
        }

        if (ct === 'application/pdf' || ext === 'pdf') {
          const u = URL.createObjectURL(new Blob([blob], { type: 'application/pdf' }))
          objectUrlRef.current = u
          setBlobUrl(u)
          setKind('pdf')
          return
        }

        if (ct.startsWith('image/') || isImageExt(ext)) {
          const u = URL.createObjectURL(blob)
          objectUrlRef.current = u
          setBlobUrl(u)
          setKind('image')
          return
        }

        if (ct.startsWith('video/') || isVideoExt(ext)) {
          const u = URL.createObjectURL(blob)
          objectUrlRef.current = u
          setBlobUrl(u)
          setKind('video')
          return
        }

        const u = URL.createObjectURL(blob)
        objectUrlRef.current = u
        setBlobUrl(u)
        setKind('binary')
      } catch (e) {
        if (!cancelled) {
          const d = e.response?.data
          let msg = e.message || 'Failed to load file'
          if (typeof d === 'string') msg = d
          else if (d?.detail) {
            const det = d.detail
            msg = Array.isArray(det) ? det.map((x) => x.msg || JSON.stringify(x)).join('; ') : String(det)
          }
          setError(msg)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    run()
    return () => {
      cancelled = true
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current)
        objectUrlRef.current = null
      }
    }
  }, [file, apiBase])

  if (!file) return null

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="bg-white rounded-2xl shadow-2xl max-w-5xl w-full max-h-[92vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-labelledby="processed-preview-title"
      >
        <div className="flex items-start justify-between gap-3 p-4 border-b border-slate-100 shrink-0">
          <div className="min-w-0 flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-sky-100 flex items-center justify-center shrink-0">
              <Eye className="w-5 h-5 text-sky-600" />
            </div>
            <div className="min-w-0">
              <h2 id="processed-preview-title" className="font-semibold text-slate-900 truncate">
                {file.name}
              </h2>
              <p className="text-xs text-slate-500 font-mono break-all mt-0.5">{file.relative_path}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {blobUrl && kind === 'binary' ? (
              <a
                href={blobUrl}
                download={file.name}
                className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-medium bg-slate-100 text-slate-700 hover:bg-slate-200"
              >
                <Download className="w-4 h-4" />
                Download
              </a>
            ) : null}
            <button
              type="button"
              onClick={onClose}
              className="p-2 rounded-xl hover:bg-slate-100 text-slate-500 transition-colors"
              aria-label="Close preview"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-auto p-4 min-h-[200px]">
          {loading && (
            <div className="flex flex-col items-center justify-center py-20 text-slate-500 gap-3">
              <Loader2 className="w-10 h-10 animate-spin text-sky-500" />
              <p className="text-sm font-medium">Loading preview…</p>
            </div>
          )}

          {!loading && error && (
            <div className="rounded-xl border border-red-200 bg-red-50 text-red-800 text-sm p-4">{error}</div>
          )}

          {!loading && !error && kind === 'json' && jsonFormatted !== null && (
            <pre className="text-xs font-mono text-slate-800 bg-slate-50 rounded-xl p-4 overflow-auto whitespace-pre-wrap break-words border border-slate-100">
              {jsonFormatted}
            </pre>
          )}

          {!loading && !error && kind === 'md' && textContent !== null && (
            <div className="prose prose-slate prose-sm max-w-none border border-slate-100 rounded-xl p-4 bg-white">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{textContent}</ReactMarkdown>
            </div>
          )}

          {!loading && !error && kind === 'text' && textContent !== null && (
            <pre className="text-xs font-mono text-slate-800 bg-slate-50 rounded-xl p-4 overflow-auto whitespace-pre-wrap break-words border border-slate-100 max-h-[min(70vh,720px)]">
              {textContent}
            </pre>
          )}

          {!loading && !error && kind === 'pdf' && blobUrl && (
            <iframe title={file.name} src={blobUrl} className="w-full min-h-[75vh] rounded-xl border border-slate-200 bg-slate-50" />
          )}

          {!loading && !error && kind === 'image' && blobUrl && (
            <div className="flex justify-center items-start bg-slate-50 rounded-xl border border-slate-200 p-4">
              <img src={blobUrl} alt={file.name} className="max-w-full max-h-[min(80vh,900px)] object-contain rounded-lg" />
            </div>
          )}

          {!loading && !error && kind === 'video' && blobUrl && (
            <video src={blobUrl} controls className="w-full max-h-[80vh] rounded-xl border border-slate-200 bg-black" playsInline />
          )}

          {!loading && !error && kind === 'binary' && blobUrl && (
            <div className="flex flex-col items-center justify-center py-16 text-center text-slate-600 gap-4">
              <FileText className="w-16 h-16 text-slate-300" />
              <p className="text-sm max-w-md">
                Preview is not available for this file type in the browser. Use <strong>Download</strong> to open it locally.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
