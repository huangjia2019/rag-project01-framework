// src/App.jsx
import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import LoadFile from './pages/LoadFile';
import ChunkFile from './pages/ChunkFile';
import EmbeddingFile from './pages/EmbeddingFile';
import Indexing from './pages/Indexing';
import Search from './pages/Search';
import ParseFile from './pages/ParseFile';
import ParseMDFile from './pages/ParseMDFile';
import Generation from './pages/Generation';

const App = () => {
  return (
    <Router>
      <div className="flex">
        <Sidebar />
        <main className="ml-64 flex-1 min-h-screen bg-gray-100">
          <Routes>
            <Route path="/load-file" element={<LoadFile />} />  
            <Route path="/chunk-file" element={<ChunkFile />} />  
            <Route path="/parse-file" element={<ParseFile />} />
            <Route path="/parse-md-file" element={<ParseMDFile />} />
            <Route path="/embedding" element={<EmbeddingFile />} />
            <Route path="/indexing" element={<Indexing />} />
            <Route path="/search" element={<Search />} />
            <Route path="/generation" element={<Generation />} />
            <Route path="/" element={<LoadFile />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
};

export default App;