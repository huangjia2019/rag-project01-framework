import os
from datetime import datetime
import json
from typing import List, Dict, Any
import logging
import hashlib
from pathlib import Path
from pymilvus import connections, utility
from pymilvus import Collection, DataType, FieldSchema, CollectionSchema
from utils.config import VectorDBProvider, MILVUS_CONFIG, CHROMA_CONFIG  # Updated import
import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

class VectorDBConfig:
    """
    向量数据库配置类，用于存储和管理向量数据库的配置信息
    """
    def __init__(self, provider="chroma", index_mode: str = "default"):
        """
        初始化向量数据库配置
        """
        self.provider = provider  # 固定为 Chroma
        self.index_mode = index_mode
        if provider == "milvus":
            self.milvus_uri = MILVUS_CONFIG["uri"]
            self.db_config = MILVUS_CONFIG
        else:
            self.milvus_uri = None 
            self.db_config = CHROMA_CONFIG

    @property
    def uri(self):
        return self.db_config.get("uri")

    def _get_index_type(self, index_mode: str) -> str:
        return self.db_config.get("index_types", {}).get(index_mode, "default")

    def _get_index_params(self, index_mode: str) -> Dict[str, Any]:
        return self.db_config.get("index_params", {}).get(index_mode, {})

class VectorStoreService:
    """
    向量存储服务类，提供向量数据的索引、查询和管理功能（仅支持 ChromaDB）
    """
    def __init__(self):
        os.makedirs("03-vector-store", exist_ok=True)
    
    def _get_milvus_index_type(self, config: VectorDBConfig) -> str:
        return config._get_milvus_index_type(config.index_mode)
    
    def _get_milvus_index_params(self, config: VectorDBConfig) -> Dict[str, Any]:
        return config._get_milvus_index_params(config.index_mode)
    
    def _init_chroma_client(self):
        client = chromadb.Client(Settings(
            persist_directory=CHROMA_CONFIG["persist_directory"],
            anonymized_telemetry=False
        ))
        return client

    def index_embeddings(self, embedding_file: str, config: VectorDBConfig) -> Dict[str, Any]:
        """
        将嵌入向量索引到 ChromaDB
        """
        logger.info(f"[index_embeddings]file: {embedding_file} | config: {config}")
        start_time = datetime.now()
        embeddings_data = self._load_embeddings(embedding_file)
        
        # 根据不同的数据库进行索引
        if config.provider == VectorDBProvider.MILVUS:
            result = self._index_to_milvus(embeddings_data, config)
        elif config.provider == VectorDBProvider.CHROMA:
            result = self._index_to_chroma(embeddings_data, config)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        return {
            "database": config.provider,
            "total_vectors": len(embeddings_data["embeddings"]),
            "index_size": result.get("index_size", "N/A"),
            "processing_time": (datetime.now() - start_time).total_seconds(),
            "collection_name": result.get("collection_name", "N/A")
        }

    def _load_embeddings(self, file_path: str) -> Dict[str, Any]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, dict) or "embeddings" not in data:
                    raise ValueError("Invalid embedding file format")
                return data
        except Exception as e:
            logger.error(f"Error loading embeddings: {str(e)}")
            raise

    def _index_to_chroma(self, embeddings_data: Dict[str, Any], config: VectorDBConfig) -> Dict[str, Any]:
        try:
            logger.info(f'[vector_store_service][config]URI:{config.uri}')
            # 客户端配置
            client = chromadb.PersistentClient(
                path=config.uri
            )

            # 生成集合名称
            filename = embeddings_data.get("filename", "").replace('.pdf', '')
            #hash file name here 
            hasher = hashlib.sha256(filename.encode('utf-8') if filename else b'')
            filename = hasher.hexdigest()[:8]  # 使用前8位作为简短哈希
            base_name = f"chroma_{filename}" if filename and not filename[0].isalpha() else filename
            collection_name = f"{base_name}_{embeddings_data.get('embedding_provider', 'unknown')}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # 准备数据
            print(f"collection_name: >>> {collection_name}")
            collection = client.get_or_create_collection(collection_name)
            documents, metadatas, ids, vectors = [], [], [], []

            for i, emb in enumerate(embeddings_data["embeddings"]):
                documents.append(str(emb["metadata"].get("content", "")))
                metadatas.append({
                    "document_name": embeddings_data.get("filename", ""),
                    "chunk_id": emb["metadata"].get("chunk_id", 0),
                    "page_number": str(emb["metadata"].get("page_number", 0)),
                    "word_count": emb["metadata"].get("word_count", 0),
                    "embedding_provider": embeddings_data.get("embedding_provider", ""),
                    "embedding_model": embeddings_data.get("embedding_model", ""),
                })
                ids.append(f"doc_{base_name}_chunk_{i}")
                vectors.append([float(x) for x in emb.get("embedding", [])])

            # 插入数据
            collection.add(
                embeddings=vectors,
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            # client.persist()

            return {
                "index_size": collection.count(),
                "collection_name": collection_name
            }

        except Exception as e:
            logger.error(f"ChromaDB indexing error: {str(e)}")
            raise

    def _index_to_milvus(self, embeddings_data: Dict[str, Any], config: VectorDBConfig) -> Dict[str, Any]:
        try:
            # 使用 filename 作为 collection 名称前缀
            filename = embeddings_data.get("filename", "")
            # 如果有 .pdf 后缀，移除它
            base_name = filename.replace('.pdf', '') if filename else "doc"
            
            # Ensure the collection name starts with a letter or underscore
            if not base_name[0].isalpha() and base_name[0] != '_':
                base_name = f"_{base_name}"
            
            # Get embedding provider
            embedding_provider = embeddings_data.get("embedding_provider", "unknown")
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            collection_name = f"{base_name}_{embedding_provider}_{timestamp}"
            
            # 连接到Milvus
            connections.connect(
                alias="default", 
                uri=config.milvus_uri
            )
            
            # 从顶层配置获取向量维度
            vector_dim = int(embeddings_data.get("vector_dimension"))
            if not vector_dim:
                raise ValueError("Missing vector_dimension in embedding file")
            
            logger.info(f"Creating collection with dimension: {vector_dim}")
            
            # 定义字段
            fields = [
                {"name": "id", "dtype": "INT64", "is_primary": True, "auto_id": True},
                {"name": "content", "dtype": "VARCHAR", "max_length": 5000},
                {"name": "document_name", "dtype": "VARCHAR", "max_length": 255},
                {"name": "chunk_id", "dtype": "INT64"},
                {"name": "total_chunks", "dtype": "INT64"},
                {"name": "word_count", "dtype": "INT64"},
                {"name": "page_number", "dtype": "VARCHAR", "max_length": 10},
                {"name": "page_range", "dtype": "VARCHAR", "max_length": 10},
                # {"name": "chunking_method", "dtype": "VARCHAR", "max_length": 50},
                {"name": "embedding_provider", "dtype": "VARCHAR", "max_length": 50},
                {"name": "embedding_model", "dtype": "VARCHAR", "max_length": 50},
                {"name": "embedding_timestamp", "dtype": "VARCHAR", "max_length": 50},
                {
                    "name": "vector",
                    "dtype": "FLOAT_VECTOR",
                    "dim": vector_dim,
                    "params": self._get_milvus_index_params(config)
                }
            ]
            
            # 准备数据为列表格式
            entities = []
            for emb in embeddings_data["embeddings"]:
                entity = {
                    "content": str(emb["metadata"].get("content", "")),
                    "document_name": embeddings_data.get("filename", ""),  # 使用 filename 而不是 document_name
                    "chunk_id": int(emb["metadata"].get("chunk_id", 0)),
                    "total_chunks": int(emb["metadata"].get("total_chunks", 0)),
                    "word_count": int(emb["metadata"].get("word_count", 0)),
                    "page_number": str(emb["metadata"].get("page_number", 0)),
                    "page_range": str(emb["metadata"].get("page_range", "")),
                    # "chunking_method": str(emb["metadata"].get("chunking_method", "")),
                    "embedding_provider": embeddings_data.get("embedding_provider", ""),  # 从顶层配置获取
                    "embedding_model": embeddings_data.get("embedding_model", ""),  # 从顶层配置获取
                    "embedding_timestamp": str(emb["metadata"].get("embedding_timestamp", "")),
                    "vector": [float(x) for x in emb.get("embedding", [])]
                }
                entities.append(entity)
            
            logger.info(f"Creating Milvus collection: {collection_name}")
            
            # 创建collection
            # field_schemas = [
            #     FieldSchema(name=field["name"], 
            #                dtype=getattr(DataType, field["dtype"]),
            #                is_primary="is_primary" in field and field["is_primary"],
            #                auto_id="auto_id" in field and field["auto_id"],
            #                max_length=field.get("max_length"),
            #                dim=field.get("dim"),
            #                params=field.get("params"))
            #     for field in fields
            # ]

            field_schemas = []
            for field in fields:
                extra_params = {}
                if field.get('max_length') is not None:
                    extra_params['max_length'] = field['max_length']
                if field.get('dim') is not None:
                    extra_params['dim'] = field['dim']
                if field.get('params') is not None:
                    extra_params['params'] = field['params']
                field_schema = FieldSchema(
                    name=field["name"], 
                    dtype=getattr(DataType, field["dtype"]),
                    is_primary=field.get("is_primary", False),
                    auto_id=field.get("auto_id", False),
                    **extra_params
                )
                field_schemas.append(field_schema)

            schema = CollectionSchema(fields=field_schemas, description=f"Collection for {collection_name}")
            collection = Collection(name=collection_name, schema=schema)
            
            # 插入数据
            logger.info(f"Inserting {len(entities)} vectors")
            insert_result = collection.insert(entities)
            
            # 创建索引
            index_params = {
                "metric_type": "COSINE",
                "index_type": self._get_milvus_index_type(config),
                "params": self._get_milvus_index_params(config)
            }
            collection.create_index(field_name="vector", index_params=index_params)
            collection.load()
            
            return {
                "index_size": len(insert_result.primary_keys),
                "collection_name": collection_name
            }
            
        except Exception as e:
            logger.error(f"Error indexing to Milvus: {str(e)}")
            raise
        
        finally:
            connections.disconnect("default")

    def list_collections(self, vector_provider) -> List[str]:
        """列出所有 Chroma 集合"""
        try:
            import chromadb
            client = chromadb.PersistentClient(
                path=CHROMA_CONFIG["uri"]
            )
            return [col.name for col in client.list_collections()]
        except Exception as e:
            logger.error(f"Error listing collections: {str(e)}")
            return []

    def delete_collection(self, provider: str, collection_name: str) -> bool:
        """删除指定集合"""
        try:
            import chromadb
            client = chromadb.PersistentClient(
                path=CHROMA_CONFIG["uri"]
            )
            client.delete_collection(collection_name)
            return True
        except Exception as e:
            logger.error(f"Error deleting collection: {str(e)}")
            return False

    def get_collection_info(self, provider: str, collection_name: str) -> Dict[str, Any]:
        """获取集合信息"""
        try:
            import chromadb
            client = chromadb.PersistentClient(
                path=CHROMA_CONFIG["uri"]
            )
            col = client.get_collection(collection_name)
            return {
                "name": col.name,
                "num_entities": col.count(),
                "metadata": col.metadata
            }
        except Exception as e:
            logger.error(f"Error getting collection info: {str(e)}")
            return {}