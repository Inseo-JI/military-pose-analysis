from flask import Flask, render_template, request, jsonify
import os
import subprocess
import sys
import uuid
from werkzeug.utils import secure_filename
import threading

app = Flask(__name__)
analysis_status = {}

def run_analysis(filepath, task_id):
    """백그라운드에서 analyzer.py를 실행하는 함수"""
    try:
        # 서버 환경에서는 venv의 파이썬이 아닌 시스템 파이썬을 사용
        python_executable = sys.executable
        subprocess.run(
            [python_executable, 'analyzer.py', filepath], 
            check=True, 
            capture_output=True, 
            text=True
        )
        analysis_status[task_id] = {'status': '성공', 'filepath': filepath}
    except subprocess.CalledProcessError as e:
        print(f"Analysis failed for {task_id}: {e.stderr}")
        analysis_status[task_id] = {'status': '분석 실패', 'error': e.stderr}

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not file.filename:
            return "파일이 선택되지 않았습니다.", 400
        
        filename = secure_filename(file.filename)
        # 고유한 파일명 생성
        unique_filename = str(uuid.uuid4()) + "_" + filename
        
        uploads_dir = os.path.join(app.root_path, 'static', 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        filepath = os.path.join(uploads_dir, unique_filename)
        file.save(filepath)
        
        task_id = str(uuid.uuid4())
        analysis_status[task_id] = {'status': '분석 중'}
        
        # 별도의 스레드에서 분석 실행
        thread = threading.Thread(target=run_analysis, args=(filepath, task_id))
        thread.start()
        
        return jsonify({'task_id': task_id})
        
    return render_template('index.html')

@app.route('/status/<task_id>')
def status(task_id):
    result = analysis_status.get(task_id, {'status': '알 수 없음'})
    if result['status'] == '성공':
        json_path = result['filepath'] + '.json'
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                analysis_data = json.load(f)
            result['data'] = analysis_data
        except FileNotFoundError:
            result['status'] = '결과 파일 없음'
            
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')