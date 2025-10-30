"""
Reading Assistant Agent using Google Gemini Function Calling

This service provides an intelligent reading assistant that uses Gemini's native function
calling to extract and analyze PDF content. The agent can:
- Extract text from specific pages or page ranges
- Search for keywords within the book
- Provide contextual answers grounded in the actual book content

The agent uses Gemini 2.0 Flash (experimental) with native function calling, which provides
the same agentic behavior as Google ADK but integrates more seamlessly with async FastAPI.
"""
import logging
from typing import Dict, Any, Optional, List
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool

from ..core.config import settings
from ..core.firebase_config import get_db
from .file_processor import FileProcessor

logger = logging.getLogger(__name__)


class ReadingAgentService:
    """Intelligent reading assistant using Gemini Function Calling"""
    
    def __init__(self):
        self.file_processor = FileProcessor()
        self.db = get_db()
        
        # Session cache for conversation history
        self.sessions = {}
        
        # Configure Gemini
        google_api_key = getattr(settings, 'GOOGLE_API_KEY', None)
        if not google_api_key:
            logger.error("❌ GOOGLE_API_KEY not configured")
            raise ValueError("GOOGLE_API_KEY not configured")
        
        genai.configure(api_key=google_api_key)
        
        # Create function declarations for the agent's tools
        self.tools = self._create_tools()
        
        # Create the model with function calling enabled
        self.model = genai.GenerativeModel(
            model_name='gemini-2.0-flash-exp',
            tools=self.tools,
            system_instruction="""You are an expert educational AI assistant helping students comprehend their textbook reading.

CAPABILITIES:
- You have access to tools to extract and analyze PDF book content
- You can answer questions, define terms, explain concepts, and summarize sections
- You can search for information across multiple pages

CRITICAL RULES:
1. Always use your tools to find relevant information from the book before answering
2. When answering, quote specific passages from the text and reference page numbers
3. If you cannot find the answer in the book content, state that clearly
4. Be concise but comprehensive
5. Maintain a helpful and educational tone

TOOL USAGE:
- Use `get_page_content` to get the full text of a single page
- Use `extract_page_range` to get text from multiple pages
- Use `search_in_pages` to find specific keywords or phrases

When a user asks a question:
1. First consider what information you need
2. Call the appropriate tool(s) to gather that information
3. Analyze the results and formulate a clear, grounded answer
"""
        )
        
        logger.info("✅ Reading Agent initialized with Gemini Function Calling")
        logger.info("   Model: gemini-2.0-flash-exp")
        logger.info(f"   Tools: {len(self.tools)} functions available")
    
    def _create_tools(self) -> List[Tool]:
        """Create function declarations for the agent's tools"""
        
        # Define function declarations that Gemini can call
        get_page_content = FunctionDeclaration(
            name="get_page_content",
            description="Extracts text content from a single specified page (1-indexed) of the PDF book",
            parameters={
                "type": "object",
                "properties": {
                    "page_number": {
                        "type": "integer",
                        "description": "The page number to extract (1-indexed)"
                    }
                },
                "required": ["page_number"]
            }
        )
        
        extract_page_range = FunctionDeclaration(
            name="extract_page_range",
            description="Extracts text content from a specified range of pages (inclusive, 1-indexed) of the PDF book",
            parameters={
                "type": "object",
                "properties": {
                    "start_page": {
                        "type": "integer",
                        "description": "The starting page number (1-indexed)"
                    },
                    "end_page": {
                        "type": "integer",
                        "description": "The ending page number (1-indexed, inclusive)"
                    }
                },
                "required": ["start_page", "end_page"]
            }
        )
        
        search_in_pages = FunctionDeclaration(
            name="search_in_pages",
            description="Searches for a query string within a specified range of pages and returns matching snippets with page numbers",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query string"
                    },
                    "start_page": {
                        "type": "integer",
                        "description": "The starting page number (1-indexed)"
                    },
                    "end_page": {
                        "type": "integer",
                        "description": "The ending page number (1-indexed, inclusive)"
                    }
                },
                "required": ["query", "start_page", "end_page"]
            }
        )
        
        # Return as a Tool object
        return [Tool(function_declarations=[get_page_content, extract_page_range, search_in_pages])]
    
    async def _execute_function_call(self, function_name: str, function_args: Dict[str, Any], book_file_path: str) -> Dict[str, Any]:
        """Execute a function call requested by the model"""
        
        try:
            if function_name == "get_page_content":
                page_number = int(function_args.get("page_number"))  # Convert to int (Gemini sends floats)
                logger.info(f"🔧 Executing: get_page_content(page={page_number})")
                logger.info(f"   Book file path: {book_file_path}")
                content = await self.file_processor.extract_text_from_pdf_page(book_file_path, page_number)
                logger.info(f"   ✅ Successfully extracted {len(content)} characters from page {page_number}")
                return {
                    "status": "success",
                    "page": page_number,
                    "content": content,
                    "char_count": len(content)
                }
            
            elif function_name == "extract_page_range":
                start_page = int(function_args.get("start_page"))  # Convert to int
                end_page = int(function_args.get("end_page"))  # Convert to int
                logger.info(f"🔧 Executing: extract_page_range(pages={start_page}-{end_page})")
                logger.info(f"   Book file path: {book_file_path}")
                content = await self.file_processor.extract_text_from_pdf_pages(book_file_path, start_page, end_page)
                logger.info(f"   ✅ Successfully extracted {len(content)} characters from pages {start_page}-{end_page}")
                return {
                    "status": "success",
                    "pages": f"{start_page}-{end_page}",
                    "content": content,
                    "char_count": len(content)
                }
            
            elif function_name == "search_in_pages":
                query = function_args.get("query")
                start_page = int(function_args.get("start_page"))  # Convert to int
                end_page = int(function_args.get("end_page"))  # Convert to int
                logger.info(f"🔧 Executing: search_in_pages(query='{query}', pages={start_page}-{end_page})")
                
                # Extract content from the page range
                full_content = await self.file_processor.extract_text_from_pdf_pages(book_file_path, start_page, end_page)
                
                # Simple keyword search
                results = []
                lines = full_content.split('\n')
                current_page = start_page
                
                for line in lines:
                    if line.startswith('--- Page '):
                        try:
                            current_page = int(line.split('Page ')[1].split(' ---')[0])
                        except:
                            pass
                    elif query.lower() in line.lower():
                        # Extract snippet around the match
                        snippet_start = max(0, line.lower().find(query.lower()) - 50)
                        snippet_end = min(len(line), line.lower().find(query.lower()) + len(query) + 50)
                        snippet = line[snippet_start:snippet_end].strip()
                        results.append(f"Page {current_page}: ...{snippet}...")
                
                return {
                    "status": "success",
                    "query": query,
                    "pages_searched": f"{start_page}-{end_page}",
                    "matches_found": len(results),
                    "results": results[:10]  # Limit to 10 results
                }
            
            else:
                return {
                    "status": "error",
                    "error": f"Unknown function: {function_name}"
                }
        
        except Exception as e:
            logger.error(f"❌ Error executing {function_name}: {e}")
            logger.error(f"   Function: {function_name}")
            logger.error(f"   Args: {function_args}")
            logger.error(f"   Book file: {book_file_path}")
            logger.exception("   Full traceback:")
            return {
                "status": "error",
                "function": function_name,
                "error": str(e),
                "details": f"Failed to execute {function_name} with args {function_args}"
            }
    
    def get_or_create_session(self, user_id: str, book_id: str) -> str:
        """Get or create a session for the user and book combination"""
        session_key = f"{user_id}:{book_id}"
        
        if session_key not in self.sessions:
            # Create new session
            self.sessions[session_key] = {
                "user_id": user_id,
                "book_id": book_id,
                "messages": [],
                "created_at": "now"
            }
            logger.info(f"📝 Created new session for {session_key}")
        
        return session_key
    
    async def save_session_to_firebase(self, session_key: str):
        """Persist session to Firebase"""
        try:
            if session_key in self.sessions:
                session_data = self.sessions[session_key]
                user_id = session_data["user_id"]
                book_id = session_data["book_id"]
                
                # Save to Firebase under user's document
                session_ref = self.db.collection('users').document(user_id)\
                    .collection('reading_sessions').document(book_id)
                
                session_ref.set({
                    "messages": session_data["messages"][-20:],  # Keep last 20 messages
                    "last_updated": "now"
                }, merge=True)
                
                logger.info(f"💾 Saved session to Firebase: {session_key}")
        except Exception as e:
            logger.warning(f"⚠️ Could not save session to Firebase: {e}")
    
    async def load_session_from_firebase(self, user_id: str, book_id: str) -> Optional[Dict]:
        """Load session from Firebase"""
        try:
            session_ref = self.db.collection('users').document(user_id)\
                .collection('reading_sessions').document(book_id)
            
            doc = session_ref.get()
            if doc.exists:
                logger.info(f"📂 Loaded session from Firebase for {user_id}:{book_id}")
                return doc.to_dict()
            return None
        except Exception as e:
            logger.warning(f"⚠️ Could not load session from Firebase: {e}")
            return None
    
    async def ask_question(
        self,
        question: str,
        book_file_path: str,
        book_metadata: Dict[str, Any],
        user_id: str,
        current_page: int,
        selected_text: Optional[str] = None,
        conversation_history: Optional[list] = None,
        provided_page_context: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Ask the reading agent a question.
        Agent will use tools to extract relevant content and reason about the answer.
        """
        try:
            session_key = self.get_or_create_session(user_id, book_metadata.get("book_id", "unknown"))
            
            # Build context for the agent
            gemini_history: List[Dict[str, Any]] = []
            if conversation_history:
                prior_messages = conversation_history[:-1]
                if prior_messages:
                    limited_history = prior_messages[-10:]
                    for message in limited_history:
                        content_text = message.get("content") if isinstance(message, dict) else None
                        role = message.get("role") if isinstance(message, dict) else None
                        if not content_text or not role:
                            continue
                        gemini_history.append({"role": role, "parts": [content_text]})

            context_parts = []
            context_parts.append(f"Book: {book_metadata.get('title')} by {book_metadata.get('author')}")
            context_parts.append(f"Subject: {book_metadata.get('subject')}")
            context_parts.append(f"Student is currently on page {current_page} of {book_metadata.get('total_pages')} pages")
            if book_metadata.get('extracted_range'):
                context_parts.append(f"Extracted PDF context spans pages {book_metadata.get('extracted_range')}")
            context_parts.append(f"Book file path: {book_file_path}")
            
            if selected_text:
                context_parts.append(f"\nStudent has selected this text (treat as the primary focus): \"{selected_text}\"")

            if provided_page_context:
                context_parts.append("\nAdditional context captured from the reading interface:")
                ordered_labels = [
                    ("previous_page_text", "Previous page"),
                    ("current_page_text", "Current page"),
                    ("next_page_text", "Next page"),
                ]
                for key, label in ordered_labels:
                    text = provided_page_context.get(key)
                    if not text:
                        continue
                    trimmed = text if len(text) <= 4000 else text[:4000] + "..."
                    context_parts.append(f"\n{label} context:\n{trimmed}")

            if conversation_history:
                prior_messages = conversation_history[:-1]
                if prior_messages:
                    recent_history = prior_messages[-6:]
                    context_parts.append("\nRecent conversation before this question:")
                    for message in recent_history:
                        role_label = "Student" if message.get("role") == "user" else "Assistant"
                        text = message.get("content", "")
                        if not text:
                            continue
                        trimmed_text = text if len(text) <= 600 else text[:600] + "..."
                        context_parts.append(f"{role_label}: {trimmed_text}")
            
            context_parts.append(f"\nStudent's question: {question}")
            context_parts.append(f"\nPlease use your tools to extract relevant content from the book and provide a thorough answer.")
            
            full_prompt = "\n".join(context_parts)
            
            logger.info(f"🤖 Agent processing question with Gemini Function Calling")
            logger.info(f"   Current page: {current_page}")
            logger.info(f"   Has selected text: {selected_text is not None}")
            logger.info(f"   Provided context keys: {list(provided_page_context.keys()) if provided_page_context else []}")
            logger.info(f"   Prior conversation turns supplied: {len(gemini_history)}")
            logger.info(f"   Book file: {book_file_path[:50]}...")
            
            # Start a chat session for multi-turn conversation
            chat = self.model.start_chat(history=gemini_history)
            
            # Send the prompt and handle function calling loop
            response = await chat.send_message_async(full_prompt)
            
            # Handle function calling loop
            max_iterations = 5  # Prevent infinite loops
            iterations = 0
            
            # Check if response has a function call in any part
            def has_function_call(resp):
                try:
                    if not resp.candidates:
                        return False
                    parts = resp.candidates[0].content.parts
                    if not parts:
                        return False
                    # Check if any part contains a function call
                    for part in parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            return True
                    return False
                except:
                    return False
            
            # Get the first function call from response parts
            def get_function_call(resp):
                try:
                    if not resp.candidates:
                        return None
                    parts = resp.candidates[0].content.parts
                    if not parts:
                        return None
                    # Return the first function call found
                    for part in parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            return part.function_call
                    return None
                except:
                    return None
            
            while has_function_call(response) and iterations < max_iterations:
                iterations += 1
                function_call = get_function_call(response)
                if not function_call:
                    logger.warning("⚠️ has_function_call returned True but couldn't extract function call")
                    break
                function_name = function_call.name
                function_args = dict(function_call.args)
                
                logger.info(f"🔧 Model requested function: {function_name}")
                logger.info(f"   Args: {function_args}")
                
                # Execute the function
                function_result = await self._execute_function_call(
                    function_name,
                    function_args,
                    book_file_path
                )
                
                logger.info(f"✅ Function executed: {function_name}")
                logger.info(f"   Result status: {function_result.get('status')}")
                if function_result.get('status') == 'error':
                    logger.error(f"   ⚠️ Function returned error: {function_result.get('error')}")
                    logger.error(f"   Error details: {function_result.get('details', 'N/A')}")
                else:
                    if 'char_count' in function_result:
                        logger.info(f"   Content length: {function_result.get('char_count')} chars")
                
                # Send function result back to the model
                response = await chat.send_message_async(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=function_name,
                            response=function_result
                        )
                    )
                )
            
            logger.info(f"🔄 Function calling loop completed after {iterations} iterations")
            logger.info(f"   Response has function call: {has_function_call(response)}")
            
            # Extract the final answer (now it should be text, not a function call)
            try:
                answer = response.text.strip()
                logger.info(f"✅ Successfully extracted answer text")
            except Exception as e:
                logger.error(f"❌ Could not extract text from response: {e}")
                logger.error(f"   Response has candidates: {bool(response.candidates)}")
                if response.candidates:
                    logger.error(f"   Response parts count: {len(response.candidates[0].content.parts)}")
                    logger.error(f"   First part type: {type(response.candidates[0].content.parts[0])}")
                
                # Fallback: try to get text from parts
                answer = ""
                if response.candidates and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, 'text') and part.text:
                            answer += part.text
                            logger.info(f"   Extracted text from part: {len(part.text)} chars")
                
                if not answer:
                    logger.error("   No text could be extracted from response")
                    answer = "I apologize, but I encountered an issue processing your question. Please try rephrasing it."
            
            # Update session
            if session_key in self.sessions:
                self.sessions[session_key]["messages"].append({
                    "role": "user",
                    "content": question
                })
                self.sessions[session_key]["messages"].append({
                    "role": "assistant",
                    "content": answer
                })
            
            # Persist to Firebase
            await self.save_session_to_firebase(session_key)
            
            logger.info(f"✅ Agent response generated")
            logger.info(f"   Response length: {len(answer)} chars")
            logger.info(f"   Function calls made: {iterations}")
            
            return {
                "answer": answer,
                "confidence": 0.95,
                "agent_used_tools": iterations > 0,  # True if model called any functions
                "function_calls_made": iterations,
                "session_key": session_key,
                "client_context_used": bool(provided_page_context)
            }
            
        except Exception as e:
            logger.error(f"❌ Error in agent question processing: {str(e)}")
            logger.exception("Full traceback:")
            raise


# Global agent instance
_reading_agent_service = None

def get_reading_agent() -> ReadingAgentService:
    """Get or create the global reading agent service"""
    global _reading_agent_service
    if _reading_agent_service is None:
        _reading_agent_service = ReadingAgentService()
    return _reading_agent_service

