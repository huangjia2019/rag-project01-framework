import logging
import os
from datetime import datetime
from pathlib import Path
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

class ParseMDService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def parse_pdf_to_md(self, parsing_option, metadata):
        """
        Convert PDF content to Markdown format using MinerU API
        
        Args:
            parsing_option (str): 'one' or 'by_headers'
            metadata (dict): Metadata about the document, must include 'temp_path'
            
        Returns:
            dict: Parsed content in markdown format
        """
        self.logger.info(f"Converting PDF to Markdown with option: {parsing_option}")
        
        if metadata is None:
            metadata = {}
        
        # Get the path to the PDF file from metadata (from temp directory)
        pdf_path = metadata.get("temp_path", "")
        
        if not pdf_path or not os.path.exists(pdf_path):
            self.logger.error(f"PDF file not found: {pdf_path}")
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        # Create output directories
        output_dir = os.path.join("05-markdown-docs")
        image_dir = os.path.join(output_dir, "images")
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(image_dir, exist_ok=True)
        
        # Generate unique filename
        filename = metadata.get("filename", "")
        basename = os.path.basename(filename).split(".")[0]
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        output_md_file = f"{basename}_{timestamp}.md"
        output_md_path = os.path.join(output_dir, output_md_file)
        
        # Use MinerU to convert PDF to Markdown
        try:
            # Read PDF file as bytes
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            
            # Mode selection for MinerU API
            ocr_mode = False  # Default
            if parsing_option == "by_headers":
                ocr_mode = True  # Use OCR mode for better header detection
                
            # Convert PDF to Markdown using MinerU API
            self._convert_using_mineru_api(
                pdf_bytes, 
                output_dir, 
                image_dir, 
                basename, 
                output_md_file,
                ocr_mode
            )
                
            # Read the generated markdown content
            with open(output_md_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
                
            # Format the results for the frontend
            result = {
                "metadata": {
                    "filename": metadata.get("filename", "unknown"),
                    "parsing_method": parsing_option,
                    "timestamp": datetime.now().isoformat(),
                    "md_file_path": output_md_path
                },
                "content": []
            }
            
            # Use LangChain's MarkdownHeaderTextSplitter for better header-based splitting
            if parsing_option == "by_headers":
                result["content"] = self._split_md_by_langchain(md_content, basename)
            else:
                # Return the entire document as a single markdown block
                result["content"].append({
                    "type": "markdown",
                    "title": basename,
                    "content": md_content
                })
                    
            return result
                
        except Exception as e:
            self.logger.error(f"Error using MinerU to convert PDF: {str(e)}")
            self.logger.info("Falling back to alternative conversion...")
            
            # Try to use another external tool or method to convert the PDF
            try:
                import subprocess
                
                # Create temporary output file
                temp_md_path = os.path.join(output_dir, f"temp_{basename}.md")
                
                # Try to use pandoc for conversion if available
                result = subprocess.run(
                    ["pandoc", pdf_path, "-o", temp_md_path], 
                    capture_output=True, 
                    text=True, 
                    check=False
                )
                
                if os.path.exists(temp_md_path):
                    # Read the generated markdown content
                    with open(temp_md_path, 'r', encoding='utf-8') as f:
                        md_content = f.read()
                    
                    # Move to final filename
                    os.rename(temp_md_path, output_md_path)
                    
                    # Format the results for the frontend
                    result = {
                        "metadata": {
                            "filename": metadata.get("filename", "unknown"),
                            "parsing_method": f"{parsing_option} (fallback)",
                            "timestamp": datetime.now().isoformat(),
                            "md_file_path": output_md_path
                        },
                        "content": []
                    }
                    
                    if parsing_option == "by_headers":
                        result["content"] = self._split_md_by_langchain(md_content, basename)
                    else:
                        # Return the entire document as a single markdown block
                        result["content"].append({
                            "type": "markdown",
                            "title": basename,
                            "content": md_content
                        })
                        
                    return result
                else:
                    raise FileNotFoundError("Failed to generate markdown file")
                    
            except Exception as fallback_error:
                self.logger.error(f"Error in fallback conversion: {str(fallback_error)}")
                
                # Create a minimal markdown file with an error message
                with open(output_md_path, 'w', encoding='utf-8') as md_file:
                    md_file.write(f"# Conversion Error\n\nFailed to convert {filename} to markdown.\n\n")
                    md_file.write(f"Error: {str(e)}\n\n")
                    md_file.write(f"Fallback error: {str(fallback_error)}\n")
                
                # Return minimal content
                return {
                    "metadata": {
                        "filename": metadata.get("filename", "unknown"),
                        "parsing_method": "error",
                        "timestamp": datetime.now().isoformat(),
                        "md_file_path": output_md_path,
                        "error": str(e)
                    },
                    "content": [{
                        "type": "markdown",
                        "title": f"Error converting {basename}",
                        "content": f"# Conversion Error\n\nFailed to convert {filename} to markdown.\n\n" +
                                   f"Error: {str(e)}\n\n" +
                                   f"Fallback error: {str(fallback_error)}\n"
                    }]
                }
    
    def _convert_using_mineru_api(self, pdf_bytes, output_dir, image_dir, basename, output_md_file, ocr_mode=False):
        """
        Use MinerU Python API to convert PDF to Markdown
        
        Following the official MinerU documentation:
        https://mineru.readthedocs.io/en/latest/user_guide/quick_start/convert_pdf.html
        """
        self.logger.info("Using MinerU Python API to convert PDF")
        
        try:
            # Import MinerU modules
            from magic_pdf.data.data_reader_writer import FileBasedDataWriter
            from magic_pdf.data.dataset import PymuDocDataset
            from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
            
            # Prepare environment
            image_dir_basename = os.path.basename(image_dir)
            
            # Create writers
            image_writer = FileBasedDataWriter(image_dir)
            md_writer = FileBasedDataWriter(output_dir)
            
            # Create dataset instance
            ds = PymuDocDataset(pdf_bytes)
            
            # Apply document analysis with specified OCR mode
            ds = ds.apply(doc_analyze, ocr=ocr_mode)
            
            # Generate markdown based on the OCR mode
            if ocr_mode:
                # Use OCR mode
                ds = ds.pipe_ocr_mode(image_writer)
            else:
                # Use text mode
                ds = ds.pipe_txt_mode(image_writer)
                
            # Generate the markdown file
            ds.dump_md(md_writer, output_md_file, image_dir_basename)
            
            self.logger.info(f"Successfully generated markdown file: {os.path.join(output_dir, output_md_file)}")
            return True
            
        except ImportError as e:
            self.logger.error(f"MinerU API import error: {str(e)}")
            raise RuntimeError(f"MinerU API not available: {str(e)}")
        except Exception as e:
            self.logger.error(f"MinerU API error: {str(e)}")
            raise RuntimeError(f"MinerU API conversion failed: {str(e)}")
    
    def _split_md_by_langchain(self, md_content, title="Document"):
        """
        Split markdown content by headers using LangChain's MarkdownHeaderTextSplitter
        Returns list of content dictionaries
        """
        self.logger.info("Splitting markdown content by headers using LangChain")
        
        # Define headers to split on (standard markdown headers)
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
            ("####", "Header 4"),
            ("#####", "Header 5"),
            ("######", "Header 6"),
        ]
        
        try:
            # Create the splitter
            markdown_splitter = MarkdownHeaderTextSplitter(
                headers_to_split_on=headers_to_split_on,
                strip_headers=False  # Keep headers in content for better context
            )
            
            # Split the markdown content
            splits = markdown_splitter.split_text(md_content)
            
            # If the content doesn't have proper headers, fallback to regular text chunking
            if not splits:
                self.logger.warning("No headers found in markdown, using RecursiveCharacterTextSplitter")
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=2000,
                    chunk_overlap=200
                )
                splits = text_splitter.create_documents([md_content])
            
            # Format for our API response
            content_list = []
            for i, doc in enumerate(splits):
                # Determine the title from metadata or use a default
                section_title = None
                
                # Check for header information in metadata
                metadata = doc.metadata
                if "Header 1" in metadata:
                    section_title = metadata["Header 1"]
                elif "Header 2" in metadata:
                    section_title = metadata["Header 2"]
                elif "Header 3" in metadata:
                    section_title = metadata["Header 3"]
                
                # If no title found, use a section number
                if not section_title:
                    section_title = f"Section {i+1}"
                
                content_list.append({
                    "type": "markdown",
                    "section": i + 1,
                    "title": section_title,
                    "content": doc.page_content,
                    "metadata": metadata
                })
            
            return content_list
            
        except Exception as e:
            self.logger.error(f"Error splitting markdown with LangChain: {str(e)}")
            # Fallback to basic splitting method
            sections = self._split_md_by_headers(md_content)
            content_list = []
            for i, (header, content) in enumerate(sections):
                content_list.append({
                    "type": "markdown",
                    "section": i + 1,
                    "title": header or title,
                    "content": content
                })
            return content_list
    
    def _split_md_by_headers(self, md_content):
        """
        Split markdown content by headers
        Returns list of tuples (header, content)
        """
        lines = md_content.split('\n')
        sections = []
        
        current_header = "Document"
        current_content = []
        
        for line in lines:
            if line.startswith('#'):
                # Found a header
                if current_content:
                    sections.append((current_header, '\n'.join(current_content)))
                    current_content = []
                
                # Remove the # markers and use as the header
                current_header = line.lstrip('#').strip()
            else:
                current_content.append(line)
        
        # Add the last section
        if current_content:
            sections.append((current_header, '\n'.join(current_content)))
        
        # If no headers were found, treat the entire document as one section
        if not sections and md_content:
            sections.append(("Document", md_content))
            
        return sections 