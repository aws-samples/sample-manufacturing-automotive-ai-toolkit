"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { dracula } from "react-syntax-highlighter/dist/esm/styles/prism";
import type { Components } from "react-markdown";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

function CodeBlock({ language, value }: { language: string; value: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const displayLang = language || "code";

  return (
    <div className="group relative my-3 rounded-lg overflow-hidden shadow-lg border border-gray-700/50">
      {/* Header bar with gradient */}
      <div className="flex items-center justify-between px-4 py-1.5 bg-gradient-to-r from-purple-900/80 via-indigo-900/80 to-blue-900/80 backdrop-blur-sm">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-purple-300 uppercase tracking-wider ml-2">
            {displayLang}
          </span>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition-colors px-2 py-0.5 rounded hover:bg-white/10"
        >
          {copied ? (
            <>
              <svg className="w-3.5 h-3.5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span className="text-green-400">Copied!</span>
            </>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              Copy
            </>
          )}
        </button>
      </div>
      {/* Code content */}
      <SyntaxHighlighter
        style={dracula}
        language={language || "text"}
        PreTag="div"
        customStyle={{
          margin: 0,
          borderRadius: 0,
          fontSize: "0.85rem",
          padding: "1rem 1.25rem",
          background: "#1a1b2e",
          lineHeight: 1.6,
        }}
        showLineNumbers={value.split("\n").length > 2}
        lineNumberStyle={{
          color: "#4a4b6a",
          fontSize: "0.75rem",
          paddingRight: "1em",
          minWidth: "2.5em",
        }}
        wrapLines
      >
        {value}
      </SyntaxHighlighter>
    </div>
  );
}

export default function MarkdownRenderer({
  content,
  className = "",
}: MarkdownRendererProps) {
  const components: Components = {
    // Headings
    h1: ({ children }) => (
      <h1 className="text-2xl font-bold mt-4 mb-2 bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
        {children}
      </h1>
    ),
    h2: ({ children }) => (
      <h2 className="text-xl font-bold mt-3 mb-2 text-gray-800">{children}</h2>
    ),
    h3: ({ children }) => (
      <h3 className="text-lg font-semibold mt-3 mb-1 text-gray-800">
        {children}
      </h3>
    ),
    h4: ({ children }) => (
      <h4 className="text-base font-semibold mt-2 mb-1 text-gray-700">
        {children}
      </h4>
    ),

    // Paragraph
    p: ({ children }) => (
      <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>
    ),

    // Links
    a: ({ href, children }) => (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-blue-600 underline decoration-blue-300 hover:decoration-blue-600 hover:text-blue-800 transition-colors"
      >
        {children}
      </a>
    ),

    // Lists
    ul: ({ children }) => (
      <ul className="list-disc list-inside mb-2 space-y-0.5">{children}</ul>
    ),
    ol: ({ children }) => (
      <ol className="list-decimal list-inside mb-2 space-y-0.5">{children}</ol>
    ),
    li: ({ children }) => <li className="ml-2">{children}</li>,

    // Blockquote
    blockquote: ({ children }) => (
      <blockquote className="border-l-4 border-purple-400 bg-purple-50 pl-4 pr-3 py-2 my-2 text-gray-700 italic rounded-r-md">
        {children}
      </blockquote>
    ),

    // Code — inline and fenced blocks with syntax highlighting
    code: ({ className: codeClassName, children, ...props }) => {
      const match = /language-(\w+)/.exec(codeClassName || "");
      const codeString = String(children).replace(/\n$/, "");

      // Fenced code block (has a language class or multiline)
      if (match) {
        return <CodeBlock language={match[1]} value={codeString} />;
      }

      // Fenced code block without a specified language
      if (codeClassName || codeString.includes("\n")) {
        return <CodeBlock language="" value={codeString} />;
      }

      // Inline code
      return (
        <code className="bg-indigo-50 text-indigo-700 border border-indigo-200 px-1.5 py-0.5 rounded text-sm font-mono">
          {children}
        </code>
      );
    },

    pre: ({ children }) => <div className="not-prose">{children}</div>,

    // Tables
    table: ({ children }) => (
      <div className="overflow-x-auto my-3 rounded-lg border border-gray-200 shadow-sm">
        <table className="min-w-full border-collapse text-sm">
          {children}
        </table>
      </div>
    ),
    thead: ({ children }) => (
      <thead className="bg-gradient-to-r from-gray-50 to-gray-100 border-b-2 border-gray-200">
        {children}
      </thead>
    ),
    tbody: ({ children }) => <tbody className="divide-y divide-gray-100">{children}</tbody>,
    tr: ({ children }) => (
      <tr className="hover:bg-blue-50/50 transition-colors">{children}</tr>
    ),
    th: ({ children }) => (
      <th className="px-4 py-2 text-left font-semibold text-gray-700 text-xs uppercase tracking-wider">
        {children}
      </th>
    ),
    td: ({ children }) => (
      <td className="px-4 py-2 text-gray-700">{children}</td>
    ),

    // Horizontal rule
    hr: () => (
      <hr className="my-4 border-0 h-px bg-gradient-to-r from-transparent via-gray-300 to-transparent" />
    ),

    // Strong and emphasis
    strong: ({ children }) => (
      <strong className="font-bold text-gray-900">{children}</strong>
    ),
    em: ({ children }) => <em className="italic">{children}</em>,
  };

  return (
    <div className={`markdown-body ${className}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}