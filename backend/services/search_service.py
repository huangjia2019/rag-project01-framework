from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
from services.embedding_service import EmbeddingService, EmbeddingProvider, EmbeddingFactory, EmbeddingConfig
from utils.config import VectorDBProvider, CHROMA_CONFIG
import chromadb
from chromadb.config import Settings
from langchain.vectorstores import Chroma
import os
import json

logger = logging.getLogger(__name__)

class SearchService:
    """
    搜索服务类，负责向量数据库的连接和向量搜索功能
    提供集合列表查询、向量相似度搜索和搜索结果保存等功能
    """
    def __init__(self):
        """
        初始化搜索服务
        创建嵌入服务实例，设置搜索结果保存目录
        """
        self.embedding_service = EmbeddingService()
        self.search_results_dir = "04-search-results"
        self.chroma_uri = CHROMA_CONFIG["uri"]
        os.makedirs(self.search_results_dir, exist_ok=True)

    def get_providers(self) -> List[Dict[str, str]]:
        """
        获取支持的向量数据库列表
        
        Returns:
            List[Dict[str, str]]: 支持的向量数据库提供商列表
        """
        return [
            {"id": VectorDBProvider.CHROMA.value, "name":"Chroma DB"},{"id": VectorDBProvider.MILVUS.value, "name":"Milvus DB"}
        ]  # 返回空列表，移除Milvus支持

    def list_collections(self, provider: str = VectorDBProvider.CHROMA.value) -> List[Dict[str, Any]]:
        """
        获取Chroma数据库中的所有集合
        
        Args:
            provider (str): 向量数据库提供商，固定为chroma
            
        Returns:
            List[Dict[str, Any]]: 集合信息列表，包含id、名称和文档数量
        """
        try:

            # 连接到Chroma
            client = chromadb.PersistentClient(
                path=CHROMA_CONFIG["uri"]
            )
            
            collections = []
            for collection in client.list_collections():
                try:
                    collections.append({
                        "id": collection.name,
                        "name": collection.name,
                        "count": collection.count(),
                        "metadata": collection.metadata
                    })
                except Exception as e:
                    logger.error(f"Error getting info for collection {collection.name}: {str(e)}")
            
            return collections
            
        except Exception as e:
            logger.error(f"Error listing Chroma collections: {str(e)}")
            raise

    def save_search_results(self, query: str, collection_id: str, results: List[Dict[str, Any]]) -> str:
        """
        保存搜索结果到JSON文件
        
        Args:
            query (str): 搜索查询文本
            collection_id (str): 集合ID
            results (List[Dict[str, Any]]): 搜索结果列表
            
        Returns:
            str: 保存文件的路径
            
        Raises:
            Exception: 保存文件时发生错误
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            # 使用集合ID的基础名称（去掉路径相关字符）
            collection_base = os.path.basename(collection_id)
            filename = f"search_{collection_base}_{timestamp}.json"
            filepath = os.path.join(self.search_results_dir, filename)
            
            search_data = {
                "query": query,
                "collection_id": collection_id,
                "timestamp": datetime.now().isoformat(),
                "results": results
            }
            
            logger.info(f"Saving search results to: {filepath}")
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(search_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Successfully saved search results to: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error saving search results: {str(e)}")
            raise

    async def search(self, 
                    query: str, 
                    collection_id: str, 
                    top_k: int = 3, 
                    threshold: float = 0.7,
                    word_count_threshold: int = 20,
                    save_results: bool = False) -> Dict[str, Any]:
        """
        执行向量搜索
        
        Args:
            query (str): 搜索查询文本
            collection_id (str): 要搜索的集合ID
            top_k (int): 返回的最大结果数量，默认为3
            threshold (float): 相似度阈值，低于此值的结果将被过滤，默认为0.7
            word_count_threshold (int): 文本字数阈值，低于此值的结果将被过滤，默认为20
            save_results (bool): 是否保存搜索结果，默认为False
            
        Returns:
            Dict[str, Any]: 包含搜索结果的字典，如果保存结果则包含保存路径
            
        Raises:
            Exception: 搜索过程中发生错误
        """
        try:
            # 添加参数日志
            logger.info(f"Search parameters:")
            logger.info(f"- Query: {query}")
            logger.info(f"- Collection ID: {collection_id}")
            logger.info(f"- Top K: {top_k}")
            logger.info(f"- Threshold: {threshold}")
            logger.info(f"- Word Count Threshold: {word_count_threshold}")
            logger.info(f"- Save Results: {save_results} (type: {type(save_results)})")

            logger.info(f"Starting search with parameters - Collection: {collection_id}, Query: {query}, Top K: {top_k}")
            

            # 连接到 Chroma
            logger.info(f"Connecting to Chroma at {self.chroma_uri}")
            
            embedding_config = EmbeddingConfig(EmbeddingProvider.OPENAI, 'text-embedding-3-large')
            embedding=EmbeddingFactory().create_embedding_function(embedding_config)
            chroma_client = Chroma(
                persist_directory=self.chroma_uri,
                embedding_function=embedding,
                collection_name=collection_id
                )
            logger.info("Successfully connected to Chroma")
            
            #get a record from chroma_client
            first = chroma_client.get()
            
            embedding_provider = first["metadatas"][0]["embedding_provider"]
            embedding_model = first["metadatas"][0]["embedding_model"]
            logger.info(f"[SearchService]{embedding_provider} | {embedding_model}")
            # 获取collection
            logger.info(f"Loading collection: {collection_id}")
            ## Create correct embedding method for Chroma
            embedding_config = EmbeddingConfig(embedding_provider, embedding_model)
            embedding=EmbeddingFactory().create_embedding_function(embedding_config)
            chroma_client = Chroma(
                persist_directory=self.chroma_uri,
                embedding_function=embedding,
                collection_name=collection_id
                )

            results = chroma_client.similarity_search_with_score(query = query, k=10)

            logger.info(f"query result: {results}")
            
            # 处理结果
            processed_results = []
            logger.info(f"Raw search results count: {len(results)}")
            # 获取所有的分数

            logger.info(f'get all scores from result')
            scores = [score for _, score in results]
            min_score = min(scores)
            max_score = max(scores)

            for doc, score in results:
                # 将余弦距离转换为相似度分数（假设使用余弦相似度）
                similarity_score = score  # 当distance是余弦距离时，1-distance即为相似度
                
                #归一化分数
                normalized_score = 1 - (similarity_score - min_score) / (max_score - min_score)

                # 解析元数据
                metadata = doc.metadata
                page_content = doc.page_content
                
                logger.info(f"Processing result - Score: {normalized_score:.4f}")
                
                processed_results.append({
                    "text": page_content,
                    "score": float(normalized_score),
                    "metadata": {
                        "source": metadata.get('document_name', 'Unknown'),
                        "page": metadata.get('page_number', 'N/A'),
                        "chunk": metadata.get('chunk_id', -1),
                        "total_chunks": metadata.get('total_chunks', -1),
                        "page_range": metadata.get('page_range', ''),
                        "word_count": metadata.get('word_count', 0),
                        "embedding_provider": metadata.get('embedding_provider', 'unknown'),
                        "embedding_model": metadata.get('embedding_model', 'unknown'),
                        "embedding_timestamp": metadata.get('embedding_timestamp', '')
                    }
                })


            all_score = [item["score"]  for item in processed_results]
            logger.info(f"All new scores: [{all_score}]")
            # 应用过滤条件
            filtered_results = [
                result for result in processed_results
                if result['score'] >= threshold 
                and result['metadata']['word_count'] >= word_count_threshold
            ]

            # 取top_k结果
            final_results = sorted(filtered_results, key=lambda x: x['score'], reverse=True)[:top_k]

            response_data = {"results": final_results}  # 取top_k结果
            
            # 添加详细的保存逻辑日志
            logger.info(f"Preparing to handle save_results (flag: {save_results})")
            if save_results:
                logger.info("Save results is True, attempting to save...")
                if processed_results:
                    try:
                        filepath = self.save_search_results(query, collection_id, processed_results)
                        logger.info(f"Successfully saved results to: {filepath}")
                        response_data["saved_filepath"] = filepath
                    except Exception as e:
                        logger.error(f"Error saving results: {str(e)}")
                        response_data["save_error"] = str(e)
                        raise  # 添加这行来查看完整的错误堆栈
                else:
                    logger.info("No results to save")
            else:
                logger.info("Save results is False, skipping save")
            
            return response_data
            
        except Exception as e:
            logger.error(f"Error performing search: {str(e)}")
            raise
        finally:
            print("search end")