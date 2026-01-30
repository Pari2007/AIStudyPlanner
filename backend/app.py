import os
from flask import Flask, render_template, request, jsonify
from gemini_client import GeminiClient
from focus_tracking import focus_tracker
import datetime
import json

app = Flask(__name__, template_folder='../templates')
client = GeminiClient()

print("Starting Flask app...")
print(f"Template folder: {app.template_folder}")

# Global storage for the latest timetable
latest_timetable = None

# Global storage for progress data
progress_data = {
    'total_hours': 0,
    'topics_covered': 0,
    'day_streak': 0,
    'average_focus': 0,
    'subjects': {}  # subject -> {'hours_studied': 0, 'total_hours': 0, 'last_updated': ''}
}

# Global storage for quiz data
quiz_data = {
    'current_quiz': None,
    'quiz_history': []
}

def parse_deadline(deadline_str):
    """Parse deadline string into datetime object"""
    try:
        # Try different date formats
        formats = [
            '%Y-%m-%d',  # 2026-01-31
            '%d/%m/%Y',  # 31/01/2026
            '%m/%d/%Y',  # 01/31/2026
            '%d %B %Y',  # 31 January 2026
            '%d %b %Y',  # 31 Jan 2026
            '%B %d, %Y', # January 31, 2026
            '%b %d, %Y', # Jan 31, 2026
        ]
        
        for fmt in formats:
            try:
                return datetime.datetime.strptime(deadline_str, fmt).date()
            except ValueError:
                continue
        
        # If no format works, try to extract date components
        # Handle formats like "31st January 2026"
        import re
        match = re.search(r'(\d{1,2})(?:st|nd|rd|th)?\s+(\w+)\s+(\d{4})', deadline_str)
        if match:
            day, month_name, year = match.groups()
            month_names = {
                'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
                'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }
            month = month_names.get(month_name.lower())
            if month:
                return datetime.date(int(year), month, int(day))
        
        return None
    except Exception:
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/focus-detection')
def focus_detection():
    return render_template('focus-detection.html')

@app.route('/timetable')
def timetable():
    return render_template('timetable.html')

@app.route('/study-now')
def study_now():
    return render_template('study-now.html')

@app.route('/progress')
def progress():
    return render_template('progress.html')

@app.route('/goal-optimizer')
def goal_optimizer():
    return render_template('goal-optimizer.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    payload = request.get_json(silent=True) or {}
    user_message = payload.get('message', '').strip()
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400

    try:
        response_text = client.generate_response(user_message)
        return jsonify({'response': response_text})
    except Exception as e:
        return jsonify({'error': 'Error generating response'}), 500

@app.route('/api/focus-tracking/start', methods=['POST'])
def start_focus_tracking():
    """Start focus tracking session"""
    try:
        focus_tracker.start_tracking()
        return jsonify({'status': 'started', 'message': 'Focus tracking started'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/focus-tracking/stop', methods=['POST'])
def stop_focus_tracking():
    """Stop focus tracking session"""
    try:
        focus_tracker.stop_tracking()
        stats = focus_tracker.get_stats()
        return jsonify({'status': 'stopped', 'stats': stats})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/focus-tracking/record-instagram', methods=['POST'])
def record_instagram_switch():
    """Record an Instagram switch"""
    try:
        focus_tracker.record_instagram_switch()
        return jsonify({'status': 'recorded'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/focus-tracking/stats', methods=['GET'])
def get_focus_stats():
    """Get current focus tracking statistics"""
    try:
        stats = focus_tracker.get_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/timetable/create', methods=['POST'])
def create_timetable():
    """Create a smart study timetable"""
    global latest_timetable
    try:
        data = request.get_json()
        deadline = data.get('deadline')
        subject = data.get('subject')
        target_hours = data.get('target')
        description = data.get('description', '')

        if not all([deadline, subject, target_hours]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Validate and parse deadline
        deadline_date = parse_deadline(deadline)
        if not deadline_date:
            return jsonify({'error': 'Invalid deadline format. Please use formats like "31 January 2026" or "2026-01-31"'}), 400
        
        current_date = datetime.datetime.now().date()
        if deadline_date <= current_date:
            return jsonify({'error': 'Deadline must be in the future'}), 400

        # Generate timetable using AI with structured output
        current_date_str = datetime.datetime.now().strftime("%d %B %Y")
        prompt = f"""
        Today is {current_date_str}.

        Create a detailed study schedule for the following:

        Subject/Topic: {subject}
        Deadline: {deadline}
        Total hours needed: {target_hours}
        Description: {description}

        Please provide:
        1. A realistic assessment of whether this goal is achievable given the time remaining until the deadline
        2. If achievable, create a daily schedule showing hours per day
        3. Include study tips and break recommendations
        4. Suggest optimal study times and duration per session

        Format the response as a structured schedule that the user can follow.

        Additionally, provide a JSON object with the following structure:
        {{
            "subject": "{subject}",
            "deadline": "{deadline}",
            "total_hours": {target_hours},
            "is_achievable": true/false,
            "daily_schedule": [
                {{
                    "date": "YYYY-MM-DD",
                    "hours": number,
                    "tasks": ["task1", "task2"],
                    "priority": "high/medium/low"
                }}
            ],
            "recommendations": ["tip1", "tip2"]
        }}

        First provide the human-readable schedule, then on a new line provide the JSON data starting with "JSON_START:" and ending with ":JSON_END"
        """

        response = client.generate_response(prompt)
        
        # Parse the response to extract schedule and JSON
        schedule_text = response
        json_data = None
        
        if "JSON_START:" in response and ":JSON_END" in response:
            parts = response.split("JSON_START:")
            if len(parts) > 1:
                schedule_text = parts[0].strip()
                json_part = parts[1].split(":JSON_END")[0].strip()
                try:
                    json_data = json.loads(json_part)
                except:
                    json_data = None
        
        # Store the timetable data
        latest_timetable = {
            'subject': subject,
            'deadline': deadline,
            'deadline_date': deadline_date.isoformat(),
            'total_hours': target_hours,
            'schedule_text': schedule_text,
            'structured_data': json_data,
            'created_at': datetime.datetime.now().isoformat()
        }
        
        # Clean up the schedule output by removing unwanted characters
        schedule_text = schedule_text.replace('*', '').replace('--', '').replace('#', '')
        
        return jsonify({'schedule': schedule_text})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/study-now/recommend', methods=['GET'])
def get_study_recommendation():
    """Get AI-powered study recommendation based on current timetable"""
    global latest_timetable
    
    try:
        if not latest_timetable:
            return jsonify({'error': 'No timetable found. Please create a timetable first.'}), 400
        
        current_time = datetime.datetime.now()
        current_hour = current_time.hour
        
        # Determine time of day
        if 6 <= current_hour < 12:
            time_of_day = "morning"
        elif 12 <= current_hour < 17:
            time_of_day = "afternoon"
        elif 17 <= current_hour < 22:
            time_of_day = "evening"
        else:
            time_of_day = "night"
        
        # If we have structured data, use it for better recommendations
        if latest_timetable.get('structured_data'):
            structured = latest_timetable['structured_data']
            
            # Find tasks for today or upcoming days
            today = current_time.date().isoformat()
            tomorrow = (current_time + datetime.timedelta(days=1)).date().isoformat()
            
            relevant_tasks = []
            for day in structured.get('daily_schedule', []):
                if day['date'] >= today:
                    for task in day.get('tasks', []):
                        relevant_tasks.append({
                            'task': task,
                            'date': day['date'],
                            'hours': day['hours'],
                            'priority': day.get('priority', 'medium'),
                            'is_today': day['date'] == today,
                            'is_tomorrow': day['date'] == tomorrow
                        })
            
            if relevant_tasks:
                # Sort by priority and urgency
                priority_order = {'high': 3, 'medium': 2, 'low': 1}
                relevant_tasks.sort(key=lambda x: (
                    1 if x['is_today'] else (0.5 if x['is_tomorrow'] else 0),  # Today first, then tomorrow
                    priority_order.get(x['priority'], 2),  # Higher priority first
                    -x['hours']  # More hours first (assuming more important)
                ), reverse=True)
                
                best_task = relevant_tasks[0]
                
                # Determine duration based on time of day and task
                if time_of_day == "morning":
                    duration = f"{min(best_task['hours'], 2)}-3 hours"
                    reason_extra = "morning study pattern for optimal focus"
                elif time_of_day == "afternoon":
                    duration = f"{min(best_task['hours'], 1.5)}-2 hours" 
                    reason_extra = "afternoon session with good energy levels"
                elif time_of_day == "evening":
                    duration = f"{min(best_task['hours'], 1)}-1.5 hours"
                    reason_extra = "evening review session"
                else:
                    duration = f"{min(best_task['hours'], 1)} hour"
                    reason_extra = "late night focused work"
                
                reason = f"{best_task['priority'].title()} priority task"
                if best_task['is_today']:
                    reason += ", scheduled for today"
                elif best_task['is_tomorrow']:
                    reason += ", scheduled for tomorrow"
                reason += f", and fits your current {reason_extra}."
                
                return jsonify({
                    'task': best_task['task'],
                    'reason': reason,
                    'duration': f"Estimated time: {duration}",
                    'subject': latest_timetable['subject'],
                    'deadline': latest_timetable['deadline']
                })
        
        # Fallback: Use AI to analyze the text schedule
        schedule_text = latest_timetable['schedule_text']
        
        prompt = f"""
        Today is {current_time.strftime('%d %B %Y')}.

        Based on the following study schedule, recommend the best task to study right now.

        Current time: {current_time.strftime('%Y-%m-%d %H:%M')} ({time_of_day})
        Deadline: {latest_timetable['deadline']}
        Schedule: {schedule_text}

        Consider:
        - Current time of day and optimal study times
        - Task priorities and deadlines
        - User's focus patterns (assume morning/afternoon are better for deep work)

        Provide a JSON response with:
        {{
            "task": "specific task name",
            "reason": "why this task is recommended now",
            "duration": "estimated time as string"
        }}
        """
        
        ai_response = client.generate_response(prompt)
        
        # Try to parse JSON from response
        try:
            # Extract JSON if wrapped in text
            json_start = ai_response.find('{')
            json_end = ai_response.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_str = ai_response[json_start:json_end]
                recommendation = json.loads(json_str)
                return jsonify(recommendation)
        except:
            pass
        
        # Fallback to simple parsing
        lines = ai_response.strip().split('\n')
        task = "Recommended study task"
        reason = "Based on your current schedule and time"
        duration = "1-2 hours"
        
        for line in lines:
            line = line.strip()
            if line.startswith('Task:') or line.startswith('"task":'):
                task = line.split(':', 1)[1].strip().strip('"')
            elif line.startswith('Reason:') or line.startswith('"reason":'):
                reason = line.split(':', 1)[1].strip().strip('"')
            elif line.startswith('Duration:') or line.startswith('"duration":'):
                duration = line.split(':', 1)[1].strip().strip('"')
        
        return jsonify({
            'task': task,
            'reason': reason,
            'duration': f"Estimated time: {duration}"
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/progress', methods=['GET'])
def get_progress():
    """Get current progress data"""
    global progress_data, latest_timetable
    
    # If we have a timetable, include subject-specific progress
    current_subject = None
    if latest_timetable:
        current_subject = latest_timetable.get('subject')
        if current_subject and current_subject not in progress_data['subjects']:
            progress_data['subjects'][current_subject] = {
                'hours_studied': 0,
                'total_hours': latest_timetable.get('total_hours', 0),
                'last_updated': ''
            }
    
    return jsonify({
        'total_hours': progress_data['total_hours'],
        'topics_covered': progress_data['topics_covered'],
        'day_streak': progress_data['day_streak'],
        'average_focus': progress_data['average_focus'],
        'subjects': progress_data['subjects'],
        'current_subject': current_subject
    })

@app.route('/api/progress/update', methods=['POST'])
def update_progress():
    """Update progress for a subject"""
    global progress_data, latest_timetable
    
    try:
        data = request.get_json()
        subject = data.get('subject')
        hours_studied = float(data.get('hours_studied', 0))
        
        if not subject:
            return jsonify({'error': 'Subject is required'}), 400
        
        if hours_studied < 0:
            return jsonify({'error': 'Hours studied cannot be negative'}), 400
        
        # Initialize subject if not exists
        if subject not in progress_data['subjects']:
            progress_data['subjects'][subject] = {
                'hours_studied': 0,
                'total_hours': latest_timetable.get('total_hours', 0) if latest_timetable and latest_timetable.get('subject') == subject else 0,
                'last_updated': ''
            }
        
        # Update progress
        progress_data['subjects'][subject]['hours_studied'] += hours_studied
        progress_data['subjects'][subject]['last_updated'] = datetime.datetime.now().isoformat()
        progress_data['total_hours'] += hours_studied
        
        # Update topics covered if this subject wasn't tracked before
        if progress_data['subjects'][subject]['hours_studied'] == hours_studied:
            progress_data['topics_covered'] += 1
        
        return jsonify({
            'success': True,
            'subject': subject,
            'hours_studied': progress_data['subjects'][subject]['hours_studied'],
            'total_hours': progress_data['total_hours']
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/quiz/generate', methods=['POST'])
def generate_quiz():
    """Generate a quiz based on the current subject"""
    global latest_timetable, quiz_data
    
    try:
        if not latest_timetable:
            return jsonify({'error': 'No timetable found. Please create a timetable first.'}), 400
        
        subject = latest_timetable.get('subject', '')
        if not subject:
            return jsonify({'error': 'No subject found in timetable.'}), 400
        
        # Generate quiz questions using AI
        prompt = f"""
        Create a 10-question multiple choice quiz for the subject: {subject}
        
        The quiz should test fundamental concepts and identify knowledge gaps.
        Each question should have 4 options (A, B, C, D) with only one correct answer.
        
        Format the response as a JSON array of questions:
        [
            {{
                "question": "What is the capital of France?",
                "options": ["London", "Berlin", "Paris", "Madrid"],
                "correct_answer": "C",
                "topic": "Geography",
                "difficulty": "easy"
            }}
        ]
        
        Make questions progressively more difficult and cover different aspects of {subject}.
        Include topics like: basic concepts, problem-solving, applications, and advanced topics.
        """
        
        ai_response = client.generate_response(prompt)
        
        # Parse the JSON response
        try:
            # Extract JSON if wrapped in text
            json_start = ai_response.find('[')
            json_end = ai_response.rfind(']') + 1
            if json_start != -1 and json_end > json_start:
                json_str = ai_response[json_start:json_end]
                questions = json.loads(json_str)
            else:
                questions = json.loads(ai_response)
            
            # Validate questions format
            for q in questions:
                if not all(key in q for key in ['question', 'options', 'correct_answer', 'topic']):
                    q['topic'] = 'General'
                    q['difficulty'] = 'medium'
            
            # Store the quiz
            quiz_data['current_quiz'] = {
                'subject': subject,
                'questions': questions,
                'answers': [],
                'results': {},
                'created_at': datetime.datetime.now().isoformat()
            }
            
            return jsonify({
                'subject': subject,
                'questions': questions,
                'total_questions': len(questions)
            })
            
        except json.JSONDecodeError:
            return jsonify({'error': 'Failed to generate quiz questions. Please try again.'}), 500
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/quiz/submit', methods=['POST'])
def submit_quiz():
    """Submit quiz answers and calculate results"""
    global quiz_data
    
    try:
        if not quiz_data.get('current_quiz'):
            return jsonify({'error': 'No active quiz found.'}), 400
        
        data = request.get_json()
        answers = data.get('answers', [])
        
        quiz = quiz_data['current_quiz']
        questions = quiz['questions']
        
        if len(answers) != len(questions):
            return jsonify({'error': 'Number of answers does not match number of questions.'}), 400
        
        # Calculate results
        correct_answers = 0
        topic_performance = {}
        difficulty_performance = {}
        weak_areas = []
        strong_areas = []
        
        for i, (question, answer) in enumerate(zip(questions, answers)):
            is_correct = answer.upper() == question['correct_answer'].upper()
            if is_correct:
                correct_answers += 1
            
            # Track performance by topic
            topic = question.get('topic', 'General')
            if topic not in topic_performance:
                topic_performance[topic] = {'correct': 0, 'total': 0}
            topic_performance[topic]['total'] += 1
            if is_correct:
                topic_performance[topic]['correct'] += 1
            
            # Track performance by difficulty
            difficulty = question.get('difficulty', 'medium')
            if difficulty not in difficulty_performance:
                difficulty_performance[difficulty] = {'correct': 0, 'total': 0}
            difficulty_performance[difficulty]['total'] += 1
            if is_correct:
                difficulty_performance[difficulty]['correct'] += 1
        
        # Calculate percentages and identify weak/strong areas
        for topic, perf in topic_performance.items():
            percentage = (perf['correct'] / perf['total']) * 100
            if percentage >= 80:
                strong_areas.append(f"{topic} ({percentage:.1f}%)")
            elif percentage <= 50:
                weak_areas.append(f"{topic} ({percentage:.1f}%)")
        
        # Store results
        results = {
            'total_questions': len(questions),
            'correct_answers': correct_answers,
            'score_percentage': (correct_answers / len(questions)) * 100,
            'topic_performance': topic_performance,
            'difficulty_performance': difficulty_performance,
            'weak_areas': weak_areas,
            'strong_areas': strong_areas,
            'recommendations': generate_recommendations(weak_areas, strong_areas, quiz['subject'])
        }
        
        quiz['results'] = results
        quiz['answers'] = answers
        
        # Add to history
        quiz_data['quiz_history'].append({
            'subject': quiz['subject'],
            'date': datetime.datetime.now().isoformat(),
            'score': results['score_percentage'],
            'weak_areas': weak_areas,
            'strong_areas': strong_areas
        })
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/quiz/results', methods=['GET'])
def get_quiz_results():
    """Get current quiz results"""
    global quiz_data
    
    try:
        if not quiz_data.get('current_quiz') or not quiz_data['current_quiz'].get('results'):
            return jsonify({'error': 'No quiz results available.'}), 400
        
        return jsonify(quiz_data['current_quiz']['results'])
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/quiz/history', methods=['GET'])
def get_quiz_history():
    """Get quiz history"""
    global quiz_data
    
    try:
        return jsonify({
            'history': quiz_data['quiz_history'],
            'total_quizzes': len(quiz_data['quiz_history'])
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def generate_recommendations(weak_areas, strong_areas, subject):
    """Generate study recommendations based on quiz performance"""
    recommendations = []
    
    if weak_areas:
        recommendations.append(f"Focus on improving your understanding of: {', '.join(weak_areas)}")
        recommendations.append("Consider reviewing fundamental concepts and practicing more problems in these areas.")
    
    if strong_areas:
        recommendations.append(f"You're performing well in: {', '.join(strong_areas)}")
        recommendations.append("Keep up the good work in these areas and use them as a foundation for more advanced topics.")
    
    if not weak_areas and not strong_areas:
        recommendations.append("Your performance is balanced across all topics. Continue with regular practice.")
    
    recommendations.append(f"Consider taking another quiz on {subject} in a few days to track your improvement.")
    
    return recommendations

if __name__ == '__main__':
    print("Starting Flask server...")
    app.run(host='127.0.0.1', port=5001)