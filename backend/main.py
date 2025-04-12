import os
import json
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body, Query, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from services.loading_service import LoadingService
from services.chunking_service import ChunkingService
from services.embedding_service import EmbeddingService, EmbeddingConfig
from services.vector_store_service import VectorStoreService, VectorDBConfig
from services.search_service import SearchService
from services.parsing_service import ParsingService
import logging
from enum import Enum
from utils.config import VectorDBProvider, MILVUS_CONFIG, CHROMA_CONFIG
import pandas as pd
from pathlib import Path
from services.generation_service import GenerationService
from typing import List, Dict, Optional

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# 确保必要的目录存在
os.makedirs("temp", exist_ok=True)
os.makedirs("01-chunked-docs", exist_ok=True)
os.makedirs("02-embedded-docs", exist_ok=True)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    # allow_origins=["*"],
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 在 VectorDBProvider 枚举类中添加 CHROMA
class VectorDBProvider(str, Enum):
    MILVUS = "milvus"
    CHROMA = "chroma"  # 添加 Chroma 支持

# 在 utils/config.py 中添加 CHROMA_CONFIG
CHROMA_CONFIG = {
    "persist_directory": "chroma_db",
    "collection_metadata": {
        "hnsw_space": "cosine",
        "hnsw:M": 8,
        "hnsw:ef_construction": 100,
        "hnsw:ef": 10
    }
}

@app.post("/process")
async def process_file(
    file: UploadFile = File(...),
    loading_method: str = Form(...),
    chunking_option: str = Form(...),
    chunk_size: int = Form(1000)
):
    try:
        # 保存上传的文件
        temp_path = os.path.join("temp", file.filename)
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # 准备元数据
        metadata = {
            "filename": file.filename,
            "loading_method": loading_method,
            "original_file_size": len(content),
            "processing_date": datetime.now().isoformat(),
            "chunking_method": chunking_option,
        }
        
        loading_service = LoadingService()
        raw_text = loading_service.load_pdf(temp_path, loading_method)
        metadata["total_pages"] = loading_service.get_total_pages()
        
        page_map = loading_service.get_page_map()
        
        chunking_service = ChunkingService()
        chunks = chunking_service.chunk_text(
            raw_text, 
            chunking_option, 
            metadata,
            page_map=page_map,
            chunk_size=chunk_size
        )
        
        # 清理临时文件
        os.remove(temp_path)
        
        return {"chunks": chunks}
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        raise

@app.post("/save")
async def save_chunks(data: dict):
    try:
        doc_name = data.get("docName")
        chunks = data.get("chunks")
        metadata = data.get("metadata", {})
        
        if not doc_name or not chunks:
            raise ValueError("Missing required fields")
        
        # 构建文件名
        filename = f"{doc_name}.json"
        filepath = os.path.join("01-chunked-docs", filename)
        
        # 保存数据
        document_data = {
            "document_name": doc_name,
            "metadata": metadata,
            "chunks": chunks
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(document_data, f, ensure_ascii=False, indent=2)
        
        return {
            "status": "success",
            "message": "Document saved successfully",
            "filepath": filepath
        }
    except Exception as e:
        logger.error(f"Error saving document: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.get("/list-docs")
async def list_documents():
    try:
        docs = []
        docs_dir = "01-chunked-docs"
        for filename in os.listdir(docs_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(docs_dir, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    doc_data = json.load(f)
                    docs.append({
                        "id": filename,
                        "name": doc_data["document_name"]
                    })
        return {"documents": docs}
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise

@app.post("/embed")
async def embed_document(data: dict = Body(...)):
    try:
        doc_id = data.get("documentId")
        provider = data.get("provider")
        model = data.get("model")
        
        if not all([doc_id, provider, model]):
            raise HTTPException(status_code=400, detail="Missing required parameters")
            
        # 直接使用完整文件名查找
        loaded_path = os.path.join("01-loaded-docs", doc_id)
        chunked_path = os.path.join("01-chunked-docs", doc_id)
        
        doc_path = None
        if os.path.exists(loaded_path):
            doc_path = loaded_path
        elif os.path.exists(chunked_path):
            doc_path = chunked_path
            
        if not doc_path:
            raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")
            
        with open(doc_path, 'r', encoding='utf-8') as f:
            doc_data = json.load(f)
        
        # 创建 EmbeddingConfig 和 EmbeddingService
        config = EmbeddingConfig(provider=provider, model_name=model)
        embedding_service = EmbeddingService()
        
        # 准备输入数据
        input_data = {
            "chunks": doc_data["chunks"],
            "metadata": {
                "filename": doc_data["filename"],
                "total_chunks": doc_data["total_chunks"],
                "total_pages": doc_data["total_pages"],
                "loading_method": doc_data["loading_method"],
                "chunking_method": doc_data["chunking_method"]
            }
        }
        
        # 创建嵌入 - 只接收两个返回值
        embeddings, _ = embedding_service.create_embeddings(input_data, config)
        
        # 保存嵌入结果
        output_path = embedding_service.save_embeddings(doc_id, embeddings)
        
        return {
            "status": "success",
            "message": "Embeddings created successfully",
            "filepath": output_path,
            "embeddings": embeddings  # 添加embeddings到响应中
        }
        
    except Exception as e:
        logger.error(f"Error creating embeddings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/list-embedded")
async def list_embedded_docs():
    """List all embedded documents"""
    try:
        documents = []
        embedded_dir = "02-embedded-docs"
        logger.info(f"Scanning directory: {embedded_dir}")
        
        if not os.path.exists(embedded_dir):
            logger.warning(f"Directory {embedded_dir} does not exist")
            return {"documents": []}
            
        for filename in os.listdir(embedded_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(embedded_dir, filename)
                logger.info(f"Reading file: {file_path}")
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # 使用实际的文件名，而不是文档名
                        doc_info = {
                            "name": filename,  # 保持原始文件名
                            "metadata": {
                                "document_name": data.get("document_name", filename),
                                "embedding_model": data.get("embedding_model", ""),
                                "embedding_provider": data.get("embedding_provider", ""),
                                "embedding_timestamp": data.get("created_at", ""),
                                "vector_dimension": data.get("vector_dimension", 0)
                            }
                        }
                        logger.info(f"Added document info: {doc_info}")
                        documents.append(doc_info)
                except Exception as e:
                    logger.error(f"Error reading file {file_path}: {str(e)}")
                    
        logger.info(f"Total documents found: {len(documents)}")
        return {"documents": documents}
    except Exception as e:
        logger.error(f"Error listing embedded documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/index")
async def index_embeddings(data: dict):
    try:
        file_id = data.get("fileId")
        vector_db = data.get("vectorDb")
        index_mode = data.get("indexMode")
        
        if not all([file_id, vector_db, index_mode]):
            raise ValueError("Missing required fields")
            
        embedding_file = os.path.join("02-embedded-docs", file_id)
        if not os.path.exists(embedding_file):
            raise FileNotFoundError(f"Embedding file not found: {file_id}")
            
        config = VectorDBConfig(provider=vector_db, index_mode=index_mode)
        vector_store_service = VectorStoreService()
        result = vector_store_service.index_embeddings(embedding_file, config)
        
        return result
    except Exception as e:
        logger.error(f"Error during indexing: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.get("/providers")
async def get_providers():
    """获取支持的向量数据库列表"""
    try:
        search_service = SearchService()
        providers = search_service.get_providers()
        return {"providers": providers}
    except Exception as e:
        logger.error(f"Error getting providers: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.get("/collections")
async def get_collections(
    provider: VectorDBProvider = Query(default=VectorDBProvider.CHROMA)
):
    """获取指定向量数据库中的集合"""
    try:
        search_service = SearchService()
        collections = search_service.list_collections(provider.value)
        return {"collections": collections}
    except Exception as e:
        logger.error(f"Error getting collections: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.post("/search")
async def search(
    query: str = Body(...),
    collection_id: str = Body(...),
    top_k: int = Body(3),
    threshold: float = Body(0.7),
    word_count_threshold: int = Body(100)
):
    """执行向量搜索"""
    try:
        # Log the incoming search request details
        logger.info(f"Search request - Query: {query}, Collection: {collection_id}, Top K: {top_k}, Threshold: {threshold}, Word Count Threshold: {word_count_threshold}")
        
        search_service = SearchService()
        
        # Log before calling the search function
        logger.info("Calling search service...")
        
        results = await search_service.search(
            query=query,
            collection_id=collection_id,
            top_k=top_k,
            threshold=threshold,
            word_count_threshold=word_count_threshold
        )
        
        # Log the search results
        logger.info(f"Search response: {results}")
        
        return {"results": results}
    except Exception as e:
        logger.error(f"Error performing search: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.get("/collections/{provider}")
async def get_provider_collections(provider: str):
    """Get collections for a specific vector database provider"""
    try:
        vector_store_service = VectorStoreService()
        collections = vector_store_service.list_collections(provider)
        return {"collections": collections}
    except Exception as e:
        logger.error(f"Error getting collections for provider {provider}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.get("/collections/{provider}/{collection_name}")
async def get_collection_info(provider: str, collection_name: str):
    """Get detailed information about a specific collection"""
    try:
        vector_store_service = VectorStoreService()
        info = vector_store_service.get_collection_info(provider, collection_name)
        return info
    except Exception as e:
        logger.error(f"Error getting collection info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.delete("/collections/{provider}/{collection_name}")
async def delete_collection(provider: str, collection_name: str):
    """Delete a specific collection"""
    try:
        vector_store_service = VectorStoreService()
        success = vector_store_service.delete_collection(provider, collection_name)
        if success:
            return {"message": f"Collection {collection_name} deleted successfully"}
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to delete collection {collection_name}"
            )
    except Exception as e:
        logger.error(f"Error deleting collection: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.get("/documents")
async def get_documents(type: str = Query("all")):
    try:
        documents = []
        
        # 读取loaded文档
        if type in ["all", "loaded"]:
            loaded_dir = "01-loaded-docs"
            if os.path.exists(loaded_dir):
                for filename in os.listdir(loaded_dir):
                    if filename.endswith('.json'):
                        file_path = os.path.join(loaded_dir, filename)
                        with open(file_path, 'r', encoding='utf-8') as f:
                            doc_data = json.load(f)
                            documents.append({
                                "id": filename,
                                "name": filename,
                                "type": "loaded",
                                "metadata": {
                                    "total_pages": doc_data.get("total_pages"),
                                    "total_chunks": doc_data.get("total_chunks"),
                                    "loading_method": doc_data.get("loading_method"),
                                    "chunking_method": doc_data.get("chunking_method"),
                                    "timestamp": doc_data.get("timestamp")
                                }
                            })

        # 读取chunked文档
        if type in ["all", "chunked"]:
            chunked_dir = "01-chunked-docs"
            if os.path.exists(chunked_dir):
                for filename in os.listdir(chunked_dir):
                    if filename.endswith('.json'):
                        file_path = os.path.join(chunked_dir, filename)
                        with open(file_path, 'r', encoding='utf-8') as f:
                            doc_data = json.load(f)
                            documents.append({
                                "id": filename,
                                "name": filename,  # 保持原始文件名
                                "type": "chunked"
                            })
        
        return {"documents": documents}
    except Exception as e:
        logger.error(f"Error getting documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents/{doc_name}")
async def get_document(doc_name: str, type: str = Query("loaded")):
    try:

        base_name = doc_name.replace('.json', '')
        file_name = f"{base_name}.json"
        
        # 根据类型选择不同的目录
        directory = "01-loaded-docs" if type == "loaded" else "01-chunked-docs"
        file_path = os.path.join(directory, file_name)
        
        logger.info(f"Attempting to read document from: {file_path}")
        
        if not os.path.exists(file_path):
            logger.error(f"Document not found at path: {file_path}")
            raise HTTPException(status_code=404, detail="Document not found")
            
        with open(file_path, 'r', encoding='utf-8') as f:
            doc_data = json.load(f)
            
        return doc_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/documents/{doc_name}")
async def delete_document(doc_name: str, type: str = Query("loaded")):
    try:
        # 移除已有的 .json 扩展名（如果有）然后添加一个
        base_name = doc_name.replace('.json', '')
        file_name = f"{base_name}.json"
        
        # 根据类型选择不同的目录
        directory = "01-loaded-docs" if type == "loaded" else "01-chunked-docs"
        file_path = os.path.join(directory, file_name)
        
        logger.info(f"Attempting to delete document: {file_path}")
        
        if not os.path.exists(file_path):
            logger.error(f"Document not found at path: {file_path}")
            raise HTTPException(status_code=404, detail="Document not found")
            
        # 删除文件
        os.remove(file_path)
        
        return {
            "status": "success",
            "message": f"Document {doc_name} deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/embedded-docs/{doc_name}")
async def get_embedded_doc(doc_name: str):
    """Get specific embedded document"""
    try:
        logger.info(f"Attempting to read document: {doc_name}")
        file_path = os.path.join("02-embedded-docs", doc_name)
        
        if not os.path.exists(file_path):
            logger.error(f"Document not found: {file_path}")
            raise HTTPException(
                status_code=404,
                detail=f"Document {doc_name} not found"
            )
            
        with open(file_path, 'r', encoding='utf-8') as f:
            doc_data = json.load(f)
            logger.info(f"Successfully read document: {doc_name}")
            
            return {
                "embeddings": [
                    {
                        "embedding": embedding["embedding"],
                        "metadata": {
                            "document_name": doc_data.get("document_name", doc_name),
                            "chunk_id": idx + 1,
                            "total_chunks": len(doc_data["embeddings"]),
                            "content": embedding["metadata"].get("content", ""),
                            "page_number": embedding["metadata"].get("page_number", ""),
                            "page_range": embedding["metadata"].get("page_range", ""),
                            # "chunking_method": embedding["metadata"].get("chunking_method", ""),
                            "embedding_model": doc_data.get("embedding_model", ""),
                            "embedding_provider": doc_data.get("embedding_provider", ""),
                            "embedding_timestamp": doc_data.get("created_at", ""),
                            "vector_dimension": doc_data.get("vector_dimension", 0)
                        }
                    }
                    for idx, embedding in enumerate(doc_data["embeddings"])
                ]
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting embedded document {doc_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/embedded-docs/{doc_name}")
async def delete_embedded_doc(doc_name: str):
    """Delete specific embedded document"""
    try:
        file_path = os.path.join("02-embedded-docs", doc_name)
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=404,
                detail=f"Document {doc_name} not found"
            )
            
        os.remove(file_path)
        return {"message": f"Document {doc_name} deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting embedded document {doc_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/parse")
async def parse_file(
    file: UploadFile = File(...),
    loading_method: str = Form(...),
    parsing_option: str = Form(...)
):
    try:
        # Save uploaded file
        temp_path = os.path.join("temp", file.filename)
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Prepare metadata
        metadata = {
            "filename": file.filename,
            "loading_method": loading_method,
            "original_file_size": len(content),
            "processing_date": datetime.now().isoformat(),
            "parsing_method": parsing_option,
        }
        
        loading_service = LoadingService()
        raw_text = loading_service.load_pdf(temp_path, loading_method)
        metadata["total_pages"] = loading_service.get_total_pages()
        
        page_map = loading_service.get_page_map()
        
        parsing_service = ParsingService()
        parsed_content = parsing_service.parse_pdf(
            raw_text, 
            parsing_option, 
            metadata,
            page_map=page_map
        )
        
        # Clean up temp file
        os.remove(temp_path)
        
        return {"parsed_content": parsed_content}
    except Exception as e:
        logger.error(f"Error parsing file: {str(e)}")
        raise

@app.post("/load")
async def load_file(
    file: UploadFile = File(...),
    loading_method: str = Form(...),
    strategy: str = Form(None),
    chunking_strategy: str = Form(None),
    chunking_options: str = Form(None)
):
    try:
        # 保存上传的文件
        temp_path = os.path.join("temp", file.filename)
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # 准备元数据
        metadata = {
            "filename": file.filename,
            "total_chunks": 0,  # 将在后面更新
            "total_pages": 0,   # 将在后面更新
            "loading_method": loading_method,
            "loading_strategy": strategy,  
            "chunking_strategy": chunking_strategy, 
            "timestamp": datetime.now().isoformat()
        }
        
        # Parse chunking options if provided
        chunking_options_dict = None
        if chunking_options:
            chunking_options_dict = json.loads(chunking_options)
        
        # 使用 LoadingService 加载文档
        loading_service = LoadingService()
        raw_text = loading_service.load_pdf(
            temp_path, 
            loading_method, 
            strategy=strategy,
            chunking_strategy=chunking_strategy,
            chunking_options=chunking_options_dict
        )
        
        metadata["total_pages"] = loading_service.get_total_pages()
        
        page_map = loading_service.get_page_map()
        
        # 转换成标准化的chunks格式
        chunks = []
        for idx, page in enumerate(page_map, 1):
            chunk_metadata = {
                "chunk_id": idx,
                "page_number": page["page"],
                "page_range": str(page["page"]),
                "word_count": len(page["text"].split())
            }
            if "metadata" in page:
                chunk_metadata.update(page["metadata"])
            
            chunks.append({
                "content": page["text"],
                "metadata": chunk_metadata
            })
        
        # 使用 LoadingService 保存文档，传递strategy参数
        filepath = loading_service.save_document(
            filename=file.filename,
            chunks=chunks,
            metadata=metadata,
            loading_method=loading_method,
            strategy=strategy,
            chunking_strategy=chunking_strategy,
        )
        
        # 读取保存的文档以返回
        with open(filepath, "r", encoding="utf-8") as f:
            document_data = json.load(f)
        
        # 清理临时文件
        os.remove(temp_path)
        
        return {"loaded_content": document_data, "filepath": filepath}
    except Exception as e:
        logger.error(f"Error loading file: {str(e)}")
        raise

@app.post("/chunk")
async def chunk_document(data: dict = Body(...)):
    try:
        doc_id = data.get("doc_id")
        chunking_option = data.get("chunking_option")
        chunk_size = data.get("chunk_size", 1000)
        
        if not doc_id or not chunking_option:
            raise HTTPException(
                status_code=400, 
                detail="Missing required parameters: doc_id and chunking_option"
            )
        
        # 读取已加载的文档
        file_path = os.path.join("01-loaded-docs", doc_id)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Document not found")
            
        with open(file_path, 'r', encoding='utf-8') as f:
            doc_data = json.load(f)
            
        # 构建页面映射
        page_map = [
            {
                'page': chunk['metadata']['page_number'],
                'text': chunk['content']
            }
            for chunk in doc_data['chunks']
        ]
            
        # 准备元数据
        metadata = {
            "filename": doc_data['filename'],
            "loading_method": doc_data['loading_method'],
            "total_pages": doc_data['total_pages']
        }
            
        chunking_service = ChunkingService()
        result = chunking_service.chunk_text(
            text="",  # 不需要传递文本，因为我们使用 page_map
            method=chunking_option,
            metadata=metadata,
            page_map=page_map,
            chunk_size=chunk_size
        )
        
        # 生成输出文件名
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        base_name = doc_data['filename'].replace('.pdf', '').split('_')[0]
        output_filename = f"{base_name}_{chunking_option}_{timestamp}.json"
        
        output_path = os.path.join("01-chunked-docs", output_filename)
        os.makedirs("01-chunked-docs", exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        return result
        
    except Exception as e:
        logger.error(f"Error chunking document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/evaluate")
async def evaluate_search(
    file: UploadFile = File(...),
    collection_id: str = Form(...),
    top_k: int = Form(10),
    threshold: float = Form(0.7)
):
    try:
        # 读取CSV文件
        df = pd.read_csv(file.file)
        
        # 只合并前四列的文本内容
        df['combined_text'] = df.apply(
            lambda row: ' '.join(
                str(val) for i, val in enumerate(row) 
                if i < 4 and pd.notna(val) and val != '[]'
            ), 
            axis=1
        )
        
        # 初始化SearchService
        search_service = SearchService()
        
        results = []
        total_score_hit = 0
        total_score_find = 0
        valid_queries = 0
        
        # 处理每个查询
        for _, row in df.iterrows():
            # 跳过没有标签的行
            if pd.isna(row['LABEL']) or row['LABEL'] == '[]':
                continue
                
            try:
                # 解析标签页码列表
                label_str = str(row['LABEL']).strip('[]').replace(' ', '')
                if label_str:
                    expected_pages = [int(x.strip()) for x in label_str.split(',') if x.strip()]
                else:
                    continue
                
                # 执行搜索
                search_results = await search_service.search(
                    query=row['combined_text'],
                    collection_id=collection_id,
                    top_k=top_k,
                    threshold=threshold
                )
                
                # 提取找到的页码
                found_pages = [int(result['metadata']['page']) for result in search_results]
                
                # 计算分数
                hits = sum(1 for page in found_pages if page in expected_pages)
                score_hit = hits / len(found_pages) if found_pages else 0
                score_find = len(set(found_pages) & set(expected_pages)) / len(expected_pages)
                
                # 添加到结果列表，包括所有top_k结果的文本
                result_entry = {
                    "query": row['combined_text'],
                    "expected_pages": expected_pages,
                    "found_pages": found_pages,
                    "score_hit": score_hit,
                    "score_find": score_find
                }
                
                # 添加每个top_k结果的文本作为单独的字段
                for i, result in enumerate(search_results, 1):
                    result_entry[f"text_{i}"] = result['text']
                    result_entry[f"page_{i}"] = result['metadata']['page']
                    result_entry[f"score_{i}"] = result['score']
                
                results.append(result_entry)
                
                total_score_hit += score_hit
                total_score_find += score_find
                valid_queries += 1
                
            except Exception as e:
                logger.warning(f"Error processing row: {str(e)}")
                continue
        
        if valid_queries == 0:
            raise ValueError("No valid queries found in the CSV file")
        
        # 计算平均分数
        average_scores = {
            "score_hit": total_score_hit / valid_queries,
            "score_find": total_score_find / valid_queries
        }
        
        # 保存结果
        output_dir = Path("06-evaluation-result")
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存详细的JSON结果
        output_path = output_dir / f"evaluation_results_{timestamp}.json"
        evaluation_results = {
            "results": results,
            "average_scores": average_scores,
            "total_queries": valid_queries,
            "parameters": {
                "collection_id": collection_id,
                "top_k": top_k,
                "threshold": threshold
            }
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(evaluation_results, f, indent=2)
            
        # 保存CSV格式的结果，每个top_k结果单独一列
        results_df = pd.DataFrame(results)
        
        # 重新排列列的顺序，使其更有逻辑性
        column_order = ['query', 'expected_pages', 'found_pages', 'score_hit', 'score_find']
        for i in range(1, top_k + 1):
            column_order.extend([f'page_{i}', f'score_{i}', f'text_{i}'])
        
        # 只选择存在的列
        existing_columns = [col for col in column_order if col in results_df.columns]
        results_df = results_df[existing_columns]
        
        csv_path = output_dir / f"evaluation_results_{timestamp}.csv"
        results_df.to_csv(csv_path, index=False)
        
        return evaluation_results
        
    except Exception as e:
        logger.error(f"Error during evaluation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/save-search")
async def save_search_results(request: Request):
    try:
        data = await request.json()
        query = data.get("query")
        collection_id = data.get("collection_id")
        results = data.get("results")
        
        if not all([query, collection_id, results]):
            raise HTTPException(status_code=400, detail="Missing required parameters")
        
        # 直接创建 SearchService 实例
        search_service = SearchService()
        filepath = search_service.save_search_results(query, collection_id, results)
        return {"saved_filepath": filepath}
        
    except Exception as e:
        logger.error(f"Error saving search results: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/generation/models")
async def get_generation_models():
    """获取可用的生成模型列表"""
    try:
        generation_service = GenerationService()
        models = generation_service.get_available_models()
        return {"models": models}
    except Exception as e:
        logger.error(f"Error getting generation models: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate")
async def generate_response(
    query: str = Body(...),
    provider: str = Body(...),
    model_name: str = Body(...),
    search_results: List[Dict] = Body(...),
    api_key: Optional[str] = Body(None)
):
    """生成回答"""
    try:
        generation_service = GenerationService()
        result = generation_service.generate(
            provider=provider,
            model_name=model_name,
            query=query,
            search_results=search_results,
            api_key=api_key
        )
        return result
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/search-results")
async def list_search_results():
    """获取所有搜索结果文件列表"""
    try:
        search_results_dir = "04-search-results"
        if not os.path.exists(search_results_dir):
            return {"files": []}
            
        files = []
        for filename in os.listdir(search_results_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(search_results_dir, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    files.append({
                        "id": filename,
                        "name": f"Search: {data.get('query', 'Unknown')} ({filename})",
                        "timestamp": data.get('timestamp', '')
                    })
                    
        # 按时间戳排序，最新的在前面
        files.sort(key=lambda x: x['timestamp'], reverse=True)
        return {"files": files}
        
    except Exception as e:
        logger.error(f"Error listing search results: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/search-results/{file_id}")
async def get_search_result(file_id: str):
    """获取特定搜索结果文件的内容"""
    try:
        file_path = os.path.join("04-search-results", file_id)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Search result file not found")
            
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data
            
    except Exception as e:
        logger.error(f"Error reading search result file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 