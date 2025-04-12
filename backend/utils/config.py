from enum import Enum
from typing import Dict, Any

class VectorDBProvider(str, Enum):
    MILVUS = "milvus"
    CHROMA = "chroma"
    # More providers can be added later

# 可以在这里添加其他配置相关的内容
MILVUS_CONFIG = {
    "uri": "03-vector-store/langchain_milvus.db",
    "index_types": {
        "flat": "FLAT",
        "ivf_flat": "IVF_FLAT",
        "ivf_sq8": "IVF_SQ8",
        "hnsw": "HNSW"
    },
    "index_params": {
        "flat": {},
        "ivf_flat": {"nlist": 1024},
        "ivf_sq8": {"nlist": 1024},
        "hnsw": {
            "M": 16,
            "efConstruction": 500
        }
    }
}

# 添加 Chroma 配置
CHROMA_CONFIG = {
    "uri": "03-vector-store/chroma_db",  #  持久化数据库的路径， 对应 MILVUS_CONFIG 的 uri
    "collection_metadata": { 
        "hnsw_space": "cosine",
        "hnsw:M": 8,
        "hnsw:ef_construction": 100,
        "hnsw:ef": 10
    },
    "index_types": {  #  对应 MILVUS_CONFIG 的 index_types， 这里代表 embedding function 的类型
        "default": "custom"  #  使用用户自定义的 embedding function,  类型名称改为 "custom" 更清晰
    },
    "index_params": {  # 对应 MILVUS_CONFIG 的 index_params， 这里是 embedding function 的参数
        "default": {}  #  自定义 embedding function  通常无需配置参数，  保留空字典
    }
} 
