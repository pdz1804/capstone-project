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
  File
} from 'lucide-react';
import { Document, Page, pdfjs } from 'react-pdf';
import { FileItem } from '../App';

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface LibraryViewProps {
  files: FileItem[];
  setFiles: React.Dispatch<React.SetStateAction<FileItem[]>>;
}

export default function LibraryView({ files, setFiles }: LibraryViewProps) {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const formatBytes = (bytes: number) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  // Enhanced Management State
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState('all');
  const [sortBy, setSortBy] = useState<'date' | 'name' | 'size'>('date');
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc');
  const [selectedFiles, setSelectedFiles] = useState<number[]>([]);
  const [activeDropdown, setActiveDropdown] = useState<number | null>(null);
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');
  const [renamingFileId, setRenamingFileId] = useState<number | null>(null);
  const [newName, setNewName] = useState('');
  const [previewFile, setPreviewFile] = useState<any | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [numPages, setNumPages] = useState<number>();
  const [textContent, setTextContent] = useState<string | null>(null);

  useEffect(() => {
    if (previewFile && previewFile.originalFile) {
      const url = URL.createObjectURL(previewFile.originalFile);
      setPreviewUrl(url);
      
      if (previewFile.originalFile.type === 'text/plain') {
        fetch(url).then(res => res.text()).then(setTextContent);
      } else {
        setTextContent(null);
      }

      return () => URL.revokeObjectURL(url);
    }
    setPreviewUrl(null);
    setTextContent(null);
  }, [previewFile]);

  function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages);
  }

  const handleDownload = (file: any) => {
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
      alert(`Downloading mock file: ${file.name}`);
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

  const simulateUploadAndProcessing = (id: number, totalBytes: number) => {
    let uploadedBytes = 0;
    // Speed between 1MB/s and 5MB/s for realistic simulation
    const speedBps = (Math.random() * 4 + 1) * 1024 * 1024; 
    
    const uploadInterval = setInterval(() => {
      uploadedBytes += speedBps * 0.8; // 800ms interval
      
      if (uploadedBytes >= totalBytes) {
        clearInterval(uploadInterval);
        
        setFiles(prev => prev.map(f => f.id === id ? { 
          ...f, 
          status: 'processing' as const, 
          progress: 0,
          uploadedBytes: totalBytes,
          timeRemaining: 0
        } : f));
        
        // Start processing simulation
        let processProgress = 0;
        const processInterval = setInterval(() => {
          processProgress += Math.floor(Math.random() * 20) + 10;
          if (processProgress >= 100) {
            clearInterval(processInterval);
            setFiles(prev => prev.map(f => f.id === id ? { ...f, status: 'indexed' as const, progress: undefined } : f));
          } else {
            setFiles(prev => prev.map(f => f.id === id ? { ...f, progress: processProgress } : f));
          }
        }, 800);
        
      } else {
        const progress = Math.floor((uploadedBytes / totalBytes) * 100);
        const timeRemaining = Math.ceil((totalBytes - uploadedBytes) / speedBps);
        
        setFiles(prev => prev.map(f => f.id === id ? { 
          ...f, 
          progress,
          uploadedBytes,
          timeRemaining
        } : f));
      }
    }, 800);
  };

  const processNewFiles = (fileList: FileList | File[]) => {
    const newFiles: FileItem[] = Array.from(fileList).map((file, index) => {
      let type: 'video' | 'document' | 'image' | 'spreadsheet' | 'audio' | 'pdf' = 'document';
      if (file.type.startsWith('video/')) type = 'video';
      else if (file.type.startsWith('image/')) type = 'image';
      else if (file.type.startsWith('audio/')) type = 'audio';
      else if (file.type === 'application/pdf' || file.name.endsWith('.pdf')) type = 'pdf';
      else if (file.name.endsWith('.xlsx') || file.name.endsWith('.csv')) type = 'spreadsheet';

      return {
        id: Date.now() + index,
        name: file.name,
        type,
        size: formatBytes(file.size),
        rawSize: file.size,
        status: 'uploading' as const,
        date: new Date().toISOString().split('T')[0],
        progress: 0,
        uploadedBytes: 0,
        timeRemaining: 0,
        originalFile: file
      };
    });

    setFiles(prev => [...newFiles, ...prev]);

    newFiles.forEach(file => {
      simulateUploadAndProcessing(file.id, file.rawSize);
    });
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files.length > 0) {
      processNewFiles(event.target.files);
      if (fileInputRef.current) fileInputRef.current.value = '';
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

  const handleDelete = (id: number) => {
    setFiles(files.filter(f => f.id !== id));
    setSelectedFiles(selectedFiles.filter(selectedId => selectedId !== id));
    setActiveDropdown(null);
  };

  const handleBulkDelete = () => {
    setFiles(files.filter(f => !selectedFiles.includes(f.id)));
    setSelectedFiles([]);
  };

  const toggleSelection = (id: number) => {
    setSelectedFiles(prev => prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]);
  };

  const handleSort = (column: 'date' | 'name' | 'size') => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortOrder(column === 'name' ? 'asc' : 'desc');
    }
  };

  // Derived State
  const filteredAndSortedFiles = files
    .filter(f => filterType === 'all' || f.type === filterType)
    .filter(f => f.name.toLowerCase().includes(searchTerm.toLowerCase()))
    .sort((a, b) => {
      let comparison = 0;
      if (sortBy === 'name') comparison = a.name.localeCompare(b.name);
      if (sortBy === 'date') comparison = new Date(a.date).getTime() - new Date(b.date).getTime();
      if (sortBy === 'size') {
        const sizeA = parseFloat(a.size);
        const sizeB = parseFloat(b.size);
        comparison = sizeA - sizeB;
      }
      return sortOrder === 'asc' ? comparison : -comparison;
    });

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

  return (
    <div className="max-w-6xl mx-auto space-y-8 pb-12">
      {/* Upload Section */}
      <div 
        className={`border-2 border-dashed rounded-2xl p-12 text-center transition-colors ${
          isDragging ? 'border-indigo-500 bg-indigo-50' : 'border-slate-300 bg-white hover:border-indigo-400 hover:bg-slate-50'
        }`}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <div className="w-16 h-16 bg-indigo-100 text-indigo-600 rounded-full flex items-center justify-center mx-auto mb-4">
          <UploadCloud className="w-8 h-8" />
        </div>
        <h3 className="text-xl font-semibold text-slate-900 mb-2">Upload Educational Content</h3>
        <p className="text-slate-500 max-w-md mx-auto mb-6">
          Drag and drop your video lectures, PDFs, presentations, or spreadsheets here. 
          BK-MInD will automatically process, transcribe, and index them for RAG.
        </p>
        <div className="flex items-center justify-center gap-4">
          <input 
            type="file" 
            multiple 
            className="hidden" 
            ref={fileInputRef} 
            onChange={handleFileUpload} 
          />
          <button 
            onClick={() => fileInputRef.current?.click()}
            className="px-6 py-2.5 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors"
          >
            Browse Files
          </button>
        </div>
        <div className="mt-8 flex items-center justify-center gap-6 text-xs text-slate-400 flex-wrap">
          <span className="flex items-center gap-1.5"><Video className="w-4 h-4" /> MP4, AVI, MOV</span>
          <span className="flex items-center gap-1.5"><FileText className="w-4 h-4" /> PDF, DOCX, PPTX</span>
          <span className="flex items-center gap-1.5"><FileText className="w-4 h-4" /> XLSX, CSV</span>
          <span className="flex items-center gap-1.5"><ImageIcon className="w-4 h-4" /> PNG, JPG</span>
          <span className="flex items-center gap-1.5"><Music className="w-4 h-4" /> MP3, WAV, AAC</span>
        </div>
      </div>

      {/* File List Section */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center gap-4">
            <h3 className="text-lg font-semibold text-slate-900">Content Library</h3>
            {selectedFiles.length > 0 && (
              <div className="flex items-center gap-3 px-3 py-1.5 bg-indigo-50 border border-indigo-100 rounded-lg">
                <span className="text-sm font-medium text-indigo-700">{selectedFiles.length} selected</span>
                <div className="w-px h-4 bg-indigo-200"></div>
                <button 
                  onClick={handleBulkDelete}
                  className="text-sm font-medium text-red-600 hover:text-red-700 flex items-center gap-1"
                >
                  <Trash2 className="w-4 h-4" /> Delete
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
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9 pr-4 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 w-64"
              />
            </div>
            <div className="flex bg-slate-100 p-1 rounded-lg">
              <button
                onClick={() => setViewMode('list')}
                className={`p-1.5 rounded-md transition-colors ${viewMode === 'list' ? 'bg-white shadow-sm text-indigo-600' : 'text-slate-500 hover:text-slate-700'}`}
                title="List View"
              >
                <List className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode('grid')}
                className={`p-1.5 rounded-md transition-colors ${viewMode === 'grid' ? 'bg-white shadow-sm text-indigo-600' : 'text-slate-500 hover:text-slate-700'}`}
                title="Grid View"
              >
                <LayoutGrid className="w-4 h-4" />
              </button>
            </div>
            <div className="relative">
              <button 
                onClick={(e) => { e.stopPropagation(); setIsFilterOpen(!isFilterOpen); setActiveDropdown(null); }}
                className={`p-2 border rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${
                  filterType !== 'all' ? 'bg-indigo-50 border-indigo-200 text-indigo-700' : 'border-slate-300 text-slate-600 hover:bg-slate-50'
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
                      onClick={() => { setFilterType(type); setIsFilterOpen(false); }}
                      className={`w-full text-left px-4 py-2 text-sm hover:bg-slate-50 ${filterType === type ? 'text-indigo-600 font-medium bg-indigo-50/50' : 'text-slate-700'}`}
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
            <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-200">
              <tr>
                <th className="px-6 py-4 w-12">
                  <input 
                    type="checkbox" 
                    checked={selectedFiles.length === filteredAndSortedFiles.length && filteredAndSortedFiles.length > 0}
                    onChange={toggleAll}
                    className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
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
              {filteredAndSortedFiles.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-slate-500">
                    No files found matching your criteria.
                  </td>
                </tr>
              ) : (
                filteredAndSortedFiles.map((file) => (
                  <tr key={file.id} className={`hover:bg-slate-50/50 transition-colors group ${selectedFiles.includes(file.id) ? 'bg-indigo-50/30' : ''}`}>
                    <td className="px-6 py-4">
                      <input 
                        type="checkbox" 
                        checked={selectedFiles.includes(file.id)}
                        onChange={() => toggleSelection(file.id)}
                        className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                      />
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-lg ${
                          file.type === 'video' ? 'bg-indigo-100 text-indigo-600' :
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
                              className="w-full px-2 py-1 text-sm border border-indigo-300 rounded focus:outline-none focus:ring-2 focus:ring-indigo-500"
                              onBlur={() => handleRename(file.id, newName)}
                              onClick={e => e.stopPropagation()}
                            />
                          ) : (
                            <p className="font-medium text-slate-900 truncate max-w-[250px] cursor-pointer hover:text-indigo-600" title={file.name} onClick={() => setPreviewFile(file)}>{file.name}</p>
                          )}
                          <p className="text-xs text-slate-400 mt-0.5">
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
                      {file.status === 'indexed' && (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          Indexed
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
                      {file.status === 'processing' && (
                        <div className="flex items-center gap-2">
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-indigo-100 text-indigo-700">
                            <div className="w-3.5 h-3.5 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
                            Processing
                          </span>
                          <span className="text-xs text-slate-500">{file.progress}%</span>
                        </div>
                      )}
                      {file.status === 'failed' && (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">
                          <AlertCircle className="w-3.5 h-3.5" />
                          Failed
                        </span>
                      )}
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
                          <button onClick={() => setPreviewFile(file)} className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2">
                            <Eye className="w-4 h-4" /> Preview
                          </button>
                          <button onClick={() => { setRenamingFileId(file.id); setNewName(file.name); setActiveDropdown(null); }} className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2">
                            <Edit2 className="w-4 h-4" /> Rename
                          </button>
                          <button onClick={() => { handleDownload(file); setActiveDropdown(null); }} className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2">
                            <Download className="w-4 h-4" /> Download
                          </button>
                          <div className="h-px bg-slate-100 my-1"></div>
                          <button 
                            onClick={() => handleDelete(file.id)}
                            className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2"
                          >
                            <Trash2 className="w-4 h-4" /> Delete
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
            {filteredAndSortedFiles.length === 0 ? (
              <div className="col-span-full text-center text-slate-500 py-12">
                No files found matching your criteria.
              </div>
            ) : (
              filteredAndSortedFiles.map((file) => (
                <div key={file.id} className={`relative group border rounded-xl p-4 transition-all ${selectedFiles.includes(file.id) ? 'border-indigo-500 bg-indigo-50/30' : 'border-slate-200 hover:border-indigo-300 hover:shadow-md bg-white'}`}>
                  <div className="absolute top-3 left-3 z-10">
                    <input 
                      type="checkbox" 
                      checked={selectedFiles.includes(file.id)}
                      onChange={() => toggleSelection(file.id)}
                      className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 opacity-0 group-hover:opacity-100 transition-opacity"
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
                        <button onClick={() => { handleDownload(file); setActiveDropdown(null); }} className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2">
                          <Download className="w-4 h-4" /> Download
                        </button>
                        <div className="h-px bg-slate-100 my-1"></div>
                        <button 
                          onClick={() => handleDelete(file.id)}
                          className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2"
                        >
                          <Trash2 className="w-4 h-4" /> Delete
                        </button>
                      </div>
                    )}
                  </div>
                  
                  <div className="flex flex-col items-center text-center mt-2 cursor-pointer" onClick={() => setPreviewFile(file)}>
                    <div className={`w-16 h-16 rounded-2xl flex items-center justify-center mb-4 ${
                      file.type === 'video' ? 'bg-indigo-100 text-indigo-600' :
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
                          className="w-full px-2 py-1 text-sm border border-indigo-300 rounded focus:outline-none focus:ring-2 focus:ring-indigo-500 text-center"
                          onBlur={() => handleRename(file.id, newName)}
                        />
                      </div>
                    ) : (
                      <h4 className="font-medium text-slate-900 text-sm line-clamp-2 mb-1 px-2 hover:text-indigo-600" title={file.name}>{file.name}</h4>
                    )}
                    
                    <div className="text-xs text-slate-500 flex items-center gap-2 mt-2">
                      <span>{file.size}</span>
                      <span>•</span>
                      <span>{file.date}</span>
                    </div>
                    
                    <div className="mt-3">
                      {file.status === 'indexed' && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-100 text-emerald-700">
                          <CheckCircle2 className="w-3 h-3" /> Indexed
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
                      {file.status === 'processing' && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-indigo-100 text-indigo-700">
                          <Loader2 className="w-3 h-3 animate-spin" /> Processing {file.progress}%
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
              ))
            )}
          </div>
        )}
      </div>

      {/* Preview Modal */}
      {previewFile && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm" onClick={() => setPreviewFile(null)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b border-slate-200">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${
                  previewFile.type === 'video' ? 'bg-indigo-100 text-indigo-600' :
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
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1 bg-slate-50 p-8 flex items-center justify-center overflow-y-auto min-h-[400px]">
              {/* Preview Content */}
              {previewUrl && previewFile.type === 'image' ? (
                <img src={previewUrl} alt={previewFile.name} className="max-w-full max-h-full object-contain rounded-xl shadow-lg" />
              ) : previewUrl && previewFile.type === 'video' ? (
                <video src={previewUrl} controls className="w-full max-w-2xl aspect-video rounded-xl shadow-lg bg-black" />
              ) : previewUrl && previewFile.type === 'audio' ? (
                <div className="w-full max-w-2xl bg-white rounded-xl shadow-lg border border-slate-200 p-12 flex flex-col items-center justify-center text-center">
                  <div className="w-24 h-24 bg-purple-100 rounded-full flex items-center justify-center mb-8 shadow-inner">
                    <Music className="w-12 h-12 text-purple-600" />
                  </div>
                  <audio src={previewUrl} controls className="w-full" />
                </div>
              ) : previewUrl && previewFile.originalFile?.type === 'application/pdf' ? (
                <div className="w-full h-full min-h-[600px] max-h-[70vh] overflow-y-auto bg-slate-200 rounded-xl shadow-inner flex flex-col items-center p-4">
                  <Document
                    file={previewUrl}
                    onLoadSuccess={onDocumentLoadSuccess}
                    loading={<Loader2 className="w-8 h-8 animate-spin text-indigo-600 my-12" />}
                    className="flex flex-col items-center gap-4"
                  >
                    {Array.from(new Array(numPages), (el, index) => (
                      <div key={`page_${index + 1}`} className="shadow-md">
                        <Page 
                          pageNumber={index + 1} 
                          width={800}
                          renderTextLayer={false}
                          renderAnnotationLayer={false}
                        />
                      </div>
                    ))}
                  </Document>
                </div>
              ) : previewUrl && previewFile.originalFile?.type === 'text/plain' ? (
                <div className="w-full h-full min-h-[600px] max-h-[70vh] overflow-y-auto bg-white rounded-xl shadow-lg p-8 border border-slate-200 text-left">
                  <pre className="whitespace-pre-wrap font-mono text-sm text-slate-800">{textContent || 'Loading text...'}</pre>
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
                      <div className="h-full bg-indigo-500 w-1/3"></div>
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
                    onClick={() => handleDownload(previewFile)} 
                    className="px-6 py-3 text-sm font-medium text-white bg-indigo-600 rounded-xl hover:bg-indigo-700 transition-colors flex items-center gap-2 shadow-sm"
                  >
                    <Download className="w-5 h-5" /> 
                    Download File
                  </button>
                </div>
              )}
            </div>
            <div className="p-4 border-t border-slate-200 bg-white flex justify-end gap-3">
              <button onClick={() => handleDownload(previewFile)} className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors flex items-center gap-2">
                <Download className="w-4 h-4" /> Download Original
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
