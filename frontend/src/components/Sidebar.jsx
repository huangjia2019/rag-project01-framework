// src/components/Sidebar.jsx
import React from 'react';
import { Link, useLocation } from 'react-router-dom';

const Sidebar = () => {
  const location = useLocation();
  const links = [
    { to: "/load-file", text: "Load File" },
    { to: "/chunk-file", text: "Chunk File" },
    { to: "/parse-file", text: "Parse File" },
    { to: "/parse-md-file", text: "PDF to Markdown" },
    { to: "/embedding", text: "Embedding File" },
    { to: "/indexing", text: "Indexing with Vector DB" },
    { to: "/search", text: "Similarity Search" },
    { to: "/generation", text: "Generation" }
  ];

  return (
    <div className="w-64 bg-gray-800 h-screen fixed left-0 top-0">
      <div className="p-4">
        <img 
          src="https://q6.itc.cn/q_70/images01/20240915/c60feb0f78bb42ebb916a4d92ecf660b.jpeg" 
          alt="Logo" 
          className="w-full mb-6 rounded"
        />
      </div>
      <nav>
        {links.map(link => (
          <Link
            key={link.to}
            to={link.to}
            className={`block px-4 py-3 text-gray-300 hover:bg-gray-700 ${
              location.pathname === link.to ? 'bg-gray-700' : ''
            }`}
          >
            {link.text}
          </Link>
        ))}
      </nav>
    </div>
  );
};

export default Sidebar;