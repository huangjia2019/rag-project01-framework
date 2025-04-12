// src/pages/LoadFile.jsx
import React, { useState, useEffect } from 'react';
import RandomImage from '../components/RandomImage';
import { apiBaseUrl } from '../config/config';

const LoadFile = () => {
  const [file, setFile] = useState(null);
  const [loadingMethod, setLoadingMethod] = useState('pymupdf');
  const [unstructuredStrategy, setUnstructuredStrategy] = useState('fast');
  const [chunkingStrategy, setChunkingStrategy] = useState('basic');
  const [chunkingOptions, setChunkingOptions] = useState({
    maxCharacters: 4000,
    newAfterNChars: 3000,
    combineTextUnderNChars: 500,
    overlap: 200,
    overlapAll: false,
    multiPageSections: false
  });
  const [loadedContent, setLoadedContent] = useState(null);
  const [status, setStatus] = useState('');
  const [documents, setDocuments] = useState([]);
  const [activeTab, setActiveTab] = useState('preview'); // 'preview' 或 'documents'
  const [selectedDoc, setSelectedDoc] = useState(null);

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/documents?type=loaded`);
      const data = await response.json();
      setDocuments(data.documents);
    } catch (error) {
      console.error('Error fetching documents:', error);
    }
  };

  const handleProcess = async () => {
    if (!file || !loadingMethod) {
      setStatus('Please select all required options');
      return;
    }

    setStatus('Loading...');
    setLoadedContent(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('loading_method', loadingMethod);
      
      if (loadingMethod === 'unstructured') {
        formData.append('strategy', unstructuredStrategy);
        formData.append('chunking_strategy', chunkingStrategy);
        formData.append('chunking_options', JSON.stringify(chunkingOptions));
      }

      const response = await fetch(`${apiBaseUrl}/load`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setLoadedContent(data.loaded_content);
      setStatus('File loaded successfully!');
      fetchDocuments();
      setActiveTab('preview');

    } catch (error) {
      console.error('Error:', error);
      setStatus(`Error: ${error.message}`);
    }
  };

  const handleDeleteDocument = async (docName) => {
    try {
      const response = await fetch(`${apiBaseUrl}/documents/${docName}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      setStatus('Document deleted successfully');
      fetchDocuments();
      if (selectedDoc?.name === docName) {
        setSelectedDoc(null);
        setLoadedContent(null);
      }
    } catch (error) {
      console.error('Error deleting document:', error);
      setStatus(`Error deleting document: ${error.message}`);
    }
  };

  const handleViewDocument = async (doc) => {
    try {
      setStatus('Loading document...');
      const response = await fetch(`${apiBaseUrl}/documents/${doc.name}.json`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setSelectedDoc(doc);
      setLoadedContent(data);
      setActiveTab('preview');
      setStatus('');
    } catch (error) {
      console.error('Error loading document:', error);
      setStatus(`Error loading document: ${error.message}`);
    }
  };

  const renderRightPanel = () => {
    return (
      <div className="p-4">
        {/* 标签页切换 */}
        <div className="flex mb-4 border-b">
          <button
            className={`px-4 py-2 ${
              activeTab === 'preview'
                ? 'border-b-2 border-blue-500 text-blue-600'
                : 'text-gray-600'
            }`}
            onClick={() => setActiveTab('preview')}
          >
            Document Preview
          </button>
          <button
            className={`px-4 py-2 ml-4 ${
              activeTab === 'documents'
                ? 'border-b-2 border-blue-500 text-blue-600'
                : 'text-gray-600'
            }`}
            onClick={() => setActiveTab('documents')}
          >
            Document Management
          </button>
        </div>

        {/* 内容区域 */}
        {activeTab === 'preview' ? (
          loadedContent ? (
            <div>
              <h3 className="text-xl font-semibold mb-4">Document Content</h3>
              <div className="mb-4 p-3 border rounded bg-gray-100">
                <h4 className="font-medium mb-2">Document Information</h4>
                <div className="text-sm text-gray-600">
                  <p>Pages: {loadedContent.total_pages || 'N/A'}</p>
                  <p>Chunks: {loadedContent.total_chunks || 'N/A'}</p>
                  <p>Loading Method: {loadedContent.loading_method || 'N/A'}</p>
                  <p>Chunking Method: {loadedContent.chunking_method || 'N/A'}</p>
                  <p>Processing Date: {loadedContent.timestamp ? 
                    new Date(loadedContent.timestamp).toLocaleString() : 'N/A'}</p>
                </div>
              </div>
              <div className="space-y-3 max-h-[calc(100vh-300px)] overflow-y-auto">
                {loadedContent.chunks.map((chunk) => (
                  <div key={chunk.metadata.chunk_id} className="p-3 border rounded bg-gray-50">
                    <div className="font-medium text-sm text-gray-500 mb-1">
                      Chunk {chunk.metadata.chunk_id} (Page {chunk.metadata.page_number})
                    </div>
                    <div className="text-xs text-gray-400 mb-2">
                      Words: {chunk.metadata.word_count} | Page Range: {chunk.metadata.page_range}
                    </div>
                    <div className="text-sm mt-2">
                      <div className="text-gray-600">{chunk.content}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <RandomImage message="Upload and load a file or select an existing document to see the results here" />
          )
        ) : (
          // 文档管理页面
          <div>
            <h3 className="text-xl font-semibold mb-4">Document Management</h3>
            <div className="space-y-4">
              {documents.map((doc) => (
                <div key={doc.name} className="p-4 border rounded-lg bg-gray-50">
                  <div className="flex justify-between items-start">
                    <div>
                      <h4 className="font-medium text-lg">{doc.name}</h4>
                      <div className="text-sm text-gray-600 mt-1">
                        <p>Pages: {doc.metadata?.total_pages || 'N/A'}</p>
                        <p>Chunks: {doc.metadata?.total_chunks || 'N/A'}</p>
                        <p>Loading Method: {doc.metadata?.loading_method || 'N/A'}</p>
                        <p>Chunking Method: {doc.metadata?.chunking_method || 'N/A'}</p>
                        <p>Created: {doc.metadata?.timestamp ? 
                          new Date(doc.metadata.timestamp).toLocaleString() : 'N/A'}</p>
                      </div>
                    </div>
                    <div className="flex space-x-2">
                      <button
                        onClick={() => handleViewDocument(doc)}
                        className="px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600"
                      >
                        View
                      </button>
                      <button
                        onClick={() => handleDeleteDocument(doc.name)}
                        className="px-3 py-1 bg-red-500 text-white rounded hover:bg-red-600"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))}
              {documents.length === 0 && (
                <div className="text-center text-gray-500 py-8">
                  No documents available
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-6">Load File</h2>
      
      <div className="grid grid-cols-12 gap-6">
        {/* Left Panel */}
        <div className="col-span-3 space-y-4">
          <div className="p-4 border rounded-lg bg-white shadow-sm">
            <div>
              <label className="block text-sm font-medium mb-1">Upload PDF</label>
              <input
                type="file"
                accept=".pdf"
                onChange={(e) => setFile(e.target.files[0])}
                className="block w-full border rounded px-3 py-2"
              />
            </div>

            <div className="mt-4">
              <label className="block text-sm font-medium mb-1">Loading Method</label>
              <select
                value={loadingMethod}
                onChange={(e) => setLoadingMethod(e.target.value)}
                className="block w-full p-2 border rounded"
              >
                <option value="pymupdf">PyMuPDF</option>
                <option value="pypdf">PyPDF</option>
                <option value="unstructured">Unstructured</option>
              </select>
            </div>

            {loadingMethod === 'unstructured' && (
              <>
                <div className="mt-4">
                  <label className="block text-sm font-medium mb-1">Unstructured Strategy</label>
                  <select
                    value={unstructuredStrategy}
                    onChange={(e) => setUnstructuredStrategy(e.target.value)}
                    className="block w-full p-2 border rounded"
                  >
                    <option value="fast">Fast</option>
                    <option value="hi_res">High Resolution</option>
                    <option value="ocr_only">OCR Only</option>
                  </select>
                </div>

                <div className="mt-4">
                  <label className="block text-sm font-medium mb-1">Chunking Strategy</label>
                  <select
                    value={chunkingStrategy}
                    onChange={(e) => setChunkingStrategy(e.target.value)}
                    className="block w-full p-2 border rounded"
                  >
                    <option value="basic">Basic</option>
                    <option value="by_title">By Title</option>
                  </select>
                </div>

                {chunkingStrategy === 'basic' && (
                  <div className="mt-4 space-y-3">
                    <div>
                      <label className="block text-sm font-medium mb-1">Max Characters</label>
                      <input
                        type="number"
                        value={chunkingOptions.maxCharacters}
                        onChange={(e) => setChunkingOptions(prev => ({
                          ...prev,
                          maxCharacters: parseInt(e.target.value)
                        }))}
                        className="block w-full p-2 border rounded"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-1">New After N Chars</label>
                      <input
                        type="number"
                        value={chunkingOptions.newAfterNChars}
                        onChange={(e) => setChunkingOptions(prev => ({
                          ...prev,
                          newAfterNChars: parseInt(e.target.value)
                        }))}
                        className="block w-full p-2 border rounded"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-1">Combine Text Under N Chars</label>
                      <input
                        type="number"
                        value={chunkingOptions.combineTextUnderNChars}
                        onChange={(e) => setChunkingOptions(prev => ({
                          ...prev,
                          combineTextUnderNChars: parseInt(e.target.value)
                        }))}
                        className="block w-full p-2 border rounded"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-1">Overlap</label>
                      <input
                        type="number"
                        value={chunkingOptions.overlap}
                        onChange={(e) => setChunkingOptions(prev => ({
                          ...prev,
                          overlap: parseInt(e.target.value)
                        }))}
                        className="block w-full p-2 border rounded"
                      />
                    </div>
                    <div className="flex items-center">
                      <input
                        type="checkbox"
                        checked={chunkingOptions.overlapAll}
                        onChange={(e) => setChunkingOptions(prev => ({
                          ...prev,
                          overlapAll: e.target.checked
                        }))}
                        className="mr-2"
                      />
                      <label className="text-sm font-medium">Overlap All</label>
                    </div>
                  </div>
                )}

                {chunkingStrategy === 'by_title' && (
                  <div className="mt-4 space-y-3">
                    <div>
                      <label className="block text-sm font-medium mb-1">Combine Text Under N Chars</label>
                      <input
                        type="number"
                        value={chunkingOptions.combineTextUnderNChars}
                        onChange={(e) => setChunkingOptions(prev => ({
                          ...prev,
                          combineTextUnderNChars: parseInt(e.target.value)
                        }))}
                        className="block w-full p-2 border rounded"
                      />
                    </div>
                    <div className="flex items-center">
                      <input
                        type="checkbox"
                        checked={chunkingOptions.multiPageSections}
                        onChange={(e) => setChunkingOptions(prev => ({
                          ...prev,
                          multiPageSections: e.target.checked
                        }))}
                        className="mr-2"
                      />
                      <label className="text-sm font-medium">Multi-page Sections</label>
                    </div>
                  </div>
                )}
              </>
            )}

            <button 
              onClick={handleProcess}
              className="mt-4 w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
              disabled={!file}
            >
              Load File
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

        {/* Right Panel */}
        <div className="col-span-9 border rounded-lg bg-white shadow-sm">
          {renderRightPanel()}
        </div>
      </div>
    </div>
  );
};

export default LoadFile;