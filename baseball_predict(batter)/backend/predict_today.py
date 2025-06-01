def get_player_from_db(player_name):
    conn = create_pg_connection()
    query = "SELECT * FROM players WHERE name = %s ORDER BY created_at DESC LIMIT 1"
    df = pd.read_sql(query, conn, params=(player_name,))
    conn.close()
    if df.empty:
        return None
    return df.iloc[0]

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
        print(f"선수 사진 URL: https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/person/middle/2025/{player['player_id']}.jpg")
