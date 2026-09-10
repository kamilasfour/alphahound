-- Check EDGAR raw_posts content to understand what ticker data we have
SELECT text FROM raw_posts 
WHERE adapter_id = 'stocks.edgar' 
ORDER BY time DESC 
LIMIT 5;
