# Knowledge Graph Storage with Neo4j and Pydantic AI

## Overview

This guide demonstrates how to extract entities and relationships from plain text using Pydantic AI, and store them in a Neo4j graph database. The agent-reminiscence package uses this approach to build knowledge graphs from memory content.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [Entity & Relationship Extraction with Pydantic AI](#entity--relationship-extraction-with-pydantic-ai)
4. [Storing in Neo4j](#storing-in-neo4j)
5. [Complete End-to-End Example](#complete-end-to-end-example)
6. [Querying the Knowledge Graph](#querying-the-knowledge-graph)

## Prerequisites

### Required Dependencies

```bash
pip install pydantic-ai neo4j psqlpy agent-reminiscence
```

### Environment Setup

Create a `.env` file:

```bash
# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
NEO4J_DATABASE=neo4j

# LLM Provider API Keys (choose at least one)
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key
GROK_API_KEY=your_grok_key
```

### Start Neo4j

Using Docker:

```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your_password \
  neo4j:latest
```

## Architecture Overview

The knowledge graph storage process has three main components:

```
┌─────────────────────────────────────────────────────────┐
│ 1. Plain Text Input                                      │
│    "John works at Google. He uses Python and            │
│     TensorFlow for ML projects."                        │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 2. Pydantic AI Agent (ER Extractor)                     │
│    - Entity Extraction                                  │
│    - Relationship Extraction                            │
│    - Confidence Scoring                                 │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ 3. Neo4j Graph Storage                                  │
│    - Nodes: Entities (Person, Org, Tech, etc.)         │
│    - Relationships: WORKS_WITH, USES, etc.              │
│    - Properties: confidence, type, metadata             │
└─────────────────────────────────────────────────────────┘
```

## Entity & Relationship Extraction with Pydantic AI

### Step 1: Define Entity and Relationship Models

Pydantic AI uses Pydantic models to structure LLM outputs:

```python
from enum import Enum
from typing import List
from pydantic import BaseModel, Field
from pydantic_ai import Agent

class EntityType(str, Enum):
    """Entity types for classification."""
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    TECHNOLOGY = "TECHNOLOGY"
    FRAMEWORK = "FRAMEWORK"
    LIBRARY = "LIBRARY"
    TOOL = "TOOL"
    CONCEPT = "CONCEPT"
    PROJECT = "PROJECT"
    LOCATION = "LOCATION"
    EVENT = "EVENT"
    OTHER = "OTHER"

class RelationshipType(str, Enum):
    """Relationship types between entities."""
    WORKS_WITH = "WORKS_WITH"
    BELONGS_TO = "BELONGS_TO"
    USES = "USES"
    DEPENDS_ON = "DEPENDS_ON"
    RELATED_TO = "RELATED_TO"
    LOCATED_AT = "LOCATED_AT"
    PART_OF = "PART_OF"
    CREATED_BY = "CREATED_BY"
    OTHER = "OTHER"

class ExtractedEntity(BaseModel):
    """An extracted entity from text."""
    name: str = Field(description="Entity name")
    type: EntityType = Field(description="Entity type")
    confidence: float = Field(ge=0.0, le=1.0, description="Extraction confidence")
    description: str = Field(default="", description="Brief description")

class ExtractedRelationship(BaseModel):
    """An extracted relationship between entities."""
    source: str = Field(description="Source entity name")
    target: str = Field(description="Target entity name")
    type: RelationshipType = Field(description="Relationship type")
    confidence: float = Field(ge=0.0, le=1.0, description="Extraction confidence")
    description: str = Field(default="", description="Brief description")

class ExtractionResult(BaseModel):
    """Result of entity and relationship extraction."""
    entities: List[ExtractedEntity] = Field(default_factory=list)
    relationships: List[ExtractedRelationship] = Field(default_factory=list)
```

### Step 2: Create the Pydantic AI Agent

```python
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel

# System prompt to guide the LLM
SYSTEM_PROMPT = """You are an Entity and Relationship Extraction Specialist.

**Your Role:**
Extract entities and relationships from text content to build a knowledge graph.

**Guidelines:**
1. Extract ALL significant entities mentioned
2. Use specific entity types (avoid OTHER unless truly ambiguous)
3. Extract relationships between entities
4. Provide confidence scores (0.0-1.0):
   - 1.0: Explicitly stated, no ambiguity
   - 0.8-0.9: Clearly implied or stated
   - 0.6-0.7: Reasonable inference
   - 0.4-0.5: Weak inference or ambiguous
5. Be consistent with entity names (use canonical forms)
6. Include brief descriptions for context

**Example Input:**
"John works at Google. He uses Python and TensorFlow for ML projects."

**Example Output:**
{
  "entities": [
    {"name": "John", "type": "PERSON", "confidence": 1.0, "description": "Person working at Google"},
    {"name": "Google", "type": "ORGANIZATION", "confidence": 1.0, "description": "Technology company"},
    {"name": "Python", "type": "LANGUAGE", "confidence": 1.0, "description": "Programming language"},
    {"name": "TensorFlow", "type": "LIBRARY", "confidence": 1.0, "description": "ML library"}
  ],
  "relationships": [
    {"source": "John", "target": "Google", "type": "WORKS_WITH", "confidence": 1.0, "description": "Employment relationship"},
    {"source": "John", "target": "Python", "type": "USES", "confidence": 1.0, "description": "Uses for development"},
    {"source": "John", "target": "TensorFlow", "type": "USES", "confidence": 1.0, "description": "Uses for ML projects"}
  ]
}
"""

# Create the agent with OpenAI model
def create_er_extractor():
    """Create an entity-relationship extraction agent."""
    model = OpenAIChatModel("gpt-4o-mini")  # or gpt-4o for better quality
    
    return Agent(
        model=model,
        deps_type=None,
        system_prompt=SYSTEM_PROMPT,
        output_type=ExtractionResult,
        model_settings={"temperature": 0.3},  # Lower temp for more consistent extraction
        retries=2,
    )
```

### Step 3: Extract from Text

```python
async def extract_knowledge(text: str) -> ExtractionResult:
    """
    Extract entities and relationships from plain text.
    
    Args:
        text: Plain text content to analyze
        
    Returns:
        ExtractionResult with entities and relationships
    """
    agent = create_er_extractor()
    result = await agent.run(text)
    
    print(f"Extracted {len(result.output.entities)} entities")
    print(f"Extracted {len(result.output.relationships)} relationships")
    print(f"Token usage: {result.usage()}")
    
    return result.output
```

## Storing in Neo4j

### Step 1: Set Up Neo4j Connection Manager

```python
from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
from contextlib import asynccontextmanager
from typing import Optional
import os

class Neo4jManager:
    """Neo4j connection manager."""
    
    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j"):
        self._uri = uri
        self._user = user
        self._password = password
        self._database = database
        self._driver: Optional[AsyncDriver] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize the Neo4j driver."""
        if not self._initialized:
            self._driver = AsyncGraphDatabase.driver(
                self._uri,
                auth=(self._user, self._password),
                max_connection_pool_size=50,
                max_transaction_retry_time=30.0,
            )
            await self._driver.verify_connectivity()
            self._initialized = True
    
    async def close(self):
        """Close the driver connection."""
        if self._driver:
            await self._driver.close()
            self._driver = None
            self._initialized = False
    
    @asynccontextmanager
    async def session(self, database: Optional[str] = None):
        """Get a session context manager."""
        if not self._initialized:
            raise RuntimeError("Neo4j manager not initialized. Call initialize() first.")
        
        db = database or self._database
        async with self._driver.session(database=db) as session:
            yield session

# Create manager from environment
neo4j_manager = Neo4jManager(
    uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    user=os.getenv("NEO4J_USER", "neo4j"),
    password=os.getenv("NEO4J_PASSWORD", "password"),
    database=os.getenv("NEO4J_DATABASE", "neo4j")
)
```

### Step 2: Create Indexes and Constraints

```python
async def setup_neo4j_schema(manager: Neo4jManager):
    """Create necessary constraints and indexes."""
    
    constraints = [
        # Unique constraints for entity IDs
        """
        CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
        FOR (e:Entity) REQUIRE e.id IS UNIQUE
        """,
    ]
    
    indexes = [
        # Indexes for faster queries
        "CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)",
        "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type)",
        "CREATE INDEX entity_external_id IF NOT EXISTS FOR (e:Entity) ON (e.external_id)",
    ]
    
    async with manager.session() as session:
        # Create constraints
        for constraint in constraints:
            try:
                await session.run(constraint)
                print(f"✓ Created constraint")
            except Exception as e:
                print(f"Constraint may already exist: {e}")
        
        # Create indexes
        for index in indexes:
            try:
                await session.run(index)
                print(f"✓ Created index")
            except Exception as e:
                print(f"Index may already exist: {e}")
```

### Step 3: Store Entities in Neo4j

```python
from datetime import datetime
from typing import Dict, Any, Optional

async def create_entity(
    manager: Neo4jManager,
    entity_id: int,
    external_id: str,  # e.g., agent/worker ID
    name: str,
    entity_type: str,
    confidence: float,
    description: str = "",
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Create an entity node in Neo4j.
    
    Args:
        manager: Neo4j connection manager
        entity_id: Unique entity ID
        external_id: External identifier (agent/worker ID)
        name: Entity name
        entity_type: Type of entity
        confidence: Confidence score (0.0-1.0)
        description: Entity description
        metadata: Additional properties
        
    Returns:
        True if created successfully
    """
    query = """
    CREATE (e:Entity {
        id: $id,
        external_id: $external_id,
        name: $name,
        type: $type,
        description: $description,
        confidence: $confidence,
        first_seen: datetime($first_seen),
        last_seen: datetime($last_seen),
        metadata: $metadata
    })
    RETURN e.id as id
    """
    
    now = datetime.now().isoformat()
    
    async with manager.session() as session:
        result = await session.run(
            query,
            id=entity_id,
            external_id=external_id,
            name=name,
            type=entity_type,
            description=description,
            confidence=confidence,
            first_seen=now,
            last_seen=now,
            metadata=metadata or {}
        )
        record = await result.single()
        return record is not None
```

### Step 4: Store Relationships in Neo4j

```python
async def create_relationship(
    manager: Neo4jManager,
    relationship_id: int,
    external_id: str,
    source_entity_id: int,
    target_entity_id: int,
    relationship_type: str,
    confidence: float,
    description: str = "",
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Create a relationship between two entities.
    
    Args:
        manager: Neo4j connection manager
        relationship_id: Unique relationship ID
        external_id: External identifier (agent/worker ID)
        source_entity_id: Source entity ID
        target_entity_id: Target entity ID
        relationship_type: Type of relationship
        confidence: Confidence score (0.0-1.0)
        description: Relationship description
        metadata: Additional properties
        
    Returns:
        True if created successfully
    """
    query = """
    MATCH (source:Entity {id: $source_id})
    MATCH (target:Entity {id: $target_id})
    CREATE (source)-[r:RELATES_TO {
        id: $rel_id,
        external_id: $external_id,
        from_entity_id: $source_id,
        to_entity_id: $target_id,
        type: $rel_type,
        description: $description,
        confidence: $confidence,
        first_observed: datetime($first_observed),
        last_observed: datetime($last_observed),
        metadata: $metadata
    }]->(target)
    RETURN r.id as id
    """
    
    now = datetime.now().isoformat()
    
    async with manager.session() as session:
        result = await session.run(
            query,
            source_id=source_entity_id,
            target_id=target_entity_id,
            rel_id=relationship_id,
            external_id=external_id,
            rel_type=relationship_type,
            description=description,
            confidence=confidence,
            first_observed=now,
            last_observed=now,
            metadata=metadata or {}
        )
        record = await result.single()
        return record is not None
```

## Complete End-to-End Example

Here's a complete example that extracts knowledge from text and stores it in Neo4j:

```python
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def process_text_to_knowledge_graph(text: str, external_id: str = "user-001"):
    """
    Complete pipeline: Extract entities/relationships and store in Neo4j.
    
    Args:
        text: Plain text to process
        external_id: Identifier for this knowledge source
    """
    # Initialize Neo4j
    neo4j_manager = Neo4jManager(
        uri=os.getenv("NEO4J_URI"),
        user=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD"),
    )
    
    await neo4j_manager.initialize()
    
    try:
        # Set up schema (run once)
        await setup_neo4j_schema(neo4j_manager)
        
        # Step 1: Extract entities and relationships using Pydantic AI
        print("🔍 Extracting knowledge from text...")
        extraction_result = await extract_knowledge(text)
        
        print(f"\n✓ Found {len(extraction_result.entities)} entities:")
        for entity in extraction_result.entities:
            print(f"  - {entity.name} ({entity.type}) - confidence: {entity.confidence}")
        
        print(f"\n✓ Found {len(extraction_result.relationships)} relationships:")
        for rel in extraction_result.relationships:
            print(f"  - {rel.source} --[{rel.type}]--> {rel.target} - confidence: {rel.confidence}")
        
        # Step 2: Store entities in Neo4j
        print("\n💾 Storing entities in Neo4j...")
        entity_id_map = {}  # Map entity names to IDs
        
        for idx, entity in enumerate(extraction_result.entities):
            entity_id = idx + 1
            entity_id_map[entity.name] = entity_id
            
            await create_entity(
                manager=neo4j_manager,
                entity_id=entity_id,
                external_id=external_id,
                name=entity.name,
                entity_type=entity.type.value,
                confidence=entity.confidence,
                description=entity.description,
                metadata={"extracted_from": "plain_text"}
            )
            print(f"  ✓ Created entity: {entity.name}")
        
        # Step 3: Store relationships in Neo4j
        print("\n💾 Storing relationships in Neo4j...")
        for idx, rel in enumerate(extraction_result.relationships):
            relationship_id = idx + 1
            
            # Get entity IDs from map
            source_id = entity_id_map.get(rel.source)
            target_id = entity_id_map.get(rel.target)
            
            if source_id and target_id:
                await create_relationship(
                    manager=neo4j_manager,
                    relationship_id=relationship_id,
                    external_id=external_id,
                    source_entity_id=source_id,
                    target_entity_id=target_id,
                    relationship_type=rel.type.value,
                    confidence=rel.confidence,
                    description=rel.description,
                    metadata={"extracted_from": "plain_text"}
                )
                print(f"  ✓ Created relationship: {rel.source} --[{rel.type}]--> {rel.target}")
            else:
                print(f"  ⚠ Skipped relationship (entities not found): {rel.source} -> {rel.target}")
        
        print("\n✅ Knowledge graph created successfully!")
        
    finally:
        await neo4j_manager.close()

# Example usage
if __name__ == "__main__":
    sample_text = """
    Sarah Johnson is a senior software engineer at Microsoft. She specializes in 
    machine learning and uses Python extensively for her work. Sarah is currently 
    working on a project that leverages TensorFlow and PyTorch frameworks to build 
    recommendation systems. The project is hosted on GitHub and uses Docker for 
    containerization. Sarah collaborates with the Azure team to deploy models to 
    the cloud.
    """
    
    asyncio.run(process_text_to_knowledge_graph(sample_text))
```

**Expected Output:**

```
🔍 Extracting knowledge from text...

✓ Found 9 entities:
  - Sarah Johnson (PERSON) - confidence: 1.0
  - Microsoft (ORGANIZATION) - confidence: 1.0
  - Python (LANGUAGE) - confidence: 1.0
  - TensorFlow (FRAMEWORK) - confidence: 1.0
  - PyTorch (FRAMEWORK) - confidence: 1.0
  - GitHub (PLATFORM) - confidence: 1.0
  - Docker (TOOL) - confidence: 1.0
  - Azure (PLATFORM) - confidence: 1.0
  - recommendation systems (CONCEPT) - confidence: 0.9

✓ Found 10 relationships:
  - Sarah Johnson --[WORKS_WITH]--> Microsoft - confidence: 1.0
  - Sarah Johnson --[USES]--> Python - confidence: 1.0
  - Sarah Johnson --[USES]--> TensorFlow - confidence: 1.0
  - Sarah Johnson --[USES]--> PyTorch - confidence: 1.0
  - Project --[USES]--> GitHub - confidence: 1.0
  - Project --[USES]--> Docker - confidence: 1.0
  - Sarah Johnson --[WORKS_WITH]--> Azure - confidence: 0.9
  ...

💾 Storing entities in Neo4j...
  ✓ Created entity: Sarah Johnson
  ✓ Created entity: Microsoft
  ...

💾 Storing relationships in Neo4j...
  ✓ Created relationship: Sarah Johnson --[WORKS_WITH]--> Microsoft
  ✓ Created relationship: Sarah Johnson --[USES]--> Python
  ...

✅ Knowledge graph created successfully!
```

## Querying the Knowledge Graph

### Find Entity Relationships

```python
async def get_entity_relationships(
    manager: Neo4jManager,
    entity_name: str,
    min_confidence: float = 0.5
):
    """Get all relationships for an entity."""
    query = """
    MATCH (e:Entity {name: $name})-[r:RELATES_TO]-(other:Entity)
    WHERE r.confidence >= $min_confidence
    RETURN e.name as entity,
           r.type as relationship_type,
           other.name as related_entity,
           r.confidence as confidence,
           r.description as description
    ORDER BY r.confidence DESC
    """
    
    async with manager.session() as session:
        result = await session.run(
            query,
            name=entity_name,
            min_confidence=min_confidence
        )
        
        relationships = []
        async for record in result:
            relationships.append({
                "entity": record["entity"],
                "relationship": record["relationship_type"],
                "related_entity": record["related_entity"],
                "confidence": record["confidence"],
                "description": record["description"]
            })
        
        return relationships
```

### Search by Entity Type

```python
async def find_entities_by_type(
    manager: Neo4jManager,
    entity_type: str,
    min_confidence: float = 0.7
):
    """Find all entities of a specific type."""
    query = """
    MATCH (e:Entity)
    WHERE e.type = $type AND e.confidence >= $min_confidence
    RETURN e.name as name,
           e.type as type,
           e.confidence as confidence,
           e.description as description
    ORDER BY e.confidence DESC
    """
    
    async with manager.session() as session:
        result = await session.run(
            query,
            type=entity_type,
            min_confidence=min_confidence
        )
        
        entities = []
        async for record in result:
            entities.append({
                "name": record["name"],
                "type": record["type"],
                "confidence": record["confidence"],
                "description": record["description"]
            })
        
        return entities
```

### Find Paths Between Entities

```python
async def find_connection_path(
    manager: Neo4jManager,
    entity1: str,
    entity2: str,
    max_depth: int = 5
):
    """Find shortest path between two entities."""
    query = """
    MATCH path = shortestPath(
        (e1:Entity {name: $entity1})-[*1..$max_depth]-(e2:Entity {name: $entity2})
    )
    RETURN [node IN nodes(path) | node.name] as entities,
           [rel IN relationships(path) | rel.type] as relationships
    """
    
    async with manager.session() as session:
        result = await session.run(
            query,
            entity1=entity1,
            entity2=entity2,
            max_depth=max_depth
        )
        
        record = await result.single()
        if record:
            return {
                "entities": record["entities"],
                "relationships": record["relationships"]
            }
        return None
```

## Integration with agent-reminiscence

The agent-reminiscence package provides a complete implementation:

```python
from agent_reminiscence import AgentMem
import asyncio

async def main():
    # Initialize AgentMem (handles Neo4j + PostgreSQL)
    agent_mem = AgentMem()
    await agent_mem.initialize()
    
    try:
        # Create an active memory
        memory = await agent_mem.create_active_memory(
            external_id="agent-123",
            title="Technical Knowledge",
            template_content={
                "template": {"id": "tech_notes", "name": "Tech Notes"},
                "sections": [{"id": "content", "description": "Main content"}]
            },
            initial_sections={
                "content": {
                    "content": """Sarah Johnson works at Microsoft. She uses Python 
                    and TensorFlow for ML projects."""
                }
            }
        )
        
        # Entities and relationships are automatically extracted and stored!
        # Search includes both text chunks AND graph relationships
        results = await agent_mem.deep_search_memories(
            external_id="agent-123",
            query="What technologies does Sarah use?",
            limit=10
        )
        
        # Access extracted knowledge triplets
        for triplet in results.shortterm_triplets:
            print(f"{triplet.subject} --[{triplet.predicate}]--> {triplet.object}")
        
    finally:
        await agent_mem.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## Best Practices

### 1. Confidence Thresholds

Set appropriate confidence thresholds based on your use case:

- **High precision** (0.8+): Use for critical relationships
- **Balanced** (0.6+): Good for most use cases
- **High recall** (0.4+): When you want to capture all possible connections

### 2. Entity Deduplication

Normalize entity names to prevent duplicates:

```python
def normalize_entity_name(name: str) -> str:
    """Normalize entity names for consistency."""
    return name.strip().title()
```

### 3. Batch Processing

For large texts, process in chunks:

```python
async def process_large_text(text: str, chunk_size: int = 2000):
    """Process large text in chunks."""
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
    
    for chunk in chunks:
        extraction_result = await extract_knowledge(chunk)
        # Store in Neo4j...
```

### 4. Model Selection

Choose LLM models based on needs:

- **GPT-4o**: Best quality, higher cost
- **GPT-4o-mini**: Good quality, lower cost (recommended)
- **Claude 3.5 Sonnet**: Excellent for technical content
- **Gemini**: Good for diverse content types

## Troubleshooting

### Issue: Low confidence scores

**Solution**: Adjust temperature or use more examples in the system prompt

### Issue: Missing relationships

**Solution**: Make extraction prompt more explicit about relationship extraction

### Issue: Neo4j connection errors

**Solution**: Verify Neo4j is running and credentials are correct:

```bash
docker ps | grep neo4j
```

## Additional Resources

- [Pydantic AI Documentation](https://ai.pydantic.dev/)
- [Neo4j Python Driver](https://neo4j.com/docs/python-manual/current/)
- [agent-reminiscence Repository](https://github.com/Ganzzi/agent-reminiscence)
