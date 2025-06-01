from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-netlify-site.netlify.app"],  # 프론트엔드 주소
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount("/static", StaticFiles(directory="../frontend/static"), name="static")

class PlayerRequest(BaseModel):
    name: str

TEAM_MAP = {
    'LG': 'LG',
    '두산': 'OB',
    '한화': 'HH',
    'KT': 'KT',
    'SSG': 'SSG',
    '롯데': 'LT',
    'NC': 'NC',
    'KIA': 'KIA',
    '삼성': 'SS',
    '키움': 'KW'
}

def create_pg_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT', 5432)
    )

@app.post("/predict")
async def predict(player: PlayerRequest):
    conn = create_pg_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT player_id, name, team, avg, hr, rbi, recent_hits, recent_hr, recent_rbi
            FROM players 
            WHERE name = %s
            ORDER BY created_at DESC
            LIMIT 1
        ''', (player.name,))
        data = cur.fetchone()
        
        if not data:
            raise HTTPException(status_code=404, detail="선수를 찾을 수 없습니다")
        
        def parse_array(val):
            if isinstance(val, str):
                return [int(x) for x in val.strip('{}[]').split(',') if x.strip().isdigit()]
            elif isinstance(val, list):
                return [int(x) for x in val]
            return [0]*5
        
        recent_hits = parse_array(data[6]) or [0]*5
        recent_hr = parse_array(data[7]) or [0]*5
        recent_rbi = parse_array(data[8]) or [0]*5

        pred_avg = round(sum(recent_hits)/len(recent_hits), 2) if recent_hits else 0.0
        pred_hr_percent = round((sum(recent_hr)/len(recent_hr))*100, 1) if recent_hr else 0.0

        def predict_rbi(recent_rbi):
            weights = [0.4, 0.3, 0.15, 0.1, 0.05]
            weighted_sum = sum(w * x for w, x in zip(weights, recent_rbi))
            return round(weighted_sum, 1)
        pred_rbi = predict_rbi(recent_rbi)

        team_code = TEAM_MAP.get(data[2], 'default')

        return JSONResponse(
            content={
                "player_id": data[0],
                "name": data[1],
                "team": data[2],
                "team_code": team_code,
                "avg": data[3],
                "hr": data[4],
                "rbi": data[5],
                "recent_hits": recent_hits,
                "recent_hr": recent_hr,
                "recent_rbi": recent_rbi,
                "player_image_url": f"<https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/person/middle/2025/{data[0]}.jpg",
                "predicted_avg": pred_avg,
                "predicted_hr_percent": pred_hr_percent,
                "predicted_rbi": pred_rbi
            },
            media_type="application/json; charset=utf-8"
        )
    finally:
        cur.close()
        conn.close()

@app.get("/")
async def root():
    return {"message": "KBO 예측 시스템 API가 정상적으로 실행 중입니다"}
