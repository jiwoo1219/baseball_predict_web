import requests
from bs4 import BeautifulSoup
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def create_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        # 풀 모드 설정 (트랜잭션 모드)
        connect_timeout=10,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10
    )

# 테스트 연결
try:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    print("✅ 연결 성공:", cursor.fetchone()[0])
except Exception as e:
    print("❌ 연결 실패:", e)
finally:
    if conn: conn.close()


def safe_int(val):
    try:
        return int(val.replace(',', ''))
    except Exception:
        return 0

def safe_float(val):
    try:
        return float(val.replace(',', ''))
    except Exception:
        return 0.0

def convert_korean_date_to_iso(korean_date):
    try:
        date = korean_date.replace('년 ', '-').replace('월 ', '-').replace('일', '').strip()
        if len(date) == 10 and date.count('-') == 2:
            return date
        else:
            return None
    except Exception:
        return None

def to_pg_array(py_list):
    try:
        return '{' + ','.join(map(str, py_list)) + '}'
    except Exception:
        return '{}'

def create_pg_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT', 5432)
    )

def crawl_player(player_id):
    url = f'https://www.koreabaseball.com/Record/Player/HitterDetail/Basic.aspx?playerId={player_id}'
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')

        # 기본 정보
        name_tag = soup.select_one('#cphContents_cphContents_cphContents_playerProfile_lblName')
        birth_tag = soup.select_one('#cphContents_cphContents_cphContents_playerProfile_lblBirthday')
        backno_tag = soup.select_one('#cphContents_cphContents_cphContents_playerProfile_lblBackNo')
        position_tag = soup.select_one('#cphContents_cphContents_cphContents_playerProfile_lblPosition')
        team_tag = soup.select_one('h4.team')

        name = name_tag.text.strip() if name_tag else f'ID:{player_id}'
        birth_raw = birth_tag.text.strip() if birth_tag else ''
        birth_date = convert_korean_date_to_iso(birth_raw)
        backno = safe_int(backno_tag.text.strip()) if backno_tag else 0
        position = position_tag.text.strip() if position_tag else ''
        team = team_tag.text.strip().split()[0] if team_tag else ''

        # 성적 테이블
        stat_table = soup.select('table.tbl.tt')
        avg, hr, rbi = 0.0, 0, 0
        if stat_table and len(stat_table) > 0:
            stat_cells = stat_table[0].select('tbody tr td')
            if len(stat_cells) >= 16:
                avg = safe_float(stat_cells[1].text.strip())
                hr = safe_int(stat_cells[15].text.strip())   # 홈런 인덱스 15 (16번째)
                rbi = safe_int(stat_cells[10].text.strip())  # 타점 인덱스 10 (11번째)

        # 최근 5경기 기록
        recent_hits = [0]*5
        recent_hr = [0]*5
        recent_rbi = [0]*5
        if stat_table and len(stat_table) > 2:
            recent_table = stat_table[2]
            temp_hits, temp_hr, temp_rbi = [], [], []
            for row in recent_table.select('tbody tr')[:5]:
                tds = row.select('td')
                if len(tds) >= 16:
                    temp_hits.append(safe_int(tds[6].text.strip()))    # 안타: 7번째(인덱스 6)
                    temp_hr.append(safe_int(tds[15].text.strip()))    # 홈런: 16번째(인덱스 15)
                    temp_rbi.append(safe_int(tds[10].text.strip()))   # 타점: 11번째(인덱스 10)
                else:
                    temp_hits.append(0)
                    temp_hr.append(0)
                    temp_rbi.append(0)
            recent_hits = (temp_hits + [0]*5)[:5]
            recent_hr = (temp_hr + [0]*5)[:5]
            recent_rbi = (temp_rbi + [0]*5)[:5]

        return {
            'player_id': player_id,
            'name': name,
            'birth_date': birth_date,
            'back_number': backno,
            'position': position,
            'team': team,
            'avg': avg,
            'hr': hr,
            'rbi': rbi,
            'recent_hits': to_pg_array(recent_hits),
            'recent_hr': to_pg_array(recent_hr),
            'recent_rbi': to_pg_array(recent_rbi),
        }
    except Exception as e:
        print(f"[{player_id}] 크롤링 실패: {str(e)}")
        return None

def insert_player(data):
    conn = create_pg_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO players 
            (player_id, name, birth_date, back_number, position, team, avg, hr, rbi, recent_hits, recent_hr, recent_rbi)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (player_id) DO NOTHING
        ''', (
            data['player_id'],
            data['name'],
            data['birth_date'] if data['birth_date'] else None,
            data['back_number'],
            data['position'],
            data['team'],
            data['avg'],
            data['hr'],
            data['rbi'],
            data['recent_hits'],
            data['recent_hr'],
            data['recent_rbi'],  # player_image 제거
        ))
        conn.commit()
        print(f"{data['name']} 저장 완료")
    except Exception as e:
        print(f"삽입 오류: {str(e)}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    player_ids = [69102, 69737, 54529, 76232]  # 원하는 선수 ID 리스트
    for pid in player_ids:
        data = crawl_player(pid)
        if data:
            insert_player(data)

print(os.getenv('DB_HOST'))  # None이 출력되면 .env 파일 로드 실패
