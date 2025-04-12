import os
import json
from datetime import datetime
from typing import List, Dict, Optional
import logging
from pathlib import Path
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
from openai import OpenAI
import requests

logger = logging.getLogger(__name__)

class GenerationService:
    """
    生成服务类：负责调用不同的模型提供商（HuggingFace、OpenAI、DeepSeek）生成回答
    支持本地模型和API调用，并将生成结果保存到文件
    """
    def __init__(self):
        """
        初始化生成服务，配置支持的模型列表和创建输出目录
        """
        self.models = {
            "huggingface": {
                "Llama-2-7b-chat": "meta-llama/Llama-2-7b-chat-hf",
                "DeepSeek-7b": "deepseek-ai/deepseek-llm-7b-chat",
                "DeepSeek-R1-Distill-Qwen": "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"
            },
            "openai": {
                "gpt-3.5-turbo": "gpt-3.5-turbo",
                "gpt-4": "gpt-4",
            },
            "deepseek": {
                "deepseek-v3": "deepseek-chat",
                "deepseek-r1": "deepseek-reasoner",
            }
        }
        
        # 确保输出目录存在
        os.makedirs("05-generation-results", exist_ok=True)
        
    def _load_huggingface_model(self, model_name: str):
        """
        加载HuggingFace模型
        
        参数:
            model_name: 模型名称，对应self.models["huggingface"]中的键
            
        返回:
            model: 加载的模型
            tokenizer: 对应的分词器
        """
        try:
            model = AutoModelForCausalLM.from_pretrained(
                self.models["huggingface"][model_name],
                torch_dtype=torch.float16,
                device_map="auto"
            )
            tokenizer = AutoTokenizer.from_pretrained(
                self.models["huggingface"][model_name]
            )
            return model, tokenizer
        except Exception as e:
            logger.error(f"Error loading HuggingFace model: {str(e)}")
            raise

    def _generate_with_huggingface(
        self,
        model_name: str,
        query: str,
        context: str,
        max_length: int = 512
    ) -> str:
        """
        使用HuggingFace模型生成回答
        
        参数:
            model_name: 模型名称
            query: 用户查询
            context: 上下文信息
            max_length: 生成文本的最大长度
            
        返回:
            生成的回答文本
        """
        try:
            model, tokenizer = self._load_huggingface_model(model_name)
            
            # 构建提示
            prompt = f"""请基于以下上下文回答问题。如果上下文中没有相关信息，请说明无法回答。

                        问题：{query}

                        上下文：
                        {context}

                        回答："""
        
            inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
            outputs = model.generate(
                **inputs,
                max_length=max_length,
                num_return_sequences=1,
                temperature=0.7,
                do_sample=True
            )
            
            response = tokenizer.decode(outputs[0], skip_special_tokens=True)
            return response.split("回答：")[-1].strip()
            
        except Exception as e:
            logger.error(f"Error generating with HuggingFace: {str(e)}")
            raise

    def _generate_with_openai(
        self,
        model_name: str,
        query: str,
        context: str,
        api_key: Optional[str] = None
    ) -> str:
        """
        使用OpenAI API生成回答
        
        参数:
            model_name: 模型名称
            query: 用户查询
            context: 上下文信息
            api_key: OpenAI API密钥，如不提供则从环境变量获取
            
        返回:
            生成的回答文本
        """
        try:
            if not api_key:
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError("OpenAI API key not provided")
                    
            client = OpenAI(api_key=api_key)
            
            messages = [
                {"role": "system", "content": "You are a helpful assistant. Use the provided context to answer the question."},
                {"role": "user", "content": f"Context: {context}\n\nQuestion: {query}"}
            ]
            
            response = client.chat.completions.create(
                model=self.models["openai"][model_name],
                messages=messages,
                temperature=0.7,
                max_tokens=512
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating with OpenAI: {str(e)}")
            raise

    def _generate_with_deepseek(
        self,
        model_name: str,
        query: str,
        context: str,
        api_key: Optional[str] = None,
        show_reasoning: bool = True
    ) -> str:
        """
        使用DeepSeek API生成回答
        
        参数:
            model_name: 模型名称
            query: 用户查询
            context: 上下文信息
            api_key: DeepSeek API密钥，如不提供则从环境变量获取
            show_reasoning: 是否显示推理过程（仅对推理模型有效）
            
        返回:
            生成的回答文本，对于推理模型可能包含思维过程
        """
        try:
            if not api_key:
                api_key = os.getenv("DEEPSEEK_API_KEY")
                if not api_key:
                    raise ValueError("DeepSeek API key not provided")
                    
            client = OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com"
            )
            
            messages = [
                {"role": "system", "content": "You are a helpful assistant. Use the provided context to answer the question."},
                {"role": "user", "content": f"Context: {context}\n\nQuestion: {query}"}
            ]
            
            response = client.chat.completions.create(
                model=self.models["deepseek"][model_name],
                messages=messages,
                max_tokens=512,
                stream=False
            )
            
            # 如果是推理模型，处理思维链输出
            if model_name == "deepseek-r1":
                message = response.choices[0].message
                reasoning = message.reasoning_content
                answer = message.content
                
                if show_reasoning and reasoning:
                    return f"【思维过程】\n{reasoning}\n\n【最终答案】\n{answer}"
                return answer
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating with DeepSeek: {str(e)}")
            raise

    def generate(
        self,
        provider: str,
        model_name: str,
        query: str,
        search_results: List[Dict],
        api_key: Optional[str] = None,
        show_reasoning: bool = True
    ) -> Dict:
        """
        生成回答并保存结果
        
        参数:
            provider: 模型提供商，可选值为"huggingface"、"openai"、"deepseek"
            model_name: 模型名称
            query: 用户查询
            search_results: 搜索结果列表，用于构建上下文
            api_key: API密钥（对于API调用）
            show_reasoning: 是否显示推理过程（仅对DeepSeek推理模型有效）
            
        返回:
            包含生成回答和保存路径的字典
        """
        try:
            # 准备上下文
            context = "\n\n".join([
                f"[Source {i+1}]: {result['text']}"
                for i, result in enumerate(search_results)
            ])
            
            # 根据不同提供商生成回答
            if provider == "huggingface":
                response = self._generate_with_huggingface(model_name, query, context)
            elif provider == "openai":
                response = self._generate_with_openai(model_name, query, context, api_key)
            elif provider == "deepseek":
                response = self._generate_with_deepseek(model_name, query, context, api_key, show_reasoning)
            else:
                raise ValueError(f"Unsupported provider: {provider}")
                
            # 准备保存的结果
            result = {
                "query": query,
                "timestamp": datetime.now().isoformat(),
                "provider": provider,
                "model": model_name,
                "response": response,
                "context": search_results
            }
            
            # 生成文件名并保存
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"generation_{provider}_{model_name}_{timestamp}.json"
            filepath = os.path.join("05-generation-results", filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
                
            return {
                "response": response,
                "saved_filepath": filepath
            }
            
        except Exception as e:
            logger.error(f"Error in generation: {str(e)}")
            raise

    def get_available_models(self) -> Dict:
        """
        获取可用的模型列表
        
        返回:
            包含所有支持模型的字典
        """
        return self.models 