import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from alphahound.engine.storage import get_conn
from datetime import date

today = date.today()

with get_conn() as conn:
    with conn.cursor() as cur:
        # Earnings for tickers with strong signals in next 60 days
        cur.execute("""
            SELECT e.canonical_symbol, ec.earnings_date,
                   (ec.earnings_date - %s) as days_away,
                   ec.estimate_eps
            FROM earnings_calendar ec
            JOIN entities e ON e.entity_id = ec.entity_id
            WHERE ec.earnings_date BETWEEN %s AND %s + interval '60 days'
            AND e.canonical_symbol IN (
                'NVDA','MSFT','IBM','NOW','AVGO','QQQ','SPY','CVX',
                'IONQ','PANW','PLTR','AMZN','TLT','SLV','V','ADBE',
                'ORCL','MU','COIN','META','TSLA','AMD','AAPL','GOOGL'
            )
            ORDER BY ec.earnings_date ASC;
        """, (today, today, today))
        rows = cur.fetchall()
        print(f"Earnings for signal tickers (next 60d):")
        for r in rows:
            in_window = 14 <= r[2] <= 45
            flag = " ✅ IN WINDOW" if in_window else f" ({'too soon' if r[2] < 14 else 'too far'})"
            print(f"  {r[0]:<8} {r[1]}  ({r[2]}d){flag}")

        print(f"\nCurrent catalyst window: 14-45 days")
        print(f"Tickers in window right now:")
        cur.execute("""
            SELECT e.canonical_symbol, ec.earnings_date, (ec.earnings_date - %s) as days
            FROM earnings_calendar ec
            JOIN entities e ON e.entity_id = ec.entity_id
            WHERE ec.earnings_date - %s BETWEEN 14 AND 45
            ORDER BY ec.earnings_date ASC
            LIMIT 20;
        """, (today, today))
        for r in cur.fetchall():
            print(f"  {r[0]:<8} {r[1]} ({r[2]}d)")
