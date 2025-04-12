import os
from datetime import datetime
from enum import Enum
import json
from typing import List, Dict, Any
import logging
from pathlib import Path

from langchain_milvus import Milvus
from pymilvus import connections, utility

logger = logging.getLogger(__name__)

class VectorDBProvider(str, Enum):
    """向量数据库提供商枚举类"""
    MILVUS = "milvus"
    # ... 其他数据库待添加

class VectorDBConfig:
    """向量数据库配置类"""
    def __init__(self, provider: str, index_mode: str):
        """
        初始化向量数据库配置
        
        参数:
            provider: 数据库提供商
            index_mode: 索引模式
        """
        self.provider = provider
        self.index_mode = index_mode
        self.milvus_uri = "03-vector-store/langchain_milvus.db"

class VectorStoreService:
    """向量存储服务类，用于管理向量数据的索引和检索"""
    def __init__(self):
        """初始化向量存储服务"""
        self.initialized_dbs = {}
        # 确保存储目录存在
        os.makedirs("03-vector-store", exist_ok=True)
    
    def index_embeddings(self, embedding_file: str, config: VectorDBConfig) -> Dict[str, Any]:
        """
        将嵌入向量索引到向量数据库
        
        参数:
            embedding_file: 嵌入向量文件路径
            config: 向量数据库配置
            
        返回:
            包含索引结果信息的字典
        """
        start_time = datetime.now()
        
        # 读取embedding文件
        embeddings = self._load_embeddings(embedding_file)
        
        # 根据不同的数据库进行索引
        if config.provider == VectorDBProvider.MILVUS:
            result = self._index_to_milvus(embeddings, config)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        return {
            "database": config.provider,
            "index_mode": config.index_mode,
            "total_vectors": len(embeddings),
            "index_size": result.get("index_size", "N/A"),
            "processing_time": processing_time,
            "collection_name": result.get("collection_name", "N/A")
        }
    
    def _load_embeddings(self, file_path: str) -> List[Dict[str, Any]]:
        """
        从文件加载嵌入向量
        
        参数:
            file_path: 嵌入向量文件路径
            
        返回:
            嵌入向量列表
            
        异常:
            如果文件格式无效或读取失败，抛出异常
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"Loading embeddings from {file_path}")
                
                if not isinstance(data, dict) or "embeddings" not in data:
                    raise ValueError("Invalid embedding file format: missing 'embeddings' key")
                    
                embeddings = data["embeddings"]
                logger.info(f"Found {len(embeddings)} embeddings")
                return embeddings
                
        except Exception as e:
            logger.error(f"Error loading embeddings from {file_path}: {str(e)}")
            raise
    
    def _index_to_milvus(self, embeddings: List[Dict], config: VectorDBConfig) -> Dict[str, Any]:
        """
        将嵌入向量索引到Milvus数据库
        
        参数:
            embeddings: 嵌入向量列表
            config: 向量数据库配置
            
        返回:
            包含索引结果的字典
            
        异常:
            如果索引过程中出现错误，抛出异常
        """
        try:
            # 准备collection名称
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            collection_name = f"doc_{timestamp}"
            
            # 连接到Milvus
            connections.connect(
                alias="default", 
                uri=config.milvus_uri
            )
            
            # 获取第一个embedding的维度
            first_embedding = embeddings[0].get("metadata", {}).get("vector_dimension")
            if not first_embedding:
                raise ValueError("Missing vector dimension in embedding metadata")
            
            # 准备schema
            vector_schema = {
                "dim": first_embedding,
                "index_type": self._get_milvus_index_type(config.index_mode),
                "metric_type": "COSINE",
                "params": self._get_milvus_index_params(config.index_mode)
            }
            
            # 准备数据
            texts = []
            vectors = []
            metadatas = []
            
            for emb in embeddings:
                metadata = emb.get("metadata", {})
                texts.append(metadata.get("content", ""))
                vectors.append(emb.get("embedding", []))
                metadatas.append({
                    "document_name": metadata.get("document_name", ""),
                    "chunk_id": metadata.get("chunk_id", 0),
                    "total_chunks": metadata.get("total_chunks", 0),
                    "page_number": metadata.get("page_number", 0),
                    "page_range": metadata.get("page_range", ""),
                    "chunking_method": metadata.get("chunking_method", ""),
                    "content": metadata.get("content", ""),
                    "embedding_provider": metadata.get("embedding_provider", ""),
                    "embedding_model": metadata.get("embedding_model", ""),
                    "embedding_timestamp": metadata.get("embedding_timestamp", "")
                })
            
            logger.info(f"Indexing {len(vectors)} vectors to Milvus")
            
            # 创建Milvus实例并添加embeddings
            vector_store = Milvus(
                collection_name=collection_name,
                connection_args={"uri": config.milvus_uri},
                embedding_function=None,  # 我们已经有了embeddings，不需要embedding function
                index_params=vector_schema,
                search_params={"metric_type": "COSINE"},
                consistency_level="Strong"
            )
            
            # 添加embeddings
            ids = vector_store.add_embeddings(
                texts=texts,
                embeddings=vectors,
                metadatas=metadatas,
                batch_size=100
            )
            
            logger.info(f"Successfully indexed {len(ids)} vectors")
            
            return {
                "index_size": len(ids),
                "collection_name": collection_name
            }
            
        except Exception as e:
            logger.error(f"Error indexing to Milvus: {str(e)}")
            raise
        
        finally:
            connections.disconnect("default")
    
    def _get_milvus_index_type(self, index_mode: str) -> str:
        """
        根据索引模式获取Milvus索引类型
        
        参数:
            index_mode: 索引模式
            
        返回:
            Milvus索引类型字符串
        """
        index_types = {
            "flat": "FLAT",
            "ivf_flat": "IVF_FLAT",
            "ivf_sq8": "IVF_SQ8",
            "hnsw": "HNSW"
        }
        return index_types.get(index_mode, "FLAT")
    
    def _get_milvus_index_params(self, index_mode: str) -> Dict[str, Any]:
        """
        根据索引模式获取Milvus索引参数
        
        参数:
            index_mode: 索引模式
            
        返回:
            索引参数字典
        """
        params = {
            "flat": {},
            "ivf_flat": {"nlist": 1024},
            "ivf_sq8": {"nlist": 1024},
            "hnsw": {
                "M": 16,
                "efConstruction": 500
            }
        }
        return params.get(index_mode, {})