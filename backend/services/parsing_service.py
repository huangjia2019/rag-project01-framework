import logging
from typing import Dict, List
import fitz  # PyMuPDF
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)

class ParsingService:
    """
    PDF文档解析服务类
    
    该类提供多种解析策略来提取和构建PDF文档内容，包括：
    - 全文提取
    - 逐页解析
    - 基于标题的分段
    - 文本和表格混合解析
    """

    def parse_pdf(self, text: str, method: str, metadata: dict, page_map: list = None) -> dict:
        """
        使用指定方法解析PDF文档

        参数:
            text (str): PDF文档的文本内容
            method (str): 解析方法 ('all_text', 'by_pages', 'by_titles', 或 'text_and_tables')
            metadata (dict): 文档元数据，包括文件名和其他属性
            page_map (list): 包含每页内容和元数据的字典列表

        返回:
            dict: 解析后的文档数据，包括元数据和结构化内容

        异常:
            ValueError: 当page_map为空或指定了不支持的解析方法时抛出
        """
        try:
            if not page_map:
                raise ValueError("Page map is required for parsing.")
            
            parsed_content = []
            total_pages = len(page_map)
            
            if method == "all_text":
                parsed_content = self._parse_all_text(page_map)
            elif method == "by_pages":
                parsed_content = self._parse_by_pages(page_map)
            elif method == "by_titles":
                parsed_content = self._parse_by_titles(page_map)
            elif method == "text_and_tables":
                parsed_content = self._parse_text_and_tables(page_map)
            else:
                raise ValueError(f"Unsupported parsing method: {method}")
                
            # Create document-level metadata
            document_data = {
                "metadata": {
                    "filename": metadata.get("filename", ""),
                    "total_pages": total_pages,
                    "parsing_method": method,
                    "timestamp": datetime.now().isoformat()
                },
                "content": parsed_content
            }
            
            return document_data
            
        except Exception as e:
            logger.error(f"Error in parse_pdf: {str(e)}")
            raise

    def _parse_all_text(self, page_map: list) -> list:
        """
        将文档中的所有文本内容提取为连续流

        参数:
            page_map (list): 包含每页内容的字典列表

        返回:
            list: 包含带页码的文本内容的字典列表
        """
        return [{
            "type": "Text",
            "content": page["text"],
            "page": page["page"]
        } for page in page_map]

    def _parse_by_pages(self, page_map: list) -> list:
        """
        逐页解析文档，保持页面边界

        参数:
            page_map (list): 包含每页内容的字典列表

        返回:
            list: 包含带页码的分页内容的字典列表
        """
        parsed_content = []
        for page in page_map:
            parsed_content.append({
                "type": "Page",
                "page": page["page"],
                "content": page["text"]
            })
        return parsed_content

    def _parse_by_titles(self, page_map: list) -> list:
        """
        通过识别标题来解析文档并将内容组织成章节

        使用简单的启发式方法识别标题：
        长度小于60个字符且全部大写的行被视为章节标题

        参数:
            page_map (list): 包含每页内容的字典列表

        返回:
            list: 包含带标题和页码的分章节内容的字典列表
        """
        parsed_content = []
        current_title = None
        current_content = []

        for page in page_map:
            lines = page["text"].split('\n')
            for line in lines:
                # Simple heuristic: consider lines with less than 60 chars and all caps as titles
                if len(line.strip()) < 60 and line.isupper():
                    if current_title:
                        parsed_content.append({
                            "type": "section",
                            "title": current_title,
                            "content": '\n'.join(current_content),
                            "page": page["page"]
                        })
                    current_title = line.strip()
                    current_content = []
                else:
                    current_content.append(line)

        # Add the last section
        if current_title:
            parsed_content.append({
                "type": "section",
                "title": current_title,
                "content": '\n'.join(current_content),
                "page": page["page"]
            })

        return parsed_content

    def _parse_text_and_tables(self, page_map: list) -> list:
        """
        通过分离文本和表格内容来解析文档

        使用基本的表格检测启发式方法（存在'|'或制表符）
        来识别潜在的表格内容

        参数:
            page_map (list): 包含每页内容的字典列表

        返回:
            list: 包含分离的文本和表格内容（带页码）的字典列表
        """
        parsed_content = []
        for page in page_map:
            # Extract tables using tabula-py or similar library
            # For this example, we'll just simulate table detection
            content = page["text"]
            if '|' in content or '\t' in content:
                parsed_content.append({
                    "type": "table",
                    "content": content,
                    "page": page["page"]
                })
            else:
                parsed_content.append({
                    "type": "text",
                    "content": content,
                    "page": page["page"]
                })
        return parsed_content 