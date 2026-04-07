import React, { useState, useEffect } from 'react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Legend,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid
} from 'recharts';
import { FileItem } from '../App';
import { Database, Eye, HardDrive } from 'lucide-react';
import IndexManagement from '../components/IndexManagement';
import {
  clearTextIndex,
  clearImageIndex,
  getInputFile,
  getFilesWithMetadata,
  getProcessedByFile,
  getProcessedFile,
  getProcessingStats,
  runIndex,
  runIndexImage,
  runIndexText,
  type FileWithMetadata,
  type ProcessedByFileResponse,
} from '../api/ragApi';

interface KnowledgeDashboardViewProps {
  files: FileItem[];
}

const COLORS = ['#6366f1', '#8b5cf6', '#ec4899', '#f43f5e', '#f59e0b', '#10b981'];

export default function KnowledgeDashboardView({ files }: KnowledgeDashboardViewProps) {
  const [indexStats, setIndexStats] = useState<Record<string, unknown> | null>(null);
  const [filesMeta, setFilesMeta] = useState<FileWithMetadata[]>([]);
  const [selectedFile, setSelectedFile] = useState<string>('');
  const [selectedProcessed, setSelectedProcessed] = useState<ProcessedByFileResponse | null>(null);
  const [processedLoading, setProcessedLoading] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void loadStatus(false);
    void loadFilesMeta();
  }, []);

  const loadStatus = async (freshStatus = false) => {
    try {
      const stats = await getProcessingStats(freshStatus);
      setIndexStats(stats);
    } catch (error) {
      console.error('Failed to load status:', error);
      setIndexStats(null);
    }
  };

  const loadFilesMeta = async () => {
    try {
      const filesWithMeta = await getFilesWithMetadata();
      setFilesMeta(filesWithMeta.files || []);
      const firstFileName = (filesWithMeta.files || [])[0]?.file_name || '';
      if (!selectedFile && firstFileName) {
        setSelectedFile(firstFileName);
      }
    } catch (error) {
      console.error('Failed to load files metadata:', error);
      setFilesMeta([]);
    }
  };

  useEffect(() => {
    if (!selectedFile) {
      setSelectedProcessed(null);
      return;
    }
    const run = async () => {
      setProcessedLoading(true);
      try {
        const data = await getProcessedByFile(selectedFile);
        setSelectedProcessed(data);
      } catch (e) {
        console.error('Failed to load processed artifacts for file:', selectedFile, e);
        setSelectedProcessed(null);
      } finally {
        setProcessedLoading(false);
      }
    };
    run();
  }, [selectedFile]);

  const handleRebuildAll = async () => {
    setLoading(true);
    try {
      await runIndex(true);
      await new Promise(r => setTimeout(r, 2000));
      await Promise.all([loadStatus(true), loadFilesMeta()]);
      alert('All indexes rebuilt successfully!');
    } catch (error) {
      alert(`Rebuild failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  const handleRebuildText = async () => {
    setLoading(true);
    try {
      await runIndexText(true);
      await new Promise(r => setTimeout(r, 2000));
      await Promise.all([loadStatus(true), loadFilesMeta()]);
      alert('Text index rebuilt successfully!');
    } catch (error) {
      alert(`Rebuild failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  const handleRebuildImage = async () => {
    setLoading(true);
    try {
      await runIndexImage(true);
      await new Promise(r => setTimeout(r, 2000));
      await Promise.all([loadStatus(true), loadFilesMeta()]);
      alert('Image index rebuilt successfully!');
    } catch (error) {
      alert(`Rebuild failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  const handleClearImageIndex = async () => {
    setLoading(true);
    try {
      await clearImageIndex();
      await new Promise(r => setTimeout(r, 1000));
      await Promise.all([loadStatus(true), loadFilesMeta()]);
      alert('Image index cleared successfully!');
    } catch (error) {
      alert(`Clear failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  const handleClearTextIndex = async () => {
    setLoading(true);
    try {
      await clearTextIndex();
      await new Promise(r => setTimeout(r, 1000));
      await Promise.all([loadStatus(true), loadFilesMeta()]);
      alert('Text index cleared successfully!');
    } catch (error) {
      alert(`Clear failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  const openBlobInNewTab = (blob: Blob, fallbackName: string) => {
    const url = URL.createObjectURL(blob);
    const win = window.open(url, '_blank');
    if (!win) {
      // Popup blocked fallback: trigger download
      const a = document.createElement('a');
      a.href = url;
      a.download = fallbackName;
      a.click();
    }
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  };

  const handlePreviewInputFile = async (fileName: string) => {
    try {
      const { body } = await getInputFile(fileName);
      openBlobInNewTab(body, fileName);
    } catch (e) {
      console.error('Preview original file failed:', e);
      alert('Cannot preview this original file.');
    }
  };

  const handlePreviewProcessedFile = async (relPath: string) => {
    try {
      const { body } = await getProcessedFile(relPath);
      const fallback = relPath.split('/').pop() || 'artifact';
      openBlobInNewTab(body, fallback);
    } catch (e) {
      console.error('Preview processed file failed:', e);
      alert('Cannot preview this processed artifact.');
    }
  };
  // Calculate stats
  const typeCounts = files.reduce((acc, file) => {
    acc[file.type] = (acc[file.type] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const pieData = Object.entries(typeCounts).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value
  }));

  const totalSize = files.reduce((acc, file) => acc + file.rawSize, 0);
  const formatSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const stats = [
    { label: 'Total Files', value: files.length, icon: Database, color: 'text-sky-600', bg: 'bg-sky-50' },
    { label: 'Storage Used', value: formatSize(totalSize), icon: HardDrive, color: 'text-emerald-600', bg: 'bg-emerald-50' },
  ];

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {stats.map((stat, i) => (
          <div key={i} className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex items-center gap-4">
            <div className={`w-12 h-12 rounded-xl ${stat.bg} flex items-center justify-center ${stat.color}`}>
              <stat.icon className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-500">{stat.label}</p>
              <p className="text-2xl font-bold text-slate-900">{stat.value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Processing Pipeline Section */}
      {/* Disabled - Use IndexManagement below instead */}
      {/* {files && files.length > 0 ? (
        <ProcessingPipeline files={files} processingStats={indexStats} />
      ) : (
        <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-sm border border-sky-100 p-8">
          <div className="text-center py-12">
            <Database className="w-12 h-12 mx-auto mb-3 opacity-20 text-slate-400" />
            <p className="text-slate-500">No documents uploaded yet. Go to Upload tab to add files.</p>
          </div>
        </div>
      )} */}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Pie Chart */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900 mb-6">Content Distribution</h3>
          <div className="h-[300px] w-full">
            {pieData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {pieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                  />
                  <Legend verticalAlign="bottom" height={36} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-slate-400">
                <Database className="w-12 h-12 mb-2 opacity-20" />
                <p>No data available</p>
              </div>
            )}
          </div>
        </div>

        {/* Bar Chart - File Status */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900 mb-6">Indexing Status</h3>
          <div className="h-[300px] w-full">
            {files.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={[
                  { name: 'Indexed', count: files.filter(f => f.status === 'indexed').length },
                  { name: 'Processed', count: files.filter(f => f.status === 'processed').length },
                  { name: 'Uploaded', count: files.filter(f => f.status === 'uploaded').length },
                  { name: 'Processing', count: files.filter(f => f.status === 'processing').length },
                  { name: 'Failed', count: files.filter(f => f.status === 'failed').length },
                ]}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
                  <Tooltip
                    cursor={{ fill: '#f8fafc' }}
                    contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                  />
                  <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} barSize={40} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-slate-400">
                <Database className="w-12 h-12 mb-2 opacity-20" />
                <p>No data available</p>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Files with Metadata</h3>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {filesMeta.length === 0 && <p className="text-sm text-slate-500">No files found.</p>}
            {filesMeta.map((f) => {
              const active = selectedFile === f.file_name;
              return (
                <button
                  key={f.path || f.file_name}
                  type="button"
                  onClick={() => setSelectedFile(f.file_name)}
                  className={`w-full text-left rounded-lg border px-3 py-2 transition ${active ? 'border-sky-400 bg-sky-50' : 'border-slate-200 hover:bg-slate-50'
                    }`}
                >
                  <p className="text-sm font-semibold text-slate-800 break-all">{f.file_name}</p>
                  <p className="text-xs text-slate-500 mt-1">
                    status: {f.status || 'uploaded'} | size: {f.size} | upload: {(f.upload_time || f.modified || '').toString().slice(0, 19)}
                  </p>
                  <div className="mt-2">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        void handlePreviewInputFile(f.file_name);
                      }}
                      className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border border-sky-200 bg-sky-50 text-sky-700 hover:bg-sky-100"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      Preview Original
                    </button>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Processed Artifacts by Selected File</h3>
          {!selectedFile && <p className="text-sm text-slate-500">Select a file from the left panel.</p>}
          {selectedFile && processedLoading && <p className="text-sm text-slate-500">Loading processed artifacts...</p>}
          {selectedFile && !processedLoading && !selectedProcessed && (
            <p className="text-sm text-slate-500">No processed artifacts found for this file.</p>
          )}
          {selectedProcessed && (
            <div className="space-y-3 max-h-80 overflow-y-auto">
              <p className="text-xs text-slate-500">
                document: {selectedProcessed.display_name || selectedProcessed.document_id || '-'} | total artifacts: {selectedProcessed.total_processed_files}
              </p>
              {selectedProcessed.stages.map((st) => (
                <div key={st.stage} className="rounded-lg border border-slate-200 p-3">
                  <p className="text-sm font-semibold text-slate-800">
                    {st.stage} ({st.file_count})
                  </p>
                  <ul className="mt-2 space-y-1">
                    {st.files.slice(0, 15).map((item, idx) => (
                      <li key={`${st.stage}-${idx}`} className="text-xs text-slate-600 break-all flex items-start justify-between gap-2">
                        <span>
                          {String((item as { relative_path?: string; name?: string }).relative_path || (item as { name?: string }).name || '')}
                        </span>
                        <button
                          type="button"
                          onClick={() => {
                            const rel = String((item as { relative_path?: string }).relative_path || '');
                            if (!rel) return;
                            void handlePreviewProcessedFile(rel);
                          }}
                          className="shrink-0 inline-flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-lg border border-sky-200 bg-sky-50 text-sky-700 hover:bg-sky-100"
                        >
                          <Eye className="w-3 h-3" />
                          Preview
                        </button>
                      </li>
                    ))}
                    {st.files.length > 15 && (
                      <li className="text-xs text-slate-400">...and {st.files.length - 15} more</li>
                    )}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Index Management Section */}
      <IndexManagement
        stats={indexStats}
        loading={loading}
        onRebuildAll={handleRebuildAll}
        onRebuildText={handleRebuildText}
        onRebuildImage={handleRebuildImage}
        onClearTextIndex={handleClearTextIndex}
        onClearImageIndex={handleClearImageIndex}
      />
    </div>
  );
}
