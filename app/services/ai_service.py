"""
AI service for content analysis and quiz generation
"""
import openai
from typing import List, Dict, Any, Optional
from fastapi import HTTPException

from ..core.config import settings
from ..models.quiz import Question, QuestionType, AnswerOption, DifficultyLevel
from ..models.note import AiInsights


class AIService:
    """Service for AI-powered features"""
    
    def __init__(self):
        openai.api_key = settings.OPENAI_API_KEY
    
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
            
            response = await openai.ChatCompletion.acreate(
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
            
            response = await openai.ChatCompletion.acreate(
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
        try:
            if question_types is None:
                question_types = [QuestionType.multiple_choice, QuestionType.true_false]
            
            prompt = f"""
            Generate {question_count} educational questions based on this content:
            
            {content[:2000]}...
            
            Requirements:
            - Difficulty level: {difficulty.value}
            - Question types: {[qt.value for qt in question_types]}
            - Focus on key concepts and important information
            - For multiple choice: provide 4 options with 1 correct answer
            - For true/false: provide clear statements
            - Include brief explanations for correct answers
            
            Format each question as:
            Type: [question_type]
            Question: [question text]
            Options: [if multiple choice - A, B, C, D]
            Correct: [correct answer]
            Explanation: [brief explanation]
            ---
            """
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
                temperature=0.6
            )
            
            # Parse response and create Question objects
            content = response.choices[0].message.content
            questions = self._parse_generated_questions(content, difficulty)
            
            return questions[:question_count]
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating questions: {str(e)}")
    
    def _parse_generated_questions(self, content: str, difficulty: DifficultyLevel) -> List[Question]:
        """Parse AI-generated questions into Question objects"""
        questions = []
        question_blocks = content.split('---')
        
        for i, block in enumerate(question_blocks):
            if not block.strip():
                continue
                
            try:
                # Simple parsing - in production, use more robust parsing
                lines = [line.strip() for line in block.split('\n') if line.strip()]
                
                question_text = ""
                question_type = QuestionType.multiple_choice
                options = []
                correct_answer = ""
                explanation = ""
                
                for line in lines:
                    if line.startswith('Type:'):
                        type_str = line.replace('Type:', '').strip()
                        if 'true_false' in type_str.lower():
                            question_type = QuestionType.true_false
                        elif 'short_answer' in type_str.lower():
                            question_type = QuestionType.short_answer
                    elif line.startswith('Question:'):
                        question_text = line.replace('Question:', '').strip()
                    elif line.startswith('Options:'):
                        # Parse options for multiple choice
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
                if question_type == QuestionType.multiple_choice and options:
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
                print(f"Error parsing question block: {e}")
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
            
            response = await openai.ChatCompletion.acreate(
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
            
            response = await openai.ChatCompletion.acreate(
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
