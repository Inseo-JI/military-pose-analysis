# 1. 베이스 이미지 선택 (Python 3.9-slim)
FROM python:3.9-slim

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. 필요한 시스템 라이브러리 설치 (OpenCV, MediaPipe 구동용)
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 4. requirements.txt 복사 및 라이브러리 설치
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 5. 프로젝트 파일 전체 복사
COPY . .

# 6. 서버 실행
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000", "--workers", "1"]