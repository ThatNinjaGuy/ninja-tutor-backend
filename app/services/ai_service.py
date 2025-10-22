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
            # Build context from available information
            context_parts = []
            
            if selected_text:
                context_parts.append(f"Selected text: \"{selected_text}\"")
            
            context_parts.append(f"Page content:\n{page_content[:2000]}")  # Limit to avoid token overflow
            
            if book_metadata:
                context_parts.append(f"Book: {book_metadata.get('title', 'Unknown')} by {book_metadata.get('author', 'Unknown')}")
                context_parts.append(f"Subject: {book_metadata.get('subject', 'General')}")
            
            context = "\n\n".join(context_parts)
            
            # Build conversation history for context
            messages = []
            if conversation_history:
                for msg in conversation_history[-6:]:  # Keep last 6 messages for context
                    messages.append({
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", "")
                    })
            
            # Add current question with context
            prompt = f"""You are an educational AI assistant helping a student understand their reading material.

Context:
{context}

Student's Question: {question}

Please provide a clear, educational answer that:
1. Directly answers the student's question
2. References the reading material when relevant
3. Explains concepts in a student-friendly way
4. Suggests related topics they might want to explore

Keep your answer concise but comprehensive (2-3 paragraphs)."""

            messages.append({"role": "user", "content": prompt})
            
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=600,
                temperature=0.5
            )
            
            answer = response.choices[0].message.content.strip()
            
            return {
                "answer": answer,
                "confidence": 0.85,
                "has_selected_text": selected_text is not None,
                "timestamp": "now"
            }
            
        except Exception as e:
            logger.error(f"Error answering reading question: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error generating answer: {str(e)}")
    
    async def quick_define(
        self,
        text: str,
        context: str,
        book_subject: str = "General"
    ) -> Dict[str, Any]:
        """Provide enhanced definition with educational context"""
        try:
            prompt = f"""Define the following term/phrase for a student reading {book_subject} material:

Term: "{text}"

Context from reading:
{context[:500]}

Provide:
1. A clear, simple definition
2. How it's used in this context
3. An example sentence
4. Any related terms the student should know

Format your response as a short, educational explanation (2-3 paragraphs max)."""

            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.3
            )
            
            definition = response.choices[0].message.content.strip()
            
            return {
                "term": text,
                "definition": definition,
                "subject": book_subject,
                "action_type": "define"
            }
            
        except Exception as e:
            logger.error(f"Error generating definition: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error generating definition: {str(e)}")
    
    async def quick_explain(
        self,
        concept: str,
        context: str,
        difficulty_level: str = "intermediate"
    ) -> Dict[str, Any]:
        """Explain concepts with examples and analogies"""
        try:
            prompt = f"""Explain this concept to a student at {difficulty_level} level:

Concept: "{concept}"

Context:
{context[:500]}

Your explanation should:
1. Break down the concept into simple terms
2. Use an analogy or real-world example
3. Explain why it's important
4. Show how it connects to the reading

Keep it concise and engaging (2-3 paragraphs)."""

            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.4
            )
            
            explanation = response.choices[0].message.content.strip()
            
            return {
                "concept": concept,
                "explanation": explanation,
                "difficulty_level": difficulty_level,
                "action_type": "explain"
            }
            
        except Exception as e:
            logger.error(f"Error generating explanation: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error generating explanation: {str(e)}")
    
    async def summarize_content(
        self,
        content: str,
        summary_type: str = "key_points",
        selected_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """Summarize page/section content"""
        try:
            # Determine what to summarize
            text_to_summarize = selected_text if selected_text else content[:2000]
            
            if summary_type == "key_points":
                prompt = f"""Extract the key points from this reading material:

{text_to_summarize}

List 3-5 main points in bullet format. Keep each point concise (1-2 sentences)."""
            
            elif summary_type == "brief":
                prompt = f"""Provide a brief summary (2-3 sentences) of this reading material:

{text_to_summarize}"""
            
            else:  # detailed
                prompt = f"""Provide a detailed summary of this reading material:

{text_to_summarize}

Include:
- Main ideas and themes
- Important details and examples
- Key concepts introduced

Keep it to 1-2 paragraphs."""

            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.3
            )
            
            summary = response.choices[0].message.content.strip()
            
            return {
                "summary": summary,
                "summary_type": summary_type,
                "content_length": len(text_to_summarize),
                "action_type": "summarize"
            }
            
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error generating summary: {str(e)}")