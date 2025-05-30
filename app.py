from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import psycopg2
import numpy as np
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class PlayerRequest(BaseModel):
    name: str

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
            SELECT name, team, avg, hr, rbi, recent_hits, recent_hr, recent_rbi
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
                return [int(x) for x in val.strip('{}[]').split(',') if x.strip()]
            elif isinstance(val, list):
                return [int(x) for x in val]
            return [0]*5
        
        recent_hits = parse_array(data[5]) or [0]*5
        recent_hr = parse_array(data[6]) or [0]*5
        recent_rbi = parse_array(data[7]) or [0]*5

        pred_avg = round(np.mean(recent_hits), 2) if recent_hits else 0.0
        pred_hr_percent = round((sum(recent_hr)/len(recent_hr))*100, 1) if recent_hr else 0.0
        pred_rbi = round(np.mean(recent_rbi), 1) if recent_rbi else 0.0

        return JSONResponse(
            content={
                "name": data[0],
                "team": data[1],
                "avg": data[2],
                "hr": data[3],
                "rbi": data[4],
                "predicted_avg": pred_avg,
                "predicted_hr_percent": pred_hr_percent,
                "predicted_rbi": pred_rbi,
                "recent_hits": recent_hits,
                "recent_hr": recent_hr,
                "recent_rbi": recent_rbi
            },
            media_type="application/json; charset=utf-8"
        )
    finally:
        cur.close()
        conn.close()

@app.get("/")
async def root():
    return {"message": "KBO 예측 시스템 API가 정상적으로 실행 중입니다"}
