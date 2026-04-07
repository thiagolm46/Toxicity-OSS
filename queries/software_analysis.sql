SELECT guild_name, COUNT(*) AS messages
FROM software_messages
GROUP BY 1
ORDER BY 2 DESC
LIMIT 25;

SELECT date_trunc('month', CAST(timestamp AS TIMESTAMPTZ)) AS month, COUNT(*) AS messages
FROM software_messages
GROUP BY 1
ORDER BY 1;

SELECT guild_name, unique_authors, message_count
FROM server_message_stats
ORDER BY message_count DESC
LIMIT 25;