"""Core data types and contracts for the entire pipeline.
整个流水线的核心数据类型和契约。

This module defines the fundamental data structures used across all pipeline stages:
本模块定义了所有流水线阶段使用的基础数据结构：
- ingestion (loaders, transforms, embedding, storage)
  数据摄取（加载器、转换、嵌入、存储）
- retrieval (query engine, search, reranking)
  检索（查询引擎、搜索、重排序）
- mcp_server (tools, response formatting)
  MCP服务器（工具、响应格式化）

Design Principles:
设计原则：
- Centralized contracts: All stages use these types to avoid coupling
  集中契约：所有阶段使用这些类型以避免耦合
- Serializable: All types support dict/JSON conversion
  可序列化：所有类型支持字典/JSON转换
- Extensible metadata: Minimum required fields with flexible extension
  可扩展元数据：最小必需字段，灵活扩展
- Type-safe: Full type hints for static analysis
  类型安全：完整的类型提示用于静态分析
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional


@dataclass
class Document:
    """Represents a raw document loaded from source.
    表示从数据源加载的原始文档。
    
    This is the output of Loaders (e.g., PDF Loader) before splitting.
    这是加载器（如PDF加载器）在分块之前的输出。
    
    Attributes:
    属性：
        id: Unique identifier for the document (e.g., file hash or path-based ID)
            文档的唯一标识符（如文件哈希或基于路径的ID）
        text: Document content in standardized Markdown format.
              Images are represented as placeholders: [IMAGE: {image_id}]
              标准化Markdown格式的文档内容。
              图片以占位符表示：[IMAGE: {image_id}]
        metadata: Document-level metadata including:
                  文档级元数据，包括：
            - source_path (required): Original file path
              source_path（必需）：原始文件路径
            - doc_type: Document type (e.g., 'pdf', 'markdown')
              doc_type：文档类型（如'pdf'、'markdown'）
            - title: Document title extracted or inferred
              title：提取或推断的文档标题
            - page_count: Total pages (if applicable)
              page_count：总页数（如适用）
            - images: List of image references (see Images Field Specification below)
              images：图片引用列表（见下方图片字段规范）
            - Any other custom metadata
              任何其他自定义元数据
    
    Images Field Specification (metadata.images):
    图片字段规范（metadata.images）：
        Structure: List[{"id": str, "path": str, "page": int, "text_offset": int, 
                        "text_length": int, "position": dict}]
        结构：List[{"id": str, "path": str, "page": int, "text_offset": int, 
                   "text_length": int, "position": dict}]
        Fields:
        字段：
            - id: Unique image identifier (format: {doc_hash}_{page}_{seq})
              id：唯一图片标识符（格式：{doc_hash}_{page}_{seq}）
            - path: Image file storage path (convention: data/images/{collection}/{image_id}.png)
              path：图片文件存储路径（约定：data/images/{collection}/{image_id}.png）
            - page: Page number in original document (optional, for paginated docs like PDF)
              page：原始文档中的页码（可选，用于PDF等分页文档）
            - text_offset: Starting character position of placeholder in Document.text (0-based)
              text_offset：占位符在Document.text中的起始字符位置（从0开始）
            - text_length: Length of placeholder string (typically len("[IMAGE: {image_id}]"))
              text_length：占位符字符串长度（通常为len("[IMAGE: {image_id}]")）
            - position: Physical position info in original doc (optional, e.g., PDF coords, pixel position)
              position：原始文档中的物理位置信息（可选，如PDF坐标、像素位置）
        Note: text_offset and text_length enable precise placeholder location, 
              supporting scenarios where the same image appears multiple times
        注意：text_offset和text_length支持精确定位占位符，
              支持同一图片多次出现的场景
    
    Example:
    示例：
        >>> doc = Document(
        ...     id="doc_abc123",
        ...     text="# Title\\n\\nContent...",
        ...     metadata={
        ...         "source_path": "data/documents/report.pdf",
        ...         "doc_type": "pdf",
        ...         "title": "Annual Report 2025"
        ...     }
        ... )
    """
    
    id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate required metadata fields.
        验证必需的元数据字段。
        """
        if "source_path" not in self.metadata:
            raise ValueError("Document metadata must contain 'source_path'")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization.
        转换为字典以便序列化。
        """
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Document":
        """Create Document from dictionary.
        从字典创建Document对象。
        """
        return cls(**data)


@dataclass
class Chunk:
    """Represents a text chunk after splitting a Document.
    表示文档分割后的文本块。
    
    This is the output of Splitters and input to Transform pipeline.
    Each chunk maintains traceability to its source document.
    这是分割器的输出，也是转换流水线的输入。
    每个块保持对其源文档的可追溯性。
    
    Attributes:
    属性：
        id: Unique chunk identifier (e.g., hash-based or sequential)
            唯一块标识符（如基于哈希或顺序）
        text: Chunk content (subset of original document text).
              Images are represented as placeholders: [IMAGE: {image_id}]
              块内容（原始文档文本的子集）。
              图片以占位符表示：[IMAGE: {image_id}]
        metadata: Chunk-level metadata inherited and extended from Document:
                  从Document继承并扩展的块级元数据：
            - source_path (required): Original file path
              source_path（必需）：原始文件路径
            - chunk_index: Sequential position in document (0-based)
              chunk_index：文档中的顺序位置（从0开始）
            - start_offset: Character offset in original document (optional)
              start_offset：原始文档中的字符偏移量（可选）
            - end_offset: Character offset in original document (optional)
              end_offset：原始文档中的字符偏移量（可选）
            - source_ref: Reference to parent document ID (optional)
              source_ref：父文档ID引用（可选）
            - images: Subset of Document.images that fall within this chunk (optional)
              images：位于此块内的Document.images子集（可选）
            - Any document-level metadata propagated from Document
              从Document传播的任何文档级元数据
        start_offset: Starting character position in original document (optional)
                       原始文档中的起始字符位置（可选）
        end_offset: Ending character position in original document (optional)
                     原始文档中的结束字符位置（可选）
        source_ref: Reference to parent Document.id (optional)
                    父Document.id的引用（可选）
    
    Note: If chunk contains image placeholders, metadata.images should contain
          only the image references relevant to this chunk's text range.
    注意：如果块包含图片占位符，metadata.images应仅包含与此块文本范围相关的图片引用。
    
    Example:
    示例：
        >>> chunk = Chunk(
        ...     id="chunk_abc123_001",
        ...     text="## Section 1\\n\\nFirst paragraph...",
        ...     metadata={
        ...         "source_path": "data/documents/report.pdf",
        ...         "chunk_index": 0,
        ...         "page": 1
        ...     },
        ...     start_offset=0,
        ...     end_offset=150
        ... )
    """
    
    id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    source_ref: Optional[str] = None
    
    def __post_init__(self):
        """Validate required metadata fields.
        验证必需的元数据字段。
        """
        if "source_path" not in self.metadata:
            raise ValueError("Chunk metadata must contain 'source_path'")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization.
        转换为字典以便序列化。
        """
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Chunk":
        """Create Chunk from dictionary.
        从字典创建Chunk对象。
        """
        return cls(**data)


@dataclass
class ChunkRecord:
    """Represents a fully processed chunk ready for storage and retrieval.
    表示已完全处理、准备存储和检索的块。
    
    This is the output of the embedding pipeline and the data structure
    stored in vector databases. It extends Chunk with vector representations.
    这是嵌入流水线的输出，也是存储在向量数据库中的数据结构。
    它用向量表示扩展了Chunk。
    
    Attributes:
    属性：
        id: Unique chunk identifier (must be stable for idempotent upsert)
            唯一块标识符（必须稳定以支持幂等upsert）
        text: Chunk content (same as Chunk.text).
              Images are represented as placeholders: [IMAGE: {image_id}]
              块内容（与Chunk.text相同）。
              图片以占位符表示：[IMAGE: {image_id}]
        metadata: Extended metadata including:
                  扩展元数据，包括：
            - source_path (required): Original file path
              source_path（必需）：原始文件路径
            - chunk_index: Sequential position
              chunk_index：顺序位置
            - All metadata from Chunk
              来自Chunk的所有元数据
            - images: Image references from Chunk (see Document.images specification)
              images：来自Chunk的图片引用（见Document.images规范）
            - Any enrichment from Transform pipeline (title, summary, tags)
              来自转换流水线的任何丰富信息（标题、摘要、标签）
            - image_captions: Dict[image_id, caption_text] if multimodal enrichment applied
              image_captions：如果应用了多模态丰富，则为Dict[image_id, caption_text]
        dense_vector: Dense embedding vector (e.g., from OpenAI, BGE)
                      稠密嵌入向量（如来自OpenAI、BGE）
        sparse_vector: Sparse vector for BM25/keyword matching (optional)
                       用于BM25/关键词匹配的稀疏向量（可选）
    
    Note: Image captions generated by ImageCaptioner are stored in metadata.image_captions
          as a dictionary mapping image_id to generated caption text.
    注意：ImageCaptioner生成的图片描述存储在metadata.image_captions中，
          作为映射image_id到生成描述文本的字典。
    
    Example:
    示例：
        >>> record = ChunkRecord(
        ...     id="chunk_abc123_001",
        ...     text="## Section 1\\n\\nFirst paragraph...",
        ...     metadata={
        ...         "source_path": "data/documents/report.pdf",
        ...         "chunk_index": 0,
        ...         "title": "Introduction",
        ...         "summary": "Overview of project goals"
        ...     },
        ...     dense_vector=[0.1, 0.2, ..., 0.3],
        ...     sparse_vector={"word1": 0.5, "word2": 0.3}
        ... )
    """
    
    id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    dense_vector: Optional[List[float]] = None
    sparse_vector: Optional[Dict[str, float]] = None
    
    def __post_init__(self):
        """Validate required metadata fields.
        验证必需的元数据字段。
        """
        if "source_path" not in self.metadata:
            raise ValueError("ChunkRecord metadata must contain 'source_path'")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization.
        转换为字典以便序列化。
        """
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChunkRecord":
        """Create ChunkRecord from dictionary.
        从字典创建ChunkRecord对象。
        """
        return cls(**data)
    
    @classmethod
    def from_chunk(cls, chunk: Chunk, dense_vector: Optional[List[float]] = None,
                   sparse_vector: Optional[Dict[str, float]] = None) -> "ChunkRecord":
        """Create ChunkRecord from a Chunk with vectors.
        从带有向量的Chunk创建ChunkRecord。
        
        Args:
        参数：
            chunk: Source Chunk object
                   源Chunk对象
            dense_vector: Dense embedding vector
                          稠密嵌入向量
            sparse_vector: Sparse vector representation
                           稀疏向量表示
            
        Returns:
        返回：
            ChunkRecord with all fields populated from chunk
            从chunk填充所有字段的ChunkRecord
        """
        return cls(
            id=chunk.id,
            text=chunk.text,
            metadata=chunk.metadata.copy(),
            dense_vector=dense_vector,
            sparse_vector=sparse_vector
        )


# Type aliases for convenience
# 便捷类型别名
Metadata = Dict[str, Any]
Vector = List[float]
SparseVector = Dict[str, float]


@dataclass
class ProcessedQuery:
    """Represents a processed query ready for retrieval.
    表示已处理、准备检索的查询。
    
    This is the output of QueryProcessor, containing extracted keywords
    and parsed filters for downstream Dense/Sparse retrievers.
    这是QueryProcessor的输出，包含提取的关键词
    和解析的过滤器，供下游稠密/稀疏检索器使用。
    
    Attributes:
    属性：
        original_query: The raw user query string
                        原始用户查询字符串
        keywords: List of extracted keywords after stopword removal
                  停用词移除后提取的关键词列表
        filters: Dictionary of filter conditions (e.g., {"collection": "api-docs"})
                 过滤条件字典（如{"collection": "api-docs"}）
        expanded_terms: Optional list of synonyms/expanded terms (for future use)
                        同义词/扩展词列表（可选，供将来使用）
    
    Example:
    示例：
        >>> pq = ProcessedQuery(
        ...     original_query="如何配置 Azure OpenAI？",
        ...     keywords=["配置", "Azure", "OpenAI"],
        ...     filters={"collection": "docs"}
        ... )
    """
    
    original_query: str
    keywords: List[str] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    expanded_terms: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization.
        转换为字典以便序列化。
        """
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcessedQuery":
        """Create ProcessedQuery from dictionary.
        从字典创建ProcessedQuery对象。
        """
        return cls(**data)


@dataclass
class RetrievalResult:
    """Represents a single retrieval result from Dense/Sparse retrievers.
    表示来自稠密/稀疏检索器的单个检索结果。
    
    This is the output of DenseRetriever, SparseRetriever, and HybridSearch,
    providing a unified contract for retrieval results across all search methods.
    这是DenseRetriever、SparseRetriever和HybridSearch的输出，
    为所有搜索方法的检索结果提供统一契约。
    
    Attributes:
    属性：
        chunk_id: Unique identifier for the retrieved chunk
                  检索到的块的唯一标识符
        score: Relevance score (higher = more relevant, normalized to [0, 1])
               相关性分数（越高越相关，归一化到[0, 1]）
        text: The actual text content of the retrieved chunk
              检索到的块的实际文本内容
        metadata: Associated metadata (source_path, chunk_index, title, etc.)
                  关联的元数据（source_path、chunk_index、title等）
    
    Example:
    示例：
        >>> result = RetrievalResult(
        ...     chunk_id="doc1_chunk_003",
        ...     score=0.85,
        ...     text="Azure OpenAI 配置步骤如下...",
        ...     metadata={
        ...         "source_path": "docs/azure-guide.pdf",
        ...         "chunk_index": 3,
        ...         "title": "Azure Configuration"
        ...     }
        ... )
    """
    
    chunk_id: str
    score: float
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate fields after initialization.
        初始化后验证字段。
        """
        if not self.chunk_id:
            raise ValueError("chunk_id cannot be empty")
        if not isinstance(self.score, (int, float)):
            raise ValueError(f"score must be numeric, got {type(self.score).__name__}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization.
        转换为字典以便序列化。
        """
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RetrievalResult":
        """Create RetrievalResult from dictionary.
        从字典创建RetrievalResult对象。
        """
        return cls(**data)
