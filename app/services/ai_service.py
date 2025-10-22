"""
AI service for content analysis and quiz generation
"""
from openai import AsyncOpenAI
from typing import List, Dict, Any, Optional
from fastapi import HTTPException
import json
import logging

from ..core.config import settings
from ..models.quiz import Question, QuestionType, AnswerOption, DifficultyLevel
from ..models.note import AiInsights

logger = logging.getLogger(__name__)


class AIService:
    """Service for AI-powered features"""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def get_definition(self, text: str, context: str) -> Dict[str, Any]:
        """Get AI-powered definition for selected text"""
        try:
            prompt = f"""
            Provide a clear, educational definition for the term or phrase: "{text}"
            
            Context: {context[:500]}...
            
            Please provide:
            1. A simple definition suitable for students
            2. An example of usage
            3. Any relevant synonyms or related terms
            
            Format as JSON with fields: definition, example, related_terms
            """
            
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.3
            )
            
            # Parse response (simplified - in production, add proper JSON parsing)
            content = response.choices[0].message.content
            
            return {
                "definition": content,
                "source": "AI Generated",
                "confidence": 0.85
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting definition: {str(e)}")
    
    async def get_explanation(self, concept: str, context: str) -> Dict[str, Any]:
        """Get AI explanation for complex concepts"""
        try:
            prompt = f"""
            Explain the concept: "{concept}" in simple, educational terms.
            
            Context: {context[:500]}...
            
            Please provide:
            1. A clear explanation suitable for students
            2. Why this concept is important
            3. How it relates to the broader topic
            4. A simple analogy if applicable
            
            Keep the explanation concise but comprehensive.
            """
            
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.4
            )
            
            content = response.choices[0].message.content
            
            return {
                "explanation": content,
                "complexity_level": "intermediate",
                "estimated_read_time": 2
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error getting explanation: {str(e)}")
    
    async def generate_questions(self, content: str, question_count: int = 5, 
                               difficulty: DifficultyLevel = DifficultyLevel.medium,
                               question_types: List[QuestionType] = None) -> List[Question]:
        """Generate practice questions from content"""
        logger.info(f"🤖 AI: Starting question generation - count={question_count}, difficulty={difficulty}")
        try:
            if question_types is None:
                question_types = [QuestionType.multiple_choice, QuestionType.true_false]
            
            logger.info(f"📝 Content length: {len(content)} chars")
            logger.info(f"🎯 Question types: {[qt.value if hasattr(qt, 'value') else str(qt) for qt in question_types]}")
            
            prompt = f"""
            Generate {question_count} educational questions based on this content:
            
            {content}...
            
            Requirements:
            - Difficulty level: {difficulty.value}
            - Question types: {[qt.value if hasattr(qt, 'value') else str(qt) for qt in question_types]}
            - Focus on key concepts and important information
            - For multiple choice: provide 4 options with 1 correct answer
            - For true/false: provide clear statements
            - Include brief explanations for correct answers
            
            Format each question as:
            Question: [question text]
            Options: [if multiple choice - A, B, C, D]
            Correct: [correct answer]
            Explanation: [brief explanation]

            Present the overall answer as a JSON array with no prefix or suffix. Definitely always include JSON array with various JSON elements indicating each question.
            ---
            """
            
            logger.info(f"🌐 Calling OpenAI API...")
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
                temperature=0.6
            )
            
            logger.info(f"✅ OpenAI response received")
            
            # Parse response and create Question objects
            content_response = response.choices[0].message.content
            logger.info(f"📄 Response content length: {len(content_response)} chars")
            logger.debug(f"🔍 AI Response:\n{content_response}")
            
            questions = self._parse_generated_questions(content_response, difficulty)
            logger.info(f"✅ Parsed {len(questions)} questions from AI response")
            
            if len(questions) < question_count:
                logger.warning(f"⚠️ Only parsed {len(questions)} questions, but {question_count} were requested!")
            
            final_questions = questions[:question_count]
            logger.info(f"🎉 Returning {len(final_questions)} questions to caller")
            
            return final_questions
            
        except Exception as e:
            logger.error(f"❌ AI question generation error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error generating questions: {str(e)}")
    
    def _parse_generated_questions(self, content: str, difficulty: DifficultyLevel) -> List[Question]:
        """Parse AI-generated questions into Question objects"""
        logger.info(f"📋 Parsing AI response into Question objects...")
        logger.debug(f"🔍 Full content to parse:\n{content}")
        questions = []
        
        try:
            # Try to parse as JSON first
            json_data = json.loads(content.strip())
            logger.info(f"✅ Successfully parsed JSON response with {len(json_data)} questions")
            
            for i, question_data in enumerate(json_data):
                try:
                    question_text = question_data.get('Question', '')
                    options_dict = question_data.get('Options', {})
                    correct_answer = question_data.get('Correct', '')
                    explanation = question_data.get('Explanation', '')
                    
                    # Convert options dict to list of AnswerOption objects
                    options = []
                    for key, value in options_dict.items():
                        is_correct = key == correct_answer or correct_answer in value
                        options.append(AnswerOption(
                            id=f"opt_{i}_{key}",
                            text=f"{key}) {value}",
                            is_correct=is_correct
                        ))
                    
                    if question_text:
                        question = Question(
                            id=f"q_{i}",
                            type=QuestionType.multiple_choice,
                            question_text=question_text,
                            options=options,
                            correct_answer=None,  # Embedded in options
                            explanation=explanation,
                            difficulty=difficulty,
                            points=1
                        )
                        questions.append(question)
                        logger.info(f"✅ Successfully parsed question {len(questions)}: {question_text[:50]}...")
                        logger.debug(f"   Options: {len(options)}, Correct: {correct_answer}")
                    else:
                        logger.warning(f"⚠️ Question {i+1} had no question text, skipping")
                        
                except Exception as e:
                    logger.error(f"❌ Error parsing question {i+1}: {e}")
                    logger.debug(f"Failed question data: {question_data}")
                    continue
                    
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Failed to parse as JSON: {e}. Falling back to text parsing...")
            # Fallback to old text-based parsing
            questions = self._parse_text_format(content, difficulty)
        
        logger.info(f"🎯 Final parsing result: {len(questions)} questions successfully parsed")
        return questions
    
    def _parse_text_format(self, content: str, difficulty: DifficultyLevel) -> List[Question]:
        """Fallback parser for text-based format"""
        questions = []
        question_blocks = content.split('---')
        
        for i, block in enumerate(question_blocks):
            if not block.strip():
                continue
                
            try:
                lines = [line.strip() for line in block.split('\n') if line.strip()]
                
                question_text = ""
                question_type = QuestionType.multiple_choice
                options = []
                correct_answer = ""
                explanation = ""
                
                for line in lines:
                    if line.startswith('Question:'):
                        question_text = line.replace('Question:', '').strip()
                    elif line.startswith('Options:'):
                        options_text = line.replace('Options:', '').strip()
                        option_list = [opt.strip() for opt in options_text.split(',')]
                        options = [
                            AnswerOption(id=f"opt_{i}_{j}", text=opt, is_correct=False)
                            for j, opt in enumerate(option_list)
                        ]
                    elif line.startswith('Correct:'):
                        correct_answer = line.replace('Correct:', '').strip()
                    elif line.startswith('Explanation:'):
                        explanation = line.replace('Explanation:', '').strip()
                
                # Set correct option
                if options:
                    for option in options:
                        if correct_answer.lower() in option.text.lower():
                            option.is_correct = True
                            break
                
                if question_text:
                    question = Question(
                        id=f"q_{i}",
                        type=question_type,
                        question_text=question_text,
                        options=options,
                        correct_answer=correct_answer if question_type != QuestionType.multiple_choice else None,
                        explanation=explanation,
                        difficulty=difficulty,
                        points=1
                    )
                    questions.append(question)
                    
            except Exception as e:
                logger.error(f"❌ Error in text parsing block {i+1}: {e}")
                continue
        
        return questions
    
    async def analyze_comprehension(self, content: str, time_spent: int, 
                                  interactions: List[str]) -> Dict[str, Any]:
        """Analyze reading comprehension based on behavior"""
        try:
            prompt = f"""
            Analyze the reading comprehension based on:
            
            Content length: {len(content)} characters
            Time spent reading: {time_spent} seconds
            User interactions: {interactions}
            
            Provide assessment of:
            1. Reading speed (words per minute)
            2. Engagement level (based on interactions)
            3. Comprehension suggestions
            4. Recommended next steps
            
            Expected reading speed: 200-300 words per minute for comprehension.
            """
            
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.3
            )
            
            content = response.choices[0].message.content
            
            # Calculate basic metrics
            word_count = len(content.split())
            wpm = (word_count / time_spent) * 60 if time_spent > 0 else 0
            
            return {
                "analysis": content,
                "reading_speed_wpm": wpm,
                "engagement_score": min(len(interactions) * 0.1, 1.0),
                "recommendations": ["Take more time for complex concepts", "Try highlighting key points"]
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error analyzing comprehension: {str(e)}")
    
    async def generate_ai_insights(self, note_content: str, book_context: str) -> AiInsights:
        """Generate AI insights for notes"""
        try:
            prompt = f"""
            Analyze this student note and provide educational insights:
            
            Note: {note_content}
            Book context: {book_context[:300]}...
            
            Provide:
            1. A brief summary of the key points
            2. 3-5 key concepts mentioned
            3. Related topics the student should explore
            4. 2-3 practice questions based on the note
            5. Difficulty assessment
            """
            
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.4
            )
            
            content = response.choices[0].message.content
            
            # Simple parsing - in production, use structured output
            return AiInsights(
                summary=content[:200] + "...",
                key_concepts=["concept1", "concept2", "concept3"],  # Parse from response
                related_topics=["topic1", "topic2"],  # Parse from response
                difficulty_analysis="medium",
                suggested_questions=["Question 1?", "Question 2?"]  # Parse from response
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating insights: {str(e)}")
    
    async def generate_study_recommendations(
        self, 
        user_id: str,
        reading_history: List[str],
        recent_subjects: List[str],
        quiz_performance: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate personalized study recommendations for dashboard"""
        try:
            # Build context from user data
            subjects_str = ", ".join(recent_subjects) if recent_subjects else "various subjects"
            performance_str = ", ".join([f"{k}: {v}%" for k, v in quiz_performance.items()]) if quiz_performance else "no quiz data yet"
            
            prompt = f"""
            Generate personalized study recommendations for a student with:
            - Reading subjects: {subjects_str}
            - Books read: {len(reading_history)}
            - Quiz performance: {performance_str}
            
            Provide 3-5 actionable study tips that are:
            1. Specific to their reading patterns
            2. Encouraging and positive
            3. Based on learning science principles
            4. Practical and achievable
            
            Format as a list of tips, each 1-2 sentences.
            """
            
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.7
            )
            
            content = response.choices[0].message.content
            
            # Parse tips (simplified)
            tips = [tip.strip() for tip in content.split('\n') if tip.strip() and not tip.strip().startswith('#')]
            
            return {
                "recommendations": tips[:5],
                "personalized": True,
                "generated_at": "now"
            }
            
        except Exception as e:
            # Return fallback recommendations if AI fails
            return {
                "recommendations": [
                    "Try the spaced repetition technique: review material at increasing intervals.",
                    "Take short breaks every 25 minutes to improve focus and retention.",
                    "Practice active recall by testing yourself without looking at notes.",
                    "Connect new concepts to things you already know for better understanding.",
                    "Review your quiz mistakes to identify knowledge gaps."
                ],
                "personalized": False,
                "generated_at": "now"
            }
    
    async def generate_contextual_tips(
        self,
        subject: str,
        content_sample: str,
        page_number: int
    ) -> Dict[str, Any]:
        """Generate contextual study tips for reading interface"""
        try:
            prompt = f"""
            Generate a helpful study tip for a student reading {subject} content.
            
            Current page: {page_number}
            Content sample: {content_sample[:300]}...
            
            Provide ONE specific, actionable tip that:
            1. Relates to the subject matter
            2. Helps with comprehension or retention
            3. Is encouraging and practical
            4. Can be applied immediately
            
            Keep it to 1-2 sentences, friendly tone.
            """
            
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.7
            )
            
            tip = response.choices[0].message.content.strip()
            
            return {
                "tip": tip,
                "subject": subject,
                "page": page_number,
                "icon": "lightbulb_outline"
            }
            
        except Exception as e:
            # Return fallback tip if AI fails
            fallback_tips = {
                "Mathematics": "Try working through examples step-by-step and verify each calculation.",
                "Science": "Visualize the concepts by drawing diagrams or creating mental models.",
                "English": "Highlight key themes and character motivations as you read.",
                "History": "Create a timeline to understand the sequence of events better.",
                "default": "Take notes on important concepts and review them within 24 hours."
            }
            
            return {
                "tip": fallback_tips.get(subject, fallback_tips["default"]),
                "subject": subject,
                "page": page_number,
                "icon": "lightbulb_outline"
            }
    
    async def answer_reading_question(
        self,
        question: str,
        page_content: str,
        selected_text: Optional[str] = None,
        book_metadata: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Answer questions about reading content with context awareness"""
        try:
            # Calculate available tokens for context
            # gpt-3.5-turbo: 4096 tokens total
            # Reserve: 800 for response, 300 for system/instructions = ~3000 tokens available
            # Approximate: 4 chars per token = 12,000 chars safe limit
            max_context_chars = 12000
            
            logger.info(f"🤖 Processing question: '{question[:50]}...'")
            logger.info(f"📊 Raw page content length: {len(page_content)} chars")
            logger.info(f"📝 Has selected text: {selected_text is not None}")
            logger.info(f"💬 Conversation history length: {len(conversation_history) if conversation_history else 0}")
            
            # Smart truncation: prioritize content while staying within limits
            if len(page_content) > max_context_chars:
                logger.warning(f"⚠️ Page content ({len(page_content)} chars) exceeds limit ({max_context_chars})")
                # Keep the first portion which likely contains the most relevant context
                page_content = page_content[:max_context_chars]
                logger.info(f"✂️ Truncated to {len(page_content)} chars")
            else:
                logger.info(f"✅ Page content within limits ({len(page_content)} chars)")
            
            # Build the message array with proper system/user pattern
            messages = []
            
            # System message: Define the AI's role and behavior
            system_message = f"""You are an educational AI assistant helping a student understand their {book_metadata.get('subject', 'textbook')} reading material.

CRITICAL RULES:
1. Answer ONLY based on the provided reading material below
2. Quote specific passages from the text when explaining concepts
3. If the answer isn't clearly in the provided material, say "I don't see that specific information in these pages"
4. When quoting, mention which page the quote is from
5. Use clear, student-friendly language
6. Be specific and reference actual content from the reading

Book: {book_metadata.get('title', 'Unknown')} by {book_metadata.get('author', 'Unknown')}
Subject: {book_metadata.get('subject', 'General')}
Current Page: {book_metadata.get('current_page', '?')}
Pages Provided: This material covers multiple pages around the current page."""

            messages.append({"role": "system", "content": system_message})
            
            # Add conversation history (clean messages without repeated context)
            if conversation_history and len(conversation_history) > 0:
                # Take last 4 Q&A pairs (8 messages) for context continuity
                for msg in conversation_history[-8:]:
                    messages.append({
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", "")
                    })
                logger.info(f"📜 Added {len(conversation_history[-8:])} messages from history")
            
            # Build current question with context
            user_message_parts = []
            
            # Add reading material
            user_message_parts.append("=== READING MATERIAL ===")
            user_message_parts.append(page_content)
            user_message_parts.append("=== END READING MATERIAL ===")
            user_message_parts.append("")  # Blank line
            
            # Add selected text if available (gives AI focus)
            if selected_text:
                user_message_parts.append(f"Selected text from page: \"{selected_text}\"")
                user_message_parts.append("")
            
            # Add the actual question
            user_message_parts.append(f"Question: {question}")
            
            current_message = "\n".join(user_message_parts)
            messages.append({"role": "user", "content": current_message})
            
            logger.info(f"📤 Sending to OpenAI:")
            logger.info(f"   Model: gpt-3.5-turbo")
            logger.info(f"   System message: {len(system_message)} chars")
            logger.info(f"   Current message: {len(current_message)} chars")
            logger.info(f"   Total messages: {len(messages)}")
            
            # Call OpenAI with improved parameters
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=800,  # Increased for more detailed answers
                temperature=0.3,  # Lower for more focused, factual responses
                top_p=0.9,  # Slight nucleus sampling for quality
            )
            
            answer = response.choices[0].message.content.strip()
            tokens_used = response.usage.total_tokens if response.usage else 0
            
            logger.info(f"✅ Received response from OpenAI")
            logger.info(f"   Response length: {len(answer)} chars")
            logger.info(f"   Tokens used: {tokens_used}")
            logger.info(f"   Finish reason: {response.choices[0].finish_reason}")
            
            return {
                "answer": answer,
                "confidence": 0.90,
                "has_selected_text": selected_text is not None,
                "timestamp": "now",
                "tokens_used": tokens_used,
                "context_chars": len(page_content)
            }
            
        except Exception as e:
            logger.error(f"❌ Error answering reading question: {str(e)}")
            logger.exception("Full traceback:")
            raise HTTPException(status_code=500, detail=f"Error generating answer: {str(e)}")
    
    async def quick_define(
        self,
        text: str,
        context: str,
        book_subject: str = "General"
    ) -> Dict[str, Any]:
        """Provide enhanced definition with educational context"""
        try:
            # Use more context for better definitions (up to 3000 chars)
            max_context = 3000
            context_text = context[:max_context] if len(context) > max_context else context
            
            logger.info(f"📖 Defining term: '{text}' (context: {len(context_text)} chars)")
            
            system_message = f"""You are an educational assistant defining terms for a {book_subject} student.
Base your definition on the provided reading material."""

            user_prompt = f"""=== READING MATERIAL ===
{context_text}
=== END READING MATERIAL ===

Term to define: "{text}"

Provide:
1. A clear definition based on how it's used in this reading
2. How it relates to the {book_subject} topic
3. A brief example from the text or similar context
4. Any related concepts the student should know

Keep it educational and concise (2-3 paragraphs)."""

            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=500,
                temperature=0.3
            )
            
            definition = response.choices[0].message.content.strip()
            tokens_used = response.usage.total_tokens if response.usage else 0
            
            logger.info(f"✅ Definition generated ({len(definition)} chars, {tokens_used} tokens)")
            
            return {
                "term": text,
                "definition": definition,
                "subject": book_subject,
                "action_type": "define",
                "tokens_used": tokens_used
            }
            
        except Exception as e:
            logger.error(f"❌ Error generating definition: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error generating definition: {str(e)}")
    
    async def quick_explain(
        self,
        concept: str,
        context: str,
        difficulty_level: str = "intermediate"
    ) -> Dict[str, Any]:
        """Explain concepts with examples and analogies"""
        try:
            # Use more context for better explanations (up to 4000 chars)
            max_context = 4000
            context_text = context[:max_context] if len(context) > max_context else context
            
            logger.info(f"💡 Explaining concept: '{concept}' (context: {len(context_text)} chars)")
            
            system_message = f"""You are an educational assistant explaining concepts to {difficulty_level} level students.
Use the provided reading material to give context-specific explanations."""

            user_prompt = f"""=== READING MATERIAL ===
{context_text}
=== END READING MATERIAL ===

Concept to explain: "{concept}"

Based on the reading material above, provide an explanation that:
1. Breaks down the concept into simple terms
2. Uses examples or analogies from the text or similar to it
3. Explains why it's important in this context
4. Shows how it connects to the broader topic
5. References specific parts of the reading when relevant

Keep it educational, engaging, and student-friendly (2-3 paragraphs)."""

            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=600,
                temperature=0.4
            )
            
            explanation = response.choices[0].message.content.strip()
            tokens_used = response.usage.total_tokens if response.usage else 0
            
            logger.info(f"✅ Explanation generated ({len(explanation)} chars, {tokens_used} tokens)")
            
            return {
                "concept": concept,
                "explanation": explanation,
                "difficulty_level": difficulty_level,
                "action_type": "explain",
                "tokens_used": tokens_used
            }
            
        except Exception as e:
            logger.error(f"❌ Error generating explanation: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error generating explanation: {str(e)}")
    
    async def summarize_content(
        self,
        content: str,
        summary_type: str = "key_points",
        selected_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """Summarize page/section content"""
        try:
            # Use full content for summarization (up to reasonable limit)
            # For summarization, we want to see as much as possible
            max_summary_chars = 8000
            text_to_summarize = selected_text if selected_text else content
            
            if len(text_to_summarize) > max_summary_chars:
                text_to_summarize = text_to_summarize[:max_summary_chars]
            
            logger.info(f"📝 Summarizing content: {len(text_to_summarize)} chars, type: {summary_type}")
            
            system_message = """You are an educational assistant helping students summarize their reading material.
Focus on the most important information and key concepts."""
            
            if summary_type == "key_points":
                user_prompt = f"""=== READING MATERIAL ===
{text_to_summarize}
=== END READING MATERIAL ===

Extract and list the 4-6 most important key points from this reading material.

Format as a bulleted list. Each point should:
- Be 1-2 sentences
- Capture a main idea or concept
- Be specific to the content above

Format:
• Point 1
• Point 2
etc."""
            
            elif summary_type == "brief":
                user_prompt = f"""=== READING MATERIAL ===
{text_to_summarize}
=== END READING MATERIAL ===

Provide a brief summary (3-4 sentences) of the reading material above.
Focus on the main ideas and most important information."""
            
            else:  # detailed
                user_prompt = f"""=== READING MATERIAL ===
{text_to_summarize}
=== END READING MATERIAL ===

Provide a detailed summary of the reading material above.

Include:
- Main ideas and themes
- Important details and examples
- Key concepts introduced
- How topics connect to each other

Keep it comprehensive but organized (2-3 paragraphs)."""

            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=500,
                temperature=0.3
            )
            
            summary = response.choices[0].message.content.strip()
            tokens_used = response.usage.total_tokens if response.usage else 0
            
            logger.info(f"✅ Summary generated ({len(summary)} chars, {tokens_used} tokens)")
            
            return {
                "summary": summary,
                "summary_type": summary_type,
                "content_length": len(text_to_summarize),
                "action_type": "summarize",
                "tokens_used": tokens_used
            }
            
        except Exception as e:
            logger.error(f"❌ Error generating summary: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error generating summary: {str(e)}")