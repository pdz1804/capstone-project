import { ChevronDown, ChevronUp, Database, BarChart3 } from 'lucide-react'

export default function SettingsPanel({ pipelineConfig, showConfig, setShowConfig, processingStats }) {
  return (
    <>
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
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Qdrant</div>
                <div className="text-sm font-medium text-slate-800">{pipelineConfig.key_settings.qdrant_mode ?? ' '}</div>
              </div>
              <div className="bg-white/60 rounded-lg p-3">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Image Retrieval</div>
                <div className="text-sm font-medium text-slate-800">{pipelineConfig.key_settings.image_retrieval_enabled ? '✓ Enabled' : '✗ Disabled'}</div>
              </div>
              <div className="bg-white/60 rounded-lg p-3 md:col-span-2">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Retrieval Methods</div>
                <div className="text-sm font-medium text-slate-800">
                  {(pipelineConfig.key_settings.retrieval_methods || []).join(', ') || ' '}
                </div>
              </div>
              <div className="bg-white/60 rounded-lg p-3">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">ColQwen Model</div>
                <div className="text-sm font-medium text-slate-800 truncate">{pipelineConfig.key_settings.colqwen_model?.split('/')?.pop() || 'N/A'}</div>
              </div>
              <div className="bg-white/60 rounded-lg p-3 md:col-span-2 lg:col-span-1">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Text Embedding</div>
                <div className="text-sm font-medium text-slate-800 truncate">{pipelineConfig.key_settings.text_embedding_model || 'N/A'}</div>
              </div>
              <div className="bg-white/60 rounded-lg p-3">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Text collection</div>
                <div className="text-sm font-medium text-slate-800 truncate">{pipelineConfig.key_settings.text_collection ?? ' '}</div>
              </div>
              <div className="bg-white/60 rounded-lg p-3">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Image collection</div>
                <div className="text-sm font-medium text-slate-800 truncate">{pipelineConfig.key_settings.image_collection ?? ' '}</div>
              </div>
              <div className="bg-white/60 rounded-lg p-3">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">SageMaker inference</div>
                <div className="text-sm font-medium text-slate-800">{pipelineConfig.key_settings.use_aws_sagemaker_inference ? '✓ Yes' : '✗ No'}</div>
              </div>
              <div className="bg-white/60 rounded-lg p-3 md:col-span-2">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">SageMaker endpoint</div>
                <div className="text-sm font-medium text-slate-800 truncate">{pipelineConfig.key_settings.sagemaker_endpoint ?? ' '}</div>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  )
}
