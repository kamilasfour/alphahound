-- Clean up duplicate trade_log signal rows — keep earliest per entity per day
-- trade_log uses (entity_id, time) — no id column

DELETE FROM trade_log
WHERE (entity_id, time) NOT IN (
    SELECT entity_id, MIN(time)
    FROM trade_log
    WHERE venue = 'signal'
    GROUP BY entity_id, DATE(time)
)
AND venue = 'signal';

-- Verify — should show 1 row per ticker
SELECT e.canonical_symbol, COUNT(*), MIN(tl.time)::date as first_signal
FROM trade_log tl
JOIN entities e ON e.entity_id = tl.entity_id
WHERE tl.venue = 'signal'
GROUP BY e.canonical_symbol
ORDER BY e.canonical_symbol;
