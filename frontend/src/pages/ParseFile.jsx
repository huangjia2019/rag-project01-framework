import React, { useState } from 'react';
import RandomImage from '../components/RandomImage';
import { apiBaseUrl } from '../config/config';

const ParseFile = () => {
  const [file, setFile] = useState(null);
  const [loadingMethod, setLoadingMethod] = useState('pymupdf');
  const [parsingOption, setParsingOption] = useState('all_text');
  const [parsedContent, setParsedContent] = useState(null);
  const [status, setStatus] = useState('');
  const [docName, setDocName] = useState('');
  const [isProcessed, setIsProcessed] = useState(false);

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

      const response = await fetch(`${apiBaseUrl}/parse`, {
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

  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-6">Parse File</h2>
      
      <div className="grid grid-cols-12 gap-6">
        {/* Left Panel (3/12) */}
        <div className="col-span-3 space-y-4">
          <div className="p-4 border rounded-lg bg-white shadow-sm">
            <div>
              <label className="block text-sm font-medium mb-1">Upload PDF</label>
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
                <option value="pymupdf">PyMuPDF</option>
                <option value="pypdf">PyPDF</option>
                <option value="unstructured">Unstructured</option>
                <option value="pdfplumber">PDF Plumber</option>
              </select>
            </div>

            <div className="mt-4">
              <label className="block text-sm font-medium mb-1">Parsing Option</label>
              <select
                value={parsingOption}
                onChange={(e) => setParsingOption(e.target.value)}
                className="block w-full p-2 border rounded"
              >
                <option value="all_text">All Text</option>
                <option value="by_pages">By Pages</option>
                <option value="by_titles">By Titles</option>
                <option value="text_and_tables">Text and Tables</option>
              </select>
            </div>

            <button 
              onClick={handleProcess}
              className="mt-4 w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
              disabled={!file}
            >
              Process File
            </button>
          </div>
        </div>

        {/* Right Panel (9/12) */}
        <div className="col-span-9 border rounded-lg bg-white shadow-sm">
          {parsedContent ? (
            <div className="p-4">
              <h3 className="text-xl font-semibold mb-4">Parsing Results</h3>
              <div className="mb-4 p-3 border rounded bg-gray-100">
                <h4 className="font-medium mb-2">Document Information</h4>
                <div className="text-sm text-gray-600">
                  <p>Total Pages: {parsedContent.metadata?.total_pages}</p>
                  <p>Parsing Method: {parsedContent.metadata?.parsing_method}</p>
                  <p>Timestamp: {parsedContent.metadata?.timestamp && new Date(parsedContent.metadata.timestamp).toLocaleString()}</p>
                </div>
              </div>
              <div className="space-y-3 max-h-[calc(100vh-300px)] overflow-y-auto">
                {parsedContent.content.map((item, idx) => (
                  <div key={idx} className="p-3 border rounded bg-gray-50">
                    <div className="font-medium text-sm text-gray-500 mb-1">
                      {item.type} - Page {item.page}
                    </div>
                    {item.title && (
                      <div className="font-bold text-gray-700 mb-2">
                        {item.title}
                      </div>
                    )}
                    <div className="text-sm text-gray-600">
                      {item.content}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <RandomImage message="Upload and parse a file to see the results here" />
          )}
        </div>
      </div>
    </div>
  );
};

export default ParseFile; 