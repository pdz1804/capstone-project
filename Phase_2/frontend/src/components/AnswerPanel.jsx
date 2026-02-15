import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import remarkGfm from 'remark-gfm'
import { MessageSquare } from 'lucide-react'

export default function AnswerPanel({ answer, onCitationClick }) {
  if (!answer) return null

  return (
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
              if (href && (href.startsWith('#chunk-') || href.startsWith('#image-'))) {
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
                      onCitationClick(e, href)
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
          {answer}
        </ReactMarkdown>
      </div>
    </div>
  )
}
