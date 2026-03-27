import { useState, useEffect } from 'react';
import { 
  Play, 
  Pause, 
  Volume2, 
  Maximize, 
  Settings, 
  ChevronRight, 
  ChevronLeft,
  Search,
  MessageSquare,
  FileText,
  Sparkles,
  Loader2,
  Target,
  Key,
  BookOpen as BookOpenIcon,
  Clock,
  RefreshCw,
  Video
} from 'lucide-react';
import { GoogleGenAI, Type } from '@google/genai';
import { FileItem } from '../App';

interface LectureViewProps {
  files?: FileItem[];
}

export default function LectureView({ files = [] }: LectureViewProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [activeTab, setActiveTab] = useState<'transcript' | 'summary'>('summary');
  
  const videoFiles = files.filter(f => f.type === 'video');
  const [selectedLectureId, setSelectedLectureId] = useState<number | null>(
    videoFiles.length > 0 ? videoFiles[0].id : null
  );

  // Update selected lecture if files change and current selection is invalid
  useEffect(() => {
    if (videoFiles.length > 0 && (!selectedLectureId || !videoFiles.find(f => f.id === selectedLectureId))) {
      setSelectedLectureId(videoFiles[0].id);
    }
  }, [files, selectedLectureId]);

  const selectedLecture = videoFiles.find(f => f.id === selectedLectureId);

  const [videoUrl, setVideoUrl] = useState<string | null>(null);

  useEffect(() => {
    if (selectedLecture?.originalFile) {
      const url = URL.createObjectURL(selectedLecture.originalFile);
      setVideoUrl(url);
      return () => URL.revokeObjectURL(url);
    } else {
      setVideoUrl(null);
    }
  }, [selectedLecture]);

  // Summary Generation State
  const [isGenerating, setIsGenerating] = useState(false);
  const [summaryLength, setSummaryLength] = useState<'brief' | 'detailed' | 'comprehensive'>('detailed');
  const [summaryFocus, setSummaryFocus] = useState<'general' | 'formulas' | 'definitions'>('general');
  const [generatedSummary, setGeneratedSummary] = useState<any>(null);

  const transcript = [
    { time: '00:00', text: 'Welcome back everyone to lecture 4 of Machine Learning.', active: false },
    { time: '00:05', text: 'Today we are going to dive deep into neural networks, specifically focusing on how they learn.', active: false },
    { time: '00:12', text: 'The core algorithm that makes this possible is called backpropagation.', active: true },
    { time: '00:18', text: 'If you recall from last week, we discussed the forward pass where data moves through the network to generate a prediction.', active: false },
    { time: '00:25', text: 'Backpropagation is essentially the reverse of that. We calculate the error at the output using a loss function, like Mean Squared Error.', active: false },
    { time: '00:32', text: 'Then, we propagate that error backwards through the layers.', active: false },
    { time: '00:40', text: 'Mathematically, this relies heavily on the chain rule from calculus. We compute partial derivatives of the loss with respect to each weight.', active: false },
    { time: '00:55', text: 'Once we have these gradients, we use an optimization algorithm, typically Gradient Descent, to update our weights: W_new = W_old - learning_rate * gradient.', active: false },
    { time: '01:15', text: 'Let\'s look at the mathematical foundation of this process on the next slide and work through a concrete example.', active: false },
  ];

  const handleGenerateSummary = async () => {
    setIsGenerating(true);
    try {
      const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
      const transcriptText = transcript.map(t => `[${t.time}] ${t.text}`).join('\n');
      
      const response = await ai.models.generateContent({
        model: 'gemini-3-flash-preview',
        contents: `Generate a ${summaryLength} summary focusing on ${summaryFocus} for the following lecture transcript:\n\n${transcriptText}`,
        config: {
          responseMimeType: "application/json",
          responseSchema: {
            type: Type.OBJECT,
            properties: {
              learningObjectives: { type: Type.ARRAY, items: { type: Type.STRING }, description: "3-4 key learning objectives" },
              keyConcepts: { type: Type.ARRAY, items: { type: Type.STRING }, description: "Main concepts discussed" },
              sections: {
                type: Type.ARRAY,
                description: "Chronological sections of the lecture",
                items: {
                  type: Type.OBJECT,
                  properties: {
                    title: { type: Type.STRING },
                    timeRange: { type: Type.STRING },
                    points: { type: Type.ARRAY, items: { type: Type.STRING } }
                  }
                }
              },
              definitionsAndFormulas: {
                type: Type.ARRAY,
                description: "Important definitions or mathematical formulas mentioned",
                items: {
                  type: Type.OBJECT,
                  properties: {
                    term: { type: Type.STRING },
                    definition: { type: Type.STRING }
                  }
                }
              }
            },
            required: ["learningObjectives", "keyConcepts", "sections", "definitionsAndFormulas"]
          }
        }
      });
      
      if (response.text) {
        setGeneratedSummary(JSON.parse(response.text));
      }
    } catch (error) {
      console.error("Failed to generate summary:", error);
      // Fallback data in case of API failure or missing key
      setGeneratedSummary({
        learningObjectives: ["Understand the purpose of backpropagation", "Explain the relationship between forward and backward passes", "Apply the chain rule to neural networks"],
        keyConcepts: ["Backpropagation", "Forward Pass", "Loss Function", "Chain Rule", "Gradient Descent"],
        sections: [
          { title: "Introduction to Neural Network Learning", timeRange: "00:00 - 00:18", points: ["Welcome to lecture 4", "Focus on how neural networks learn via backpropagation"] },
          { title: "Forward vs Backward Pass", timeRange: "00:18 - 00:40", points: ["Forward pass generates predictions", "Backward pass calculates error at output using a loss function (e.g., MSE)", "Error is propagated backwards through layers"] },
          { title: "Mathematical Foundations", timeRange: "00:40 - 01:15", points: ["Relies on the chain rule from calculus", "Computes partial derivatives of loss w.r.t weights", "Uses Gradient Descent to update weights"] }
        ],
        definitionsAndFormulas: [
          { term: "Backpropagation", definition: "The core algorithm for training neural networks by propagating errors backward." },
          { term: "Weight Update Rule", definition: "W_new = W_old - learning_rate * gradient" }
        ]
      });
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="h-full flex flex-col lg:flex-row gap-8 max-w-[1600px] mx-auto">
      {/* Left Column: Video & Slides */}
      <div className="flex-1 flex flex-col gap-8 min-w-0">
        
        {/* Lecture Selector */}
        <div className="bg-white rounded-[2rem] p-6 border border-slate-200 shadow-sm flex items-center justify-between gap-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-indigo-50 text-indigo-600 rounded-2xl flex items-center justify-center shadow-sm">
              <Video className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-black text-slate-900 tracking-tight">Current Lecture</h2>
              <p className="text-xs text-slate-500 font-medium">Select a resource from your library</p>
            </div>
          </div>
          <div className="flex-1 max-w-md relative group">
            <select 
              value={selectedLectureId || ''}
              onChange={(e) => setSelectedLectureId(Number(e.target.value))}
              className="w-full appearance-none border border-slate-200 rounded-2xl px-5 py-3 text-sm font-bold text-slate-700 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none bg-slate-50/50 hover:bg-slate-50 transition-all cursor-pointer"
              disabled={videoFiles.length === 0}
            >
              {videoFiles.length === 0 ? (
                <option value="">No video lectures uploaded</option>
              ) : (
                videoFiles.map(file => (
                  <option key={file.id} value={file.id}>
                    {file.name} {file.duration ? `(${file.duration})` : ''}
                  </option>
                ))
              )}
            </select>
            <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400 group-hover:text-indigo-500 transition-colors">
              <ChevronRight className="w-4 h-4 rotate-90" />
            </div>
          </div>
        </div>

        {/* Video Player */}
        <div className="bg-slate-900 rounded-[2.5rem] overflow-hidden shadow-2xl relative aspect-video group flex items-center justify-center border-4 border-white">
          {videoUrl ? (
            <video 
              src={videoUrl} 
              controls 
              className="w-full h-full object-contain"
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
            />
          ) : (
            <>
              {/* Mock Video Content */}
              <div className="absolute inset-0 flex items-center justify-center bg-slate-900">
                {selectedLecture ? (
                  <div className="text-center">
                    <div className="w-20 h-20 bg-white/10 rounded-full flex items-center justify-center mx-auto mb-4 backdrop-blur-sm">
                      <Play className="w-10 h-10 text-white fill-white" />
                    </div>
                    <span className="text-white/40 font-bold tracking-widest uppercase text-xs">Video Player ({selectedLecture.name})</span>
                  </div>
                ) : (
                  <div className="text-center">
                    <div className="w-20 h-20 bg-white/5 rounded-full flex items-center justify-center mx-auto mb-4">
                      <Video className="w-10 h-10 text-white/20" />
                    </div>
                    <span className="text-white/20 font-bold tracking-widest uppercase text-xs">No video selected</span>
                  </div>
                )}
              </div>
              
              {/* Video Controls Overlay (Mock) */}
              <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 via-black/40 to-transparent p-8 opacity-0 group-hover:opacity-100 transition-all duration-300 transform translate-y-2 group-hover:translate-y-0">
                <div className="w-full h-1.5 bg-white/20 rounded-full mb-6 cursor-pointer group/progress">
                  <div className="h-full bg-indigo-500 rounded-full w-1/3 relative">
                    <div className="absolute right-0 top-1/2 -translate-y-1/2 w-4 h-4 bg-white rounded-full shadow-lg scale-0 group-hover/progress:scale-100 transition-transform"></div>
                  </div>
                </div>
                <div className="flex items-center justify-between text-white">
                  <div className="flex items-center gap-6">
                    <button onClick={() => setIsPlaying(!isPlaying)} className="hover:text-indigo-400 transition-all transform hover:scale-110">
                      {isPlaying ? <Pause className="w-6 h-6 fill-current" /> : <Play className="w-6 h-6 fill-current" />}
                    </button>
                    <div className="flex items-center gap-3">
                      <Volume2 className="w-5 h-5 text-white/70" />
                      <div className="w-20 h-1 bg-white/20 rounded-full overflow-hidden">
                        <div className="h-full bg-white rounded-full w-2/3"></div>
                      </div>
                    </div>
                    <span className="text-xs font-black font-mono tracking-wider text-white/80">15:42 / {selectedLecture?.duration || '45:00'}</span>
                  </div>
                  <div className="flex items-center gap-5">
                    <button className="hover:text-indigo-400 transition-all"><Settings className="w-5 h-5" /></button>
                    <button className="hover:text-indigo-400 transition-all"><Maximize className="w-5 h-5" /></button>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Right Column: Transcript & Summary */}
      <div className="w-full lg:w-[480px] bg-white rounded-[2.5rem] border border-slate-200 shadow-sm flex flex-col shrink-0 h-[calc(100vh-10rem)] overflow-hidden">
        {/* Tabs */}
        <div className="flex items-center p-3 bg-slate-50/50 border-b border-slate-100 shrink-0">
          <button 
            onClick={() => setActiveTab('transcript')}
            className={`flex-1 py-3 text-xs font-black uppercase tracking-widest rounded-2xl transition-all flex items-center justify-center gap-2 ${activeTab === 'transcript' ? 'bg-white text-indigo-600 shadow-sm border border-slate-200' : 'text-slate-400 hover:text-slate-600 hover:bg-white/50'}`}
          >
            <MessageSquare className="w-4 h-4" />
            Transcript
          </button>
          <button 
            onClick={() => setActiveTab('summary')}
            className={`flex-1 py-3 text-xs font-black uppercase tracking-widest rounded-2xl transition-all flex items-center justify-center gap-2 ${activeTab === 'summary' ? 'bg-white text-indigo-600 shadow-sm border border-slate-200' : 'text-slate-400 hover:text-slate-600 hover:bg-white/50'}`}
          >
            <Sparkles className="w-4 h-4" />
            AI Summary
          </button>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto relative custom-scrollbar">
          {activeTab === 'transcript' ? (
            <div className="p-8 space-y-6">
              <div className="relative group">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 group-focus-within:text-indigo-500 transition-colors" />
                <input 
                  type="text" 
                  placeholder="Search transcript..."
                  className="w-full pl-11 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all shadow-inner"
                />
              </div>
              <div className="space-y-2">
                {transcript.map((item, i) => (
                  <div key={i} className={`flex gap-4 p-4 rounded-2xl transition-all cursor-pointer group ${item.active ? 'bg-indigo-50/80 border border-indigo-100 shadow-sm' : 'hover:bg-slate-50 border border-transparent'}`}>
                    <span className={`text-[10px] font-black font-mono pt-1 shrink-0 uppercase tracking-tighter ${item.active ? 'text-indigo-600' : 'text-slate-300 group-hover:text-slate-400'}`}>
                      {item.time}
                    </span>
                    <p className={`text-sm leading-relaxed font-medium ${item.active ? 'text-indigo-900' : 'text-slate-600 group-hover:text-slate-900'}`}>
                      {item.text}
                    </p>
                  </div>
                ))}
              </div>
              <div className="flex gap-4 p-4 opacity-50">
                <span className="text-[10px] font-black font-mono pt-1 shrink-0 text-slate-200">01:25</span>
                <div className="h-4 bg-slate-100 rounded-full w-3/4 animate-pulse"></div>
              </div>
            </div>
          ) : (
            <div className="flex flex-col h-full">
              {!generatedSummary && !isGenerating ? (
                <div className="flex-1 flex flex-col items-center justify-center p-10 text-center m-6 bg-[#F8FAFC] rounded-[2rem] border border-slate-100 shadow-inner">
                  <div className="w-20 h-20 bg-white text-indigo-600 rounded-[1.5rem] flex items-center justify-center mb-6 shadow-xl shadow-indigo-100/50">
                    <Sparkles className="w-10 h-10" />
                  </div>
                  <h3 className="text-xl font-black text-slate-900 mb-3 tracking-tight">Lecture Insight</h3>
                  <p className="text-sm text-slate-500 mb-8 max-w-xs font-medium leading-relaxed">
                    Generate a structured, multi-level summary from the lecture transcript using AI.
                  </p>
                  
                  <div className="w-full max-w-sm space-y-5 mb-10 text-left">
                    <div>
                      <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2 ml-1">Summary Length</label>
                      <select 
                        value={summaryLength}
                        onChange={(e) => setSummaryLength(e.target.value as any)}
                        className="w-full border border-slate-200 rounded-2xl px-4 py-3 text-sm font-bold text-slate-700 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none bg-white shadow-sm"
                      >
                        <option value="brief">Brief (Executive Summary)</option>
                        <option value="detailed">Detailed (Standard)</option>
                        <option value="comprehensive">Comprehensive (In-depth)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2 ml-1">Focus Area</label>
                      <select 
                        value={summaryFocus}
                        onChange={(e) => setSummaryFocus(e.target.value as any)}
                        className="w-full border border-slate-200 rounded-2xl px-4 py-3 text-sm font-bold text-slate-700 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none bg-white shadow-sm"
                      >
                        <option value="general">General Concepts</option>
                        <option value="formulas">Formulas & Math</option>
                        <option value="definitions">Key Definitions</option>
                      </select>
                    </div>
                  </div>

                  <button 
                    onClick={handleGenerateSummary}
                    className="w-full max-w-sm py-4 bg-indigo-600 text-white font-black uppercase tracking-widest text-xs rounded-2xl hover:bg-indigo-700 transition-all flex items-center justify-center gap-3 shadow-lg shadow-indigo-200 hover:-translate-y-0.5"
                  >
                    <Sparkles className="w-5 h-5" />
                    Generate Summary
                  </button>
                </div>
              ) : isGenerating ? (
                <div className="flex-1 flex flex-col items-center justify-center p-10 text-center m-6">
                  <div className="relative">
                    <div className="absolute inset-0 bg-indigo-600/20 blur-2xl animate-pulse rounded-full"></div>
                    <Loader2 className="w-16 h-16 text-indigo-600 animate-spin mb-8 relative" />
                  </div>
                  <h3 className="text-xl font-black text-slate-900 tracking-tight">Analyzing Transcript...</h3>
                  <p className="text-sm text-slate-500 mt-3 font-medium max-w-[200px] mx-auto leading-relaxed">Extracting key concepts and generating structured summary.</p>
                </div>
              ) : (
                <div className="flex-1 overflow-y-auto p-8 space-y-10 custom-scrollbar">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-black text-slate-900 text-xl tracking-tight">Lecture Summary</h3>
                      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mt-1">AI Generated Insights</p>
                    </div>
                    <button 
                      onClick={() => setGeneratedSummary(null)}
                      className="p-2 text-indigo-600 hover:bg-indigo-50 rounded-xl transition-all border border-transparent hover:border-indigo-100"
                    >
                      <RefreshCw className="w-5 h-5" />
                    </button>
                  </div>

                  {/* Objectives & Concepts */}
                  <div className="space-y-6">
                    <div className="bg-indigo-50/50 rounded-[1.5rem] p-6 border border-indigo-100 shadow-sm">
                      <h4 className="text-xs font-black text-indigo-900 mb-4 flex items-center gap-2 uppercase tracking-widest">
                        <Target className="w-4 h-4" /> Learning Objectives
                      </h4>
                      <ul className="space-y-3">
                        {generatedSummary.learningObjectives.map((obj: string, i: number) => (
                          <li key={i} className="flex gap-3 text-sm text-indigo-800 font-medium leading-relaxed">
                            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-2 shrink-0"></span>
                            {obj}
                          </li>
                        ))}
                      </ul>
                    </div>
                    
                    <div className="bg-emerald-50/50 rounded-[1.5rem] p-6 border border-emerald-100 shadow-sm">
                      <h4 className="text-xs font-black text-emerald-900 mb-4 flex items-center gap-2 uppercase tracking-widest">
                        <Key className="w-4 h-4" /> Key Concepts
                      </h4>
                      <div className="flex flex-wrap gap-2">
                        {generatedSummary.keyConcepts.map((concept: string, i: number) => (
                          <span key={i} className="px-3 py-1.5 bg-white border border-emerald-200 text-emerald-700 rounded-xl text-[10px] font-black uppercase tracking-wider shadow-sm">
                            {concept}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Timeline Sections */}
                  <div className="space-y-6">
                    <h4 className="text-xs font-black text-slate-400 mb-6 flex items-center gap-3 uppercase tracking-widest">
                      <Clock className="w-4 h-4" /> Lecture Timeline
                    </h4>
                    <div className="space-y-10">
                      {generatedSummary.sections.map((section: any, i: number) => (
                        <div key={i} className="relative pl-8 border-l-2 border-slate-100 pb-2 last:pb-0 group">
                          <div className="absolute w-4 h-4 bg-white border-4 border-indigo-500 rounded-full -left-[9px] top-0 shadow-sm group-hover:scale-125 transition-transform"></div>
                          <div className="flex items-center justify-between mb-3">
                            <h5 className="font-black text-slate-900 text-sm tracking-tight">{section.title}</h5>
                            <span className="text-[10px] font-black text-indigo-600 bg-indigo-50 px-2 py-1 rounded-lg border border-indigo-100 uppercase tracking-widest">{section.timeRange}</span>
                          </div>
                          <ul className="space-y-3">
                            {section.points.map((point: string, j: number) => (
                              <li key={j} className="text-sm text-slate-600 flex items-start gap-3 font-medium leading-relaxed">
                                <span className="w-1 h-1 bg-slate-300 rounded-full mt-2 shrink-0"></span>
                                {point}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Definitions & Formulas */}
                  {generatedSummary.definitionsAndFormulas && generatedSummary.definitionsAndFormulas.length > 0 && (
                    <div className="space-y-6">
                      <h4 className="text-xs font-black text-slate-400 mb-6 flex items-center gap-3 uppercase tracking-widest">
                        <BookOpenIcon className="w-4 h-4" /> Definitions & Formulas
                      </h4>
                      <div className="space-y-4">
                        {generatedSummary.definitionsAndFormulas.map((item: any, i: number) => (
                          <div key={i} className="bg-slate-50/50 rounded-2xl p-5 border border-slate-100 shadow-sm group hover:bg-white hover:border-indigo-200 transition-all">
                            <span className="font-black text-slate-900 text-sm block mb-2 tracking-tight group-hover:text-indigo-600 transition-colors">{item.term}</span>
                            <span className="text-sm text-slate-500 font-medium leading-relaxed">{item.definition}</span>
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
      </div>
    </div>
  );
}
