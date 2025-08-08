from flask import Flask, request, jsonify, Response, make_response
import requests
import uuid

app = Flask(__name__)

# ===============================
# STEP 1: Insert your Gemini API Key here
# ===============================
API_KEY = 'AIzaSyA43y8RuCMUadZQERHru1SGvvuc3Aw3gAY'  
API_URL = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={API_KEY}'

# In-memory session storage for conversations and interview contexts
conversations = {}      # session_id -> list of message dicts {'role','content'}
interview_contexts = {} # session_id -> dict with 'role' and 'initial_questions'

# =============================================
# STEP 2: Define function to call Gemini API
# =============================================
def call_gemini_api(prompt_text):
    headers = {"Content-Type": "application/json"}
    body = {
        "contents": [
            {
                "parts": [{"text": prompt_text}]
            }
        ]
    }
    response = requests.post(API_URL, headers=headers, json=body)
    if response.status_code == 200:
        data = response.json()
        try:
            content = data['candidates'][0]['content']
            # Sometimes content is nested dict -> unwrap it safely
            if isinstance(content, dict):
                content = content.get('text', str(content))
            return content.strip()
        except Exception as e:
            return f"[Error parsing API response: {e}]"
    else:
        return f"[API Error: {response.status_code} {response.text}]"

# =============================================
# STEP 3: Helper to build conversational prompt with history + optional context
# =============================================
def build_contextual_prompt(history, user_message, initial_context=None):
    prompt = (
        "You are an expert job interview coach chatbot. "
        "Help the user prepare by having a natural, constructive conversation. "
        "Give clear, concise advice and feedback.\n"
    )
    if initial_context:
        prompt += f"[Context: {initial_context}]\n"
    for turn in history:
        if turn['role'] == 'user':
            prompt += f"User: {turn['content']}\n"
        else:
            prompt += f"Coach: {turn['content']}\n"
    prompt += f"User: {user_message}\nCoach:"
    return prompt

# =============================================
# STEP 4: Route to serve the full HTML frontend + embedded CSS + JS
# =============================================
@app.route('/')
def index():
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>JobReady AI Resume & Interview Coach</title>
<style>
  /* Basic styling & layout */
  * { box-sizing: border-box; }
  body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: #333;
    margin: 0; padding: 2rem;
    min-height: 100vh;
    display: flex; flex-direction: column; align-items: center;
  }
  h1 {
    color: #fff;
    text-shadow: 0 0 10px rgba(0,0,0,0.3);
    margin-bottom: 1.5rem;
  }
  .container {
    background: #fff;
    border-radius: 15px;
    padding: 25px;
    max-width: 700px;
    width: 100%;
    box-shadow: 0 12px 30px rgba(0,0,0,0.2);
    display: flex; flex-direction: column;
    min-height: 650px;
  }
  label {
    font-weight: 600;
    margin-top: 15px;
    color: #764ba2;
  }
  select, textarea, input[type="text"], button {
    width: 100%;
    margin-top: 8px;
    padding: 12px;
    border: 2px solid #764ba2;
    border-radius: 12px;
    font-size: 1.1rem;
    transition: border-color 0.3s ease;
  }
  select:focus, textarea:focus, input[type="text"]:focus {
    border-color: #667eea;
    outline: none;
    box-shadow: 0 0 8px #667eea;
  }
  button {
    margin-top: 20px;
    background: #667eea;
    color: white;
    border: none;
    cursor: pointer;
    font-weight: bold;
    border-radius: 14px;
    transition: background 0.3s ease;
  }
  button:hover:not(:disabled) {
    background: #764ba2;
  }
  button:disabled {
    background: #a2a2d0;
    cursor: not-allowed;
  }
  /* Interview Questions output */
  #interview-output {
    white-space: pre-wrap; /* Preserve line breaks */
    background: #f0f5ff;
    border-left: 6px solid #764ba2;
    padding: 15px;
    border-radius: 10px;
    margin-top: 15px;
    min-height: 180px;
    overflow-y: auto;
  }
  /* Chat UI */
  #chat-window {
    flex-grow: 1;
    margin-top: 15px;
    background: #fafafa;
    border: 2px solid #764ba2;
    border-radius: 10px;
    padding: 15px;
    overflow-y: auto;
    max-height: 400px;
    display: flex;
    flex-direction: column;
  }
  .message {
    margin-bottom: 12px;
    padding: 12px 16px;
    border-radius: 12px;
    max-width: 75%;
    white-space: pre-wrap; /* Preserve newlines */
    line-height: 1.4;
    word-wrap: break-word;
  }
  .user-msg {
    background-color: #d1e7ff;
    align-self: flex-end;
    margin-left: auto;
  }
  .bot-msg {
    background-color: #eee;
    align-self: flex-start;
    margin-right: auto;
  }
  #chat-input {
    resize: none;
    padding: 12px;
    border: 2px solid #764ba2;
    border-radius: 14px;
    font-size: 1rem;
    margin-top: 10px;
  }
  /* Hide elements */
  .hidden { display: none; }
  .footer {
    margin-top: 20px;
    font-style: italic;
    color: #ddd;
    text-align: center;
  }
</style>
</head>
<body>

<h1>🤖 JobReady AI Resume & Interview Coach</h1>

<div class="container">
  <label for="mode">Select Mode:</label>
  <select id="mode">
    <option value="interview_questions">Interview Questions</option>
    <option value="interview_chat">Interview Practice Chat</option>
    <option value="resume_feedback">Resume Feedback</option>
  </select>

  <!-- Interview Questions Input/Output -->
  <div id="interview_questions_section" class="mode-section">
    <label for="job-role">Enter Job Role:</label>
    <input type="text" id="job-role" placeholder="e.g. Software Engineer" />
    <button id="get-questions-btn">Get Interview Questions</button>
    <div id="interview-output" aria-live="polite" aria-atomic="false"></div>
    <button id="start-chat-btn" class="hidden">Start Practice Chat</button>
  </div>

  <!-- Interview Chat Section -->
  <div id="interview_chat_section" class="mode-section hidden" style="flex-direction: column; display: flex;">
    <div id="chat-window" aria-live="polite" aria-atomic="false" role="log" aria-relevant="additions"></div>
    <textarea id="chat-input" rows="3" placeholder="Type your practice answer or ask a question..."></textarea>
    <button id="send-chat-btn">Send</button>
  </div>

  <!-- Resume Feedback Section -->
  <div id="resume_feedback_section" class="mode-section hidden">
    <label for="resume-text">Paste your resume text:</label>
    <textarea id="resume-text" rows="10" placeholder="Paste your resume here..."></textarea>
    <button id="get-resume-feedback-btn">Get Resume Feedback</button>
    <div id="resume-output" aria-live="polite" aria-atomic="false" style="white-space: pre-wrap; min-height: 180px; margin-top: 15px; background: #f0f5ff; border-left: 6px solid #764ba2; padding: 15px; border-radius: 10px;"></div>
  </div>
</div>

<div class="footer">Powered by Google Gemini API & Flask</div>

<script>
  // --- Mode selection logic ---
  const modeSelect = document.getElementById('mode');
  const interviewQuestionsSection = document.getElementById('interview_questions_section');
  const interviewChatSection = document.getElementById('interview_chat_section');
  const resumeFeedbackSection = document.getElementById('resume_feedback_section');

  function showSection(section) {
    interviewQuestionsSection.classList.add('hidden');
    interviewChatSection.classList.add('hidden');
    resumeFeedbackSection.classList.add('hidden');
    section.classList.remove('hidden');
  }

  modeSelect.addEventListener('change', () => {
    const mode = modeSelect.value;
    if (mode === 'interview_questions') showSection(interviewQuestionsSection);
    else if (mode === 'interview_chat') showSection(interviewChatSection);
    else if (mode === 'resume_feedback') showSection(resumeFeedbackSection);
  });

  // ------------- Interview Questions mode -------------
  const getQuestionsBtn = document.getElementById('get-questions-btn');
  const interviewOutput = document.getElementById('interview-output');
  const startChatBtn = document.getElementById('start-chat-btn');
  const jobRoleInput = document.getElementById('job-role');

  getQuestionsBtn.addEventListener('click', async () => {
    const role = jobRoleInput.value.trim();
    if (!role) {
      alert('Please enter a job role.');
      return;
    }
    getQuestionsBtn.disabled = true;
    interviewOutput.textContent = 'Generating interview questions...';
    startChatBtn.classList.add('hidden');

    try {
      const res = await fetch('/interview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role }),
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json();
      interviewOutput.textContent = data.questions;
      startChatBtn.classList.remove('hidden');
    } catch (e) {
      interviewOutput.textContent = 'Error: ' + e.message;
    } finally {
      getQuestionsBtn.disabled = false;
    }
  });

  startChatBtn.addEventListener('click', async () => {
    modeSelect.value = 'interview_chat';
    showSection(interviewChatSection);
    clearChat();
    await setInterviewContext(jobRoleInput.value.trim());
  });

  // ------------- Interview Chat mode -------------
  const chatWindow = document.getElementById('chat-window');
  const chatInput = document.getElementById('chat-input');
  const sendChatBtn = document.getElementById('send-chat-btn');

  let interviewContext = null;

  function appendMessage(sender, text) {
    const div = document.createElement('div');
    div.classList.add('message', sender === 'user' ? 'user-msg' : 'bot-msg');
    div.textContent = text;
    chatWindow.appendChild(div);
    chatWindow.scrollTop = chatWindow.scrollHeight;
  }

  function clearChat() {
    chatWindow.innerHTML = '';
    chatInput.value = '';
    interviewContext = null;
  }

  async function setInterviewContext(role) {
    const res = await fetch('/interview_chat_start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role }),
    });
    if (res.ok) {
      interviewContext = role;
      appendMessage('bot', `Let's practice interview questions for the role: ${role}. You can ask me questions or provide your answers, and I'll give feedback.`);
    } else {
      appendMessage('bot', 'Failed to initialize interview chat session.');
    }
  }

  async function sendInterviewMessage() {
    const message = chatInput.value.trim();
    if (!message) return;
    appendMessage('user', message);
    chatInput.value = '';
    sendChatBtn.disabled = true;

    try {
      const res = await fetch('/interview_chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      });
      if (!res.ok) throw new Error('Server error ' + res.status);
      const data = await res.json();
      appendMessage('bot', data.response);
    } catch (e) {
      appendMessage('bot', 'Error: ' + e.message);
    } finally {
      sendChatBtn.disabled = false;
      chatInput.focus();
    }
  }

  sendChatBtn.addEventListener('click', sendInterviewMessage);
  chatInput.addEventListener('keypress', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendInterviewMessage();
    }
  });

  // ------------- Resume Feedback mode -------------
  const getResumeFeedbackBtn = document.getElementById('get-resume-feedback-btn');
  const resumeTextArea = document.getElementById('resume-text');
  const resumeOutput = document.getElementById('resume-output');

  getResumeFeedbackBtn.addEventListener('click', async () => {
    const resumeText = resumeTextArea.value.trim();
    if (!resumeText) {
      alert('Please paste your resume text.');
      return;
    }
    getResumeFeedbackBtn.disabled = true;
    resumeOutput.textContent = 'Generating resume feedback...';
    try {
      const res = await fetch('/resume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resume: resumeText }),
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json();
      resumeOutput.textContent = data.feedback;
    } catch (e) {
      resumeOutput.textContent = 'Error: ' + e.message;
    } finally {
      getResumeFeedbackBtn.disabled = false;
    }
  });
</script>

</body>
</html>
"""
    return Response(html, mimetype='text/html')

# =============================================
# STEP 5: API endpoint to generate initial interview questions
# =============================================
@app.route('/interview', methods=['POST'])
def interview():
    data = request.get_json()
    role = data.get('role', '').strip()
    if not role:
        return jsonify({'questions': 'Please provide a job role.'})

    prompt = f"Act as a job interview coach. Provide 3 common interview questions and sample answers for the role of {role}."
    response = call_gemini_api(prompt)

    # Manage session and store initial questions related to this session’s role
    session_id = request.cookies.get('session_id')
    if not session_id:
        session_id = str(uuid.uuid4())

    interview_contexts[session_id] = {
        'role': role,
        'initial_questions': response,
    }

    # Return questions and set cookie
    resp = make_response(jsonify({'questions': response}))
    resp.set_cookie('session_id', session_id, max_age=3600*24)
    return resp

# =============================================
# STEP 6: API endpoint to initiate interview chat session (clears history)
# =============================================
@app.route('/interview_chat_start', methods=['POST'])
def interview_chat_start():
    data = request.get_json()
    role = data.get('role', '').strip()
    if not role:
        return jsonify({'error': 'Role is required to start chat.'}), 400

    session_id = request.cookies.get('session_id')
    if not session_id:
        session_id = str(uuid.uuid4())

    # Initialize chat history empty for this session
    conversations[session_id] = []

    # Store interview context role also
    interview_contexts[session_id] = {
        'role': role
    }

    resp = make_response(jsonify({'message': 'Interview chat session started.'}))
    resp.set_cookie('session_id', session_id, max_age=3600*24)
    return resp

# =============================================
# STEP 7: API endpoint for interview practice multi-turn chat
# =============================================
@app.route('/interview_chat', methods=['POST'])
def interview_chat():
    data = request.get_json()
    user_message = data.get('message', '').strip()
    if not user_message:
        return jsonify({'response': 'Please enter a message.'})

    session_id = request.cookies.get('session_id')
    if not session_id or session_id not in conversations:
        return jsonify({'response': 'Session not found. Please generate interview questions and start chat.'})

    history = conversations.get(session_id, [])
    context_data = interview_contexts.get(session_id, {})
    role = context_data.get('role', '')

    prompt = build_contextual_prompt(history, user_message, initial_context=f"Job Role: {role}")

    bot_response = call_gemini_api(prompt)

    history.append({'role': 'user', 'content': user_message})
    history.append({'role': 'bot', 'content': bot_response})
    conversations[session_id] = history

    return jsonify({'response': bot_response})

# =============================================
# STEP 8: API endpoint for resume feedback
# =============================================
@app.route('/resume', methods=['POST'])
def resume():
    data = request.get_json()
    resume_text = data.get('resume', '').strip()
    if not resume_text:
        return jsonify({'feedback': 'Please provide resume text.'})

    prompt = f"Analyze this resume and provide feedback to improve it:\n{resume_text}"
    feedback = call_gemini_api(prompt)
    return jsonify({'feedback': feedback})

# =============================================
# STEP 9: Run Flask app
# =============================================
if __name__ == '__main__':
    print("Starting JobReady AI Resume & Interview Coach")
    print("Open http://127.0.0.1:5000 in your browser")
    app.run(debug=True)
