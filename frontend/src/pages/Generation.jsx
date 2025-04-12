import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import RandomImage from '../components/RandomImage';
import { apiBaseUrl } from '../config/config';

const Generation = () => {
  const location = useLocation();
  const [provider, setProvider] = useState('');
  const [modelName, setModelName] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [models, setModels] = useState({});
  const [isGenerating, setIsGenerating] = useState(false);
  const [response, setResponse] = useState('');
  const [status, setStatus] = useState('');
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [selectedFile, setSelectedFile] = useState('');
  const [searchFiles, setSearchFiles] = useState([]);
  const [showReasoning, setShowReasoning] = useState(true);

  // 加载可用模型列表和搜索结果文件列表
  useEffect(() => {
    const fetchData = async () => {
      try {
        // 获取模型列表
        const modelsResponse = await fetch(`${apiBaseUrl}/generation/models`);
        const modelsData = await modelsResponse.json();
        setModels(modelsData.models);

        // 获取搜索结果文件列表
        const filesResponse = await fetch(`${apiBaseUrl}/search-results`);
        const filesData = await filesResponse.json();
        setSearchFiles(filesData.files);
      } catch (error) {
        console.error('Error fetching data:', error);
        setStatus('获取数据失败');
      }
    };

    fetchData();
  }, []);

  // 加载选中的搜索结果文件内容
  useEffect(() => {
    const loadSearchResults = async () => {
      if (!selectedFile) {
        setQuery('');
        setSearchResults([]);
        return;
      }

      try {
        const response = await fetch(`${apiBaseUrl}/search-results/${selectedFile}`);
        const data = await response.json();
        setQuery(data.query);
        setSearchResults(data.results);
      } catch (error) {
        console.error('Error loading search results:', error);
        setStatus('加载搜索结果失败');
      }
    };

    loadSearchResults();
  }, [selectedFile]);

  // 如果从搜索页面跳转过来，获取搜索结果
  useEffect(() => {
    if (location.state) {
      const { query: searchQuery, results } = location.state;
      if (searchQuery) setQuery(searchQuery);
      if (results) setSearchResults(results);
    }
  }, [location]);

  const handleGenerate = async () => {
    if (!provider || !modelName) {
      setStatus('请选择生成模型');
      return;
    }

    if (!query || searchResults.length === 0) {
      setStatus('请输入问题并确保有搜索结果');
      return;
    }

    setIsGenerating(true);
    setStatus('');
    try {
      const response = await fetch(`${apiBaseUrl}/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query,
          provider,
          model_name: modelName,
          search_results: searchResults,
          api_key: apiKey || null,
          show_reasoning: showReasoning
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setResponse(data.response);
      setStatus(`生成完成！结果已保存至: ${data.saved_filepath}`);
    } catch (error) {
      console.error('Generation error:', error);
      setStatus(`生成失败: ${error.message}`);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-6">Generation</h2>
      
      <div className="grid grid-cols-12 gap-6">
        {/* Left Panel - Generation Controls */}
        <div className="col-span-4 space-y-4">
          <div className="p-4 border rounded-lg bg-white shadow-sm">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Search Results File</label>
                <select
                  value={selectedFile}
                  onChange={(e) => setSelectedFile(e.target.value)}
                  className="block w-full p-2 border rounded"
                >
                  <option value="">Select search results file...</option>
                  {searchFiles.map(file => (
                    <option key={file.id} value={file.id}>
                      {file.name}
                    </option>
                  ))}
                </select>
              </div>

              {selectedFile && (
                <>
                  <div>
                    <label className="block text-sm font-medium mb-1">Question</label>
                    <textarea
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="Enter your question..."
                      className="block w-full p-2 border rounded h-32 resize-none"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-1">Provider</label>
                    <select
                      value={provider}
                      onChange={(e) => setProvider(e.target.value)}
                      className="block w-full p-2 border rounded"
                    >
                      <option value="">Select provider...</option>
                      {Object.keys(models).map(p => (
                        <option key={p} value={p}>{p}</option>
                      ))}
                    </select>
                  </div>

                  {provider && (
                    <div>
                      <label className="block text-sm font-medium mb-1">Model</label>
                      <select
                        value={modelName}
                        onChange={(e) => setModelName(e.target.value)}
                        className="block w-full p-2 border rounded"
                      >
                        <option value="">Select model...</option>
                        {Object.entries(models[provider] || {}).map(([id, name]) => (
                          <option key={id} value={id}>
                            {id === 'deepseek-v3' ? 'DeepSeek V3' :
                             id === 'deepseek-r1' ? 'DeepSeek R1' :
                             name}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  {(provider === 'openai' || provider === 'deepseek') && (
                    <div>
                      <label className="block text-sm font-medium mb-1">API Key</label>
                      <input
                        type="password"
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        placeholder="Enter your API key..."
                        className="block w-full p-2 border rounded"
                      />
                    </div>
                  )}

                  {provider === 'deepseek' && modelName === 'deepseek-r1' && (
                    <div className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        id="showReasoning"
                        checked={showReasoning}
                        onChange={(e) => setShowReasoning(e.target.checked)}
                        className="rounded border-gray-300 text-green-500 focus:ring-green-500"
                      />
                      <label htmlFor="showReasoning" className="text-sm font-medium">
                        显示思维链过程
                      </label>
                    </div>
                  )}

                  <button
                    onClick={handleGenerate}
                    disabled={isGenerating}
                    className="w-full px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 disabled:bg-green-300"
                  >
                    {isGenerating ? 'Generating...' : 'Generate'}
                  </button>

                  {status && (
                    <div className={`p-4 rounded-lg ${
                      status.includes('失败') ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                    }`}>
                      {status}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>

        {/* Right Panel - Context and Response */}
        <div className="col-span-8">
          {selectedFile ? (
            <>
              {/* Search Results Context */}
              <div className="mb-6 p-4 border rounded-lg bg-white shadow-sm">
                <h3 className="text-xl font-semibold mb-4">Search Context</h3>
                <div className="space-y-4 max-h-[300px] overflow-y-auto">
                  {searchResults.map((result, idx) => (
                    <div key={idx} className="p-4 border rounded bg-gray-50">
                      <div className="flex justify-between items-start mb-2">
                        <span className="font-medium text-sm text-gray-500">
                          Match Score: {(result.score * 100).toFixed(1)}%
                        </span>
                        <div className="text-sm text-gray-500">
                          <div>Source: {result.metadata.source}</div>
                          <div>Page: {result.metadata.page}</div>
                        </div>
                      </div>
                      <p className="text-sm whitespace-pre-wrap">{result.text}</p>
                    </div>
                  ))}
                  {searchResults.length === 0 && (
                    <div className="text-gray-500 text-center py-4">
                      No search results available. Please perform a search first.
                    </div>
                  )}
                </div>
              </div>

              {/* Generated Response */}
              {response && (
                <div className="p-4 border rounded-lg bg-white shadow-sm">
                  <h3 className="text-xl font-semibold mb-4">Generated Response</h3>
                  <div className="p-4 border rounded bg-gray-50">
                    <p className="whitespace-pre-wrap">{response}</p>
                  </div>
                </div>
              )}
            </>
          ) : (
            <RandomImage message="Select a search results file to start generation" />
          )}
        </div>
      </div>
    </div>
  );
};

export default Generation; 