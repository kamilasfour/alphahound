import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from alphahound.engine.storage import get_conn

with get_conn() as conn:
    with conn.cursor() as cur:
        # Check if structure is being saved in pillar_breakdown
        cur.execute("""
            SELECT ticker, time,
                   pillar_breakdown ? 'structure' as has_structure,
                   jsonb_typeof(pillar_breakdown->'structure') as structure_type,
                   LEFT(pillar_breakdown::text, 300) as preview
            FROM convergence_signals
            WHERE super_signal = TRUE
            ORDER BY time DESC LIMIT 4;
        """)
        rows = cur.fetchall()
        if not rows:
            print("NO super signals in DB at all")
        for r in rows:
            print(f"ticker={r[0]}  time={r[1]}")
            print(f"  has_structure={r[2]}  structure_jsonb_type={r[3]}")
            print(f"  preview: {r[4][:200]}")
            print()
