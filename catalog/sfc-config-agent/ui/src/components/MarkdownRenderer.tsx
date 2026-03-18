import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export default function MarkdownRenderer({
  content,
  className = "",
}: MarkdownRendererProps) {
  const components: Components = {
    h1: ({ children }) => (
      <h1 className="text-2xl font-bold mt-5 mb-3 text-sky-300 border-b border-sky-800/50 pb-1">
        {children}
      </h1>
    ),
    h2: ({ children }) => (
      <h2 className="text-xl font-bold mt-4 mb-2 text-sky-200">{children}</h2>
    ),
    h3: ({ children }) => (
      <h3 className="text-base font-semibold mt-3 mb-1 text-slate-200">
        {children}
      </h3>
    ),
    h4: ({ children }) => (
      <h4 className="text-sm font-semibold mt-2 mb-1 text-slate-300">
        {children}
      </h4>
    ),
    p: ({ children }) => (
      <p className="mb-2 last:mb-0 leading-relaxed text-slate-300">{children}</p>
    ),
    a: ({ href, children }) => (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-sky-400 underline decoration-sky-600 hover:decoration-sky-400 hover:text-sky-200 transition-colors"
      >
        {children}
      </a>
    ),
    ul: ({ children }) => (
      <ul className="list-disc list-inside mb-2 space-y-0.5 text-slate-300">{children}</ul>
    ),
    ol: ({ children }) => (
      <ol className="list-decimal list-inside mb-2 space-y-0.5 text-slate-300">{children}</ol>
    ),
    li: ({ children }) => <li className="ml-2">{children}</li>,
    blockquote: ({ children }) => (
      <blockquote className="border-l-4 border-sky-600 bg-sky-950/30 pl-4 pr-3 py-2 my-2 text-slate-400 italic rounded-r-md">
        {children}
      </blockquote>
    ),
    code: ({ className: codeClassName, children }) => {
      const match = /language-(\w+)/.exec(codeClassName || "");
      const codeString = String(children).replace(/\n$/, "");

      if (match || codeClassName || codeString.includes("\n")) {
        return (
          <div className="my-3 rounded-lg overflow-hidden border border-slate-700/50">
            {match && (
              <div className="flex items-center px-4 py-1.5 bg-slate-800 border-b border-slate-700/50">
                <span className="text-xs font-semibold text-sky-400 uppercase tracking-wider">
                  {match[1]}
                </span>
              </div>
            )}
            <pre className="overflow-auto bg-[#0d1117] p-4 text-sm text-slate-300 font-mono leading-relaxed">
              <code>{codeString}</code>
            </pre>
          </div>
        );
      }

      return (
        <code className="bg-slate-800 text-sky-300 border border-slate-700 px-1.5 py-0.5 rounded text-sm font-mono">
          {children}
        </code>
      );
    },
    pre: ({ children }) => <div className="not-prose">{children}</div>,
    table: ({ children }) => (
      <div className="overflow-x-auto my-3 rounded-lg border border-slate-700 shadow-sm">
        <table className="min-w-full border-collapse text-sm">{children}</table>
      </div>
    ),
    thead: ({ children }) => (
      <thead className="bg-slate-800 border-b-2 border-slate-700">{children}</thead>
    ),
    tbody: ({ children }) => (
      <tbody className="divide-y divide-slate-800">{children}</tbody>
    ),
    tr: ({ children }) => (
      <tr className="hover:bg-slate-800/50 transition-colors">{children}</tr>
    ),
    th: ({ children }) => (
      <th className="px-4 py-2 text-left font-semibold text-sky-300 text-xs uppercase tracking-wider">
        {children}
      </th>
    ),
    td: ({ children }) => (
      <td className="px-4 py-2 text-slate-300">{children}</td>
    ),
    hr: () => (
      <hr className="my-4 border-0 h-px bg-gradient-to-r from-transparent via-slate-600 to-transparent" />
    ),
    strong: ({ children }) => (
      <strong className="font-bold text-slate-100">{children}</strong>
    ),
    em: ({ children }) => <em className="italic text-slate-300">{children}</em>,
  };

  return (
    <div className={`overflow-auto h-full p-5 ${className}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
