# 최종 수정된 predict_today.py
import psycopg2
import pandas as pd
import numpy as np
from dotenv import load_dotenv
import os

load_dotenv()

def create_pg_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT', 5432)
    )

def get_player_from_db(player_name):
    conn = create_pg_connection()
    query = "SELECT * FROM players WHERE name = %s ORDER BY created_at DESC LIMIT 1"
    df = pd.read_sql(query, conn, params=(player_name,))
    conn.close()
    if df.empty:
        return None
    return df.iloc[0]

def predict_today_hit(recent_hits):
    if not recent_hits or len(recent_hits) == 0:
        return 0.0
    return round(np.mean(recent_hits), 2)

if __name__ == "__main__":
    player_name = input("선수 이름을 입력하세요: ").strip()
    player = get_player_from_db(player_name)
    if player is None:
        print("해당 선수의 데이터가 DB에 없습니다.")
    else:
        print(f"\n[{player['name']}] 최근 기록")
        print(f"팀명: {player['team']}")
        print(f"타율: {player['avg']}")
        print(f"홈런: {player['hr']}, 타점: {player['rbi']}")
        print(f"최근 5경기 안타수: {player['recent_hits']}")
        
        # 리스트로 변환 (PostgreSQL 배열 → Python 리스트)
        recent_hits = player['recent_hits']
        if isinstance(recent_hits, str):  # 예전 데이터 대비
            recent_hits = [int(x) for x in recent_hits.strip('{}').split(',')]
        elif isinstance(recent_hits, list):
            recent_hits = [int(x) for x in recent_hits]
            
        pred = predict_today_hit(recent_hits)
        print(f"\n오늘 예상 안타수: {pred}")
