import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import rehypeHighlight from 'rehype-highlight';
import remarkGfm from 'remark-gfm';
import RandomImage from '../components/RandomImage';
import { apiBaseUrl } from '../config/config';

const ParseMDFile = () => {
  const [file, setFile] = useState(null);
  const [loadingMethod, setLoadingMethod] = useState('mineru');
  const [parsingOption, setParsingOption] = useState('one');
  const [parsedContent, setParsedContent] = useState(null);
  const [status, setStatus] = useState('');
  const [docName, setDocName] = useState('');
  const [isProcessed, setIsProcessed] = useState(false);
  const [viewMode, setViewMode] = useState('rendered'); // 'rendered' or 'raw'

  const handleProcess = async () => {
    if (!file || !loadingMethod || !parsingOption) {
      setStatus('Please select all required options');
      return;
    }

    setStatus('Processing...');
    setParsedContent(null);
    setIsProcessed(false);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('loading_method', loadingMethod);
      formData.append('parsing_option', parsingOption);

      const response = await fetch(`${apiBaseUrl}/parse_md`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setParsedContent(data.parsed_content);
      setStatus('Processing completed successfully!');
      setIsProcessed(true);
    } catch (error) {
      console.error('Error:', error);
      setStatus(`Error: ${error.message}`);
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setFile(file);
      const baseName = file.name.replace('.pdf', '');
      setDocName(baseName);
    }
  };

  const toggleViewMode = () => {
    setViewMode(viewMode === 'rendered' ? 'raw' : 'rendered');
  };

  // Component to render markdown content
  const MarkdownContent = ({ content }) => {
    if (viewMode === 'rendered') {
      return (
        <div className="markdown-content">
          <ReactMarkdown
            rehypePlugins={[rehypeRaw, rehypeHighlight]}
            remarkPlugins={[remarkGfm]}
          >
            {content}
          </ReactMarkdown>
        </div>
      );
    } else {
      return (
        <pre className="bg-gray-100 p-3 rounded font-mono text-sm overflow-auto whitespace-pre-wrap">
          {content}
        </pre>
      );
    }
  };

  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-6">Parse PDF to Markdown</h2>
      
      <div className="grid grid-cols-12 gap-6">
        {/* Left Panel (3/12) */}
        <div className="col-span-3 space-y-4">
          <div className="p-4 border rounded-lg bg-white shadow-sm">
            <div>
              <label className="block text-sm font-medium mb-1">Upload PDF File</label>
              <input
                type="file"
                accept=".pdf"
                onChange={handleFileSelect}
                className="block w-full border rounded px-3 py-2"
                required
              />
            </div>

            <div className="mt-4">
              <label className="block text-sm font-medium mb-1">Loading Tool</label>
              <select
                value={loadingMethod}
                onChange={(e) => setLoadingMethod(e.target.value)}
                className="block w-full p-2 border rounded"
              >
                <option value="mineru">MinerU</option>
              </select>
            </div>

            <div className="mt-4">
              <label className="block text-sm font-medium mb-1">Parsing Option</label>
              <select
                value={parsingOption}
                onChange={(e) => setParsingOption(e.target.value)}
                className="block w-full p-2 border rounded"
              >
                <option value="one">One</option>
                <option value="by_headers">By Headers</option>
              </select>
            </div>

            <button 
              onClick={handleProcess}
              className="mt-4 w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
              disabled={!file}
            >
              Convert to Markdown
            </button>
          </div>
          
          {status && (
            <div className={`p-4 rounded-lg ${
              status.includes('Error') ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
            }`}>
              {status}
            </div>
          )}
        </div>

        {/* Right Panel (9/12) */}
        <div className="col-span-9 border rounded-lg bg-white shadow-sm">
          {parsedContent ? (
            <div className="p-4">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-xl font-semibold">Markdown Results</h3>
                <div className="flex items-center">
                  <span className="mr-2 text-sm text-gray-600">View mode:</span>
                  <button 
                    onClick={toggleViewMode}
                    className="px-3 py-1 bg-blue-100 text-blue-800 rounded hover:bg-blue-200"
                  >
                    {viewMode === 'rendered' ? 'Show Raw' : 'Show Rendered'}
                  </button>
                </div>
              </div>
              
              <div className="mb-4 p-3 border rounded bg-gray-100">
                <h4 className="font-medium mb-2">Document Information</h4>
                <div className="text-sm text-gray-600">
                  <p>Filename: {parsedContent.metadata?.filename}</p>
                  <p>Parsing Method: {parsedContent.metadata?.parsing_method}</p>
                  <p>Timestamp: {parsedContent.metadata?.timestamp && new Date(parsedContent.metadata.timestamp).toLocaleString()}</p>
                </div>
              </div>
              
              <div className="space-y-3 max-h-[calc(100vh-300px)] overflow-y-auto">
                {parsedContent.content.map((item, idx) => (
                  <div key={idx} className="p-3 border rounded bg-gray-50">
                    <div className="font-medium text-sm text-gray-500 mb-1">
                      {item.type} {item.section && `- Section ${item.section}`}
                    </div>
                    {item.title && (
                      <div className="font-bold text-gray-700 mb-2">
                        {item.title}
                      </div>
                    )}
                    <div className={`${viewMode === 'raw' ? 'text-sm text-gray-600' : 'markdown-preview'}`}>
                      <MarkdownContent content={item.content} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <RandomImage message="Upload a PDF file to convert to Markdown" />
          )}
        </div>
      </div>
    </div>
  );
};

export default ParseMDFile; 