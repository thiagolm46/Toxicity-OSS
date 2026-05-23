SELECT
    guild_name,
    COUNT(*) AS messages
FROM
    software_messages
GROUP BY
    1
ORDER BY
    2 DESC
LIMIT
    25;

SELECT
    date_trunc('month', CAST(timestamp AS TIMESTAMPTZ)) AS month,
    COUNT(*) AS messages
FROM
    software_messages
GROUP BY
    1
ORDER BY
    1;

SELECT
    guild_name,
    unique_authors,
    message_count
FROM
    server_message_stats
ORDER BY
    message_count DESC
LIMIT
    25;

SELECT
    guild_name,
    channel_name,
    channel_class,
    software_channel_score,
    n_messages
FROM
    software_channels
ORDER BY
    software_channel_score DESC,
    n_messages DESC
LIMIT
    25;

SELECT
    channel_class,
    COUNT(*) AS channels,
    SUM(n_messages) AS messages
FROM
    software_channels
GROUP BY
    1
ORDER BY
    1;