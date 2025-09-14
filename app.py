from flask import Flask, render_template, request, url_for
import os
import subprocess
import json
import sys
import csv
from werkzeug.utils import secure_filename

app = Flask(__name__)

# --- 지식 베이스 ---
EXPERT_KNOWLEDGE_BASE = {
    "back": { "위험": { "흉·요추 후만 변형": {"진단명": "부하 유발성 동적 요추 굴곡"}, "골반 측방 붕괴": {"진단명": "중둔근 약화로 인한 보행 불안정성"}}, "주의": { "기본": {"진단명": "고관절 우세 상체 기울임"}}},
    "knee": { "위험": { "대퇴사두근 우세": {"진단명": "대퇴사두근 우세 보행"}}, "주의": { "충격 흡수 부전": {"진단명": "충격 흡수 부전 보행"}}},
    "neck": { "위험": { "굽은 등 보상": {"진단명": "굽은 등 보상성 경추 과신전"}, "목 자체의 문제": {"진단명": "만성적 전방 머리 자세"}}, "주의": { "기본": {"진단명": "초기 전방 머리 자세"}}}
}
EXERCISE_PRESCRIPTION_DB = {
    "back": { "흉·요추 후만 변형": [{"name": "맥길 빅3"}], "골반 측방 붕괴": [{"name": "클램쉘"}], "기본": [{"name": "데드버그"}]},
    "knee": { "대퇴사두근 우세": [{"name": "중둔근 강화 운동"}], "충격 흡수 부전": [{"name": "대퇴사두근/햄스트링 이완"}]},
    "neck": { "굽은 등 보상": [{"name": "폼롤러 흉추 신전"}], "목 자체의 문제": [{"name": "턱 당기기"}], "기본": [{"name": "턱 당기기"}]}
}

# 지식 베이스를 HTML로 보내주는 함수
@app.context_processor
def inject_knowledge_base():
    return dict(
        EXPERT_KNOWLEDGE_BASE=EXPERT_KNOWLEDGE_BASE, 
        EXERCISE_PRESCRIPTION_DB=EXERCISE_PRESCRIPTION_DB
    )

# --- 웹페이지 라우팅 ---
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not file.filename:
            return render_template('index.html', error="파일이 선택되지 않았습니다.")
        
        filename = secure_filename(file.filename)
        uploads_dir = os.path.join(app.root_path, 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        filepath = os.path.join(uploads_dir, filename)
        file.save(filepath)
        
        try:
            subprocess.run([sys.executable, 'analyzer.py', filepath], check=True, timeout=60)
            result_filepath = filepath + '.json'
            with open(result_filepath, 'r', encoding='utf-8') as f:
                analysis_result = json.load(f)
        except Exception as e:
            print(f"Error occurred: {e}")
            analysis_result = {'status': '분석 엔진 실행 중 오류 발생'}
            
        return render_template('index.html', result=analysis_result)
        
    return render_template('index.html', result=None)

@app.route('/history')
def history():
    records = []
    history_file = os.path.join(app.root_path, 'history.csv')
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8-sig') as hf:
            reader = csv.reader(hf)
            try:
                header = next(reader)
                for row in reader:
                    records.append(row)
            except StopIteration:
                pass # 파일이 비어있는 경우
    return render_template('history.html', records=records)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')