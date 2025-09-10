import os
import requests
import gradio as gr
import time
import threading
from dotenv import load_dotenv
import argparse
import folium

# 실행 시 사용할 .env 파일 지정 (기본값: t1)
# python 실행 명령어 e.g. python test1.py --env seongho
parser = argparse.ArgumentParser()
parser.add_argument("--env", type=str, default="t1", help="사용할 환경 변수 파일 지정")
parser.add_argument("--port", type=int, default=7860, help="사용할 port 지정")
args = parser.parse_args()

# ENV_FILE_PATH = "/home/azureuser/workspace/test_gradio/env/"+str(args.env)+".env"
ENV_FILE_AZURE_PATH = "env/"+str(args.env)+".env"
ENV_FILE_KAKAO_PATH = "env/kakao.env"
port = args.port
# ENV_FILE_PATH = "env/t1.env"
last_env_mtime = time.time() - 80  # 마지막으로 로드한 .env 파일의 수정 시간
env_vars = {}  # 환경 변수 저장


# 환경 변수 로드
def env_load():
    # print(ENV_FILE_AZURE_PATH)
    load_dotenv(ENV_FILE_AZURE_PATH)
    # print("t1.env load")
    load_dotenv(ENV_FILE_KAKAO_PATH)
    # print("kakao.env load")
    return {
        "CUSTOM_VISION_ENDPOINT": os.getenv("endpoint"),
        "CUSTOM_VISION_PREDICTION_KEY": os.getenv("prediction_key"),
        "CUSTOM_VISION_PROJECT_ID": os.getenv("project_id"),
        "CUSTOM_VISION_ITERATION_NAME": os.getenv("iteration_name"),
        "KAKAO_API_KEY": os.getenv("KAKAO_API_KEY"),
        "GOOGLE_GEOLOCATION_API_KEY": os.getenv("GOOGLE_GEOLOCATION_API_KEY")
    }

# .env 파일을 감지하고 변경되었을 때만 다시 로드
def load_env_variables():
    global last_env_mtime, env_vars
    # print(env_vars)
    try:
        if time.time() - last_env_mtime > 60:  # 1분마다 환경변수 체크
            new_env_vars = env_load()
            if new_env_vars != env_vars:
                env_vars = new_env_vars
                print("환경변수 변경 감지, 재로드 완료.")
            last_env_mtime = time.time()
    except Exception as e:
        print(f"환경 변수 로드 실패: {e}")

# 일정 시간마다 환경 변수를 다시 로드하는 스레드
def start_env_watcher(interval=10):
    def watch_env():
        while True:
            load_env_variables()
            time.sleep(interval)

    thread = threading.Thread(target=watch_env, daemon=True)
    thread.start()

# 처음 한 번 로드 및 감시 스레드 시작
load_env_variables()
start_env_watcher()

# # Azure Custom Vision API 엔드포인트와 키 
# endpoint = os.getenv("endpoint")
# prediction_key = os.getenv("prediction_key")
# project_id = os.getenv("project_id")
# iteration_name = os.getenv("iteration_name")

# print(endpoint)
# print(prediction_key)
# print(project_id)
# print(iteration_name)

# 사용자 위치 자동 감지 (IP 기반)
# def get_user_location():
#     try:
#         response = requests.get("https://ipinfo.io/json")
#         if response.status_code == 200:
#             data = response.json()
#             print(data)
#             lat, lng = map(float, data["loc"].split(","))
#             return lat, lng
#     except Exception as e:
#         print(f"위치 정보 가져오기 실패: {e}")
#     return None

# 사용자 위치 자동 감지 (wifi 기반. google location api)
def get_user_location():
    """Google Geolocation API를 사용하여 사용자 현재 위치(위도, 경도) 가져오기"""
    url = f"https://www.googleapis.com/geolocation/v1/geolocate?key={env_vars["GOOGLE_GEOLOCATION_API_KEY"]}"
    try:
        response = requests.post(url, json={})
        response.raise_for_status()
        location_data = response.json()
        print(location_data)
        latitude = location_data["location"]["lat"]
        longitude = location_data["location"]["lng"]
        return latitude, longitude
    except Exception as e:
        print(f'{e}')
        return None, None

def classify_wound(image):
    print("in classify_wound")
    try:
        # Azure Custom Vision API 엔드포인트와 키 
        endpoint = env_vars["CUSTOM_VISION_ENDPOINT"]
        prediction_key = env_vars["CUSTOM_VISION_PREDICTION_KEY"]
        project_id = env_vars["CUSTOM_VISION_PROJECT_ID"]
        iteration_name = env_vars["CUSTOM_VISION_ITERATION_NAME"]

        print(f"{endpoint}, {prediction_key}, {project_id}, {iteration_name}")
        print("end of load env")
        
        # iteration_name 변경 시 endpoint 일부분 변경 필요 대응
        print(endpoint.split("/"))
        temp_endpoint = endpoint.split("/")
        temp_endpoint[9] = iteration_name
        endpoint = "/".join(temp_endpoint)
        print(endpoint)

        # 이미지를 Azure Custom Vision API에 업로드할 수 있는 형식으로 변환 
        image = image.convert("RGB") 
        image.save("temp.jpg") 

        # API 요청 헤더 설정 
        headers = { 
            'Prediction-Key': prediction_key, 
            'Content-Type': 'application/octet-stream' 
        }
        print("before post")

        # 이미지를 바이너리 형식으로 읽어와 API 요청 수행 
        with open("temp.jpg", "rb") as image_data: 
            response = requests.post(endpoint, headers=headers, data=image_data)

        print("after post")
        
        # 응답 상태 코드 확인
        if response.ok:
            predictions = response.json().get("predictions", [])
            # results = {prediction["tagName"]: prediction["probability"] for prediction in predictions}
            print(predictions)
            predictions = predictions[:2]
            if len(predictions) < 2:
                results = predictions[0], {'tagName' : '', 'probabillity' : 0}
            else:
                results = (predictions[0], predictions[1])
            # results = {f"이 상처는 {prediction["tagName"]}일 확률 {prediction["probability"] * 100:.2f}%" for prediction in predictions}
        else:
            results = f"API 요청 실패: {response.status_code} {response.text}"
    except Exception as e:
        results = f"에러발생{str(e)}"
    
    return results


# def search_hospital(wound_type, location=[37.4979,127.0276]):
#     """카카오맵 API를 사용하여 주변 병원 검색"""
#     hospital_map = {
#         "burn": "화상 전문 병원",
#         "bruise": "정형외과",
#         "acne": "피부과"
#     }
#     query = hospital_map.get(wound_type, "병원")
#     # url = f"https://dapi.kakao.com/v2/local/search/keyword.json?query={query}&x=127.0276&y=37.4979&radius=5000"
#     url = f"https://dapi.kakao.com/v2/local/search/keyword.json"
#     headers = {"Authorization": f"KakaoAK {env_vars['KAKAO_API_KEY']}"}
#     print(location[0])
#     print(location[1])
#     print(type(location[1]))
#     params = {"query": query, "x": location[1], "y": location[0], "radius": 5000, "category_group_code":"HP8"}
#     response = requests.get(url, headers=headers, params=params)
#     response.raise_for_status()
    
#     print(response.json())
#     places = response.json().get("documents", [])
#     if not places:
#         return "근처에 추천할 병원이 없습니다.", []

#     # 병원 이름 + 주소 + 좌표 정보 반환
#     hospital_list = [
#         {"name": place["place_name"], "address": place["road_address_name"], "lng": float(place["x"]), "lat": float(place["y"]), "place_url": place["place_url"]}
#         for place in places[:5] if place["category_group_code"] == "HP8"
#     ]
#     return [f"{h['name']} - {h['address']}" for h in hospital_list], hospital_list
    # return ["🏥 **추천 병원 리스트** 🏥\n\n" + "\n".join(f"- {h['name']} : {h['address']}" for h in hospital_list)], hospital_list

def search_hospital(wound_type, location=[37.4979, 127.0276]):
    hospital_map = {
        "burn": ["화상 전문 병원", "종합병원", "응급실"],
        "bruise": ["정형외과", "종합병원", "응급실"],
        "acne": ["피부과", "종합병원", "일반 병원"]
    }
    
    search_queries = hospital_map.get(wound_type, ["병원"])
    for query in search_queries:
        url = "https://dapi.kakao.com/v2/local/search/keyword.json"
        headers = {"Authorization": f"KakaoAK {env_vars['KAKAO_API_KEY']}"}
        params = {"query": query, "x": location[1], "y": location[0], "radius": 5000, "category_group_code": "HP8"}
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            places = response.json().get("documents", [])
            
            if places:
                hospital_list = [
                    {"name": place["place_name"], "address": place["road_address_name"], "lng": float(place["x"]), "lat": float(place["y"]), "place_url": place["place_url"]}
                    for place in places[:5] if place["category_group_code"] == "HP8"
                ]
                return [f"{h['name']} - {h['address']}" for h in hospital_list], hospital_list
        except Exception as e:
            print(f"병원 검색 실패: {e}")
    
    return "근처에 추천할 병원이 없습니다.", []

# Folium 지도 생성
def generate_map(location, hospital_list):
    m = folium.Map(location=location, zoom_start=14)
    
    # 현재 위치 마커 추가
    folium.Marker(location, tooltip="현재 위치", icon=folium.Icon(color="blue")).add_to(m)
    
    # 병원 위치 마커 추가
    for hospital in hospital_list:
        popup_html = f"""
            <b>{hospital['name']}</b><br>
            {hospital['address']}<br>
            <a href='{hospital['place_url']}' target='_blank'>{hospital['place_url']}</a>
        """
        folium.Marker(
            [hospital["lat"], hospital["lng"]],
            tooltip=hospital["name"],
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(color="red")
        ).add_to(m)
    
    return m._repr_html_()  # HTML 반환

# 상처별 케어 파일 로드 함수
def load_care_text(wound_type):
    file_path = f"text_tip/{wound_type}.txt"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    return "해당 상처에 대한 케어 정보가 없습니다."

def process_image(image):
    print("start process")

    ko_kr = {
        "acne": "여드름",
        "burn": "화상",
        "bruise": "타박상(멍)",
        "skin": "일반피부"
    }

    tip_images = {
        "acne": "image_tip/acne_tip.png",
        "burn": "image_tip/burn_tip.png",
        "bruise": "image_tip/bruise_tip.png",
        "skin": "image_tip/skin_tip.png"
    }

    location = get_user_location()
    print(location)
    if not location:
        return "위치 정보를 가져오는 데 실패했습니다. 코드 수정해주세세요.", [], "", None, ""

    top1, top2 = classify_wound(image)
    if top1['tagName'] == "skin":
        return "일반 피부를 보내주신 것 같아요!", [], load_care_text(top1['tagName']), tip_images.get(top1['tagName'], None), ""  # 병원 검색 없이 메시지만 출력
    
    result_text = f"이 사진은 {ko_kr.get(top1['tagName'])}일 확률이 {top1['probability']:.2%}이며, \n{ko_kr.get(top2['tagName'])}일 확률도 {top2['probability']:.2%}입니다.\n"
    result_text += f"따라서 {ko_kr.get(top1['tagName'])} 또는 {ko_kr.get(top2['tagName'])} 관련 병원을 방문하는 것이 좋습니다.\n"

    # 병원 정보 가져오기 (이름, 주소 + x, y 좌표)
    hospital_list, hospital_locations = search_hospital(top1["tagName"], location)

    
    # 상처 타입에 따라 적절한 이미지 선택
    tip_image_path = tip_images.get(top1['tagName'], None)

    # 지도 생성
    hospital_map = generate_map(location, hospital_locations)

    print(result_text)
    return result_text, hospital_list, load_care_text(top1['tagName']), tip_image_path, hospital_map


with gr.Blocks() as demo:
    gr.Markdown("# 상처 분석 및 병원 추천")

    with gr.Row():
        with gr.Column(scale=1):
            image_input = gr.Image(type="pil", label="이미지 업로드")
            with gr.Row():
                clear_btn = gr.Button("초기화")
                submit_btn = gr.Button("제출", variant='primary')
        with gr.Column(scale=1):
            text_output = gr.Text(label="분석 결과")
            hospital_list = gr.List(headers=['추천 병원'])
    with gr.Row():
            care_text_output = gr.Markdown(label="상처 케어 방법")
            tip_image_output = gr.Image(label="상처 관리 팁", elem_id="tip_image")
    with gr.Row():
        map_output = gr.HTML(label="지도")  # 넓게 표시

    # 버튼 이벤트 연결
    submit_btn.click(process_image, inputs=image_input, outputs=[text_output, hospital_list, care_text_output, tip_image_output, map_output])
    clear_btn.click(lambda: (None, "", [], "", None, ""), outputs=[image_input, text_output, hospital_list, care_text_output, tip_image_output, map_output])


# Gradio 인터페이스 생성
# demo = gr.Interface(
#     fn=process_image,
#     inputs=[gr.Image(type="pil")],
#     outputs=[gr.Text(), gr.List(), gr.HTML()],
#     title="상처 분석 및 병원 추천",
#     description="이미지를 업로드하면 분석된 상처 종류와 가까운 병원을 추천해줍니다.",
#     live=True
# )

# demo.launch(server_name="0.0.0.0", server_port=port)
demo.launch(share=True)