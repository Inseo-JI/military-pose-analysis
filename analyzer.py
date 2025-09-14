import cv2
import mediapipe as mp
import numpy as np
import sys
import json
import os
from datetime import datetime

# 라이브러리 초기화 (안정성 확보)
mp.solutions.pose = mp.solutions.pose
mp.solutions.drawing_utils = mp.solutions.drawing_utils

# --- 1. 유틸리티 함수 ---
def calculate_angle(a, b, c):
    if a is None or b is None or c is None: return None
    a, b, c = np.array(a), np.array(b), np.array(c)
    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angle = np.abs(radians * 180.0 / np.pi)
    return angle if angle <= 180.0 else 360 - angle

def calculate_angle_with_vertical(p1, p2):
    if p1 is None or p2 is None: return None
    p1, p2 = np.array(p1), np.array(p2)
    body_vector = p2 - p1
    vertical_vector = np.array([0, -1])
    dot_product = np.dot(body_vector, vertical_vector)
    norm_product = np.linalg.norm(body_vector) * np.linalg.norm(vertical_vector)
    if norm_product == 0: return None
    angle = np.arccos(dot_product / norm_product) * 180.0 / np.pi
    return angle

# --- 2. 분석 엔진 함수들 ---
def analyze_marching_pose(landmarks, visibility_threshold=0.5):
    analysis = {}
    side = "LEFT" if landmarks[mp.solutions.pose.PoseLandmark.LEFT_SHOULDER.value].visibility > landmarks[mp.solutions.pose.PoseLandmark.RIGHT_SHOULDER.value].visibility else "RIGHT"
    def get_coords(name, side_override=None):
        side_to_use = side_override or side
        lm = landmarks[mp.solutions.pose.PoseLandmark[f"{side_to_use}_{name}"].value]
        return [lm.x, lm.y] if lm.visibility > visibility_threshold else None
    shoulder, hip, knee, ankle, ear = (get_coords(name) for name in ["SHOULDER", "HIP", "KNEE", "ANKLE", "EAR"])
    
    analysis['back_angle'] = calculate_angle_with_vertical(hip, shoulder)
    analysis['knee_angle'] = calculate_angle(hip, knee, ankle)
    analysis['neck_angle'] = calculate_angle(ear, shoulder, hip)

    if analysis.get('back_angle') is not None:
        lean = analysis['back_angle']
        if lean < 15: analysis['back_diagnosis'] = "양호"
        elif lean < 25: analysis.update({'back_diagnosis': "주의", 'back_pattern': "기본"})
        else:
            analysis['back_diagnosis'] = "위험"
            left_hip, right_hip = get_coords("HIP", "LEFT"), get_coords("HIP", "RIGHT")
            analysis['back_pattern'] = "골반 측방 붕괴" if shoulder and left_hip and right_hip and abs(shoulder[0] - (left_hip[0] + right_hip[0]) / 2) > 0.05 else "흉·요추 후만 변형"
    if analysis.get('knee_angle') is not None:
        if 160 < analysis['knee_angle'] < 180: analysis.update({'knee_diagnosis': "주의", 'knee_pattern': "충격 흡수 부전"})
        elif 140 < analysis['knee_angle'] <= 160: analysis['knee_diagnosis'] = "양호"
        else:
            analysis['knee_diagnosis'] = "위험"
            analysis['knee_pattern'] = "대퇴사두근 우세" if knee and ankle and abs(knee[0] - ankle[0]) > 0.08 else "기본"
    if analysis.get('neck_angle') is not None:
        if analysis['neck_angle'] > 150: analysis['neck_diagnosis'] = "양호"
        elif analysis['neck_angle'] > 135: analysis.update({'neck_diagnosis': "주의", 'neck_pattern': "기본"})
        else:
            analysis['neck_diagnosis'] = "위험"
            mid_shoulder = [(landmarks[mp.solutions.pose.PoseLandmark.LEFT_SHOULDER.value].x + landmarks[mp.solutions.pose.PoseLandmark.RIGHT_SHOULDER.value].x) / 2,
                            (landmarks[mp.solutions.pose.PoseLandmark.LEFT_SHOULDER.value].y + landmarks[mp.solutions.pose.PoseLandmark.RIGHT_SHOULDER.value].y) / 2]
            thoracic_angle = calculate_angle(mid_shoulder, shoulder, hip) if mid_shoulder and shoulder and hip else None
            analysis['neck_pattern'] = "굽은 등 보상" if thoracic_angle and thoracic_angle < 150 else "목 자체의 문제"
    return analysis

def calculate_load_score(analysis, rucksack_weight_kg):
    score_mapping = {"양호": 0, "주의": 1, "위험": 2}
    weights = {"back": 0.5, "knee": 0.3, "neck": 0.2}
    base_score = sum(score_mapping.get(analysis.get(f"{part}_diagnosis"), 0) * weights[part] for part in weights)
    weight_factor = 1.5 if rucksack_weight_kg >= 25 else (1.2 if rucksack_weight_kg >= 15 else 1.0)
    return min(100, ((base_score * weight_factor) / 3.0) * 100)

def visualize_results(result):
    image = result['image'].copy()
    if result.get('pose_landmarks'):
        mp.solutions.drawing_utils.draw_landmarks(image, result['pose_landmarks'], mp.solutions.pose.POSE_CONNECTIONS)
    load_score = result.get('load_score')
    if load_score is not None:
        score_color = (0, 255, 0) if load_score <= 40 else ((0, 255, 255) if load_score <= 70 else (0, 0, 255))
        cv2.putText(image, f"Load Score: {load_score:.0f}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, score_color, 3)
    return image

def analyze_image_controller(image_path, rucksack_weight_kg):
    pose = mp.solutions.pose.Pose(static_image_mode=True, model_complexity=2, min_detection_confidence=0.3)
    analysis_result = {"path": image_path, "status": "파일 없음"}
    if not os.path.exists(image_path): return analysis_result
    image = cv2.imread(image_path)
    if image is None: 
        analysis_result["status"] = "이미지 파일 오류"
        return analysis_result
    results = pose.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    analysis_result.update({"image": image, "status": "감지 실패"})
    if results.pose_landmarks:
        analysis_result.update({"status": "성공", "pose_landmarks": results.pose_landmarks})
        pose_analysis = analyze_marching_pose(results.pose_landmarks.landmark)
        analysis_result.update(pose_analysis)
        analysis_result['load_score'] = calculate_load_score(analysis_result, rucksack_weight_kg)
    pose.close()
    return analysis_result

# --- 3. 메인 실행 함수 ---
def main(image_path):
    rucksack_weight = 25
    result = analyze_image_controller(image_path, rucksack_weight)

    if result['status'] == '성공':
        # 시각화 이미지 저장
        static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
        os.makedirs(static_dir, exist_ok=True)
        vis_filename = 'vis_' + os.path.basename(image_path)
        cv2.imwrite(os.path.join(static_dir, vis_filename), visualize_results(result))
        result['visualized_image_url'] = vis_filename

        # CSV 파일에 기록 저장
        history_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'history.csv')
        new_entry = [
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            os.path.basename(image_path),
            result.get('load_score', 'N/A'),
            result.get('back_diagnosis', 'N/A'),
            result.get('knee_diagnosis', 'N/A'),
            result.get('neck_diagnosis', 'N/A')
        ]
        if not os.path.exists(history_file):
            with open(history_file, 'w', encoding='utf-8-sig') as hf:
                hf.write('Timestamp,Filename,Load Score,Back,Knee,Neck\n')
        with open(history_file, 'a', encoding='utf-8-sig') as hf:
            hf.write(','.join(map(str, new_entry)) + '\n')

    # json으로 변환할 수 없는 객체 제거
    if 'image' in result: del result['image']
    if 'pose_landmarks' in result: del result['pose_landmarks']

    # 결과를 json 파일로 저장
    result_filepath = image_path + '.json'
    with open(result_filepath, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
    
    print(f"Analysis complete for {os.path.basename(image_path)}")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        main(sys.argv[1])